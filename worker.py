import inspect
import json
import logging
import os
import tempfile
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urljoin

import httpx

from app.analyzer import analyze
from app.fetcher import fetch_page
from app.notifications import send_email, send_sms, send_telegram
from app.scheduler import recommended_interval_minutes

logger = logging.getLogger(__name__)

IMPORTANT_TRANSITIONS = {
    ("NOT_OPEN", "OPEN"),
    ("SCHEDULED", "OPEN"),
    ("APPROXIMATE_DATE", "SCHEDULED"),
    ("NOT_OPEN", "SCHEDULED"),
    ("OPEN", "LIMITED"),
    ("OPEN", "WAITLIST"),
    ("OPEN", "SOLD_OUT"),
    ("LIMITED", "SOLD_OUT"),
    ("WAITLIST", "SOLD_OUT"),
    ("OPEN", "CLOSED"),
}

SOURCE_PRIORITIES = {
    "organizer": 1,
    "registration": 2,
    "news": 3,
    "calendar": 4,
    "other": 5,
}


def source_candidates(event: dict) -> list[dict]:
    candidates = []
    if event.get("official_url"):
        candidates.append({"url": event["official_url"], "type": "organizer"})
    if event.get("registration_url"):
        candidates.append({"url": event["registration_url"], "type": "registration"})
    for source in event.get("sources", []):
        if isinstance(source, dict) and source.get("url"):
            candidates.append({
                "url": source["url"],
                "type": source.get("type", "other"),
            })

    unique = {}
    for candidate in candidates:
        unique.setdefault(candidate["url"], candidate)
    return sorted(
        unique.values(),
        key=lambda candidate: SOURCE_PRIORITIES.get(candidate["type"], SOURCE_PRIORITIES["other"]),
    )


def notify_transition(event: dict, old_status: str, observation: dict) -> list[dict]:
    new_status = observation["status"]
    transition_is_cancellation = new_status == "CANCELLED"
    message = (
        f"Sportevent-Alarm: {event['name']}\n"
        f"Status: {old_status} -> {new_status}\n"
        f"Event-Datum: {event.get('event_date') or 'unbekannt'}\n"
        f"Registrierung: {event.get('registration_url') or event.get('official_url')}\n"
        f"Confidence: {observation.get('confidence', 0):.0%}\n"
    )
    if observation.get("registration_start"):
        message += f"Registrierungsbeginn: {observation['registration_start']}\n"
    if observation.get("evidence"):
        message += f"Beleg: {observation['evidence'][:1000]}\n"
    if transition_is_cancellation:
        message = f"WICHTIG: Veranstaltung abgesagt\n{message}"
    deliveries = []
    for channel, sender in (
        ("telegram", lambda: send_telegram(message)),
        ("sms", lambda: send_sms(message)),
        ("email", lambda: send_email(f"Sportevent: {new_status} - {event['name']}", message)),
    ):
        try:
            success, error = sender()
            if success:
                delivery_status = "SENT"
            elif error and "nicht konfiguriert" in error.lower():
                delivery_status = "NOT_CONFIGURED"
            else:
                delivery_status = "FAILED"
            deliveries.append({
                "channel": channel,
                "status": delivery_status,
                "error": error if delivery_status == "FAILED" else None,
            })
        except Exception as exc:
            logger.exception("Notification delivery failed for event %s", event["id"])
            deliveries.append({"channel": channel, "status": "FAILED", "error": str(exc)})
    return deliveries


def notification_transition_key(event_id: int | str, old_status: str, new_status: str, content_hash: str | None) -> str:
    material = f"{event_id}:{old_status}:{new_status}:{content_hash or ''}"
    return sha256(material.encode("utf-8")).hexdigest()


def _notification_was_recorded(event: dict, transition_key: str) -> bool:
    return any(
        item.get("transition_key") == transition_key
        for item in event.get("notification_history", [])
        if isinstance(item, dict)
    )


def _record_notification(event: dict, transition_key: str, deliveries: list[dict], attempted_at: datetime) -> None:
    history = event.setdefault("notification_history", [])
    history.append({
        "transition_key": transition_key,
        "attempted_at": attempted_at.isoformat(),
        "channels": deliveries,
    })


def load_events(path: str | Path) -> list[dict]:
    events = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(events, list):
        raise TypeError("events.json must contain a JSON array")
    for index, event in enumerate(events):
        if not isinstance(event, dict) or not event.get("name"):
            raise ValueError(f"Event at index {index} must be an object with a name")
        if not (event.get("registration_url") or event.get("official_url")):
            raise ValueError(f"Event {event['name']!r} needs registration_url or official_url")
        event.setdefault("id", index + 1)
    return events


def load_previous_snapshot(pages_url: str | None) -> dict:
    if not pages_url:
        return {"events": []}
    try:
        response = httpx.get(urljoin(pages_url.rstrip("/") + "/", "status.json"), timeout=15)
        if response.is_success:
            snapshot = response.json()
            if isinstance(snapshot, dict) and isinstance(snapshot.get("events"), list):
                return snapshot
    except (httpx.HTTPError, ValueError):
        pass
    return {"events": []}


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _parse_date(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None


def _analyze_event(analyze_fn, text: str, event: dict) -> dict:
    parameters = inspect.signature(analyze_fn).parameters
    if "event_context" in parameters:
        return analyze_fn(text, event_context=event)
    return analyze_fn(text)


def process_events(
    configured_events: list[dict],
    previous_snapshot: dict,
    now: datetime | None = None,
    fetch_page_fn=fetch_page,
    analyze_fn=analyze,
    notify_fn=notify_transition,
) -> tuple[list[dict], list[dict]]:
    now = now or datetime.now(timezone.utc)
    previous_by_id = {str(event.get("id")): event for event in previous_snapshot.get("events", [])}
    updated_events = []
    results = []

    for configured in configured_events:
        old = previous_by_id.get(str(configured["id"]), {})
        event = {**old, **configured}
        event.setdefault("status", "ANNOUNCED")
        sources = source_candidates(event)
        if not sources:
            raise ValueError(f"Event {event.get('name', event.get('id'))!r} has no source URL")
        source = sources[0]
        url = source["url"]
        next_check = _parse_datetime(old.get("next_check_at"))
        if next_check and next_check > now:
            updated_events.append(event)
            continue

        old_status = event["status"]
        try:
            text, content_hash = fetch_page_fn(url)
            observation = _analyze_event(analyze_fn, text, event)
            should_notify = (
                (old_status, observation["status"]) in IMPORTANT_TRANSITIONS
                or observation["status"] == "CANCELLED"
            )
            transition_key = notification_transition_key(
                event["id"], old_status, observation["status"], content_hash
            )
            if should_notify and not _notification_was_recorded(event, transition_key):
                deliveries = notify_fn(event, old_status, observation) or []
                _record_notification(event, transition_key, deliveries, now)
            event.update({
                "status": observation["status"],
                "source_url": url,
                "registration_start": observation.get("registration_start"),
                "registration_end": observation.get("registration_end"),
                "approximate_registration_text": observation.get("approximate_registration_text"),
                "participant_limit": observation.get("participant_limit"),
                "confidence": observation.get("confidence"),
                "evidence": observation.get("evidence"),
                "last_content_hash": content_hash,
            })
            result = {"id": event["id"], "name": event["name"], "status": event["status"], "ok": True}
        except Exception as exc:
            logger.exception("Monitoring failed for event %s", event["id"])
            result = {"id": event["id"], "name": event["name"], "status": old_status, "ok": False, "error": str(exc)}

        checked_at = now
        event["last_checked_at"] = checked_at.isoformat()
        interval_event = SimpleNamespace(
            status=event["status"],
            registration_start=_parse_datetime(event.get("registration_start")),
            event_date=_parse_date(event.get("event_date")),
        )
        event["next_check_at"] = (
            checked_at + timedelta(minutes=recommended_interval_minutes(interval_event, checked_at))
        ).isoformat()
        updated_events.append(event)
        results.append(result)

    updated_events.sort(key=lambda event: (event.get("event_date") or "9999-12-31", event["name"].casefold()))
    return updated_events, results


def build_dashboard_snapshot(
    events: list[dict],
    results: list[dict] | dict,
    generated_at: datetime | None = None,
    run_number: str | None = None,
    run_url: str | None = None,
) -> dict:
    generated_at = generated_at or datetime.now(timezone.utc)
    if isinstance(results, dict):
        results = results.get("results", [])

    serialized_events = []
    for event in events:
        if isinstance(event, dict):
            serialized_events.append(event)
            continue
        serialized_events.append({
            "id": event.id,
            "name": event.name,
            "sport": event.sport,
            "location": event.location,
            "event_date": event.event_date.isoformat() if event.event_date else None,
            "status": event.status,
            "priority": event.priority,
            "registration_start": event.registration_start.isoformat() if event.registration_start else None,
            "registration_end": event.registration_end.isoformat() if event.registration_end else None,
            "approximate_registration_text": event.approximate_registration_text,
            "registration_url": event.registration_url,
            "participant_limit": event.participant_limit,
            "confidence": event.confidence,
            "last_checked_at": event.last_checked_at.isoformat() if event.last_checked_at else None,
            "next_check_at": event.next_check_at.isoformat() if event.next_check_at else None,
        })
    return {
        "last_run": {
            "completed_at": generated_at.isoformat(),
            "number": run_number,
            "url": run_url,
            "checked": len(results),
            "failures": sum(not result.get("ok", False) for result in results),
        },
        "events": serialized_events,
    }


def export_dashboard(output_dir: str | Path, snapshot: dict) -> Path:
    output_path = Path(output_dir) / "status.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path


def run_worker(
    events_path: str | Path,
    output_dir: str | Path,
    pages_url: str | None = None,
    run_number: str | None = None,
    run_url: str | None = None,
    now: datetime | None = None,
) -> dict:
    events = load_events(events_path)
    previous = load_previous_snapshot(pages_url)
    updated_events, results = process_events(events, previous, now)
    snapshot = build_dashboard_snapshot(updated_events, results, now, run_number, run_url)
    export_dashboard(output_dir, snapshot)
    return {"events": len(results), "results": results, "snapshot": snapshot}


if __name__ == "__main__":
    output_dir = os.environ.get("DASHBOARD_OUTPUT_DIR", str(Path(tempfile.gettempdir()) / "sportevent-dashboard"))
    repository = os.environ.get("GITHUB_REPOSITORY")
    run_id = os.environ.get("GITHUB_RUN_ID")
    server = os.environ.get("GITHUB_SERVER_URL", "https://github.com")
    run_url = f"{server}/{repository}/actions/runs/{run_id}" if repository and run_id else None
    result = run_worker(
        events_path=os.environ.get("EVENTS_FILE", "events.json"),
        output_dir=output_dir,
        pages_url=os.environ.get("PAGES_URL"),
        run_number=os.environ.get("GITHUB_RUN_NUMBER"),
        run_url=run_url,
    )
    print(json.dumps(result["results"], ensure_ascii=False, indent=2))
import json
import logging
import os
import tempfile
from datetime import date, datetime, timedelta, timezone
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
    ("OPEN", "SOLD_OUT"),
    ("LIMITED", "SOLD_OUT"),
    ("OPEN", "WAITLIST"),
}


def notify_transition(event: dict, old_status: str, observation: dict) -> None:
    new_status = observation["status"]
    message = (
        f"Sportevent-Alarm: {event['name']}\n"
        f"Status: {old_status} -> {new_status}\n"
        f"Registrierung: {event.get('registration_url') or event.get('official_url')}\n"
        f"Confidence: {observation.get('confidence', 0):.0%}\n"
    )
    for sender in (
        lambda: send_telegram(message),
        lambda: send_sms(message),
        lambda: send_email(f"Sportevent: {new_status} - {event['name']}", message),
    ):
        try:
            sender()
        except Exception:
            logger.exception("Notification delivery failed for event %s", event["id"])


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
        url = event.get("registration_url") or event["official_url"]
        next_check = _parse_datetime(old.get("next_check_at"))
        if next_check and next_check > now:
            updated_events.append(event)
            continue

        old_status = event["status"]
        try:
            text, content_hash = fetch_page_fn(url)
            observation = analyze_fn(text)
            if (old_status, observation["status"]) in IMPORTANT_TRANSITIONS:
                notify_fn(event, old_status, observation)
            event.update({
                "status": observation["status"],
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
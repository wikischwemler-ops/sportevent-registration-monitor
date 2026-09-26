from datetime import datetime, timedelta, timezone

from sqlalchemy import or_, select

from .analyzer import analyze
from .db import SessionLocal
from .fetcher import fetch_page
from .models import Event, EventStatus, NotificationLog, Observation
from .notifications import send_email, send_sms, send_telegram
from .scheduler import recommended_interval_minutes

IMPORTANT_TRANSITIONS = {
    (EventStatus.NOT_OPEN.value, EventStatus.OPEN.value),
    (EventStatus.SCHEDULED.value, EventStatus.OPEN.value),
    (EventStatus.APPROXIMATE_DATE.value, EventStatus.SCHEDULED.value),
    (EventStatus.NOT_OPEN.value, EventStatus.SCHEDULED.value),
    (EventStatus.OPEN.value, EventStatus.LIMITED.value),
    (EventStatus.OPEN.value, EventStatus.SOLD_OUT.value),
    (EventStatus.LIMITED.value, EventStatus.SOLD_OUT.value),
    (EventStatus.OPEN.value, EventStatus.WAITLIST.value),
}

def notification_key(event_id: int, old: str, new: str) -> str:
    return f"{event_id}:{old}:{new}"

def notify(event: Event, old: str, new: str, observation: dict):
    key = notification_key(event.id, old, new)
    message = (
        f"Sportevent-Alarm: {event.name}\n"
        f"Status: {old} -> {new}\n"
        f"Registrierung: {event.registration_url or event.official_url}\n"
        f"Confidence: {observation.get('confidence', 0):.0%}\n"
    )
    with SessionLocal() as db:
        for channel, sender in [
            ("telegram", lambda: send_telegram(message)),
            ("sms", lambda: send_sms(message)),
            ("email", lambda: send_email(f"Sportevent: {new} – {event.name}", message)),
        ]:
            already = db.scalar(select(NotificationLog).where(
                NotificationLog.event_id == event.id,
                NotificationLog.channel == channel,
                NotificationLog.notification_key == key,
            ))
            if already:
                continue
            success, error = sender()
            db.add(NotificationLog(
                event_id=event.id, channel=channel, notification_key=key,
                success=success, error=error
            ))
        db.commit()

def monitor_all() -> dict:
    now = datetime.now(timezone.utc)
    with SessionLocal() as db:
        events = list(db.scalars(select(Event).where(
            Event.active.is_(True),
            or_(Event.next_check_at.is_(None), Event.next_check_at <= now),
        )))
    results = []
    for event in events:
        try:
            text, content_hash = fetch_page(event.registration_url or event.official_url)
            observation = analyze(text)
            new_status = observation["status"]
            old_status = event.status
            with SessionLocal() as db:
                current = db.get(Event, event.id)
                current.status = new_status
                current.registration_start = _parse_dt(observation.get("registration_start"))
                current.registration_end = _parse_dt(observation.get("registration_end"))
                current.approximate_registration_text = observation.get("approximate_registration_text")
                current.participant_limit = observation.get("participant_limit")
                current.confidence = observation.get("confidence")
                checked_at = datetime.now(timezone.utc)
                current.last_checked_at = checked_at
                current.next_check_at = checked_at + timedelta(
                    minutes=recommended_interval_minutes(current, checked_at)
                )
                current.last_content_hash = content_hash
                db.add(Observation(
                    event_id=event.id,
                    source_url=event.registration_url or event.official_url,
                    status=new_status,
                    confidence=observation.get("confidence", 0),
                    evidence=observation.get("evidence"),
                    content_hash=content_hash,
                ))
                db.commit()
            if (old_status, new_status) in IMPORTANT_TRANSITIONS:
                notify(event, old_status, new_status, observation)
            results.append({"id": event.id, "status": new_status, "ok": True})
        except Exception as exc:
            with SessionLocal() as db:
                current = db.get(Event, event.id)
                if current:
                    checked_at = datetime.now(timezone.utc)
                    current.last_checked_at = checked_at
                    current.next_check_at = checked_at + timedelta(
                        minutes=recommended_interval_minutes(current, checked_at)
                    )
                    db.commit()
            results.append({"id": event.id, "ok": False, "error": str(exc)})
    return {"events": len(events), "results": results}

def _parse_dt(value):
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))

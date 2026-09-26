from datetime import datetime, time, timedelta, timezone

from .models import EventStatus


def recommended_interval_minutes(event, now: datetime | None = None) -> int:
    now = now or datetime.now(timezone.utc)
    if event.status in {EventStatus.OPEN.value, EventStatus.LIMITED.value}:
        return 5
    if event.registration_start:
        start = event.registration_start
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        if start - now <= timedelta(hours=48):
            return 5
    if event.event_date:
        event_dt = datetime.combine(event.event_date, time.min, tzinfo=timezone.utc)
        delta = event_dt - now
        if delta <= timedelta(days=30):
            return 120
        if delta <= timedelta(days=90):
            return 1440
        if delta <= timedelta(days=180):
            return 4320
    return 10080

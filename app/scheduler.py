from datetime import datetime, timezone, timedelta
from .models import EventStatus

def recommended_interval_minutes(event):
    now = datetime.now(timezone.utc)
    if event.status in {EventStatus.OPEN.value, EventStatus.LIMITED.value}:
        return 5
    if event.registration_start:
        start = event.registration_start
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        delta = start - now
        if delta <= timedelta(hours=48): return 5
        if delta <= timedelta(days=14): return 30
        if delta <= timedelta(days=30): return 120
        if delta <= timedelta(days=90): return 1440
        return 4320
    if event.event_date:
        event_dt = datetime.combine(event.event_date, datetime.min.time(), tzinfo=timezone.utc)
        delta = event_dt - now
        if delta <= timedelta(days=30): return 1440
        if delta <= timedelta(days=90): return 2880
    return 10080

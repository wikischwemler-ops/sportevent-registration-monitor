from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

from app.scheduler import recommended_interval_minutes


def test_known_registration():
    now = datetime(2027, 1, 1, tzinfo=timezone.utc)
    event = SimpleNamespace(
        status="SCHEDULED",
        registration_start=now + timedelta(hours=12),
        event_date=None,
    )
    assert recommended_interval_minutes(event, now) == 5

def test_far_event():
    now = datetime(2027, 1, 1, tzinfo=timezone.utc)
    event = SimpleNamespace(
        status="ANNOUNCED", registration_start=None,
        event_date=date(2027, 1, 1) + timedelta(days=200),
    )
    assert recommended_interval_minutes(event, now) == 10080

def test_event_within_six_months_is_checked_every_three_days():
    now = datetime(2027, 1, 1, tzinfo=timezone.utc)
    event = SimpleNamespace(
        status="ANNOUNCED", registration_start=None,
        event_date=date(2027, 1, 1) + timedelta(days=120),
    )
    assert recommended_interval_minutes(event, now) == 4320

def test_event_within_three_months_is_checked_daily():
    now = datetime(2027, 1, 1, tzinfo=timezone.utc)
    event = SimpleNamespace(
        status="ANNOUNCED", registration_start=None,
        event_date=date(2027, 1, 1) + timedelta(days=60),
    )
    assert recommended_interval_minutes(event, now) == 1440

def test_event_within_thirty_days_is_checked_every_two_hours():
    now = datetime(2027, 1, 1, tzinfo=timezone.utc)
    event = SimpleNamespace(
        status="ANNOUNCED", registration_start=None,
        event_date=date(2027, 1, 1) + timedelta(days=14),
    )
    assert recommended_interval_minutes(event, now) == 120

def test_open_event_is_checked_every_five_minutes():
    now = datetime(2027, 1, 1, tzinfo=timezone.utc)
    event = SimpleNamespace(status="OPEN", registration_start=None, event_date=None)
    assert recommended_interval_minutes(event, now) == 5

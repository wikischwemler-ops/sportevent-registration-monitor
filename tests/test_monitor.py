from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import monitor
from app.db import Base
from app.models import Event


@pytest.fixture
def monitor_db(monkeypatch):
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(monitor, "SessionLocal", session_factory)
    yield session_factory
    engine.dispose()


def add_event(db, name, next_check_at=None):
    event = Event(
        name=name,
        official_url=f"https://example.com/{name}",
        status="ANNOUNCED",
        next_check_at=next_check_at,
    )
    db.add(event)
    db.commit()
    return event.id


def test_monitor_only_checks_due_events(monitor_db, monkeypatch):
    now = datetime.now(timezone.utc)
    with monitor_db() as db:
        due_id = add_event(db, "due")
        overdue_id = add_event(db, "overdue", now - timedelta(minutes=1))
        future_id = add_event(db, "future", now + timedelta(hours=1))

    monkeypatch.setattr(monitor, "fetch_page", lambda url: ("Event information", "hash"))
    monkeypatch.setattr(monitor, "analyze", lambda text: {
        "status": "NOT_OPEN",
        "registration_start": None,
        "registration_end": None,
        "approximate_registration_text": None,
        "participant_limit": None,
        "confidence": 0.9,
        "evidence": text,
    })

    result = monitor.monitor_all()

    assert result["events"] == 2
    assert {item["id"] for item in result["results"]} == {due_id, overdue_id}
    with monitor_db() as db:
        future = db.get(Event, future_id)
        assert future.next_check_at.replace(tzinfo=timezone.utc) > now
        for event_id in (due_id, overdue_id):
            checked = db.get(Event, event_id)
            assert checked.last_checked_at is not None
            assert checked.next_check_at is not None


def test_failed_fetch_still_schedules_next_check(monitor_db, monkeypatch):
    with monitor_db() as db:
        event_id = add_event(db, "unavailable")

    def fail_fetch(url):
        raise RuntimeError("temporary fetch failure")

    monkeypatch.setattr(monitor, "fetch_page", fail_fetch)

    result = monitor.monitor_all()

    assert result["results"] == [{
        "id": event_id,
        "ok": False,
        "error": "temporary fetch failure",
    }]
    with monitor_db() as db:
        event = db.get(Event, event_id)
        assert event.last_checked_at is not None
        assert event.next_check_at is not None
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

from worker import build_dashboard_snapshot


def test_snapshot_contains_latest_run_and_event_status():
    checked_at = datetime(2026, 9, 26, 12, tzinfo=timezone.utc)
    event = SimpleNamespace(
        id=7,
        name="City Run",
        sport="Running",
        location="Berlin",
        event_date=date(2027, 5, 1),
        status="OPEN",
        priority="high",
        registration_start=checked_at,
        registration_end=None,
        approximate_registration_text=None,
        registration_url="https://example.com/register",
        participant_limit=500,
        confidence=0.95,
        last_checked_at=checked_at,
        next_check_at=checked_at + timedelta(minutes=5),
    )

    snapshot = build_dashboard_snapshot(
        [event],
        {"events": 1, "results": [{"id": 7, "ok": True}]},
        generated_at=checked_at,
        run_number="42",
        run_url="https://github.com/example/project/actions/runs/42",
    )

    assert snapshot["last_run"] == {
        "completed_at": checked_at.isoformat(),
        "number": "42",
        "url": "https://github.com/example/project/actions/runs/42",
        "checked": 1,
        "failures": 0,
    }
    assert snapshot["events"][0]["name"] == "City Run"
    assert snapshot["events"][0]["status"] == "OPEN"
    assert snapshot["events"][0]["next_check_at"] == (checked_at + timedelta(minutes=5)).isoformat()


def test_snapshot_counts_failed_checks():
    snapshot = build_dashboard_snapshot(
        [],
        {"events": 1, "results": [{"id": 7, "ok": False, "error": "private details"}]},
        generated_at=datetime(2026, 9, 26, tzinfo=timezone.utc),
    )

    assert snapshot["last_run"]["failures"] == 1
    assert "private details" not in str(snapshot)
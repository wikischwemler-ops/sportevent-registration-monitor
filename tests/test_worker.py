from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

from worker import (
    build_dashboard_snapshot,
    build_run_summary,
    load_events,
    process_events,
    source_candidates,
)


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


def test_process_events_reuses_future_status_without_fetching():
    now = datetime(2026, 9, 26, 12, tzinfo=timezone.utc)
    future_check = now + timedelta(hours=1)
    configured = [{
        "id": 1,
        "name": "City Run",
        "official_url": "https://example.com",
        "event_date": "2027-05-01",
    }]
    previous = {"events": [{
        **configured[0],
        "status": "SCHEDULED",
        "next_check_at": future_check.isoformat(),
    }]}

    def unexpected_fetch(url):
        raise AssertionError("A future event must not be fetched")

    updated, results = process_events(configured, previous, now, fetch_page_fn=unexpected_fetch)

    assert updated[0]["status"] == "SCHEDULED"
    assert results == []


def test_process_events_checks_due_event_and_schedules_next_check():
    now = datetime(2026, 9, 26, 12, tzinfo=timezone.utc)
    configured = [{
        "id": 1,
        "name": "City Run",
        "official_url": "https://example.com",
        "event_date": "2027-05-01",
    }]

    updated, results = process_events(
        configured,
        {"events": []},
        now,
        fetch_page_fn=lambda url: ("Registration is scheduled", "content-hash"),
        analyze_fn=lambda text: {
            "status": "SCHEDULED",
            "registration_start": (now + timedelta(hours=12)).isoformat(),
            "confidence": 0.9,
            "evidence": text,
        },
    )

    assert results == [{"id": 1, "name": "City Run", "status": "SCHEDULED", "ok": True}]
    assert updated[0]["last_content_hash"] == "content-hash"
    assert updated[0]["next_check_at"] == (now + timedelta(minutes=5)).isoformat()


def test_load_events_requires_event_name_and_source(tmp_path):
    events_file = tmp_path / "events.json"
    events_file.write_text('[{"name":"No URL"}]', encoding="utf-8")

    import pytest

    with pytest.raises(ValueError, match="needs registration_url or official_url"):
        load_events(events_file)


def test_source_candidates_prefer_official_source():
    sources = source_candidates({
        "official_url": "https://example.com/official",
        "registration_url": "https://example.com/register",
        "sources": [
            {"url": "https://example.com/news", "type": "news"},
            {"url": "https://example.com/other", "type": "other"},
        ],
    })

    assert [source["type"] for source in sources] == [
        "organizer", "registration", "news", "other"
    ]


def test_notification_history_deduplicates_same_transition_content():
    now = datetime(2026, 9, 26, 12, tzinfo=timezone.utc)
    configured = [{
        "id": 1,
        "name": "City Run",
        "official_url": "https://example.com",
        "event_date": "2027-05-01",
    }]
    previous = {"events": [{
        **configured[0],
        "status": "SCHEDULED",
        "next_check_at": None,
    }]}
    notifications = []

    def notify(event, old_status, observation):
        notifications.append((event["id"], old_status, observation["status"]))
        return [{"channel": "telegram", "status": "NOT_CONFIGURED", "error": None}]

    updated, _ = process_events(
        configured,
        previous,
        now,
        fetch_page_fn=lambda url: ("Registration is now open", "same-hash"),
        analyze_fn=lambda text: {"status": "OPEN", "confidence": 0.9, "evidence": text},
        notify_fn=notify,
    )
    updated[0]["next_check_at"] = None

    process_events(
        configured,
        {"events": updated},
        now + timedelta(minutes=5),
        fetch_page_fn=lambda url: ("Registration is now open", "same-hash"),
        analyze_fn=lambda text: {"status": "OPEN", "confidence": 0.9, "evidence": text},
        notify_fn=notify,
    )

    assert notifications == [(1, "SCHEDULED", "OPEN")]


def test_build_run_summary_contains_run_counts_and_statuses():
    summary = build_run_summary(
        [{"status": "OPEN"}, {"status": "SCHEDULED"}],
        [
            {"id": 1, "name": "City Run", "ok": True},
            {"id": 2, "name": "Trail", "ok": False, "error": "timeout"},
        ],
        run_number="42",
    )

    assert "Lauf abgeschlossen #42" in summary
    assert "Geprüft: 2 von 2 Events" in summary
    assert "Erfolgreich: 1" in summary
    assert "Fehler: 1" in summary
    assert "OPEN: 1" in summary
    assert "Trail: timeout" in summary


def test_send_run_summary_reports_delivery_status(monkeypatch):
    import worker

    monkeypatch.setattr(worker, "send_telegram", lambda message: (True, None))

    assert worker.send_run_summary([], [], "42") == {"status": "SENT", "error": None}
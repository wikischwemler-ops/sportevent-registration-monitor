import json
import os
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

from app.db import SessionLocal, init_db
from app.models import Event
from app.monitor import monitor_all


def build_dashboard_snapshot(events, run_result: dict, generated_at=None, run_number=None, run_url=None) -> dict:
    generated_at = generated_at or datetime.now(timezone.utc)
    results = run_result.get("results", [])
    return {
        "last_run": {
            "completed_at": generated_at.isoformat(),
            "number": run_number,
            "url": run_url,
            "checked": len(results),
            "failures": sum(not result.get("ok", False) for result in results),
        },
        "events": [
            {
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
            }
            for event in events
        ],
    }


def export_dashboard(output_dir, run_result: dict) -> Path:
    with SessionLocal() as db:
        events = list(db.scalars(
            select(Event)
            .where(Event.active.is_(True))
            .order_by(Event.event_date, Event.name)
        ))

    repository = os.environ.get("GITHUB_REPOSITORY")
    run_id = os.environ.get("GITHUB_RUN_ID")
    server = os.environ.get("GITHUB_SERVER_URL", "https://github.com")
    run_url = f"{server}/{repository}/actions/runs/{run_id}" if repository and run_id else None
    snapshot = build_dashboard_snapshot(
        events,
        run_result,
        run_number=os.environ.get("GITHUB_RUN_NUMBER"),
        run_url=run_url,
    )

    output_path = Path(output_dir) / "status.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path


if __name__ == "__main__":
    init_db()
    result = monitor_all()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    output_dir = os.environ.get("DASHBOARD_OUTPUT_DIR")
    if output_dir:
        export_dashboard(output_dir, result)

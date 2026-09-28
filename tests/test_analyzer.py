from app.analyzer import heuristic_analyze
from app.models import EventStatus


def test_open():
    result = heuristic_analyze("Registration is now open. Register here.")
    assert result["status"] == EventStatus.OPEN.value

def test_sold_out():
    result = heuristic_analyze("The race is sold out.")
    assert result["status"] == EventStatus.SOLD_OUT.value

def test_scheduled():
    result = heuristic_analyze("Registration opens 12.01.2027 at 10:00.")
    assert result["status"] == EventStatus.SCHEDULED.value


def test_approximate_registration_date_is_not_made_specific():
    result = heuristic_analyze("Registration opens in January.")

    assert result["status"] == EventStatus.APPROXIMATE_DATE.value
    assert result["registration_start"] is None
    assert result["approximate_registration_text"] == "Registration opens in January."


def test_registration_date_for_wrong_event_year_is_unknown():
    result = heuristic_analyze(
        "Registration opens 12.01.2026 at 10:00.",
        {"name": "Example Event", "event_date": "2027-08-22"},
    )

    assert result["status"] == EventStatus.UNKNOWN.value
    assert result["registration_start"] is None
    assert result["confidence"] < 0.5

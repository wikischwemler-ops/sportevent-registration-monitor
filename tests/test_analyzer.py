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

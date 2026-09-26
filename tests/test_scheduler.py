from datetime import datetime,timedelta,timezone,date
from types import SimpleNamespace
from app.scheduler import recommended_interval_minutes

def test_known_registration():
    e=SimpleNamespace(status="SCHEDULED",registration_start=datetime.now(timezone.utc)+timedelta(hours=12),event_date=None)
    assert recommended_interval_minutes(e)==5

def test_far_event():
    e=SimpleNamespace(status="ANNOUNCED",registration_start=None,event_date=date.today()+timedelta(days=200))
    assert recommended_interval_minutes(e)==10080

from fastapi import APIRouter, Depends
from sqlalchemy import select

from .db import SessionLocal
from .models import Event
from .scheduler import recommended_interval_minutes

router = APIRouter(prefix="/api")

def db_session():
    db = SessionLocal()
    try: yield db
    finally: db.close()

@router.get("/dashboard")
def dashboard(db=Depends(db_session)):
    events = list(db.scalars(select(Event).where(Event.active.is_(True)).order_by(Event.event_date)))
    return {"events": [{
        "id": e.id, "name": e.name, "sport": e.sport,
        "event_date": e.event_date.isoformat() if e.event_date else None,
        "status": e.status, "priority": e.priority,
        "registration_start": e.registration_start.isoformat() if e.registration_start else None,
        "registration_url": e.registration_url, "confidence": e.confidence,
        "next_check_interval_minutes": recommended_interval_minutes(e),
        "next_check_at": e.next_check_at.isoformat() if e.next_check_at else None,
        "last_checked_at": e.last_checked_at.isoformat() if e.last_checked_at else None
    } for e in events]}

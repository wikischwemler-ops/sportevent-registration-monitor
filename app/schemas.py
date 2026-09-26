from datetime import date, datetime
from pydantic import BaseModel, HttpUrl, ConfigDict
from .models import EventStatus, Priority

class EventCreate(BaseModel):
    name: str
    sport: str | None = None
    organizer: str | None = None
    location: str | None = None
    event_date: date | None = None
    official_url: HttpUrl
    registration_url: HttpUrl | None = None
    priority: Priority = Priority.MEDIUM

class EventRead(EventCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    status: EventStatus
    registration_start: datetime | None = None
    registration_end: datetime | None = None
    approximate_registration_text: str | None = None
    participant_limit: int | None = None
    confidence: float | None = None
    last_checked_at: datetime | None = None

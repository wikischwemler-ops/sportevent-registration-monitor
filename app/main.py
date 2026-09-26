from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select
from .db import init_db, SessionLocal
from .models import Event
from .schemas import EventCreate, EventRead
from .monitor import monitor_all
from .api import router as api_router
from .web import router as web_router

app=FastAPI(title="SportEvent Registration Monitor",version="0.2.0")
@app.on_event("startup")
def startup(): init_db()
def get_db():
    db=SessionLocal()
    try: yield db
    finally: db.close()
@app.get("/health")
def health(): return {"status":"ok"}
@app.get("/events",response_model=list[EventRead])
def list_events(db:Session=Depends(get_db)): return list(db.scalars(select(Event).order_by(Event.id.desc())))
@app.post("/events",response_model=EventRead,status_code=201)
def create_event(payload:EventCreate,db:Session=Depends(get_db)):
    e=Event(name=payload.name,sport=payload.sport,organizer=payload.organizer,location=payload.location,event_date=payload.event_date,official_url=str(payload.official_url),registration_url=str(payload.registration_url) if payload.registration_url else None,priority=payload.priority.value,status="UNKNOWN")
    db.add(e);db.commit();db.refresh(e);return e
@app.delete("/events/{event_id}",status_code=204)
def delete_event(event_id:int,db:Session=Depends(get_db)):
    e=db.get(Event,event_id)
    if not e: raise HTTPException(404,"Event nicht gefunden")
    e.active=False;db.commit()
@app.post("/monitor/run")
def run_monitor(): return monitor_all()
app.include_router(api_router);app.include_router(web_router)

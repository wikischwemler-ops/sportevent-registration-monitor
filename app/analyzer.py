import json
import re
from datetime import datetime, timezone
from dateutil import parser as dateparser
from .config import settings
from .models import EventStatus

def heuristic_analyze(text: str) -> dict:
    lower = text.lower()

    if any(x in lower for x in ["registration is open", "registration now open", "anmeldung geöffnet", "anmeldung ist geöffnet", "anmeldung offen"]):
        status = EventStatus.OPEN.value
    elif any(x in lower for x in ["sold out", "ausverkauft", "fully booked", "keine plätze"]):
        status = EventStatus.SOLD_OUT.value
    elif any(x in lower for x in ["waitlist", "warteliste"]):
        status = EventStatus.WAITLIST.value
    elif any(x in lower for x in ["registration opens", "anmeldung öffnet", "anmeldung startet", "registration will open"]):
        status = EventStatus.SCHEDULED.value
    else:
        status = EventStatus.NOT_OPEN.value

    # Conservative extraction of an explicit date/time near registration language.
    registration_start = None
    patterns = [
        r"(?:registration|anmeldung).{0,120}?(\d{1,2}[./-]\d{1,2}[./-]\d{2,4})",
        r"(?:opens|öffnet|startet).{0,80}?(\d{1,2}[./-]\d{1,2}[./-]\d{2,4})",
    ]
    for pattern in patterns:
        match = re.search(pattern, lower, re.DOTALL)
        if match:
            try:
                registration_start = dateparser.parse(match.group(1), dayfirst=True).replace(tzinfo=timezone.utc).isoformat()
                break
            except (ValueError, OverflowError):
                pass

    return {
        "status": status,
        "registration_start": registration_start,
        "registration_end": None,
        "approximate_registration_text": None,
        "participant_limit": None,
        "confidence": 0.65,
        "evidence": text[:1000],
    }

def analyze(text: str) -> dict:
    if not settings.openai_api_key:
        return heuristic_analyze(text)

    from openai import OpenAI
    client = OpenAI(api_key=settings.openai_api_key)
    schema = {
        "type": "object",
        "properties": {
            "status": {"type": "string", "enum": [x.value for x in EventStatus]},
            "registration_start": {"type": ["string", "null"]},
            "registration_end": {"type": ["string", "null"]},
            "approximate_registration_text": {"type": ["string", "null"]},
            "participant_limit": {"type": ["integer", "null"]},
            "confidence": {"type": "number"},
            "evidence": {"type": "string"},
        },
        "required": ["status", "registration_start", "registration_end", "approximate_registration_text", "participant_limit", "confidence", "evidence"],
        "additionalProperties": False,
    }
    response = client.chat.completions.create(
        model=settings.openai_model,
        temperature=0,
        messages=[
            {"role": "system", "content": "Du analysierst Sportevent-Webseiten. Extrahiere nur Fakten aus dem Text. Erfinde niemals Registrierungsdaten. Bei Unsicherheit status UNKNOWN und niedrige confidence. Beachte das Eventjahr und verwechsle vergangene Termine nicht mit dem kommenden Event."},
            {"role": "user", "content": text},
        ],
        response_format={"type": "json_schema", "json_schema": {"name": "registration_observation", "strict": True, "schema": schema}},
    )
    return json.loads(response.choices[0].message.content)

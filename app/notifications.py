import smtplib
from email.message import EmailMessage

import httpx

from .config import settings


def send_telegram(message: str) -> tuple[bool, str | None]:
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        return False, "Telegram nicht konfiguriert"
    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    try:
        r = httpx.post(
            url,
            json={
                "chat_id": settings.telegram_chat_id,
                "text": message[:4096],
                "disable_web_page_preview": True,
            },
            timeout=settings.request_timeout_seconds,
        )
        payload = r.json()
        if not payload.get("ok"):
            return False, payload.get("description", "Telegram API Fehler")
        r.raise_for_status()
        return True, None
    except Exception as exc:
        return False, str(exc)

def send_sms(message: str) -> tuple[bool, str | None]:
    if not all([settings.twilio_account_sid, settings.twilio_auth_token, settings.twilio_from, settings.twilio_to]):
        return False, "Twilio nicht konfiguriert"
    try:
        from twilio.rest import Client
        client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
        client.messages.create(body=message, from_=settings.twilio_from, to=settings.twilio_to)
        return True, None
    except Exception as exc:
        return False, str(exc)

def send_email(subject: str, body: str) -> tuple[bool, str | None]:
    if not all([settings.smtp_host, settings.smtp_user, settings.smtp_password, settings.smtp_from, settings.notify_email_to]):
        return False, "SMTP nicht konfiguriert"
    try:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = settings.smtp_from
        msg["To"] = settings.notify_email_to
        msg.set_content(body)
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
            server.starttls()
            server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(msg)
        return True, None
    except Exception as exc:
        return False, str(exc)

from app import notifications
from app.config import settings


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


def test_telegram_is_not_configured(monkeypatch):
    monkeypatch.setattr(settings, "telegram_bot_token", None)
    monkeypatch.setattr(settings, "telegram_chat_id", None)

    assert notifications.send_telegram("Alarm") == (False, "Telegram nicht konfiguriert")


def test_telegram_api_error_is_reported(monkeypatch):
    monkeypatch.setattr(settings, "telegram_bot_token", "token")
    monkeypatch.setattr(settings, "telegram_chat_id", "chat")
    monkeypatch.setattr(
        notifications.httpx,
        "post",
        lambda *args, **kwargs: FakeResponse({"ok": False, "description": "Bad Request"}),
    )

    assert notifications.send_telegram("Alarm") == (False, "Bad Request")


def test_telegram_http_error_reports_api_description(monkeypatch):
    monkeypatch.setattr(settings, "telegram_bot_token", "token")
    monkeypatch.setattr(settings, "telegram_chat_id", "chat")
    monkeypatch.setattr(
        notifications.httpx,
        "post",
        lambda *args, **kwargs: FakeResponse({
            "ok": False,
            "error_code": 403,
            "description": "Forbidden: bot was blocked by the user",
        }),
    )

    assert notifications.send_telegram("Alarm") == (
        False,
        "Forbidden: bot was blocked by the user",
    )


def test_telegram_success_uses_expected_payload(monkeypatch):
    monkeypatch.setattr(settings, "telegram_bot_token", "token")
    monkeypatch.setattr(settings, "telegram_chat_id", "chat")
    captured = {}

    def fake_post(url, **kwargs):
        captured["url"] = url
        captured["kwargs"] = kwargs
        return FakeResponse({"ok": True, "result": {"message_id": 1}})

    monkeypatch.setattr(notifications.httpx, "post", fake_post)

    assert notifications.send_telegram("Alarm") == (True, None)
    assert captured["url"] == "https://api.telegram.org/bottoken/sendMessage"
    assert captured["kwargs"]["json"] == {
        "chat_id": "chat",
        "text": "Alarm",
        "disable_web_page_preview": True,
    }


def test_telegram_message_is_limited_to_api_maximum(monkeypatch):
    monkeypatch.setattr(settings, "telegram_bot_token", "token")
    monkeypatch.setattr(settings, "telegram_chat_id", "chat")
    captured = {}

    def fake_post(url, **kwargs):
        captured["text"] = kwargs["json"]["text"]
        return FakeResponse({"ok": True})

    monkeypatch.setattr(notifications.httpx, "post", fake_post)

    assert notifications.send_telegram("x" * 5000) == (True, None)
    assert len(captured["text"]) == 4096

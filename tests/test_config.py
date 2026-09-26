from app.config import Settings


def test_empty_optional_environment_values_use_defaults(monkeypatch):
    monkeypatch.setenv("SMTP_PORT", "")
    monkeypatch.setenv("SMTP_HOST", "")

    settings = Settings(_env_file=None)

    assert settings.smtp_port == 587
    assert settings.smtp_host is None
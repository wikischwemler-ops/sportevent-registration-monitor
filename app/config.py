from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/sportmonitor"
    openai_api_key: str | None = None
    openai_model: str = "gpt-5-mini"
    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None
    twilio_account_sid: str | None = None
    twilio_auth_token: str | None = None
    twilio_from: str | None = None
    twilio_to: str | None = None
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_from: str | None = None
    notify_email_to: str | None = None
    request_timeout_seconds: int = 30
    user_agent: str = "SportEventRegistrationMonitor/1.0"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()

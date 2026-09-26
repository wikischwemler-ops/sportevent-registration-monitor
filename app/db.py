from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings


class Base(DeclarativeBase):
    pass

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

def init_db():
    from . import models  # noqa: F401
    Base.metadata.create_all(engine)
    if engine.dialect.name == "postgresql":
        with engine.begin() as connection:
            connection.execute(text(
                "ALTER TABLE events ADD COLUMN IF NOT EXISTS next_check_at TIMESTAMPTZ"
            ))
            connection.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_events_next_check_at ON events (next_check_at)"
            ))

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.backend.core.config import get_settings

DATABASE_URL = get_settings().database_url
engine_options: dict = {"pool_pre_ping": True}
if DATABASE_URL.startswith("sqlite"):
    engine_options["connect_args"] = {"check_same_thread": False}

engine = create_engine(
    DATABASE_URL,
    **engine_options,
)


SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False,
)


def get_db() -> Generator[Session, None, None]:
    """Provide a database session to a FastAPI route."""

    database = SessionLocal()

    try:
        yield database
    finally:
        database.close()

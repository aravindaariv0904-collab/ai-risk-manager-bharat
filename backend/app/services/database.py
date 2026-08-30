from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import NullPool
from contextlib import contextmanager

from app.config import settings
from app.models import Base

_engine = None
_SessionLocal = None


def get_database_url() -> str:
    return settings.SUPABASE_URL.replace("https://", "postgresql+psycopg://").replace(".supabase.co", ".supabase.co:5432/postgres")


def get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(
            get_database_url(),
            poolclass=NullPool,
            connect_args={
                "sslmode": "require",
            } if settings.ENVIRONMENT == "production" else {},
        )
    return _engine


def get_session_factory():
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=get_engine())
    return _SessionLocal


@contextmanager
def get_db() -> Session:
    db = get_session_factory()()
    try:
        yield db
    finally:
        db.close()


def init_db():
    Base.metadata.create_all(bind=get_engine())
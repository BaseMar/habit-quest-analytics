import os

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine, URL, make_url
from sqlalchemy.orm import sessionmaker


def get_database_url() -> URL | None:
    """Read the configured PostgreSQL URL."""
    configured_url = os.getenv("DATABASE_URL")
    if not configured_url:
        return None
    url = make_url(configured_url)
    if url.drivername in {"postgres", "postgresql"}:
        return url.set(drivername="postgresql+psycopg")
    if url.get_backend_name() != "postgresql":
        raise ValueError("DATABASE_URL must point to a PostgreSQL database.")
    return url


DATABASE_URL = get_database_url()
engine = (
    create_engine(DATABASE_URL, pool_pre_ping=True, hide_parameters=True)
    if DATABASE_URL is not None
    else None
)
SessionLocal = sessionmaker(bind=engine, autoflush=False)


def get_engine() -> Engine:
    if engine is None:
        raise ValueError("Set DATABASE_URL to the PostgreSQL connection URL.")
    return engine


def get_session():
    """Return a SQLAlchemy session for scripts and services."""
    get_engine()
    return SessionLocal()

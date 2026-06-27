import os
from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from src.database.models import Base


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATABASE_PATH = PROJECT_ROOT / "data" / "habit_quest.db"
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DEFAULT_DATABASE_PATH}")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    """Create database tables if they do not already exist."""
    DEFAULT_DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)
    _ensure_sqlite_schema()


def get_session():
    """Return a SQLAlchemy session for scripts and services."""
    return SessionLocal()


def _ensure_sqlite_schema() -> None:
    """Apply tiny local SQLite schema additions before migrations exist."""
    if not DATABASE_URL.startswith("sqlite"):
        return

    inspector = inspect(engine)
    if "quests" not in inspector.get_table_names():
        return

    quest_columns = {column["name"] for column in inspector.get_columns("quests")}
    if "estimated_minutes" not in quest_columns:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE quests ADD COLUMN estimated_minutes INTEGER"))

    if "player_profiles" not in inspector.get_table_names():
        return

    profile_columns = {column["name"] for column in inspector.get_columns("player_profiles")}
    if "avatar_path" not in profile_columns:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE player_profiles ADD COLUMN avatar_path VARCHAR(255)"))

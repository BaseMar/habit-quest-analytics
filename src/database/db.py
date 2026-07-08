import os
from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from src.database.models import Base, Goal, QuestCheckin, RecurringHabit, RecurringHabitInstance


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
    table_names = inspector.get_table_names()
    if "quests" not in table_names:
        return

    if "quest_checkins" not in table_names:
        QuestCheckin.__table__.create(bind=engine, checkfirst=True)
    if "goals" not in table_names:
        Goal.__table__.create(bind=engine, checkfirst=True)
        table_names.append("goals")
    recurring_habits_created = False
    if "recurring_habits" not in table_names:
        RecurringHabit.__table__.create(bind=engine, checkfirst=True)
        table_names.append("recurring_habits")
        recurring_habits_created = True
    if "recurring_habit_instances" not in table_names:
        RecurringHabitInstance.__table__.create(bind=engine, checkfirst=True)
        table_names.append("recurring_habit_instances")

    quest_columns = {column["name"] for column in inspector.get_columns("quests")}
    if "difficulty" in quest_columns:
        _drop_sqlite_column_if_exists("quests", "difficulty")
        quest_columns.remove("difficulty")
    if "estimated_minutes" not in quest_columns:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE quests ADD COLUMN estimated_minutes INTEGER"))
    if "planned_start_at" not in quest_columns:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE quests ADD COLUMN planned_start_at DATETIME"))
    if "planned_end_at" not in quest_columns:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE quests ADD COLUMN planned_end_at DATETIME"))
    if "goal_id" not in quest_columns:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE quests ADD COLUMN goal_id INTEGER"))

    recurring_habit_columns = (
        set(RecurringHabit.__table__.columns.keys())
        if recurring_habits_created
        else {column["name"] for column in inspector.get_columns("recurring_habits")}
        if "recurring_habits" in table_names
        else set()
    )
    if "difficulty" in recurring_habit_columns:
        _drop_sqlite_column_if_exists("recurring_habits", "difficulty")
        recurring_habit_columns.remove("difficulty")
    if "planned_start_time" not in recurring_habit_columns:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE recurring_habits ADD COLUMN planned_start_time TIME"))
    if "planned_end_time" not in recurring_habit_columns:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE recurring_habits ADD COLUMN planned_end_time TIME"))

    if "player_profiles" not in inspector.get_table_names():
        return

    profile_columns = {column["name"] for column in inspector.get_columns("player_profiles")}
    if "avatar_path" not in profile_columns:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE player_profiles ADD COLUMN avatar_path VARCHAR(255)"))


def _drop_sqlite_column_if_exists(table_name: str, column_name: str) -> None:
    """Drop a legacy SQLite column when the local SQLite version supports it."""
    columns = {column["name"] for column in inspect(engine).get_columns(table_name)}
    if column_name not in columns:
        return

    with engine.begin() as connection:
        connection.execute(text(f"ALTER TABLE {table_name} DROP COLUMN {column_name}"))

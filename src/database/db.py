import os
from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine, URL, make_url
from sqlalchemy.orm import Session, sessionmaker

from src.database.models import Base, Goal, QuestCheckin, RecurringHabit, RecurringHabitInstance


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATABASE_PATH = PROJECT_ROOT / "data" / "habit_quest.db"


def get_database_url() -> URL:
    """Read the configured database URL, defaulting to the local SQLite file."""
    configured_url = os.getenv("DATABASE_URL")
    if not configured_url:
        return URL.create("sqlite", database=str(DEFAULT_DATABASE_PATH))
    url = make_url(configured_url)
    if url.drivername in {"postgres", "postgresql"}:
        return url.set(drivername="postgresql+psycopg")
    return url


DATABASE_URL = get_database_url()
if DATABASE_URL.get_backend_name() == "sqlite":
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(DATABASE_URL, pool_pre_ping=True, hide_parameters=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    """Initialize local SQLite. PostgreSQL schema changes run through Alembic."""
    if engine.dialect.name == "sqlite":
        DEFAULT_DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
        init_sqlite_db(engine)


def init_sqlite_db(bind: Engine) -> None:
    """Prepare a SQLite database, including older local files."""
    Base.metadata.create_all(bind=bind)
    _ensure_sqlite_schema(bind)
    from src.services.quest_service import backfill_goal_session_numbers

    with Session(bind, autoflush=False) as session:
        backfill_goal_session_numbers(session=session)


def get_session():
    """Return a SQLAlchemy session for scripts and services."""
    return SessionLocal()


def _ensure_sqlite_schema(bind: Engine | None = None) -> None:
    """Apply tiny local SQLite schema additions before migrations exist."""
    bind = bind if bind is not None else engine
    if bind.dialect.name != "sqlite":
        return

    inspector = inspect(bind)
    table_names = inspector.get_table_names()
    if "quests" not in table_names:
        return

    if "quest_checkins" not in table_names:
        QuestCheckin.__table__.create(bind=bind, checkfirst=True)
    if "goals" not in table_names:
        Goal.__table__.create(bind=bind, checkfirst=True)
        table_names.append("goals")
    else:
        _ensure_goals_allow_unspecified_planned_time(bind)
    recurring_habits_created = False
    if "recurring_habits" not in table_names:
        RecurringHabit.__table__.create(bind=bind, checkfirst=True)
        table_names.append("recurring_habits")
        recurring_habits_created = True
    if "recurring_habit_instances" not in table_names:
        RecurringHabitInstance.__table__.create(bind=bind, checkfirst=True)
        table_names.append("recurring_habit_instances")

    quest_columns = {column["name"] for column in inspector.get_columns("quests")}
    if "estimated_minutes" not in quest_columns:
        with bind.begin() as connection:
            connection.execute(text("ALTER TABLE quests ADD COLUMN estimated_minutes INTEGER"))
    if "planned_start_at" not in quest_columns:
        with bind.begin() as connection:
            connection.execute(text("ALTER TABLE quests ADD COLUMN planned_start_at DATETIME"))
    if "planned_end_at" not in quest_columns:
        with bind.begin() as connection:
            connection.execute(text("ALTER TABLE quests ADD COLUMN planned_end_at DATETIME"))
    if "goal_id" not in quest_columns:
        with bind.begin() as connection:
            connection.execute(text("ALTER TABLE quests ADD COLUMN goal_id INTEGER"))
    if "goal_session_number" not in quest_columns:
        with bind.begin() as connection:
            connection.execute(text("ALTER TABLE quests ADD COLUMN goal_session_number INTEGER"))

    recurring_habit_columns = (
        set(RecurringHabit.__table__.columns.keys())
        if recurring_habits_created
        else {column["name"] for column in inspector.get_columns("recurring_habits")}
        if "recurring_habits" in table_names
        else set()
    )
    if "planned_start_time" not in recurring_habit_columns:
        with bind.begin() as connection:
            connection.execute(text("ALTER TABLE recurring_habits ADD COLUMN planned_start_time TIME"))
    if "planned_end_time" not in recurring_habit_columns:
        with bind.begin() as connection:
            connection.execute(text("ALTER TABLE recurring_habits ADD COLUMN planned_end_time TIME"))

    if "player_profiles" not in inspector.get_table_names():
        return

    profile_columns = {column["name"] for column in inspector.get_columns("player_profiles")}
    if "avatar_path" not in profile_columns:
        with bind.begin() as connection:
            connection.execute(text("ALTER TABLE player_profiles ADD COLUMN avatar_path VARCHAR(255)"))


def _ensure_goals_allow_unspecified_planned_time(bind: Engine) -> None:
    """Rebuild old local SQLite goals tables that required planned time > 0."""
    with bind.connect() as connection:
        table_sql = connection.execute(
            text("SELECT sql FROM sqlite_master WHERE type='table' AND name='goals'")
        ).scalar()

    if not table_sql or "planned_total_minutes > 0" not in table_sql:
        return

    with bind.begin() as connection:
        connection.execute(text("PRAGMA foreign_keys=OFF"))
        connection.execute(text("ALTER TABLE goals RENAME TO goals_old"))
        Goal.__table__.create(bind=connection, checkfirst=False)
        connection.execute(
            text(
                """
                INSERT INTO goals (
                    id,
                    title,
                    description,
                    planned_total_minutes,
                    start_date,
                    target_end_date,
                    status,
                    created_at,
                    updated_at,
                    category_id
                )
                SELECT
                    id,
                    title,
                    description,
                    planned_total_minutes,
                    start_date,
                    target_end_date,
                    status,
                    created_at,
                    updated_at,
                    category_id
                FROM goals_old
                """
            )
        )
        connection.execute(text("DROP TABLE goals_old"))
        connection.execute(text("PRAGMA foreign_keys=ON"))

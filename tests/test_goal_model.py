from datetime import date

from sqlalchemy import create_engine, inspect
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

import src.database.db as database_db
from src.database.models import Base, Category, Goal, Quest


def test_goals_table_exists():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)

    inspector = inspect(engine)

    assert "goals" in inspector.get_table_names()


def test_goal_can_link_to_category():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine)
    session = TestingSession()
    try:
        category = Category(name="Work", description="Work quests")
        session.add(category)
        session.commit()

        goal = Goal(
            title="Portfolio Project",
            category_id=category.id,
            planned_total_minutes=1200,
            start_date=date(2026, 7, 1),
            target_end_date=date(2026, 8, 31),
        )
        session.add(goal)
        session.commit()
        session.refresh(goal)

        assert goal.category == category
        assert goal in category.goals
        assert goal.status == "Active"
    finally:
        session.close()


def test_quest_goal_id_is_nullable():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine)
    session = TestingSession()
    try:
        quest = Quest(title="Standalone quest", status="Planned")
        session.add(quest)
        session.commit()
        session.refresh(quest)

        assert quest.goal_id is None
        assert quest.goal_session_number is None
    finally:
        session.close()


def test_quest_can_link_to_goal_and_relationships_work():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine)
    session = TestingSession()
    try:
        goal = Goal(title="Portfolio Project", planned_total_minutes=1200)
        session.add(goal)
        session.commit()

        quest = Quest(title="Portfolio session", status="Planned", goal_id=goal.id)
        session.add(quest)
        session.commit()
        session.refresh(goal)
        session.refresh(quest)

        assert quest.goal == goal
        assert quest in goal.quests
    finally:
        session.close()


def test_sqlite_schema_helper_adds_goals_table_to_existing_database(tmp_path, monkeypatch):
    database_path = tmp_path / "existing.db"
    engine = create_engine(f"sqlite:///{database_path}")
    Base.metadata.tables["categories"].create(bind=engine)
    Base.metadata.tables["quests"].create(bind=engine)

    monkeypatch.setattr(database_db, "DATABASE_URL", f"sqlite:///{database_path}")
    monkeypatch.setattr(database_db, "engine", engine)

    database_db._ensure_sqlite_schema()
    database_db._ensure_sqlite_schema()

    inspector = inspect(engine)
    table_names = inspector.get_table_names()
    goal_columns = {column["name"] for column in inspector.get_columns("goals")}

    assert "goals" in table_names
    assert {
        "id",
        "title",
        "description",
        "category_id",
        "planned_total_minutes",
        "start_date",
        "target_end_date",
        "status",
        "created_at",
        "updated_at",
    }.issubset(goal_columns)


def test_sqlite_schema_helper_adds_goal_id_to_existing_quests_table(tmp_path, monkeypatch):
    database_path = tmp_path / "existing.db"
    engine = create_engine(f"sqlite:///{database_path}")
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE categories (
                    id INTEGER PRIMARY KEY,
                    name VARCHAR(100) NOT NULL UNIQUE,
                    description TEXT
                )
                """
            )
        )
        connection.execute(
            text(
                """
                CREATE TABLE quests (
                    id INTEGER PRIMARY KEY,
                    title VARCHAR(200) NOT NULL,
                    description TEXT,
                    status VARCHAR(30) NOT NULL DEFAULT 'active',
                    is_habit BOOLEAN NOT NULL DEFAULT 0,
                    xp_reward INTEGER NOT NULL DEFAULT 10,
                    due_date DATE,
                    completed_at DATETIME,
                    created_at DATETIME,
                    category_id INTEGER
                )
                """
            )
        )

    monkeypatch.setattr(database_db, "DATABASE_URL", f"sqlite:///{database_path}")
    monkeypatch.setattr(database_db, "engine", engine)

    database_db._ensure_sqlite_schema()
    database_db._ensure_sqlite_schema()

    inspector = inspect(engine)
    quest_columns = {column["name"] for column in inspector.get_columns("quests")}

    assert "goal_id" in quest_columns
    assert "goal_session_number" in quest_columns

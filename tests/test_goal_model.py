from datetime import date

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

import src.database.db as database_db
from src.database.models import Base, Category, Goal


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

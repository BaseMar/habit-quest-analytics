from datetime import date, time

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

import src.database.db as database_db
from src.database.models import Base, Category, Quest, RecurringHabit, RecurringHabitInstance


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine)
    session = TestingSession()
    session.add(Category(name="Health", description="Health quests"))
    session.commit()
    try:
        yield session
    finally:
        session.close()


def _create_recurring_habit(
    session,
    title: str = "Gym Workout",
    weekdays: str = "[0, 2, 4]",
    description: str | None = "Strength training",
    end_date: date | None = None,
    planned_start_time: time | None = None,
    planned_end_time: time | None = None,
) -> RecurringHabit:
    category = session.query(Category).one()
    habit = RecurringHabit(
        title=title,
        description=description,
        category_id=category.id,
        xp_reward=75,
        estimated_minutes=60,
        recurrence_type="selected_weekdays",
        weekdays=weekdays,
        start_date=date(2026, 7, 1),
        end_date=end_date,
        planned_start_time=planned_start_time,
        planned_end_time=planned_end_time,
    )
    session.add(habit)
    session.commit()
    session.refresh(habit)
    return habit


def _create_quest(session, title: str = "Generated gym workout") -> Quest:
    category = session.query(Category).one()
    quest = Quest(
        title=title,
        description="Generated from recurring habit",
        category_id=category.id,
        status="Planned",
        xp_reward=75,
        due_date=date(2026, 7, 1),
        estimated_minutes=60,
    )
    session.add(quest)
    session.commit()
    session.refresh(quest)
    return quest


def _create_instance(
    session,
    habit: RecurringHabit,
    quest: Quest,
    scheduled_date: date = date(2026, 7, 1),
) -> RecurringHabitInstance:
    instance = RecurringHabitInstance(
        recurring_habit_id=habit.id,
        quest_id=quest.id,
        scheduled_date=scheduled_date,
    )
    session.add(instance)
    session.commit()
    session.refresh(instance)
    return instance


def test_recurring_habits_table_exists():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)

    inspector = inspect(engine)

    assert "recurring_habits" in inspector.get_table_names()


def test_recurring_habit_instances_table_exists():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)

    inspector = inspect(engine)

    assert "recurring_habit_instances" in inspector.get_table_names()


def test_sqlite_schema_helper_adds_recurring_habit_tables_to_existing_database(tmp_path, monkeypatch):
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

    assert "recurring_habits" in table_names
    assert "recurring_habit_instances" in table_names
    recurring_habit_columns = {column["name"] for column in inspector.get_columns("recurring_habits")}
    assert "planned_start_time" in recurring_habit_columns
    assert "planned_end_time" in recurring_habit_columns


def test_recurring_habit_can_be_created_with_selected_weekdays(session):
    habit = _create_recurring_habit(session)

    assert habit.id is not None
    assert habit.title == "Gym Workout"
    assert habit.recurrence_type == "selected_weekdays"
    assert habit.start_date == date(2026, 7, 1)


def test_recurring_habit_weekdays_store_serialized_json_list(session):
    habit = _create_recurring_habit(session, weekdays="[0, 2, 4]")

    assert habit.weekdays == "[0, 2, 4]"


def test_recurring_habit_is_active_defaults_to_true(session):
    habit = _create_recurring_habit(session)

    assert habit.is_active is True


def test_recurring_habit_can_link_to_category(session):
    habit = _create_recurring_habit(session)
    category = session.query(Category).one()

    assert habit.category == category
    assert habit in category.recurring_habits


def test_recurring_habit_instance_links_habit_quest_and_date(session):
    habit = _create_recurring_habit(session)
    quest = _create_quest(session)
    instance = _create_instance(session, habit, quest, date(2026, 7, 3))

    assert instance.recurring_habit_id == habit.id
    assert instance.quest_id == quest.id
    assert instance.scheduled_date == date(2026, 7, 3)


def test_recurring_habit_instances_relationship_works(session):
    habit = _create_recurring_habit(session)
    quest = _create_quest(session)
    instance = _create_instance(session, habit, quest)
    session.refresh(habit)

    assert habit.instances == [instance]


def test_recurring_habit_instance_recurring_habit_relationship_works(session):
    habit = _create_recurring_habit(session)
    quest = _create_quest(session)
    instance = _create_instance(session, habit, quest)

    assert instance.recurring_habit == habit


def test_recurring_habit_instance_quest_relationship_works(session):
    habit = _create_recurring_habit(session)
    quest = _create_quest(session)
    instance = _create_instance(session, habit, quest)

    assert instance.quest == quest
    assert quest.recurring_habit_instance == instance


def test_unique_habit_date_prevents_duplicate_instances_for_same_day(session):
    habit = _create_recurring_habit(session)
    first_quest = _create_quest(session, "First generated workout")
    second_quest = _create_quest(session, "Second generated workout")
    _create_instance(session, habit, first_quest, date(2026, 7, 1))

    duplicate = RecurringHabitInstance(
        recurring_habit_id=habit.id,
        quest_id=second_quest.id,
        scheduled_date=date(2026, 7, 1),
    )
    session.add(duplicate)

    with pytest.raises(IntegrityError):
        session.commit()


def test_unique_quest_id_prevents_same_quest_on_multiple_instances(session):
    first_habit = _create_recurring_habit(session, "Gym Workout")
    second_habit = _create_recurring_habit(session, "SQL Study")
    quest = _create_quest(session)
    _create_instance(session, first_habit, quest, date(2026, 7, 1))

    duplicate = RecurringHabitInstance(
        recurring_habit_id=second_habit.id,
        quest_id=quest.id,
        scheduled_date=date(2026, 7, 2),
    )
    session.add(duplicate)

    with pytest.raises(IntegrityError):
        session.commit()


def test_recurring_habit_nullable_end_date_works(session):
    habit = _create_recurring_habit(session, end_date=None)

    assert habit.end_date is None


def test_recurring_habit_nullable_description_works(session):
    habit = _create_recurring_habit(session, description=None)

    assert habit.description is None


def test_recurring_habit_planned_times_can_be_stored(session):
    habit = _create_recurring_habit(
        session,
        planned_start_time=time(9, 0),
        planned_end_time=time(10, 30),
    )

    assert habit.planned_start_time == time(9, 0)
    assert habit.planned_end_time == time(10, 30)

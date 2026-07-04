from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.models import Base, Category, Quest, QuestCheckin, RecurringHabitInstance
from src.services.recurring_habit_service import (
    create_recurring_habit,
    deserialize_weekdays,
    get_recurring_habit,
    list_recurring_habits,
    serialize_weekdays,
    set_recurring_habit_active,
    validate_weekdays,
)


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


def _category_id(session) -> int:
    return session.query(Category).one().id


def _create_habit(
    session,
    title: str = "Gym Workout",
    is_active: bool = True,
):
    return create_recurring_habit(
        title=title,
        category_id=_category_id(session),
        difficulty="Hard",
        estimated_minutes=60,
        recurrence_type="selected_weekdays",
        weekdays=[4, 0, 2],
        start_date=date(2026, 7, 1),
        description="Strength training",
        is_active=is_active,
        session=session,
    )


def test_create_recurring_habit_creates_selected_weekdays_habit(session):
    habit = _create_habit(session)

    assert habit.id is not None
    assert habit.title == "Gym Workout"
    assert habit.description == "Strength training"
    assert habit.category_id == _category_id(session)
    assert habit.difficulty == "Hard"
    assert habit.estimated_minutes == 60
    assert habit.recurrence_type == "selected_weekdays"
    assert habit.start_date == date(2026, 7, 1)
    assert habit.end_date is None
    assert habit.is_active is True


def test_create_recurring_habit_calculates_xp_from_difficulty(session):
    habit = create_recurring_habit(
        title="Boss Study",
        category_id=_category_id(session),
        difficulty="Boss",
        estimated_minutes=90,
        recurrence_type="selected_weekdays",
        weekdays=[1, 3],
        start_date=date(2026, 7, 1),
        session=session,
    )

    assert habit.xp_reward == 150


def test_create_recurring_habit_stores_weekdays_as_stable_json(session):
    habit = _create_habit(session)

    assert habit.weekdays == "[0, 2, 4]"


def test_deserialize_weekdays_returns_expected_list():
    assert deserialize_weekdays("[0, 2, 4]") == [0, 2, 4]


def test_create_recurring_habit_rejects_empty_title(session):
    with pytest.raises(ValueError, match="title is required"):
        create_recurring_habit(
            title=" ",
            category_id=_category_id(session),
            difficulty="Hard",
            estimated_minutes=60,
            recurrence_type="selected_weekdays",
            weekdays=[0],
            start_date=date(2026, 7, 1),
            session=session,
        )


def test_create_recurring_habit_rejects_invalid_estimated_minutes(session):
    with pytest.raises(ValueError, match="Estimated minutes"):
        create_recurring_habit(
            title="Gym Workout",
            category_id=_category_id(session),
            difficulty="Hard",
            estimated_minutes=0,
            recurrence_type="selected_weekdays",
            weekdays=[0],
            start_date=date(2026, 7, 1),
            session=session,
        )


def test_create_recurring_habit_rejects_end_date_before_start_date(session):
    with pytest.raises(ValueError, match="End date"):
        create_recurring_habit(
            title="Gym Workout",
            category_id=_category_id(session),
            difficulty="Hard",
            estimated_minutes=60,
            recurrence_type="selected_weekdays",
            weekdays=[0],
            start_date=date(2026, 7, 2),
            end_date=date(2026, 7, 1),
            session=session,
        )


@pytest.mark.parametrize("weekdays", [[7], [-1], [True], ["0"]])
def test_validate_weekdays_rejects_invalid_values(weekdays):
    with pytest.raises(ValueError, match="Weekday values"):
        validate_weekdays(weekdays)


def test_duplicate_weekdays_are_deduplicated_and_sorted():
    assert validate_weekdays([4, 0, 2, 2, 4]) == [0, 2, 4]
    assert serialize_weekdays([4, 0, 2, 2, 4]) == "[0, 2, 4]"


def test_selected_weekdays_requires_at_least_one_weekday(session):
    with pytest.raises(ValueError, match="At least one weekday"):
        create_recurring_habit(
            title="Gym Workout",
            category_id=_category_id(session),
            difficulty="Hard",
            estimated_minutes=60,
            recurrence_type="selected_weekdays",
            weekdays=[],
            start_date=date(2026, 7, 1),
            session=session,
        )


def test_list_recurring_habits_returns_created_habits(session):
    _create_habit(session, "SQL Study")
    _create_habit(session, "Gym Workout", is_active=False)

    habits = list_recurring_habits(session=session)

    assert [habit.title for habit in habits] == ["SQL Study", "Gym Workout"]


def test_list_recurring_habits_active_only_excludes_inactive_habits(session):
    active_habit = _create_habit(session, "SQL Study")
    _create_habit(session, "Gym Workout", is_active=False)

    habits = list_recurring_habits(active_only=True, session=session)

    assert habits == [active_habit]


def test_get_recurring_habit_returns_existing_habit(session):
    habit = _create_habit(session)

    found = get_recurring_habit(habit.id, session=session)

    assert found == habit


def test_get_recurring_habit_returns_none_for_missing_habit(session):
    assert get_recurring_habit(999, session=session) is None


def test_set_recurring_habit_active_deactivates_habit(session):
    habit = _create_habit(session)

    updated = set_recurring_habit_active(habit.id, False, session=session)

    assert updated.is_active is False


def test_set_recurring_habit_active_reactivates_habit(session):
    habit = _create_habit(session, is_active=False)

    updated = set_recurring_habit_active(habit.id, True, session=session)

    assert updated.is_active is True


def test_set_recurring_habit_active_rejects_missing_habit(session):
    with pytest.raises(ValueError, match="was not found"):
        set_recurring_habit_active(999, False, session=session)


def test_create_recurring_habit_does_not_create_quest_rows(session):
    _create_habit(session)

    assert session.query(Quest).count() == 0


def test_create_recurring_habit_does_not_create_quest_checkin_rows(session):
    _create_habit(session)

    assert session.query(QuestCheckin).count() == 0


def test_create_recurring_habit_does_not_create_recurring_habit_instance_rows(session):
    _create_habit(session)

    assert session.query(RecurringHabitInstance).count() == 0

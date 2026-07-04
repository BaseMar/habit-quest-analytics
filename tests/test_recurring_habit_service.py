from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.models import Base, Category, Quest, QuestCheckin, RecurringHabitInstance
from src.services.checklist_service import complete_checkin, get_month_checklist
from src.services.recurring_habit_service import (
    build_recurring_habit_dates_for_month,
    create_recurring_habit,
    deserialize_weekdays,
    generate_all_recurring_habits_for_month,
    generate_recurring_habit_for_month,
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
    weekdays: list[int] | None = None,
    start_date: date = date(2026, 7, 1),
    end_date: date | None = None,
    difficulty: str = "Hard",
    estimated_minutes: int = 60,
):
    return create_recurring_habit(
        title=title,
        category_id=_category_id(session),
        difficulty=difficulty,
        estimated_minutes=estimated_minutes,
        recurrence_type="selected_weekdays",
        weekdays=weekdays or [4, 0, 2],
        start_date=start_date,
        end_date=end_date,
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


def test_build_recurring_habit_dates_for_month_generates_selected_weekdays(session):
    habit = _create_habit(session, weekdays=[0, 2, 4])

    dates = build_recurring_habit_dates_for_month(habit, 2026, 7)

    assert dates == [
        date(2026, 7, 1),
        date(2026, 7, 3),
        date(2026, 7, 6),
        date(2026, 7, 8),
        date(2026, 7, 10),
        date(2026, 7, 13),
        date(2026, 7, 15),
        date(2026, 7, 17),
        date(2026, 7, 20),
        date(2026, 7, 22),
        date(2026, 7, 24),
        date(2026, 7, 27),
        date(2026, 7, 29),
        date(2026, 7, 31),
    ]


def test_build_recurring_habit_dates_for_month_daily_preset_generates_every_day(session):
    habit = _create_habit(session, weekdays=[0, 1, 2, 3, 4, 5, 6])

    dates = build_recurring_habit_dates_for_month(habit, 2026, 7)

    assert len(dates) == 31
    assert dates[0] == date(2026, 7, 1)
    assert dates[-1] == date(2026, 7, 31)


def test_build_recurring_habit_dates_for_month_weekdays_preset_generates_weekdays(session):
    habit = _create_habit(session, weekdays=[0, 1, 2, 3, 4])

    dates = build_recurring_habit_dates_for_month(habit, 2026, 7)

    assert len(dates) == 23
    assert all(day.weekday() < 5 for day in dates)


def test_build_recurring_habit_dates_respects_start_date_boundary(session):
    habit = _create_habit(session, weekdays=[0, 2, 4], start_date=date(2026, 7, 10))

    dates = build_recurring_habit_dates_for_month(habit, 2026, 7)

    assert dates[0] == date(2026, 7, 10)
    assert all(day >= date(2026, 7, 10) for day in dates)


def test_build_recurring_habit_dates_respects_end_date_boundary(session):
    habit = _create_habit(session, weekdays=[0, 2, 4], end_date=date(2026, 7, 10))

    dates = build_recurring_habit_dates_for_month(habit, 2026, 7)

    assert dates == [
        date(2026, 7, 1),
        date(2026, 7, 3),
        date(2026, 7, 6),
        date(2026, 7, 8),
        date(2026, 7, 10),
    ]


def test_build_recurring_habit_dates_inactive_habit_returns_no_dates(session):
    habit = _create_habit(session, is_active=False)

    assert build_recurring_habit_dates_for_month(habit, 2026, 7) == []


def test_build_recurring_habit_dates_rejects_invalid_month(session):
    habit = _create_habit(session)

    with pytest.raises(ValueError, match="month must be between 1 and 12"):
        build_recurring_habit_dates_for_month(habit, 2026, 13)


def test_generate_recurring_habit_for_month_creates_quest_rows(session):
    habit = _create_habit(session, weekdays=[2])

    summary = generate_recurring_habit_for_month(habit.id, 2026, 7, session=session)

    assert summary["generated_count"] == 5
    assert session.query(Quest).count() == 5


def test_generated_quest_has_expected_fields(session):
    habit = _create_habit(
        session,
        title="SQL Study",
        weekdays=[2],
        difficulty="Boss",
        estimated_minutes=45,
    )

    generate_recurring_habit_for_month(habit.id, 2026, 7, session=session)
    quest = session.query(Quest).order_by(Quest.due_date).first()

    assert quest.title == "SQL Study"
    assert quest.description == "Strength training"
    assert quest.category_id == habit.category_id
    assert quest.difficulty == "Boss"
    assert quest.xp_reward == 150
    assert quest.estimated_minutes == 45
    assert quest.due_date == date(2026, 7, 1)
    assert quest.status == "Planned"
    assert quest.planned_start_at is None
    assert quest.planned_end_at is None


def test_generate_recurring_habit_for_month_creates_planned_checkins(session):
    habit = _create_habit(session, weekdays=[2])

    generate_recurring_habit_for_month(habit.id, 2026, 7, session=session)
    checkins = session.query(QuestCheckin).order_by(QuestCheckin.checkin_date).all()

    assert len(checkins) == 5
    assert {checkin.status for checkin in checkins} == {"Planned"}
    assert [checkin.checkin_date for checkin in checkins] == [
        date(2026, 7, 1),
        date(2026, 7, 8),
        date(2026, 7, 15),
        date(2026, 7, 22),
        date(2026, 7, 29),
    ]


def test_generated_checkins_have_zero_xp_awarded(session):
    habit = _create_habit(session, weekdays=[2])

    generate_recurring_habit_for_month(habit.id, 2026, 7, session=session)

    assert {checkin.xp_awarded for checkin in session.query(QuestCheckin).all()} == {0}


def test_generate_recurring_habit_for_month_creates_instances(session):
    habit = _create_habit(session, weekdays=[2])

    generate_recurring_habit_for_month(habit.id, 2026, 7, session=session)
    instances = session.query(RecurringHabitInstance).order_by(RecurringHabitInstance.scheduled_date).all()

    assert len(instances) == 5
    assert {instance.recurring_habit_id for instance in instances} == {habit.id}
    assert instances[0].quest is not None


def test_repeated_generation_does_not_duplicate_quest_rows(session):
    habit = _create_habit(session, weekdays=[2])

    generate_recurring_habit_for_month(habit.id, 2026, 7, session=session)
    generate_recurring_habit_for_month(habit.id, 2026, 7, session=session)

    assert session.query(Quest).count() == 5


def test_repeated_generation_does_not_duplicate_checkins(session):
    habit = _create_habit(session, weekdays=[2])

    generate_recurring_habit_for_month(habit.id, 2026, 7, session=session)
    generate_recurring_habit_for_month(habit.id, 2026, 7, session=session)

    assert session.query(QuestCheckin).count() == 5


def test_repeated_generation_does_not_duplicate_instances(session):
    habit = _create_habit(session, weekdays=[2])

    generate_recurring_habit_for_month(habit.id, 2026, 7, session=session)
    generate_recurring_habit_for_month(habit.id, 2026, 7, session=session)

    assert session.query(RecurringHabitInstance).count() == 5


def test_repeated_generation_reports_skipped_existing_count(session):
    habit = _create_habit(session, weekdays=[2])

    first = generate_recurring_habit_for_month(habit.id, 2026, 7, session=session)
    second = generate_recurring_habit_for_month(habit.id, 2026, 7, session=session)

    assert first["eligible_count"] == 5
    assert first["generated_count"] == 5
    assert first["skipped_existing_count"] == 0
    assert second["eligible_count"] == 5
    assert second["generated_count"] == 0
    assert second["skipped_existing_count"] == 5


def test_generate_all_recurring_habits_for_month_generates_for_active_habits(session):
    _create_habit(session, "Gym Workout", weekdays=[2])
    _create_habit(session, "SQL Study", weekdays=[4])

    summary = generate_all_recurring_habits_for_month(2026, 7, session=session)

    assert summary["total_generated"] == 10
    assert summary["total_eligible"] == 10
    assert len(summary["habit_summaries"]) == 2
    assert session.query(Quest).count() == 10


def test_generate_all_recurring_habits_for_month_skips_inactive_by_default(session):
    _create_habit(session, "Gym Workout", weekdays=[2])
    _create_habit(session, "SQL Study", is_active=False, weekdays=[4])

    summary = generate_all_recurring_habits_for_month(2026, 7, session=session)

    assert summary["total_generated"] == 5
    assert len(summary["habit_summaries"]) == 1
    assert session.query(Quest).count() == 5


def test_generated_checkins_appear_in_month_checklist(session):
    habit = _create_habit(session, weekdays=[2])

    generate_recurring_habit_for_month(habit.id, 2026, 7, session=session)
    checklist = get_month_checklist(2026, 7, session=session)

    assert len(checklist["rows"]) == 5
    assert {row["title"] for row in checklist["rows"]} == {"Gym Workout"}
    assert all(row["cells"][row_date]["status"] == "Planned" for row in checklist["rows"] for row_date in row["cells"] if row["cells"][row_date]["checkin_id"] is not None)


def test_completing_generated_checkin_awards_xp_once(session):
    habit = _create_habit(session, weekdays=[2])
    generate_recurring_habit_for_month(habit.id, 2026, 7, session=session)
    instance = session.query(RecurringHabitInstance).order_by(RecurringHabitInstance.scheduled_date).first()

    first = complete_checkin(instance.quest_id, instance.scheduled_date, session=session)
    second = complete_checkin(instance.quest_id, instance.scheduled_date, session=session)

    assert first.xp_awarded == habit.xp_reward
    assert second.xp_awarded == habit.xp_reward
    assert session.query(QuestCheckin).filter_by(quest_id=instance.quest_id).count() == 1

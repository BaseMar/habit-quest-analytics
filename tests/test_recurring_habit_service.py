from datetime import date, datetime, time

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.models import Base, Category, Quest, QuestCheckin, RecurringHabitInstance
from src.services.checklist_service import complete_checkin, fail_checkin, get_month_checklist, skip_checkin
from src.services.quest_service import get_quests_for_calendar, get_quests_for_day
from src.services.recurring_habit_service import (
    archive_recurring_habit,
    build_recurring_habit_dates_for_month,
    create_recurring_habit,
    delete_recurring_habit_if_unused,
    deserialize_weekdays,
    generate_all_recurring_habits_for_month,
    generate_recurring_habit_for_month,
    get_recurring_habit,
    get_recurring_habit_history_summary,
    list_recurring_habits,
    remove_future_planned_recurring_instances,
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
    planned_start_time: time | None = None,
    planned_end_time: time | None = None,
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
        planned_start_time=planned_start_time,
        planned_end_time=planned_end_time,
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


def test_create_recurring_habit_calculates_xp_from_estimated_minutes(session):
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

    assert habit.xp_reward == 30


def test_create_recurring_habit_difficulty_does_not_change_xp_for_same_minutes(session):
    easy = create_recurring_habit(
        title="Easy Study",
        category_id=_category_id(session),
        difficulty="Easy",
        estimated_minutes=60,
        recurrence_type="selected_weekdays",
        weekdays=[1],
        start_date=date(2026, 7, 1),
        session=session,
    )
    boss = create_recurring_habit(
        title="Boss Study",
        category_id=_category_id(session),
        difficulty="Boss",
        estimated_minutes=60,
        recurrence_type="selected_weekdays",
        weekdays=[1],
        start_date=date(2026, 7, 1),
        session=session,
    )

    assert easy.xp_reward == 20
    assert boss.xp_reward == 20


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


def test_delete_unused_recurring_habit_removes_template_from_list(session):
    habit = _create_habit(session)

    summary = delete_recurring_habit_if_unused(habit.id, session=session)

    assert summary["deleted"] is True
    assert summary["generated_instances_count"] == 0
    assert get_recurring_habit(habit.id, session=session) is None
    assert list_recurring_habits(session=session) == []


def test_delete_recurring_habit_with_generated_history_does_not_hard_delete(session):
    habit = _create_habit(session, weekdays=[2])
    generate_recurring_habit_for_month(habit.id, 2026, 7, session=session)

    summary = delete_recurring_habit_if_unused(habit.id, session=session)

    assert summary["deleted"] is False
    assert summary["generated_instances_count"] == 5
    assert get_recurring_habit(habit.id, session=session) == habit
    assert session.query(RecurringHabitInstance).count() == 5
    assert session.query(Quest).count() == 5
    assert session.query(QuestCheckin).count() == 5


def test_archive_recurring_habit_with_history_preserves_generated_rows(session):
    habit = _create_habit(session, weekdays=[2])
    generate_recurring_habit_for_month(habit.id, 2026, 7, session=session)

    summary = archive_recurring_habit(habit.id, session=session)
    session.refresh(habit)

    assert habit.is_active is False
    assert summary["generated_instances_count"] == 5
    assert session.query(RecurringHabitInstance).count() == 5
    assert session.query(Quest).count() == 5
    assert session.query(QuestCheckin).count() == 5


def test_create_recurring_habit_does_not_create_quest_rows(session):
    _create_habit(session)

    assert session.query(Quest).count() == 0


def test_create_recurring_habit_does_not_create_quest_checkin_rows(session):
    _create_habit(session)

    assert session.query(QuestCheckin).count() == 0


def test_create_recurring_habit_does_not_create_recurring_habit_instance_rows(session):
    _create_habit(session)

    assert session.query(RecurringHabitInstance).count() == 0


def test_create_recurring_habit_stores_planned_times(session):
    habit = _create_habit(
        session,
        planned_start_time=time(9, 0),
        planned_end_time=time(10, 30),
    )

    assert habit.planned_start_time == time(9, 0)
    assert habit.planned_end_time == time(10, 30)


def test_create_recurring_habit_rejects_partial_planned_time(session):
    with pytest.raises(ValueError, match="both be provided"):
        _create_habit(session, planned_start_time=time(9, 0), planned_end_time=None)


def test_create_recurring_habit_rejects_end_time_before_start_time(session):
    with pytest.raises(ValueError, match="End time must be after start time"):
        _create_habit(
            session,
            planned_start_time=time(10, 30),
            planned_end_time=time(9, 0),
        )


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
    assert quest.xp_reward == 15
    assert quest.estimated_minutes == 45
    assert quest.due_date == date(2026, 7, 1)
    assert quest.status == "Planned"
    assert quest.planned_start_at is None
    assert quest.planned_end_at is None


def test_generated_quest_uses_template_planned_times(session):
    habit = _create_habit(
        session,
        weekdays=[2],
        planned_start_time=time(9, 0),
        planned_end_time=time(10, 30),
    )

    generate_recurring_habit_for_month(habit.id, 2026, 7, session=session)
    quest = session.query(Quest).order_by(Quest.due_date).first()

    assert quest.planned_start_at == datetime(2026, 7, 1, 9, 0)
    assert quest.planned_end_at == datetime(2026, 7, 1, 10, 30)


def test_all_day_recurring_habit_generation_keeps_null_planned_datetimes(session):
    habit = _create_habit(session, weekdays=[2])

    generate_recurring_habit_for_month(habit.id, 2026, 7, session=session)
    quest = session.query(Quest).order_by(Quest.due_date).first()

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


def test_deactivated_recurring_habit_does_not_generate_new_instances(session):
    habit = _create_habit(session, weekdays=[2], is_active=False)

    summary = generate_recurring_habit_for_month(habit.id, 2026, 7, session=session)

    assert summary["eligible_count"] == 0
    assert summary["generated_count"] == 0
    assert session.query(Quest).count() == 0


def test_archived_recurring_habit_does_not_generate_new_instances(session):
    habit = _create_habit(session, weekdays=[2])
    archive_recurring_habit(habit.id, session=session)

    summary = generate_recurring_habit_for_month(habit.id, 2026, 7, session=session)

    assert summary["eligible_count"] == 0
    assert summary["generated_count"] == 0
    assert session.query(Quest).count() == 0


def test_get_recurring_habit_history_summary_counts_statuses_and_removable_days(session):
    habit = _create_habit(session, weekdays=[0, 1, 2, 3, 4, 5, 6])
    generate_recurring_habit_for_month(habit.id, 2026, 7, session=session)
    _complete_instance_on(session, date(2026, 7, 10))
    _skip_instance_on(session, date(2026, 7, 11))
    _fail_instance_on(session, date(2026, 7, 12))
    _set_instance_xp_awarded(session, date(2026, 7, 13), 5)

    summary = get_recurring_habit_history_summary(
        habit.id,
        today=date(2026, 7, 10),
        session=session,
    )

    assert summary["generated_instances_count"] == 31
    assert summary["completed_count"] == 1
    assert summary["skipped_count"] == 1
    assert summary["failed_count"] == 1
    assert summary["planned_count"] == 28
    assert summary["removable_future_planned_count"] == 18


def test_remove_future_planned_recurring_instances_preserves_history_and_past_plans(session):
    habit = _create_habit(session, weekdays=[0, 1, 2, 3, 4, 5, 6])
    generate_recurring_habit_for_month(habit.id, 2026, 7, session=session)
    _complete_instance_on(session, date(2026, 7, 10))
    _skip_instance_on(session, date(2026, 7, 11))
    _fail_instance_on(session, date(2026, 7, 12))
    _set_instance_xp_awarded(session, date(2026, 7, 13), 5)

    summary = remove_future_planned_recurring_instances(
        habit.id,
        today=date(2026, 7, 10),
        session=session,
    )

    assert summary["removed_instances_count"] == 18
    assert summary["removed_checkins_count"] == 18
    assert summary["removed_quests_count"] == 18
    assert _instance_on(session, date(2026, 7, 1)) is not None
    assert _instance_on(session, date(2026, 7, 9)) is not None
    assert _instance_on(session, date(2026, 7, 10)) is not None
    assert _instance_on(session, date(2026, 7, 11)) is not None
    assert _instance_on(session, date(2026, 7, 12)) is not None
    assert _instance_on(session, date(2026, 7, 13)) is not None
    assert _instance_on(session, date(2026, 7, 14)) is None
    assert session.query(Quest).filter(Quest.due_date == date(2026, 7, 14)).count() == 0
    assert session.query(QuestCheckin).filter(QuestCheckin.checkin_date == date(2026, 7, 14)).count() == 0
    assert _checkin_on(session, date(2026, 7, 10)).status == "Completed"
    assert _checkin_on(session, date(2026, 7, 11)).status == "Skipped"
    assert _checkin_on(session, date(2026, 7, 12)).status == "Failed"
    assert _checkin_on(session, date(2026, 7, 13)).xp_awarded == 5


def test_month_checklist_still_groups_remaining_instances_after_future_removal(session):
    habit = _create_habit(session, weekdays=[0, 1, 2, 3, 4, 5, 6])
    generate_recurring_habit_for_month(habit.id, 2026, 7, session=session)

    remove_future_planned_recurring_instances(
        habit.id,
        today=date(2026, 7, 10),
        session=session,
    )

    checklist = get_month_checklist(2026, 7, session=session)
    row = checklist["rows"][0]

    assert len(checklist["rows"]) == 1
    assert row["row_type"] == "recurring_habit"
    assert row["cells"][date(2026, 7, 9)]["status"] == "Planned"
    assert row["cells"][date(2026, 7, 10)]["status"] is None


def test_generated_checkins_appear_in_month_checklist(session):
    habit = _create_habit(session, weekdays=[2])

    generate_recurring_habit_for_month(habit.id, 2026, 7, session=session)
    checklist = get_month_checklist(2026, 7, session=session)
    row = checklist["rows"][0]

    assert len(checklist["rows"]) == 1
    assert row["row_type"] == "recurring_habit"
    assert row["title"] == "Gym Workout"
    assert row["cells"][date(2026, 7, 1)]["status"] == "Planned"
    assert row["cells"][date(2026, 7, 1)]["quest_id"] is not None
    assert row["cells"][date(2026, 7, 2)]["status"] is None
    assert row["cells"][date(2026, 7, 2)]["quest_id"] is None
    assert row["cells"][date(2026, 7, 2)]["checkin_id"] is None


def test_calendar_and_day_schedule_display_generated_recurring_status(session):
    habit = _create_habit(
        session,
        weekdays=[2],
        planned_start_time=time(9, 0),
        planned_end_time=time(10, 30),
    )
    generate_recurring_habit_for_month(habit.id, 2026, 7, session=session)
    instance = session.query(RecurringHabitInstance).order_by(RecurringHabitInstance.scheduled_date).first()
    complete_checkin(instance.quest_id, instance.scheduled_date, session=session)

    calendar_events = get_quests_for_calendar(session=session)
    day_quests = get_quests_for_day(date(2026, 7, 1), session=session)

    assert calendar_events[0]["status"] == "Completed"
    assert calendar_events[0]["start"] == "2026-07-01T09:00:00"
    assert calendar_events[0]["end"] == "2026-07-01T10:30:00"
    assert day_quests[0].display_status == "Completed"


def test_completing_generated_checkin_awards_xp_once(session):
    habit = _create_habit(session, weekdays=[2])
    generate_recurring_habit_for_month(habit.id, 2026, 7, session=session)
    instance = session.query(RecurringHabitInstance).order_by(RecurringHabitInstance.scheduled_date).first()

    first = complete_checkin(instance.quest_id, instance.scheduled_date, session=session)
    second = complete_checkin(instance.quest_id, instance.scheduled_date, session=session)

    assert first.xp_awarded == habit.xp_reward
    assert second.xp_awarded == habit.xp_reward
    assert session.query(QuestCheckin).filter_by(quest_id=instance.quest_id).count() == 1


def _instance_on(session, scheduled_date: date) -> RecurringHabitInstance | None:
    return (
        session.query(RecurringHabitInstance)
        .filter(RecurringHabitInstance.scheduled_date == scheduled_date)
        .one_or_none()
    )


def _checkin_on(session, checkin_date: date) -> QuestCheckin | None:
    return (
        session.query(QuestCheckin)
        .filter(QuestCheckin.checkin_date == checkin_date)
        .one_or_none()
    )


def _complete_instance_on(session, scheduled_date: date) -> QuestCheckin:
    instance = _instance_on(session, scheduled_date)
    return complete_checkin(instance.quest_id, scheduled_date, session=session)


def _skip_instance_on(session, scheduled_date: date) -> QuestCheckin:
    instance = _instance_on(session, scheduled_date)
    return skip_checkin(instance.quest_id, scheduled_date, session=session)


def _fail_instance_on(session, scheduled_date: date) -> QuestCheckin:
    instance = _instance_on(session, scheduled_date)
    return fail_checkin(instance.quest_id, scheduled_date, session=session)


def _set_instance_xp_awarded(session, scheduled_date: date, xp_awarded: int) -> QuestCheckin:
    checkin = _checkin_on(session, scheduled_date)
    checkin.xp_awarded = xp_awarded
    session.commit()
    return checkin

from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.models import Base, Category, Goal, Quest, QuestCheckin
from src.services.checklist_service import (
    build_month_days,
    complete_checkin,
    ensure_checkin,
    fail_checkin,
    get_month_checklist,
    is_checklist_cell_editable,
    mark_stale_planned_checkins_failed,
    reset_checkin,
    skip_checkin,
    update_checklist_cell_status,
    update_checkin_status,
)
from src.services.quest_service import create_quest, create_scheduled_quest
from src.services.recurring_habit_service import create_recurring_habit, generate_recurring_habit_for_month


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


def _create_quest(session, title: str = "Morning workout", estimated_minutes: int = 225):
    category = session.query(Category).one()
    return create_quest(
        title,
        category_id=category.id,
        planned_date=date(2026, 7, 1),
        estimated_minutes=estimated_minutes,
        session=session,
    )


def _create_raw_quest(
    session,
    title: str,
    due_date: date | None = None,
    planned_start_at: datetime | None = None,
    planned_end_at: datetime | None = None,
):
    category = session.query(Category).one()
    quest = Quest(
        title=title,
        category_id=category.id,
        status="Planned",
        xp_reward=75,
        due_date=due_date,
        planned_start_at=planned_start_at,
        planned_end_at=planned_end_at,
        estimated_minutes=60,
    )
    session.add(quest)
    session.commit()
    session.refresh(quest)
    return quest


def _create_recurring_habit(session, weekdays: list[int] | None = None):
    category = session.query(Category).one()
    return create_recurring_habit(
        title="Gym Workout",
        category_id=category.id,
        estimated_minutes=60,
        recurrence_type="selected_weekdays",
        weekdays=weekdays or [0, 2, 4],
        start_date=date(2026, 7, 1),
        session=session,
    )


def test_ensure_checkin_creates_planned_checkin(session):
    quest = _create_quest(session)

    checkin = ensure_checkin(quest.id, date(2026, 7, 1), session=session)

    assert checkin.quest_id == quest.id
    assert checkin.checkin_date == date(2026, 7, 1)
    assert checkin.status == "Planned"
    assert checkin.xp_awarded == 0


def test_ensure_checkin_returns_existing_checkin_without_duplicate(session):
    quest = _create_quest(session)

    first = ensure_checkin(quest.id, date(2026, 7, 1), session=session)
    second = ensure_checkin(quest.id, date(2026, 7, 1), session=session)

    assert second.id == first.id
    assert session.query(QuestCheckin).count() == 1


def test_complete_checkin_sets_completed_status_timestamp_and_xp(session):
    quest = _create_quest(session)

    checkin = complete_checkin(quest.id, date(2026, 7, 1), session=session)

    assert checkin.status == "Completed"
    assert checkin.completed_at is not None
    assert checkin.xp_awarded == quest.xp_reward


def test_complete_checkin_twice_does_not_duplicate_xp(session):
    quest = _create_quest(session)

    first = complete_checkin(quest.id, date(2026, 7, 1), session=session)
    first_completed_at = first.completed_at
    second = complete_checkin(quest.id, date(2026, 7, 1), session=session)

    assert second.status == "Completed"
    assert second.xp_awarded == quest.xp_reward
    assert second.completed_at == first_completed_at
    assert session.query(QuestCheckin).count() == 1


def test_skip_checkin_sets_skipped_status_timestamp_and_no_xp(session):
    quest = _create_quest(session)

    checkin = skip_checkin(quest.id, date(2026, 7, 1), session=session)

    assert checkin.status == "Skipped"
    assert checkin.skipped_at is not None
    assert checkin.completed_at is None
    assert checkin.failed_at is None
    assert checkin.xp_awarded == 0


def test_fail_checkin_sets_failed_status_timestamp_and_no_xp(session):
    quest = _create_quest(session)

    checkin = fail_checkin(quest.id, date(2026, 7, 1), session=session)

    assert checkin.status == "Failed"
    assert checkin.failed_at is not None
    assert checkin.completed_at is None
    assert checkin.skipped_at is None
    assert checkin.xp_awarded == 0


def test_reset_checkin_returns_to_planned_and_clears_timestamps_and_xp(session):
    quest = _create_quest(session)
    complete_checkin(quest.id, date(2026, 7, 1), session=session)

    checkin = reset_checkin(quest.id, date(2026, 7, 1), session=session)

    assert checkin.status == "Planned"
    assert checkin.xp_awarded == 0
    assert checkin.completed_at is None
    assert checkin.skipped_at is None
    assert checkin.failed_at is None


def test_update_checkin_status_rejects_invalid_status(session):
    quest = _create_quest(session)

    with pytest.raises(ValueError, match="Unknown check-in status"):
        update_checkin_status(quest.id, date(2026, 7, 1), "Archived", session=session)


def test_mark_stale_planned_checkins_failed_updates_only_old_planned_checkins(session):
    today = date(2026, 7, 10)
    old_quest = _create_quest(session, "Old planned")
    boundary_quest = _create_quest(session, "Boundary planned")
    fresh_quest = _create_quest(session, "Fresh planned")
    completed_quest = _create_quest(session, "Completed planned")
    skipped_quest = _create_quest(session, "Skipped planned")
    failed_quest = _create_quest(session, "Failed planned")

    old_checkin = ensure_checkin(old_quest.id, today - timedelta(days=4), session=session)
    boundary_checkin = ensure_checkin(boundary_quest.id, today - timedelta(days=3), session=session)
    fresh_checkin = ensure_checkin(fresh_quest.id, today - timedelta(days=2), session=session)
    completed_checkin = complete_checkin(completed_quest.id, today - timedelta(days=5), session=session)
    skipped_checkin = skip_checkin(skipped_quest.id, today - timedelta(days=5), session=session)
    failed_checkin = fail_checkin(failed_quest.id, today - timedelta(days=5), session=session)

    updated_count = mark_stale_planned_checkins_failed(today, grace_days=3, session=session)

    session.refresh(old_checkin)
    session.refresh(boundary_checkin)
    session.refresh(fresh_checkin)
    session.refresh(completed_checkin)
    session.refresh(skipped_checkin)
    session.refresh(failed_checkin)

    assert updated_count == 2
    assert old_checkin.status == "Failed"
    assert old_checkin.failed_at is not None
    assert boundary_checkin.status == "Failed"
    assert boundary_checkin.failed_at is not None
    assert fresh_checkin.status == "Planned"
    assert completed_checkin.status == "Completed"
    assert skipped_checkin.status == "Skipped"
    assert failed_checkin.status == "Failed"


def test_mark_stale_planned_checkins_failed_is_idempotent(session):
    today = date(2026, 7, 10)
    quest = _create_quest(session)
    ensure_checkin(quest.id, today - timedelta(days=3), session=session)

    first_count = mark_stale_planned_checkins_failed(today, grace_days=3, session=session)
    second_count = mark_stale_planned_checkins_failed(today, grace_days=3, session=session)

    assert first_count == 1
    assert second_count == 0


def test_checkin_service_uses_quest_relationship_and_xp_reward(session):
    quest = _create_quest(session, estimated_minutes=450)

    checkin = complete_checkin(quest.id, date(2026, 7, 1), session=session)

    assert checkin.quest == quest
    assert checkin in quest.checkins
    assert checkin.xp_awarded == 150


def test_get_month_checklist_returns_selected_year_month_and_days(session):
    checklist = get_month_checklist(2026, 2, session=session)

    assert checklist["year"] == 2026
    assert checklist["month"] == 2
    assert checklist["days"] == build_month_days(2026, 2)
    assert checklist["days"][0] == date(2026, 2, 1)
    assert checklist["days"][-1] == date(2026, 2, 28)


def test_get_month_checklist_includes_scheduled_quest_and_creates_planned_checkin(session):
    quest = _create_raw_quest(
        session,
        "Scheduled workout",
        planned_start_at=datetime(2026, 7, 5, 9, 0),
        planned_end_at=datetime(2026, 7, 5, 10, 0),
    )

    checklist = get_month_checklist(2026, 7, session=session)

    assert [row["quest_id"] for row in checklist["rows"]] == [quest.id]
    row = checklist["rows"][0]
    assert row["title"] == "Scheduled workout"
    assert row["category"] == "Health"
    assert row["xp_reward"] == 75
    assert row["estimated_minutes"] == 60

    checkin = session.query(QuestCheckin).filter_by(quest_id=quest.id).one()
    assert checkin.status == "Planned"
    assert checkin.xp_awarded == 0
    assert checkin.checkin_date == date(2026, 7, 5)
    assert row["cells"][date(2026, 7, 5)]["checkin_id"] == checkin.id
    assert row["cells"][date(2026, 7, 5)]["status"] == "Planned"


def test_get_month_checklist_uses_neutral_cells_for_days_without_checkins(session):
    _create_raw_quest(session, "Monthly due quest", due_date=date(2026, 7, 5))

    checklist = get_month_checklist(2026, 7, session=session)
    row = checklist["rows"][0]
    empty_cell = row["cells"][date(2026, 7, 1)]

    assert empty_cell["checkin_id"] is None
    assert empty_cell["status"] is None
    assert empty_cell["xp_awarded"] == 0
    assert empty_cell["completed_at"] is None
    assert empty_cell["skipped_at"] is None
    assert empty_cell["failed_at"] is None


def test_one_time_quest_scheduled_date_is_editable_from_checklist(session):
    quest = _create_raw_quest(session, "Monthly due quest", due_date=date(2026, 7, 5))
    checklist = get_month_checklist(2026, 7, session=session)
    row = checklist["rows"][0]

    updated = update_checklist_cell_status(row, date(2026, 7, 5), "Completed", session=session)

    assert is_checklist_cell_editable(row, date(2026, 7, 5)) is True
    assert updated.quest_id == quest.id
    assert updated.checkin_date == date(2026, 7, 5)
    assert updated.status == "Completed"


def test_one_time_quest_unscheduled_date_is_blocked_from_checklist(session):
    _create_raw_quest(session, "Monthly due quest", due_date=date(2026, 7, 5))
    checklist = get_month_checklist(2026, 7, session=session)
    row = checklist["rows"][0]

    with pytest.raises(ValueError, match="not scheduled"):
        update_checklist_cell_status(row, date(2026, 7, 8), "Completed", session=session)

    assert is_checklist_cell_editable(row, date(2026, 7, 8)) is False
    assert session.query(QuestCheckin).filter_by(checkin_date=date(2026, 7, 8)).count() == 0


def test_neutral_checklist_cell_is_not_editable_and_does_not_create_checkin(session):
    _create_raw_quest(session, "Monthly due quest", due_date=date(2026, 7, 5))
    checklist = get_month_checklist(2026, 7, session=session)
    row = checklist["rows"][0]
    neutral_cell = row["cells"][date(2026, 7, 8)]

    assert neutral_cell["status"] is None
    assert neutral_cell["quest_id"] is None
    assert neutral_cell["checkin_id"] is None
    assert is_checklist_cell_editable(row, date(2026, 7, 8)) is False

    with pytest.raises(ValueError, match="not scheduled"):
        update_checklist_cell_status(row, date(2026, 7, 8), "Skipped", session=session)

    assert session.query(QuestCheckin).filter_by(checkin_date=date(2026, 7, 8)).count() == 0


def test_get_month_checklist_preserves_completed_checkin_status_and_xp(session):
    quest = _create_raw_quest(session, "Completed quest", due_date=date(2026, 7, 6))
    completed_checkin = complete_checkin(quest.id, date(2026, 7, 6), session=session)
    completed_at = completed_checkin.completed_at

    checklist = get_month_checklist(2026, 7, session=session)
    cell = checklist["rows"][0]["cells"][date(2026, 7, 6)]

    assert cell["status"] == "Completed"
    assert cell["xp_awarded"] == quest.xp_reward
    assert cell["completed_at"] == completed_at


def test_get_month_checklist_preserves_skipped_and_failed_checkins(session):
    skipped_quest = _create_raw_quest(session, "Skipped quest", due_date=date(2026, 7, 7))
    failed_quest = _create_raw_quest(session, "Failed quest", due_date=date(2026, 7, 8))
    skipped_checkin = skip_checkin(skipped_quest.id, date(2026, 7, 7), session=session)
    failed_checkin = fail_checkin(failed_quest.id, date(2026, 7, 8), session=session)

    checklist = get_month_checklist(2026, 7, session=session)
    rows_by_quest = {row["quest_id"]: row for row in checklist["rows"]}

    skipped_cell = rows_by_quest[skipped_quest.id]["cells"][date(2026, 7, 7)]
    failed_cell = rows_by_quest[failed_quest.id]["cells"][date(2026, 7, 8)]
    assert skipped_cell["status"] == "Skipped"
    assert skipped_cell["skipped_at"] == skipped_checkin.skipped_at
    assert skipped_cell["xp_awarded"] == 0
    assert failed_cell["status"] == "Failed"
    assert failed_cell["failed_at"] == failed_checkin.failed_at
    assert failed_cell["xp_awarded"] == 0


def test_get_month_checklist_excludes_outside_quests_unless_checkin_is_in_month(session):
    outside_quest = _create_raw_quest(session, "Outside quest", due_date=date(2026, 8, 1))
    checkin_quest = _create_raw_quest(session, "Outside quest with July checkin", due_date=date(2026, 8, 2))
    ensure_checkin(checkin_quest.id, date(2026, 7, 10), session=session)

    checklist = get_month_checklist(2026, 7, session=session)
    row_ids = [row["quest_id"] for row in checklist["rows"]]

    assert outside_quest.id not in row_ids
    assert checkin_quest.id in row_ids


def test_get_month_checklist_does_not_duplicate_quest_matching_due_date_and_start(session):
    quest = _create_raw_quest(
        session,
        "Single row quest",
        due_date=date(2026, 7, 5),
        planned_start_at=datetime(2026, 7, 5, 9, 0),
        planned_end_at=datetime(2026, 7, 5, 10, 0),
    )

    checklist = get_month_checklist(2026, 7, session=session)

    assert [row["quest_id"] for row in checklist["rows"]].count(quest.id) == 1
    assert session.query(QuestCheckin).filter_by(quest_id=quest.id).count() == 1


def test_get_month_checklist_does_not_overwrite_existing_checkins(session):
    quest = _create_raw_quest(session, "Existing checkin quest", due_date=date(2026, 7, 9))
    checkin = complete_checkin(quest.id, date(2026, 7, 9), session=session)
    original_completed_at = checkin.completed_at
    original_xp_awarded = checkin.xp_awarded

    get_month_checklist(2026, 7, session=session)
    session.refresh(checkin)

    assert checkin.status == "Completed"
    assert checkin.completed_at == original_completed_at
    assert checkin.xp_awarded == original_xp_awarded


def test_get_month_checklist_groups_goal_sessions_into_one_goal_row(session):
    category = session.query(Category).one()
    goal = Goal(title="Portfolio Project", category_id=category.id, planned_total_minutes=1200, status="Active")
    session.add(goal)
    session.commit()
    first = create_scheduled_quest(
        "Ignored",
        category_id=category.id,
        goal_id=goal.id,
        planned_date=date(2026, 7, 7),
        start_time=datetime(2026, 7, 7, 9, 0).time(),
        end_time=datetime(2026, 7, 7, 10, 0).time(),
        session=session,
    )
    second = create_scheduled_quest(
        "Ignored",
        category_id=category.id,
        goal_id=goal.id,
        planned_date=date(2026, 7, 9),
        start_time=datetime(2026, 7, 9, 9, 0).time(),
        end_time=datetime(2026, 7, 9, 10, 0).time(),
        session=session,
    )

    checklist = get_month_checklist(2026, 7, session=session)

    assert len(checklist["rows"]) == 1
    row = checklist["rows"][0]
    assert row["row_type"] == "goal"
    assert row["goal_id"] == goal.id
    assert row["quest_id"] is None
    assert row["title"] == "Portfolio Project"
    assert row["cells"][date(2026, 7, 7)]["quest_id"] == first.id
    assert row["cells"][date(2026, 7, 7)]["status"] == "Planned"
    assert row["cells"][date(2026, 7, 9)]["quest_id"] == second.id
    assert row["cells"][date(2026, 7, 9)]["status"] == "Planned"


def test_goal_sessions_on_same_date_remain_separately_editable(session):
    category = session.query(Category).one()
    goal = Goal(title="Portfolio Project", category_id=category.id, planned_total_minutes=1200, status="Active")
    session.add(goal)
    session.commit()
    first = create_scheduled_quest(
        "Ignored",
        category_id=category.id,
        goal_id=goal.id,
        planned_date=date(2026, 7, 7),
        start_time=datetime(2026, 7, 7, 9, 0).time(),
        end_time=datetime(2026, 7, 7, 10, 0).time(),
        session=session,
    )
    second = create_scheduled_quest(
        "Ignored",
        category_id=category.id,
        goal_id=goal.id,
        planned_date=date(2026, 7, 7),
        start_time=datetime(2026, 7, 7, 11, 0).time(),
        end_time=datetime(2026, 7, 7, 12, 0).time(),
        session=session,
    )
    checklist = get_month_checklist(2026, 7, session=session)
    row = checklist["rows"][0]
    cell = row["cells"][date(2026, 7, 7)]

    updated = update_checklist_cell_status(
        row,
        date(2026, 7, 7),
        "Completed",
        quest_id=second.id,
        checkin_id=cell["entries"][1]["checkin_id"],
        session=session,
    )
    first_checkin = session.query(QuestCheckin).filter_by(quest_id=first.id).one()
    second_checkin = session.query(QuestCheckin).filter_by(quest_id=second.id).one()

    assert is_checklist_cell_editable(row, date(2026, 7, 7)) is True
    assert len(cell["entries"]) == 2
    assert updated.quest_id == second.id
    assert first_checkin.status == "Planned"
    assert second_checkin.status == "Completed"


def test_goal_blank_checklist_date_is_locked(session):
    category = session.query(Category).one()
    goal = Goal(title="Portfolio Project", category_id=category.id, planned_total_minutes=1200, status="Active")
    session.add(goal)
    session.commit()
    create_scheduled_quest(
        "Ignored",
        category_id=category.id,
        goal_id=goal.id,
        planned_date=date(2026, 7, 7),
        start_time=datetime(2026, 7, 7, 9, 0).time(),
        end_time=datetime(2026, 7, 7, 10, 0).time(),
        session=session,
    )
    checklist = get_month_checklist(2026, 7, session=session)
    row = checklist["rows"][0]

    with pytest.raises(ValueError, match="not scheduled"):
        update_checklist_cell_status(row, date(2026, 7, 8), "Completed", session=session)

    assert is_checklist_cell_editable(row, date(2026, 7, 8)) is False
    assert session.query(QuestCheckin).filter_by(checkin_date=date(2026, 7, 8)).count() == 0


def test_get_month_checklist_groups_recurring_habit_instances_into_one_row(session):
    habit = _create_recurring_habit(session, weekdays=[0, 2, 4])
    generate_recurring_habit_for_month(habit.id, 2026, 7, session=session)

    checklist = get_month_checklist(2026, 7, session=session)

    assert len(checklist["rows"]) == 1
    row = checklist["rows"][0]
    assert row["row_type"] == "recurring_habit"
    assert row["recurring_habit_id"] == habit.id
    assert row["quest_id"] is None
    assert row["title"] == "Gym Workout"


def test_get_month_checklist_recurring_habit_cells_appear_on_scheduled_dates(session):
    habit = _create_recurring_habit(session, weekdays=[2])
    generate_recurring_habit_for_month(habit.id, 2026, 7, session=session)

    checklist = get_month_checklist(2026, 7, session=session)
    row = checklist["rows"][0]

    assert row["cells"][date(2026, 7, 1)]["status"] == "Planned"
    assert row["cells"][date(2026, 7, 8)]["status"] == "Planned"
    assert row["cells"][date(2026, 7, 1)]["quest_id"] is not None


def test_get_month_checklist_recurring_habit_non_scheduled_dates_are_neutral(session):
    habit = _create_recurring_habit(session, weekdays=[2])
    generate_recurring_habit_for_month(habit.id, 2026, 7, session=session)

    checklist = get_month_checklist(2026, 7, session=session)
    row = checklist["rows"][0]
    neutral_cell = row["cells"][date(2026, 7, 2)]

    assert neutral_cell["status"] is None
    assert neutral_cell["quest_id"] is None
    assert neutral_cell["checkin_id"] is None
    assert session.query(QuestCheckin).filter_by(checkin_date=date(2026, 7, 2)).count() == 0


def test_recurring_generated_date_is_editable_from_checklist(session):
    habit = _create_recurring_habit(session, weekdays=[1])
    generate_recurring_habit_for_month(habit.id, 2026, 7, session=session)
    checklist = get_month_checklist(2026, 7, session=session)
    row = checklist["rows"][0]

    updated = update_checklist_cell_status(row, date(2026, 7, 7), "Completed", session=session)

    assert is_checklist_cell_editable(row, date(2026, 7, 7)) is True
    assert updated.checkin_date == date(2026, 7, 7)
    assert updated.status == "Completed"
    assert updated.xp_awarded == habit.xp_reward


def test_recurring_blank_day_is_blocked_from_checklist(session):
    habit = _create_recurring_habit(session, weekdays=[1])
    generate_recurring_habit_for_month(habit.id, 2026, 7, session=session)
    checklist = get_month_checklist(2026, 7, session=session)
    row = checklist["rows"][0]

    with pytest.raises(ValueError, match="not scheduled"):
        update_checklist_cell_status(row, date(2026, 7, 8), "Completed", session=session)

    assert is_checklist_cell_editable(row, date(2026, 7, 8)) is False
    assert session.query(QuestCheckin).filter_by(checkin_date=date(2026, 7, 8)).count() == 0


def test_completing_recurring_habit_checklist_cell_updates_generated_checkin(session):
    habit = _create_recurring_habit(session, weekdays=[2])
    generate_recurring_habit_for_month(habit.id, 2026, 7, session=session)
    checklist = get_month_checklist(2026, 7, session=session)
    cell = checklist["rows"][0]["cells"][date(2026, 7, 1)]

    completed = complete_checkin(cell["quest_id"], date(2026, 7, 1), session=session)
    refreshed = get_month_checklist(2026, 7, session=session)

    assert completed.status == "Completed"
    assert refreshed["rows"][0]["cells"][date(2026, 7, 1)]["status"] == "Completed"
    assert refreshed["rows"][0]["cells"][date(2026, 7, 1)]["xp_awarded"] == habit.xp_reward


def test_get_month_checklist_rejects_invalid_month(session):
    with pytest.raises(ValueError, match="month must be between 1 and 12"):
        get_month_checklist(2026, 13, session=session)

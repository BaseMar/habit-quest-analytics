from datetime import date, time

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.models import Base, Category, Goal, Quest, QuestCheckin
from src.services.checklist_service import complete_checkin, fail_checkin, reset_checkin, skip_checkin
from src.services.goal_service import (
    archive_goal,
    complete_goal,
    create_goal as service_create_goal,
    delete_goal_if_unused,
    get_goal,
    get_goal_completion_forecast,
    get_goal_history_summary,
    get_goal_progress,
    list_active_goals,
    list_goals,
    reopen_goal,
    update_goal,
)
from src.services.quest_service import create_scheduled_quest


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine)
    session = TestingSession()
    session.add(Category(name="Work", description="Work quests"))
    session.commit()
    try:
        yield session
    finally:
        session.close()


def _create_goal_session(
    session,
    goal: Goal,
    title: str = "Portfolio session",
    planned_date: date = date(2026, 7, 1),
    minutes: int = 120,
) -> Quest:
    category = session.query(Category).one()
    return create_scheduled_quest(
        title=title,
        category_id=category.id,
        goal_id=goal.id,
        planned_date=planned_date,
        start_time=time(9, 0),
        end_time=time(9 + minutes // 60, minutes % 60),
        estimated_minutes=minutes,
        session=session,
    )


def create_goal(*args, **kwargs):
    session = kwargs.get("session")
    if kwargs.get("category_id") is None and session is not None:
        kwargs["category_id"] = session.query(Category).one().id
    return service_create_goal(*args, **kwargs)


def test_create_goal_creates_valid_goal(session):
    category = session.query(Category).one()

    goal = create_goal(
        " Portfolio Project ",
        planned_total_minutes=1200,
        description=" Build a portfolio app ",
        category_id=category.id,
        start_date=date(2026, 7, 1),
        target_end_date=date(2026, 8, 31),
        session=session,
    )

    assert goal.id is not None
    assert goal.title == "Portfolio Project"
    assert goal.description == "Build a portfolio app"
    assert goal.category_id == category.id
    assert goal.planned_total_minutes == 1200
    assert goal.status == "Active"


def test_create_goal_rejects_empty_title(session):
    with pytest.raises(ValueError, match="Goal title is required"):
        create_goal("  ", planned_total_minutes=1200, session=session)


def test_create_goal_allows_unspecified_planned_total_minutes(session):
    goal = create_goal("Portfolio Project", planned_total_minutes=0, session=session)

    assert goal.planned_total_minutes == 0


def test_create_goal_rejects_negative_planned_total_minutes(session):
    with pytest.raises(ValueError, match="planned total minutes cannot be negative"):
        create_goal("Portfolio Project", planned_total_minutes=-1, session=session)


def test_create_goal_rejects_missing_category(session):
    with pytest.raises(ValueError, match="Goal category is required"):
        service_create_goal("Portfolio Project", planned_total_minutes=1200, session=session)


def test_create_goal_rejects_unknown_category(session):
    with pytest.raises(ValueError, match="Category with id 999 was not found"):
        service_create_goal(
            "Portfolio Project",
            planned_total_minutes=1200,
            category_id=999,
            session=session,
        )


def test_create_goal_rejects_invalid_status(session):
    with pytest.raises(ValueError, match="Unknown goal status"):
        create_goal(
            "Portfolio Project",
            planned_total_minutes=1200,
            status="Paused",
            session=session,
        )


def test_create_goal_rejects_target_end_date_before_start_date(session):
    with pytest.raises(ValueError, match="target end date cannot be before start date"):
        create_goal(
            "Portfolio Project",
            planned_total_minutes=1200,
            start_date=date(2026, 8, 31),
            target_end_date=date(2026, 7, 1),
            session=session,
        )


def test_list_goals_returns_created_goals(session):
    first = create_goal("Portfolio Project", planned_total_minutes=1200, session=session)
    second = create_goal("Learning Track", planned_total_minutes=600, session=session)

    goals = list_goals(session=session)

    assert [goal.id for goal in goals] == [second.id, first.id]


def test_list_goals_can_filter_by_status(session):
    active = create_goal("Portfolio Project", planned_total_minutes=1200, session=session)
    archived = create_goal(
        "Old Project",
        planned_total_minutes=300,
        status="Archived",
        session=session,
    )

    goals = list_goals(status="Active", session=session)

    assert goals == [active]
    assert archived not in goals


def test_list_active_goals_returns_only_active_goals(session):
    active = create_goal("Portfolio Project", planned_total_minutes=1200, session=session)
    archived = create_goal(
        "Old Project",
        planned_total_minutes=300,
        status="Archived",
        session=session,
    )

    goals = list_active_goals(session=session)

    assert goals == [active]
    assert archived not in goals


def test_list_active_goals_excludes_completed_goals(session):
    active = create_goal("Portfolio Project", planned_total_minutes=1200, session=session)
    completed = create_goal(
        "Finished Project",
        planned_total_minutes=300,
        status="Completed",
        session=session,
    )

    goals = list_active_goals(session=session)

    assert goals == [active]
    assert completed not in goals


def test_reopened_goal_returns_to_active_goals(session):
    goal = create_goal("Portfolio Project", planned_total_minutes=1200, status="Archived", session=session)
    reopen_goal(goal.id, session=session)

    goals = list_active_goals(session=session)

    assert goals == [goal]


def test_get_goal_returns_correct_goal(session):
    goal = create_goal("Portfolio Project", planned_total_minutes=1200, session=session)

    result = get_goal(goal.id, session=session)

    assert result == goal


def test_update_goal_updates_editable_fields(session):
    category = session.query(Category).one()
    goal = create_goal("Portfolio Project", planned_total_minutes=1200, session=session)

    updated = update_goal(
        goal.id,
        title="Portfolio Website",
        description="Ship a polished portfolio",
        category_id=category.id,
        planned_total_minutes=900,
        start_date=date(2026, 7, 2),
        target_end_date=date(2026, 8, 15),
        status="Completed",
        session=session,
    )

    assert updated.title == "Portfolio Website"
    assert updated.description == "Ship a polished portfolio"
    assert updated.category_id == category.id
    assert updated.planned_total_minutes == 900
    assert updated.start_date == date(2026, 7, 2)
    assert updated.target_end_date == date(2026, 8, 15)
    assert updated.status == "Completed"


def test_update_goal_rejects_invalid_status(session):
    goal = create_goal("Portfolio Project", planned_total_minutes=1200, session=session)

    with pytest.raises(ValueError, match="Unknown goal status"):
        update_goal(goal.id, status="Paused", session=session)


def test_update_goal_rejects_missing_category(session):
    goal = create_goal("Portfolio Project", planned_total_minutes=1200, session=session)

    with pytest.raises(ValueError, match="Goal category is required"):
        update_goal(goal.id, category_id=None, session=session)


def test_archive_goal_sets_status_archived(session):
    goal = create_goal("Portfolio Project", planned_total_minutes=1200, session=session)

    archived = archive_goal(goal.id, session=session)

    assert archived.status == "Archived"


def test_complete_goal_sets_status_completed(session):
    goal = create_goal("Portfolio Project", planned_total_minutes=1200, session=session)

    completed = complete_goal(goal.id, session=session)

    assert completed.status == "Completed"


def test_complete_goal_with_linked_quest_preserves_quest_and_checkin(session):
    goal = create_goal("Portfolio Project", planned_total_minutes=1200, session=session)
    quest = _create_goal_session(session, goal)
    checkin = session.query(QuestCheckin).filter_by(quest_id=quest.id).one()

    completed = complete_goal(goal.id, session=session)

    assert completed.status == "Completed"
    assert session.get(Quest, quest.id) is not None
    assert session.get(QuestCheckin, checkin.id) is not None


def test_reopen_goal_sets_status_active(session):
    goal = create_goal("Portfolio Project", planned_total_minutes=1200, status="Archived", session=session)

    reopened = reopen_goal(goal.id, session=session)

    assert reopened.status == "Active"


def test_delete_goal_if_unused_deletes_goal(session):
    goal = create_goal("Portfolio Project", planned_total_minutes=1200, session=session)

    summary = delete_goal_if_unused(goal.id, session=session)

    assert summary["deleted"] is True
    assert summary["linked_quests_count"] == 0
    assert session.get(Goal, goal.id) is None


def test_delete_goal_if_unused_blocks_goal_with_linked_quest(session):
    goal = create_goal("Portfolio Project", planned_total_minutes=1200, session=session)
    quest = _create_goal_session(session, goal)

    summary = delete_goal_if_unused(goal.id, session=session)

    assert summary["deleted"] is False
    assert summary["linked_quests_count"] == 1
    assert summary["reason"] == "This goal has linked quest sessions and cannot be deleted safely."
    assert session.get(Goal, goal.id) is not None
    assert session.get(Quest, quest.id) is not None


def test_archive_goal_with_linked_quest_preserves_quest_and_checkin(session):
    goal = create_goal("Portfolio Project", planned_total_minutes=1200, session=session)
    quest = _create_goal_session(session, goal)
    checkin = session.query(QuestCheckin).filter_by(quest_id=quest.id).one()

    archived = archive_goal(goal.id, session=session)

    assert archived.status == "Archived"
    assert session.get(Quest, quest.id) is not None
    assert session.get(QuestCheckin, checkin.id) is not None


def test_get_goal_progress_with_no_linked_quests_returns_zero_progress(session):
    goal = create_goal("Portfolio Project", planned_total_minutes=1200, session=session)

    progress = get_goal_progress(goal.id, session=session)

    assert progress == {
        "goal_id": goal.id,
        "title": "Portfolio Project",
        "planned_total_minutes": 1200,
        "completed_minutes": 0,
        "remaining_minutes": 1200,
        "progress_percent": 0,
        "linked_sessions_count": 0,
        "completed_sessions_count": 0,
        "planned_sessions_count": 0,
        "skipped_sessions_count": 0,
        "failed_sessions_count": 0,
        "earned_xp": 0,
        "expected_total_xp": 400,
    }


def test_get_goal_progress_with_unspecified_time_target_is_safe(session):
    goal = create_goal("Open-ended Strength Goal", planned_total_minutes=0, session=session)

    progress = get_goal_progress(goal.id, session=session)

    assert progress["planned_total_minutes"] == 0
    assert progress["completed_minutes"] == 0
    assert progress["remaining_minutes"] == 0
    assert progress["progress_percent"] == 0
    assert progress["expected_total_xp"] == 0


def test_planned_linked_quest_does_not_increase_completed_minutes(session):
    goal = create_goal("Portfolio Project", planned_total_minutes=1200, session=session)
    _create_goal_session(session, goal)

    progress = get_goal_progress(goal.id, session=session)

    assert progress["linked_sessions_count"] == 1
    assert progress["planned_sessions_count"] == 1
    assert progress["completed_minutes"] == 0
    assert progress["earned_xp"] == 0


def test_completed_linked_quest_increases_completed_minutes_and_earned_xp(session):
    goal = create_goal("Portfolio Project", planned_total_minutes=1200, session=session)
    quest = _create_goal_session(session, goal, minutes=120)
    complete_checkin(quest.id, date(2026, 7, 1), session=session)

    progress = get_goal_progress(goal.id, session=session)

    assert progress["completed_sessions_count"] == 1
    assert progress["completed_minutes"] == 120
    assert progress["remaining_minutes"] == 1080
    assert progress["progress_percent"] == 10
    assert progress["earned_xp"] == 40


def test_goal_completion_forecast_uses_completed_planned_effort_and_target_date(session):
    goal = create_goal(
        "Portfolio Project",
        planned_total_minutes=300,
        target_end_date=date(2026, 7, 10),
        session=session,
    )
    first = _create_goal_session(session, goal, minutes=100, planned_date=date(2026, 7, 1))
    second = _create_goal_session(session, goal, minutes=100, planned_date=date(2026, 7, 3))
    complete_checkin(first.id, date(2026, 7, 1), actual_minutes=120, session=session)
    complete_checkin(second.id, date(2026, 7, 3), actual_minutes=80, session=session)

    forecast = get_goal_completion_forecast(goal.id, today=date(2026, 7, 5), session=session)

    assert forecast == {
        "available": True,
        "reason": None,
        "target_end_date": date(2026, 7, 10),
        "projected_completion_date": date(2026, 7, 7),
        "on_track": True,
        "daily_completed_minutes": 40.0,
        "required_daily_minutes": 17,
        "observed_completed_days": 5,
        "remaining_minutes": 100,
    }


def test_goal_completion_forecast_requires_target_effort_date_and_history(session):
    open_ended = create_goal("Open-ended", planned_total_minutes=0, session=session)
    no_target = create_goal("No target", planned_total_minutes=120, session=session)
    target_without_history = create_goal(
        "No history",
        planned_total_minutes=120,
        target_end_date=date(2026, 7, 10),
        session=session,
    )

    assert get_goal_completion_forecast(open_ended.id, session=session)["reason"] == "Set a target effort to forecast this project."
    assert get_goal_completion_forecast(no_target.id, session=session)["reason"] == "Set a target date to forecast this project."
    assert get_goal_completion_forecast(target_without_history.id, session=session)["reason"] == (
        "Complete at least one project session to calculate a forecast."
    )


@pytest.mark.parametrize(
    ("action", "status_key"),
    [
        (skip_checkin, "skipped_sessions_count"),
        (fail_checkin, "failed_sessions_count"),
    ],
)
def test_skipped_or_failed_linked_quest_does_not_increase_completed_minutes(session, action, status_key):
    goal = create_goal("Portfolio Project", planned_total_minutes=1200, session=session)
    quest = _create_goal_session(session, goal)
    action(quest.id, date(2026, 7, 1), session=session)

    progress = get_goal_progress(goal.id, session=session)

    assert progress[status_key] == 1
    assert progress["completed_minutes"] == 0
    assert progress["earned_xp"] == 0


def test_reset_linked_checkin_removes_completed_contribution(session):
    goal = create_goal("Portfolio Project", planned_total_minutes=1200, session=session)
    quest = _create_goal_session(session, goal, minutes=120)
    complete_checkin(quest.id, date(2026, 7, 1), session=session)
    reset_checkin(quest.id, date(2026, 7, 1), session=session)

    progress = get_goal_progress(goal.id, session=session)

    assert progress["completed_sessions_count"] == 0
    assert progress["planned_sessions_count"] == 1
    assert progress["completed_minutes"] == 0
    assert progress["earned_xp"] == 0


def test_goal_progress_percent_is_capped_and_remaining_minutes_not_negative(session):
    goal = create_goal("Tiny Goal", planned_total_minutes=60, session=session)
    quest = _create_goal_session(session, goal, minutes=120)
    complete_checkin(quest.id, date(2026, 7, 1), session=session)

    progress = get_goal_progress(goal.id, session=session)

    assert progress["completed_minutes"] == 120
    assert progress["remaining_minutes"] == 0
    assert progress["progress_percent"] == 100


def test_goal_history_summary_counts_linked_sessions(session):
    goal = create_goal("Portfolio Project", planned_total_minutes=1200, session=session)
    planned = _create_goal_session(session, goal, title="Planned", planned_date=date(2026, 7, 1))
    completed = _create_goal_session(session, goal, title="Completed", planned_date=date(2026, 7, 2))
    skipped = _create_goal_session(session, goal, title="Skipped", planned_date=date(2026, 7, 3))
    failed = _create_goal_session(session, goal, title="Failed", planned_date=date(2026, 7, 4))
    complete_checkin(completed.id, date(2026, 7, 2), session=session)
    skip_checkin(skipped.id, date(2026, 7, 3), session=session)
    fail_checkin(failed.id, date(2026, 7, 4), session=session)

    summary = get_goal_history_summary(goal.id, session=session)

    assert planned.goal_id == goal.id
    assert summary == {
        "goal_id": goal.id,
        "linked_quests_count": 4,
        "completed_sessions_count": 1,
        "planned_sessions_count": 1,
        "skipped_sessions_count": 1,
        "failed_sessions_count": 1,
        "earned_xp": 40,
    }


def test_goal_progress_remains_available_after_archive_complete_and_reopen(session):
    goal = create_goal("Portfolio Project", planned_total_minutes=1200, session=session)
    quest = _create_goal_session(session, goal, minutes=120)
    complete_checkin(quest.id, date(2026, 7, 1), session=session)

    archive_goal(goal.id, session=session)
    archived_progress = get_goal_progress(goal.id, session=session)
    complete_goal(goal.id, session=session)
    completed_progress = get_goal_progress(goal.id, session=session)
    reopen_goal(goal.id, session=session)
    reopened_progress = get_goal_progress(goal.id, session=session)

    assert archived_progress["completed_minutes"] == 120
    assert completed_progress["earned_xp"] == 40
    assert reopened_progress["completed_sessions_count"] == 1

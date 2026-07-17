from datetime import date, datetime, time, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.models import Base, Category, Goal, Quest, QuestCheckin
from src.services.checklist_service import complete_checkin, fail_checkin, skip_checkin
from src.services.goal_session_planner_service import (
    build_goal_session_plan_preview,
    get_goal_session_planning_summary,
    plan_goal_sessions,
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


def _category(session) -> Category:
    return session.query(Category).one()


def _add_goal(
    session,
    planned_total_minutes: int = 1200,
    status: str = "Active",
    target_end_date: date | None = None,
) -> Goal:
    goal = Goal(
        title="Portfolio Project",
        category_id=_category(session).id,
        planned_total_minutes=planned_total_minutes,
        status=status,
        target_end_date=target_end_date,
    )
    session.add(goal)
    session.commit()
    return goal


def _time_after(start: time, minutes: int) -> time:
    return (datetime.combine(date(2026, 7, 1), start) + timedelta(minutes=minutes)).time()


def _add_goal_session(
    session,
    goal: Goal,
    planned_date: date = date(2026, 7, 1),
    minutes: int = 120,
    start_time: time = time(9, 0),
) -> Quest:
    return create_scheduled_quest(
        title="Ignored",
        category_id=_category(session).id,
        goal_id=goal.id,
        planned_date=planned_date,
        start_time=start_time,
        end_time=_time_after(start_time, minutes),
        estimated_minutes=minutes,
        session=session,
    )


def test_planning_summary_with_no_existing_sessions(session):
    goal = _add_goal(session, planned_total_minutes=1200)

    summary = get_goal_session_planning_summary(goal.id, session_duration_minutes=120, session=session)

    assert summary["planned_total_minutes"] == 1200
    assert summary["completed_minutes"] == 0
    assert summary["currently_planned_minutes"] == 0
    assert summary["effort_to_schedule_minutes"] == 1200
    assert summary["suggested_sessions_count"] == 10


def test_completed_effort_reduces_effort_to_schedule(session):
    goal = _add_goal(session, planned_total_minutes=1200)
    quest = _add_goal_session(session, goal, minutes=120)
    complete_checkin(quest.id, date(2026, 7, 1), session=session)

    summary = get_goal_session_planning_summary(goal.id, session_duration_minutes=120, session=session)

    assert summary["completed_minutes"] == 120
    assert summary["effort_to_schedule_minutes"] == 1080


def test_planned_effort_reduces_effort_to_schedule(session):
    goal = _add_goal(session, planned_total_minutes=1200)
    _add_goal_session(session, goal, minutes=240)

    summary = get_goal_session_planning_summary(goal.id, session_duration_minutes=120, session=session)

    assert summary["currently_planned_minutes"] == 240
    assert summary["effort_to_schedule_minutes"] == 960


def test_failed_effort_does_not_reduce_effort_to_schedule(session):
    goal = _add_goal(session, planned_total_minutes=1200)
    quest = _add_goal_session(session, goal, minutes=120)
    fail_checkin(quest.id, date(2026, 7, 1), session=session)

    summary = get_goal_session_planning_summary(goal.id, session_duration_minutes=120, session=session)

    assert summary["failed_minutes"] == 120
    assert summary["effort_to_schedule_minutes"] == 1200


def test_skipped_effort_does_not_reduce_effort_to_schedule(session):
    goal = _add_goal(session, planned_total_minutes=1200)
    quest = _add_goal_session(session, goal, minutes=120)
    skip_checkin(quest.id, date(2026, 7, 1), session=session)

    summary = get_goal_session_planning_summary(goal.id, session_duration_minutes=120, session=session)

    assert summary["skipped_minutes"] == 120
    assert summary["effort_to_schedule_minutes"] == 1200


def test_effort_to_schedule_never_goes_below_zero(session):
    goal = _add_goal(session, planned_total_minutes=60)
    quest = _add_goal_session(session, goal, minutes=120)
    complete_checkin(quest.id, date(2026, 7, 1), session=session)

    summary = get_goal_session_planning_summary(goal.id, session_duration_minutes=120, session=session)

    assert summary["completed_minutes"] == 120
    assert summary["effort_to_schedule_minutes"] == 0
    assert summary["suggested_sessions_count"] == 0


def test_preview_does_not_create_database_records(session):
    goal = _add_goal(session, planned_total_minutes=1200)

    preview = build_goal_session_plan_preview(
        goal.id,
        session_duration_minutes=120,
        start_date=date(2026, 7, 13),
        selected_weekdays=[0, 2, 4],
        planned_start_time=time(18, 0),
        session=session,
    )

    assert preview["total_sessions"] == 10
    assert session.query(Quest).count() == 0
    assert session.query(QuestCheckin).count() == 0


def test_20h_goal_with_2h_duration_produces_10_sessions(session):
    goal = _add_goal(session, planned_total_minutes=1200)

    summary = plan_goal_sessions(
        goal.id,
        session_duration_minutes=120,
        start_date=date(2026, 7, 13),
        selected_weekdays=[0, 2, 4],
        planned_start_time=time(18, 0),
        session=session,
    )

    assert summary["created_count"] == 10
    assert summary["total_planned_minutes"] == 1200
    assert summary["remaining_unallocated_minutes"] == 0


def test_partial_final_session_is_generated_correctly(session):
    goal = _add_goal(session, planned_total_minutes=290)

    preview = build_goal_session_plan_preview(
        goal.id,
        session_duration_minutes=120,
        start_date=date(2026, 7, 13),
        selected_weekdays=[0, 1, 2],
        planned_start_time=time(9, 0),
        session=session,
    )

    assert [row["duration_minutes"] for row in preview["sessions"]] == [120, 120, 50]
    assert preview["fully_covers_effort"] is True


def test_partial_final_session_can_be_disabled(session):
    goal = _add_goal(session, planned_total_minutes=290)

    summary = plan_goal_sessions(
        goal.id,
        session_duration_minutes=120,
        start_date=date(2026, 7, 13),
        selected_weekdays=[0, 1, 2],
        planned_start_time=time(9, 0),
        allow_short_final_session=False,
        session=session,
    )

    assert summary["created_count"] == 2
    assert summary["total_planned_minutes"] == 240
    assert summary["remaining_unallocated_minutes"] == 50


def test_titles_and_session_numbers_are_generated_correctly(session):
    goal = _add_goal(session, planned_total_minutes=240)

    summary = plan_goal_sessions(
        goal.id,
        session_duration_minutes=120,
        start_date=date(2026, 7, 13),
        selected_weekdays=[0, 1],
        planned_start_time=time(9, 0),
        session=session,
    )
    quests = session.query(Quest).order_by(Quest.goal_session_number).all()

    assert summary["created_session_numbers"] == [1, 2]
    assert [quest.title for quest in quests] == [
        "Portfolio Project Session 1",
        "Portfolio Project Session 2",
    ]


def test_existing_maximum_session_number_is_respected(session):
    goal = _add_goal(session, planned_total_minutes=360)
    existing = _add_goal_session(session, goal, minutes=120)
    existing.goal_session_number = 7
    existing.title = "Portfolio Project Session 7"
    session.commit()

    summary = plan_goal_sessions(
        goal.id,
        session_duration_minutes=120,
        start_date=date(2026, 7, 13),
        selected_weekdays=[0, 1],
        planned_start_time=time(9, 0),
        session=session,
    )

    assert summary["created_session_numbers"] == [8, 9]


def test_eligible_weekdays_are_respected(session):
    goal = _add_goal(session, planned_total_minutes=360)

    preview = build_goal_session_plan_preview(
        goal.id,
        session_duration_minutes=120,
        start_date=date(2026, 7, 13),
        selected_weekdays=[0, 2, 4],
        planned_start_time=time(18, 0),
        session=session,
    )

    assert [row["date"].weekday() for row in preview["sessions"]] == [0, 2, 4]
    assert [row["date"] for row in preview["sessions"]] == [
        date(2026, 7, 13),
        date(2026, 7, 15),
        date(2026, 7, 17),
    ]


def test_goal_target_date_is_respected(session):
    goal = _add_goal(session, planned_total_minutes=360, target_end_date=date(2026, 7, 17))

    preview = build_goal_session_plan_preview(
        goal.id,
        session_duration_minutes=120,
        start_date=date(2026, 7, 13),
        selected_weekdays=[0, 2, 4],
        planned_start_time=time(18, 0),
        session=session,
    )

    assert preview["date_range_complete"] is True
    assert preview["sessions"][-1]["date"] == date(2026, 7, 17)


def test_planner_target_date_cannot_exceed_goal_target_date(session):
    goal = _add_goal(session, planned_total_minutes=120, target_end_date=date(2026, 7, 17))

    with pytest.raises(ValueError, match="cannot be after the goal target date"):
        build_goal_session_plan_preview(
            goal.id,
            session_duration_minutes=120,
            start_date=date(2026, 7, 13),
            selected_weekdays=[0],
            planned_start_time=time(18, 0),
            target_end_date=date(2026, 7, 20),
            session=session,
        )


def test_incomplete_date_range_is_rejected_safely(session):
    goal = _add_goal(session, planned_total_minutes=360)
    preview = build_goal_session_plan_preview(
        goal.id,
        session_duration_minutes=120,
        start_date=date(2026, 7, 13),
        selected_weekdays=[0],
        planned_start_time=time(18, 0),
        target_end_date=date(2026, 7, 20),
        session=session,
    )

    assert preview["date_range_complete"] is False
    assert preview["total_sessions"] == 2
    with pytest.raises(ValueError, match="Not enough eligible dates"):
        plan_goal_sessions(
            goal.id,
            session_duration_minutes=120,
            start_date=date(2026, 7, 13),
            selected_weekdays=[0],
            planned_start_time=time(18, 0),
            target_end_date=date(2026, 7, 20),
            session=session,
        )
    assert session.query(Quest).count() == 0
    assert session.query(QuestCheckin).count() == 0


@pytest.mark.parametrize("status", ["Archived", "Completed"])
def test_non_active_goal_cannot_generate_sessions(session, status):
    goal = _add_goal(session, planned_total_minutes=120, status=status)

    with pytest.raises(ValueError, match="Only active goals can use the session planner"):
        plan_goal_sessions(
            goal.id,
            session_duration_minutes=120,
            start_date=date(2026, 7, 13),
            selected_weekdays=[0],
            planned_start_time=time(18, 0),
            session=session,
        )


@pytest.mark.parametrize("duration", [0, -30])
def test_invalid_or_zero_duration_is_rejected(session, duration):
    goal = _add_goal(session, planned_total_minutes=120)

    with pytest.raises(ValueError, match="Session duration must be greater than 0"):
        build_goal_session_plan_preview(
            goal.id,
            session_duration_minutes=duration,
            start_date=date(2026, 7, 13),
            selected_weekdays=[0],
            planned_start_time=time(18, 0),
            session=session,
        )


def test_sessions_crossing_midnight_are_rejected(session):
    goal = _add_goal(session, planned_total_minutes=120)

    with pytest.raises(ValueError, match="cannot cross midnight"):
        build_goal_session_plan_preview(
            goal.id,
            session_duration_minutes=120,
            start_date=date(2026, 7, 13),
            selected_weekdays=[0],
            planned_start_time=time(23, 0),
            session=session,
        )


def test_every_generated_quest_has_goal_id_and_one_planned_checkin(session):
    goal = _add_goal(session, planned_total_minutes=240)

    plan_goal_sessions(
        goal.id,
        session_duration_minutes=120,
        start_date=date(2026, 7, 13),
        selected_weekdays=[0, 1],
        planned_start_time=time(18, 0),
        session=session,
    )
    quests = session.query(Quest).order_by(Quest.id).all()

    assert [quest.goal_id for quest in quests] == [goal.id, goal.id]
    for quest in quests:
        checkins = session.query(QuestCheckin).filter_by(quest_id=quest.id).all()
        assert len(checkins) == 1
        assert checkins[0].status == "Planned"
        assert checkins[0].xp_awarded == 0


def test_no_xp_is_awarded_during_planning(session):
    goal = _add_goal(session, planned_total_minutes=120)

    plan_goal_sessions(
        goal.id,
        session_duration_minutes=120,
        start_date=date(2026, 7, 13),
        selected_weekdays=[0],
        planned_start_time=time(18, 0),
        session=session,
    )

    assert session.query(QuestCheckin).one().xp_awarded == 0


def test_repeating_generation_does_not_over_allocate_already_planned_effort(session):
    goal = _add_goal(session, planned_total_minutes=240)

    first = plan_goal_sessions(
        goal.id,
        session_duration_minutes=120,
        start_date=date(2026, 7, 13),
        selected_weekdays=[0, 1],
        planned_start_time=time(18, 0),
        session=session,
    )
    second = plan_goal_sessions(
        goal.id,
        session_duration_minutes=120,
        start_date=date(2026, 7, 13),
        selected_weekdays=[0, 1],
        planned_start_time=time(18, 0),
        session=session,
    )

    assert first["created_count"] == 2
    assert second["created_count"] == 0
    assert session.query(Quest).count() == 2
    assert second["planning_summary"]["effort_to_schedule_minutes"] == 0

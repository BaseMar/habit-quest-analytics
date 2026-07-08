from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.models import Base, Category, Goal
from src.services.goal_service import (
    archive_goal,
    complete_goal,
    create_goal,
    delete_goal_if_unused,
    get_goal,
    get_goal_progress,
    list_goals,
    reopen_goal,
    update_goal,
)


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


@pytest.mark.parametrize("planned_total_minutes", [0, -1])
def test_create_goal_rejects_non_positive_planned_total_minutes(session, planned_total_minutes):
    with pytest.raises(ValueError, match="planned total minutes must be positive"):
        create_goal("Portfolio Project", planned_total_minutes=planned_total_minutes, session=session)


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


def test_archive_goal_sets_status_archived(session):
    goal = create_goal("Portfolio Project", planned_total_minutes=1200, session=session)

    archived = archive_goal(goal.id, session=session)

    assert archived.status == "Archived"


def test_complete_goal_sets_status_completed(session):
    goal = create_goal("Portfolio Project", planned_total_minutes=1200, session=session)

    completed = complete_goal(goal.id, session=session)

    assert completed.status == "Completed"


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


def test_get_goal_progress_returns_placeholder_until_quests_are_linked(session):
    goal = create_goal("Portfolio Project", planned_total_minutes=1200, session=session)

    progress = get_goal_progress(goal.id, session=session)

    assert progress == {
        "goal_id": goal.id,
        "planned_total_minutes": 1200,
        "completed_minutes": 0,
        "remaining_minutes": 1200,
        "progress_percent": 0,
        "earned_xp": 0,
    }

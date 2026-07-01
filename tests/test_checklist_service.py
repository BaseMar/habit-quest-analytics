from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.models import Base, Category, QuestCheckin
from src.services.checklist_service import (
    complete_checkin,
    ensure_checkin,
    fail_checkin,
    mark_stale_planned_checkins_failed,
    reset_checkin,
    skip_checkin,
    update_checkin_status,
)
from src.services.quest_service import create_quest


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


def _create_quest(session, title: str = "Morning workout", xp_difficulty: str = "Hard"):
    category = session.query(Category).one()
    return create_quest(
        title,
        category_id=category.id,
        difficulty=xp_difficulty,
        planned_date=date(2026, 7, 1),
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
    quest = _create_quest(session, xp_difficulty="Boss")

    checkin = complete_checkin(quest.id, date(2026, 7, 1), session=session)

    assert checkin.quest == quest
    assert checkin in quest.checkins
    assert checkin.xp_awarded == 150

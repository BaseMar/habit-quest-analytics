from datetime import date, datetime, time

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.models import Base, Category, QuestCheckin
from src.services.checklist_service import (
    complete_checkin,
    ensure_checkin,
    fail_checkin,
    reset_checkin,
    skip_checkin,
)
from src.services.quest_service import (
    create_quest,
    create_scheduled_quest,
    get_all_quests,
    get_quests_by_date,
    get_quests_for_calendar,
    get_quests_for_day,
    quest_to_calendar_event,
    update_quest_status,
    validate_schedule_times,
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


def test_create_quest_persists_xp_reward_and_details(session):
    category = session.query(Category).one()

    quest = create_quest(
        title="Morning workout",
        description="Complete strength training",
        category_id=category.id,
        difficulty="Hard",
        planned_date=date(2026, 6, 26),
        estimated_minutes=45,
        session=session,
    )

    assert quest.id is not None
    assert quest.title == "Morning workout"
    assert quest.status == "Planned"
    assert quest.xp_reward == 75
    assert quest.due_date == date(2026, 6, 26)
    assert quest.estimated_minutes == 45


def test_create_scheduled_quest_sets_planned_datetimes_and_duration(session):
    category = session.query(Category).one()

    quest = create_scheduled_quest(
        title="Morning workout",
        description="Complete strength training",
        category_id=category.id,
        difficulty="Medium",
        planned_date=date(2026, 6, 26),
        start_time=time(9, 0),
        end_time=time(11, 0),
        session=session,
    )

    assert quest.status == "Planned"
    assert quest.xp_reward == 30
    assert quest.due_date == date(2026, 6, 26)
    assert quest.planned_start_at == datetime(2026, 6, 26, 9, 0)
    assert quest.planned_end_at == datetime(2026, 6, 26, 11, 0)
    assert quest.estimated_minutes == 120


def test_create_scheduled_quest_creates_planned_checkin(session):
    category = session.query(Category).one()

    quest = create_scheduled_quest(
        title="Morning workout",
        category_id=category.id,
        difficulty="Hard",
        planned_date=date(2026, 6, 26),
        start_time=time(9, 0),
        end_time=time(10, 0),
        session=session,
    )

    checkin = session.query(QuestCheckin).filter_by(quest_id=quest.id).one()

    assert checkin.status == "Planned"
    assert checkin.xp_awarded == 0
    assert checkin.checkin_date == date(2026, 6, 26)


def test_create_scheduled_quest_checkin_is_not_duplicated_by_ensure_checkin(session):
    category = session.query(Category).one()
    quest = create_scheduled_quest(
        title="Morning workout",
        category_id=category.id,
        planned_date=date(2026, 6, 26),
        start_time=time(9, 0),
        end_time=time(10, 0),
        session=session,
    )

    existing_checkin = session.query(QuestCheckin).filter_by(quest_id=quest.id).one()
    ensured_checkin = ensure_checkin(quest.id, date(2026, 6, 26), session=session)

    assert ensured_checkin.id == existing_checkin.id
    assert session.query(QuestCheckin).filter_by(quest_id=quest.id).count() == 1


def test_validate_schedule_times_rejects_end_before_start():
    with pytest.raises(ValueError, match="End time must be after start time"):
        validate_schedule_times(date(2026, 6, 26), time(11, 0), time(10, 0))


def test_get_all_quests_returns_created_quests(session):
    category = session.query(Category).one()
    create_quest("Read", category_id=category.id, difficulty="Easy", session=session)

    quests = get_all_quests(session=session)

    assert len(quests) == 1
    assert quests[0].title == "Read"
    assert quests[0].category.name == "Health"


def test_get_quests_by_date_filters_by_planned_date(session):
    category = session.query(Category).one()
    target_date = date(2026, 6, 26)
    create_quest("Target day", category_id=category.id, planned_date=target_date, session=session)
    create_quest("Other day", category_id=category.id, planned_date=date(2026, 6, 27), session=session)

    quests = get_quests_by_date(target_date, session=session)

    assert [quest.title for quest in quests] == ["Target day"]


def test_get_quests_for_day_sorts_by_start_time_then_created_at(session):
    category = session.query(Category).one()
    target_date = date(2026, 6, 26)
    legacy = create_quest("Legacy task", category_id=category.id, planned_date=target_date, session=session)
    later = create_scheduled_quest(
        "Later task",
        category_id=category.id,
        planned_date=target_date,
        start_time=time(15, 0),
        end_time=time(16, 0),
        session=session,
    )
    earlier = create_scheduled_quest(
        "Earlier task",
        category_id=category.id,
        planned_date=target_date,
        start_time=time(9, 0),
        end_time=time(10, 0),
        session=session,
    )
    create_scheduled_quest(
        "Other day",
        category_id=category.id,
        planned_date=date(2026, 6, 27),
        start_time=time(8, 0),
        end_time=time(9, 0),
        session=session,
    )

    quests = get_quests_for_day(target_date, session=session)

    assert [quest.title for quest in quests] == [earlier.title, later.title, legacy.title]


def test_get_quests_for_day_uses_checkin_status_for_selected_date(session):
    category = session.query(Category).one()
    quest = create_scheduled_quest(
        "Workout",
        category_id=category.id,
        planned_date=date(2026, 6, 26),
        start_time=time(9, 0),
        end_time=time(10, 0),
        session=session,
    )
    complete_checkin(quest.id, date(2026, 6, 26), session=session)

    quests = get_quests_for_day(date(2026, 6, 26), session=session)

    assert quests[0].status == "Planned"
    assert quests[0].display_status == "Completed"


@pytest.mark.parametrize(
    ("action", "expected_status"),
    [
        (skip_checkin, "Skipped"),
        (fail_checkin, "Failed"),
    ],
)
def test_get_quests_for_day_displays_skipped_and_failed_checkin_statuses(session, action, expected_status):
    category = session.query(Category).one()
    quest = create_scheduled_quest(
        "Workout",
        category_id=category.id,
        planned_date=date(2026, 6, 26),
        start_time=time(9, 0),
        end_time=time(10, 0),
        session=session,
    )
    action(quest.id, date(2026, 6, 26), session=session)

    quests = get_quests_for_day(date(2026, 6, 26), session=session)

    assert quests[0].display_status == expected_status


def test_get_quests_for_day_displays_planned_after_checkin_reset(session):
    category = session.query(Category).one()
    quest = create_scheduled_quest(
        "Workout",
        category_id=category.id,
        planned_date=date(2026, 6, 26),
        start_time=time(9, 0),
        end_time=time(10, 0),
        session=session,
    )
    complete_checkin(quest.id, date(2026, 6, 26), session=session)
    reset_checkin(quest.id, date(2026, 6, 26), session=session)

    quests = get_quests_for_day(date(2026, 6, 26), session=session)

    assert quests[0].display_status == "Planned"


def test_get_quests_for_day_includes_quest_with_checkin_on_selected_date(session):
    category = session.query(Category).one()
    quest = create_scheduled_quest(
        "Workout",
        category_id=category.id,
        planned_date=date(2026, 6, 26),
        start_time=time(9, 0),
        end_time=time(10, 0),
        session=session,
    )
    complete_checkin(quest.id, date(2026, 6, 27), session=session)

    quests = get_quests_for_day(date(2026, 6, 27), session=session)

    assert [day_quest.title for day_quest in quests] == ["Workout"]
    assert quests[0].display_status == "Completed"


def test_get_quests_for_calendar_returns_event_dicts(session):
    category = session.query(Category).one()
    create_scheduled_quest(
        "SQL study",
        category_id=category.id,
        difficulty="Hard",
        planned_date=date(2026, 6, 26),
        start_time=time(11, 30),
        end_time=time(13, 0),
        session=session,
    )

    events = get_quests_for_calendar(session=session)

    assert events == [
        {
            "id": "1",
            "title": "SQL study",
            "start": "2026-06-26T11:30:00",
            "end": "2026-06-26T13:00:00",
            "status": "Planned",
            "category": "Health",
            "difficulty": "Hard",
            "xp_reward": 75,
            "color": "#38bdf8",
            "backgroundColor": "#38bdf8",
            "borderColor": "#38bdf8",
            "extendedProps": {
                "status": "Planned",
                "category": "Health",
                "difficulty": "Hard",
                "xp_reward": 75,
            },
        }
    ]


def test_get_quests_for_calendar_uses_checkin_status_and_color(session):
    category = session.query(Category).one()
    quest = create_scheduled_quest(
        "SQL study",
        category_id=category.id,
        difficulty="Hard",
        planned_date=date(2026, 6, 26),
        start_time=time(11, 30),
        end_time=time(13, 0),
        session=session,
    )
    complete_checkin(quest.id, date(2026, 6, 26), session=session)

    events = get_quests_for_calendar(session=session)

    assert quest.status == "Planned"
    assert events[0]["status"] == "Completed"
    assert events[0]["extendedProps"]["status"] == "Completed"
    assert events[0]["color"] == "#22c55e"
    assert events[0]["backgroundColor"] == "#22c55e"
    assert events[0]["borderColor"] == "#22c55e"


def test_get_quests_for_calendar_falls_back_to_quest_status_without_checkin(session):
    category = session.query(Category).one()
    quest = create_quest(
        "Legacy planned task",
        category_id=category.id,
        planned_date=date(2026, 6, 26),
        session=session,
    )
    update_quest_status(quest.id, "Failed", session=session)

    events = get_quests_for_calendar(session=session)

    assert session.query(QuestCheckin).filter_by(quest_id=quest.id).count() == 0
    assert events[0]["status"] == "Failed"
    assert events[0]["color"] == "#ef4444"


def test_reading_calendar_and_day_schedule_does_not_duplicate_checkins(session):
    category = session.query(Category).one()
    quest = create_scheduled_quest(
        "SQL study",
        category_id=category.id,
        planned_date=date(2026, 6, 26),
        start_time=time(11, 30),
        end_time=time(13, 0),
        session=session,
    )

    get_quests_for_calendar(session=session)
    get_quests_for_calendar(session=session)
    get_quests_for_day(date(2026, 6, 26), session=session)
    get_quests_for_day(date(2026, 6, 26), session=session)

    assert session.query(QuestCheckin).filter_by(quest_id=quest.id).count() == 1


def test_quest_to_calendar_event_supports_legacy_planned_date(session):
    category = session.query(Category).one()
    quest = create_quest(
        "Legacy planned task",
        category_id=category.id,
        planned_date=date(2026, 6, 26),
        session=session,
    )

    event = quest_to_calendar_event(quest)

    assert event["start"] == "2026-06-26"
    assert event["end"] is None
    assert event["allDay"] is True
    assert event["status"] == "Planned"
    assert event["category"] == "Health"


def test_update_quest_status_sets_completed_at_once(session):
    category = session.query(Category).one()
    quest = create_quest("Finish report", category_id=category.id, session=session)

    completed = update_quest_status(quest.id, "Completed", session=session)
    first_completed_at = completed.completed_at
    completed_again = update_quest_status(quest.id, "Completed", session=session)

    assert completed.status == "Completed"
    assert first_completed_at is not None
    assert completed_again.completed_at == first_completed_at
    assert completed_again.xp_reward == 10


def test_update_quest_status_rejects_unknown_status(session):
    category = session.query(Category).one()
    quest = create_quest("Stretch", category_id=category.id, session=session)

    with pytest.raises(ValueError):
        update_quest_status(quest.id, "Archived", session=session)

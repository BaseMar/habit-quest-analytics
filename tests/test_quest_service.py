from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.models import Base, Category
from src.services.quest_service import (
    create_quest,
    get_all_quests,
    get_quests_by_date,
    update_quest_status,
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

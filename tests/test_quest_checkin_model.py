from datetime import date

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from src.database.models import Base, Category, Quest, QuestCheckin


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


def _create_quest(session) -> Quest:
    category = session.query(Category).one()
    quest = Quest(
        title="Morning workout",
        status="Planned",
        xp_reward=75,
        due_date=date(2026, 7, 1),
        category_id=category.id,
    )
    session.add(quest)
    session.commit()
    session.refresh(quest)
    return quest


def test_quest_checkins_table_exists():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)

    inspector = inspect(engine)

    assert "quest_checkins" in inspector.get_table_names()


def test_quest_checkin_can_be_created_for_existing_quest(session):
    quest = _create_quest(session)
    checkin = QuestCheckin(quest_id=quest.id, checkin_date=date(2026, 7, 1))

    session.add(checkin)
    session.commit()
    session.refresh(checkin)

    assert checkin.id is not None
    assert checkin.quest_id == quest.id
    assert checkin.checkin_date == date(2026, 7, 1)


def test_quest_checkin_relationships_work(session):
    quest = _create_quest(session)
    checkin = QuestCheckin(quest_id=quest.id, checkin_date=date(2026, 7, 1))
    session.add(checkin)
    session.commit()
    session.refresh(quest)
    session.refresh(checkin)

    assert quest.checkins == [checkin]
    assert checkin.quest == quest


def test_quest_checkin_unique_constraint_prevents_duplicate_quest_date(session):
    quest = _create_quest(session)
    session.add(QuestCheckin(quest_id=quest.id, checkin_date=date(2026, 7, 1)))
    session.commit()

    session.add(QuestCheckin(quest_id=quest.id, checkin_date=date(2026, 7, 1)))

    with pytest.raises(IntegrityError):
        session.commit()


def test_quest_checkin_defaults_and_nullable_timestamps(session):
    quest = _create_quest(session)
    checkin = QuestCheckin(quest_id=quest.id, checkin_date=date(2026, 7, 1))

    session.add(checkin)
    session.commit()
    session.refresh(checkin)

    assert checkin.status == "Planned"
    assert checkin.xp_awarded == 0
    assert checkin.completed_at is None
    assert checkin.skipped_at is None
    assert checkin.failed_at is None
    assert checkin.created_at is not None
    assert checkin.updated_at is not None

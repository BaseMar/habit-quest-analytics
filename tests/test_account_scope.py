from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.database import db
from src.database.models import Base, Category, Goal, Quest, QuestCheckin, UserAccount
from src.database.user_session import UserSession
from src.services.account_service import register_google_account
from src.services.analytics_service import get_character_profile_data, get_habit_analytics_data
from src.services.checklist_service import update_checkin_status
from src.services.goal_service import create_goal, delete_goal
from src.services.profile_service import remove_avatar, save_avatar
from src.services.quest_service import create_quest, get_all_quests, get_categories
from src.services.recurring_habit_service import create_recurring_habit, generate_recurring_habit_for_month


@pytest.fixture
def accounts(monkeypatch):
    engine = create_engine("sqlite://")

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    monkeypatch.setattr(db, "engine", engine)
    try:
        yield engine
    finally:
        engine.dispose()


def test_google_account_uses_its_subject_and_provisions_defaults_once(accounts):
    user_id = register_google_account("first-subject", "first@example.com")
    assert register_google_account("first-subject", "changed@example.com") == user_id
    second_id = register_google_account("second-subject", "first@example.com")
    assert second_id != user_id

    with Session(accounts) as session:
        assert session.get(UserAccount, user_id).email == "changed@example.com"
    with UserSession(bind=accounts, user_id=user_id) as session:
        assert len(get_categories(session=session)) == 5
        assert get_character_profile_data(session=session)["total_xp"] == 0


def test_personal_queries_and_writes_stay_in_the_signed_in_account(accounts, tmp_path):
    first_id = register_google_account("one", "one@example.com")
    second_id = register_google_account("two", "two@example.com")
    today = date(2026, 11, 23)
    with Session(accounts) as admin:
        admin.add(Quest(title="Unassigned legacy task", due_date=today))
        admin.commit()

    with UserSession(bind=accounts, user_id=first_id) as first:
        category = get_categories(session=first)[0]
        goal = create_goal("Private goal", 30, category_id=category.id, session=first)
        quest = create_quest(
            "Private task", category_id=category.id, goal_id=goal.id, planned_date=today,
            estimated_minutes=30, session=first,
        )
        update_checkin_status(quest.id, today, "Completed", session=first)
        routine = create_recurring_habit(
            "Private habit", category.id, 15, "selected_weekdays", [today.weekday()],
            today, end_date=today, session=first,
        )
        generate_recurring_habit_for_month(routine.id, today.year, today.month, session=first)
        first_avatar = save_avatar("avatar.png", b"first owner", upload_dir=tmp_path, session=first)
        category_id, quest_id, goal_id = category.id, quest.id, goal.id
        assert get_character_profile_data(today=today, session=first)["total_xp"] > 0
        assert len(get_all_quests(session=first)) == 2
        analytics = get_habit_analytics_data(today=today, session=first)
        assert analytics["routine_performance"]["Routine"].tolist() == ["Private habit"]

    with UserSession(bind=accounts, user_id=second_id) as second:
        assert category_id not in {category.id for category in get_categories(session=second)}
        assert get_all_quests(session=second) == []
        assert second.query(Quest).count() == 0
        assert second.get(Quest, quest_id) is None
        assert second.get(Goal, goal_id) is None
        assert second.scalars(select(QuestCheckin.id)).all() == []
        assert get_habit_analytics_data(today=today, session=second)["routine_performance"].empty
        assert get_character_profile_data(today=today, session=second)["total_xp"] == 0
        with pytest.raises(ValueError):
            update_checkin_status(quest_id, today, "Failed", session=second)
        with pytest.raises(ValueError):
            delete_goal(goal_id, session=second)
        second.add(Quest(title="Foreign category", category_id=category_id))
        with pytest.raises(IntegrityError):
            second.commit()
        second.rollback()
        with pytest.raises(PermissionError):
            second.execute(Quest.__table__.select())
        second_avatar = save_avatar("avatar.png", b"second owner", upload_dir=tmp_path, session=second)
        remove_avatar(upload_dir=tmp_path, session=second)
        assert Path(second_avatar).exists() is False
        assert Path(first_avatar).read_bytes() == b"first owner"

    with UserSession(bind=accounts, user_id=first_id) as first:
        assert first.get(Quest, quest_id).checkins[0].status == "Completed"
        assert delete_goal(goal_id, session=first) == 1
        assert first.get(Quest, quest_id).goal_id is None

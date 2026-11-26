from datetime import date

import pytest
from sqlalchemy import create_engine, inspect, select
from sqlalchemy.engine import URL
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.database import db
from src.database.claim_legacy import claim_legacy_data
from src.database.import_sqlite import import_sqlite
from src.database.models import Base, Category, Goal, PlayerProfile, Quest, QuestCheckin
from src.database.seed import ensure_default_categories
from src.database.user_session import UserSession
from src.services.account_service import register_google_account
from src.services.goal_service import delete_goal, get_goal_progress
from src.services.quest_service import create_quest


@pytest.mark.parametrize("scheme", ["postgres", "postgresql", "postgresql+psycopg"])
def test_postgresql_url_selects_psycopg_and_keeps_connection_parameters(monkeypatch, scheme):
    monkeypatch.setenv("DATABASE_URL", f"{scheme}://user:p%40ss@localhost:5433/habits?sslmode=require")

    url = db.get_database_url()

    assert url.drivername == "postgresql+psycopg"
    assert url.password == "p@ss"
    assert url.port == 5433
    assert url.query["sslmode"] == "require"


def test_import_preserves_history_and_generates_new_ids(postgres, tmp_path):
    source_path = tmp_path / "old habit quest.db"
    sqlite = create_engine(URL.create("sqlite", database=str(source_path)))
    completed_date = date(2026, 7, 1)
    long_title = "Portfolio project " * 14
    try:
        Base.metadata.create_all(sqlite)
        with Session(sqlite) as session:
            category = Category(id=10, name="Work", description="My own description")
            goal = Goal(id=20, title=long_title, planned_total_minutes=120, category=category)
            quest = Quest(
                id=40, title="Portfolio session", category=category, goal=goal, estimated_minutes=60
            )
            session.add_all([
                QuestCheckin(id=80, quest=quest, checkin_date=completed_date, status="Completed", xp_awarded=20),
                PlayerProfile(id=5, character_name="Explorer", avatar_path="data/uploads/avatar.png"),
            ])
            session.commit()
        with sqlite.begin() as connection:
            connection.exec_driver_sql("ALTER TABLE quests DROP COLUMN goal_session_number")
    finally:
        sqlite.dispose()

    source_bytes = source_path.read_bytes()
    counts = import_sqlite(source_path, postgres)

    assert source_path.read_bytes() == source_bytes
    assert counts["goals"] == counts["quests"] == counts["quest_checkins"] == counts["player_profiles"] == 1
    with pytest.raises(ValueError, match="destination must be empty"):
        import_sqlite(source_path, postgres)

    with Session(postgres) as session:
        assert session.get(Goal, 20).title == long_title
        quest = session.get(Quest, 40)
        assert quest.goal_id == 20
        assert quest.goal_session_number == 1
        assert quest.checkins[0].checkin_date == completed_date
        assert get_goal_progress(20, session=session)["earned_xp"] == 20
        assert session.get(PlayerProfile, 5).avatar_path == "data/uploads/avatar.png"

        ensure_default_categories(session=session)
        ensure_default_categories(session=session)
        assert session.get(Category, 10).description == "My own description"
        assert create_quest("New task", category_id=10, session=session).id > quest.id

        assert delete_goal(20, session=session) == 1
        assert quest.goal_id is None
        assert quest.checkins[0].xp_awarded == 20


def test_import_rolls_back_if_sqlite_contains_an_orphaned_checkin(postgres, tmp_path):
    source_path = tmp_path / "orphaned.db"
    sqlite = create_engine(URL.create("sqlite", database=str(source_path)))
    try:
        Base.metadata.create_all(sqlite)
        with Session(sqlite) as session:
            session.add_all([
                Category(id=10, name="Work"),
                QuestCheckin(id=20, quest_id=999, checkin_date=date(2026, 7, 1)),
            ])
            session.commit()
    finally:
        sqlite.dispose()

    with pytest.raises(IntegrityError):
        import_sqlite(source_path, postgres)

    with postgres.connect() as connection:
        assert connection.execute(select(Category)).first() is None
        assert connection.execute(select(QuestCheckin)).first() is None
        assert "goals" in inspect(connection).get_table_names()


def test_legacy_data_stays_hidden_until_assigned_to_the_selected_google_account(postgres):
    with Session(postgres) as admin, admin.begin():
        category = Category(name="Work", description="Legacy description")
        quest = Quest(title="Legacy task", category=category)
        admin.add_all([QuestCheckin(quest=quest, checkin_date=date(2026, 11, 23)), PlayerProfile(character_name="Explorer")])

    other_id = register_google_account("other-google-account", "other@example.com")
    owner_id = register_google_account("owner-google-account", "owner@example.com")
    with UserSession(bind=postgres, user_id=owner_id) as owner:
        assert owner.scalars(select(Quest)).all() == []
    with pytest.raises(ValueError):
        claim_legacy_data("unknown@example.com")
    assert claim_legacy_data("owner@example.com") == 4
    assert claim_legacy_data("owner@example.com") == 0

    with UserSession(bind=postgres, user_id=owner_id) as owner:
        quest = owner.scalars(select(Quest)).one()
        assert quest.category.description == "Legacy description"
        assert quest.checkins[0].user_id == owner_id
        assert owner.scalars(select(PlayerProfile)).one().character_name == "Explorer"
        assert len(owner.scalars(select(Category)).all()) == 5
    with UserSession(bind=postgres, user_id=other_id) as other:
        assert other.scalars(select(Quest)).all() == []
        assert other.scalars(select(PlayerProfile)).one().character_name == "Adventurer"
    with postgres.connect() as connection:
        assert connection.exec_driver_sql("SELECT relrowsecurity FROM pg_class WHERE oid = 'quests'::regclass").scalar_one()

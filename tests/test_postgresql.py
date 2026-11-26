from concurrent.futures import ThreadPoolExecutor
from datetime import date, time
from threading import Barrier, local

import pytest
from sqlalchemy import create_engine, event, func, inspect, select
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
from src.services.goal_service import create_goal, delete_goal, get_goal_progress
from src.services.goal_session_planner_service import plan_goal_sessions
from src.services.quest_service import create_quest, create_scheduled_quest, get_categories


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


DAY = date(2026, 11, 23)


def _race(postgres, marker, action):
    """Release both workers at their first competing database statement."""
    barrier = Barrier(2)
    worker = local()

    def synchronize(_connection, _cursor, statement, _parameters, _context, _executemany):
        if not getattr(worker, "synchronized", False) and marker(statement):
            worker.synchronized = True
            barrier.wait(timeout=10)

    event.listen(postgres, "before_cursor_execute", synchronize)
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(action) for _ in range(2)]
            return [future.result(timeout=30) for future in futures]
    finally:
        event.remove(postgres, "before_cursor_execute", synchronize)


@pytest.fixture
def shared_goal(postgres):
    owner = register_google_account("goal-owner", "synthetic@example.com")
    with UserSession(bind=postgres, user_id=owner) as session:
        category = get_categories(session=session)[0]
        goal = create_goal("Project", 120, category_id=category.id, session=session)
        return owner, goal.id, category.id


def _assert_numbered_goal_sessions(postgres, owner, goal_id):
    with UserSession(bind=postgres, user_id=owner) as session:
        quests = session.scalars(select(Quest).where(Quest.goal_id == goal_id).order_by(Quest.goal_session_number)).all()
        assert [(quest.goal_session_number, quest.title) for quest in quests] == [
            (1, "Project Session 1"), (2, "Project Session 2"),
        ]
        checkins = session.scalars(select(QuestCheckin)).all()
        assert len(checkins) == 2
        assert {checkin.quest_id for checkin in checkins} == {quest.id for quest in quests}
        assert {(checkin.status, checkin.xp_awarded) for checkin in checkins} == {("Planned", 0)}


def test_postgresql_concurrent_goal_session_numbering(postgres, shared_goal):
    owner, goal_id, category_id = shared_goal

    def create_session():
        with UserSession(bind=postgres, user_id=owner, autoflush=False) as session:
            quest = create_scheduled_quest(
                "Session", category_id=category_id, goal_id=goal_id, planned_date=DAY,
                start_time=time(9), end_time=time(10), session=session,
            )
            return quest.goal_session_number

    numbers = _race(postgres, lambda statement: "FROM goals" in statement and "FOR UPDATE" in statement, create_session)
    assert sorted(numbers) == [1, 2]
    _assert_numbered_goal_sessions(postgres, owner, goal_id)


def test_postgresql_concurrent_bulk_planning_does_not_overallocate(postgres, shared_goal):
    owner, goal_id, _ = shared_goal

    def plan():
        with UserSession(bind=postgres, user_id=owner, autoflush=False) as session:
            return plan_goal_sessions(goal_id, 60, DAY, [DAY.weekday()], time(9), session=session)["created_count"]

    results = _race(postgres, lambda statement: "FROM goals" in statement and "FOR UPDATE" in statement, plan)
    assert sorted(results) == [0, 2]
    _assert_numbered_goal_sessions(postgres, owner, goal_id)


@pytest.mark.parametrize("bulk", [False, True], ids=["single", "bulk"])
def test_postgresql_failed_checkin_write_rolls_back_scheduling(postgres, shared_goal, bulk):
    owner, goal_id, category_id = shared_goal
    with UserSession(bind=postgres, user_id=owner, autoflush=False) as session:
        def schedule():
            if bulk:
                return plan_goal_sessions(goal_id, 60, DAY, [DAY.weekday()], time(9), session=session)["created_count"]
            quest = create_scheduled_quest(
                "Session", category_id=category_id, goal_id=goal_id, planned_date=DAY,
                start_time=time(9), end_time=time(10), session=session,
            )
            return quest.goal_session_number

        expected = 2 if bulk else 1
        _assert_scheduling_rollback(session, schedule, expected)
        assert schedule() == expected
        assert session.scalars(select(Quest.goal_session_number).order_by(Quest.goal_session_number)).all() == list(
            range(1, expected + 1)
        )
        assert session.scalar(select(func.count(QuestCheckin.id))) == expected


def _assert_scheduling_rollback(session, schedule, checkins_before_failure):
    checkin_flushes = 0

    def reject_checkin(current_session, _context, _instances):
        nonlocal checkin_flushes
        checkin_flushes += sum(isinstance(row, QuestCheckin) for row in current_session.new)
        if checkin_flushes >= checkins_before_failure:
            raise RuntimeError("Synthetic check-in write failure")

    event.listen(session, "before_flush", reject_checkin)
    try:
        with pytest.raises(RuntimeError, match="Synthetic check-in write failure"):
            schedule()
    finally:
        event.remove(session, "before_flush", reject_checkin)
    assert session.scalars(select(Quest.id)).all() == []
    assert session.scalars(select(QuestCheckin.id)).all() == []

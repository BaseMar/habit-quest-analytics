from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, time
from threading import Barrier, local
from uuid import uuid4

import pytest
from alembic import command
from sqlalchemy import MetaData, Table, create_engine, delete, event, func, insert, inspect, select, update
from sqlalchemy.engine import URL
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from src.database import db
from src.database.claim_legacy import claim_legacy_data
from src.database.import_sqlite import import_sqlite
from src.database.models import (
    Base, Category, Goal, PlayerProfile, Quest, QuestCheckin, RecurringHabitInstance, UserAccount,
)
from src.database.seed import ensure_default_categories
from src.database.user_session import UserSession
from src.services.account_service import register_google_account
from src.services.checklist_service import complete_checkin
from src.services.goal_service import create_goal, delete_goal, get_goal_progress
from src.services.goal_session_planner_service import plan_goal_sessions
from src.services.quest_service import create_quest, create_scheduled_quest, get_categories
from src.services.recurring_habit_service import create_recurring_habit, generate_recurring_habit_for_month


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


def test_legacy_data_stays_hidden_until_assigned_to_the_selected_google_account(postgres, migration_config):
    command.downgrade(migration_config, "0001")
    with postgres.begin() as connection:
        metadata = MetaData()
        categories = Table("categories", metadata, autoload_with=connection)
        quests = Table("quests", metadata, autoload_with=connection)
        checkins = Table("quest_checkins", metadata, autoload_with=connection)
        profiles = Table("player_profiles", metadata, autoload_with=connection)
        created_at = datetime(2026, 11, 23, 9)
        assert "user_id" not in quests.c
        category_id = connection.scalar(
            insert(categories).values(name="Work", description="Legacy description").returning(categories.c.id)
        )
        quest_id = connection.scalar(
            insert(quests).values(
                title="Legacy task", category_id=category_id, status="Planned", is_habit=False,
                xp_reward=20, created_at=created_at,
            ).returning(quests.c.id)
        )
        connection.execute(insert(checkins).values(
            quest_id=quest_id, checkin_date=created_at.date(), status="Completed",
            xp_awarded=20, created_at=created_at, updated_at=created_at,
        ))
        connection.execute(insert(profiles).values(
            character_name="Explorer", total_xp=0, created_at=created_at, updated_at=created_at,
        ))
    command.upgrade(migration_config, "head")
    command.check(migration_config)
    with Session(postgres) as admin:
        assert admin.get(Quest, quest_id).user_id is None

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
        assert quest.id == quest_id
        assert quest.category.description == "Legacy description"
        assert quest.checkins[0].user_id == owner_id
        assert quest.checkins[0].xp_awarded == 20
        assert owner.scalars(select(PlayerProfile)).one().character_name == "Explorer"
        assert len(owner.scalars(select(Category)).all()) == 5
    with UserSession(bind=postgres, user_id=other_id) as other:
        assert other.scalars(select(Quest)).all() == []
        assert other.scalars(select(PlayerProfile)).one().character_name == "Adventurer"
    with postgres.connect() as connection:
        assert connection.exec_driver_sql("SELECT relrowsecurity FROM pg_class WHERE oid = 'quests'::regclass").scalar_one()


def test_postgresql_owner_foreign_keys_and_per_account_uniqueness(postgres):
    first = register_google_account("first-owner", "first@example.com")
    second = register_google_account("second-owner", "second@example.com")
    missing_owner = max(first, second) + 1
    invalid = (
        (insert(Category).values(name="Unknown account", user_id=missing_owner), "23503", "fk_categories_user_id"),
        (insert(Category).values(name="Work", user_id=first), "23505", "uq_categories_owner_name"),
        (insert(PlayerProfile).values(user_id=first), "23505", "uq_player_profiles_owner"),
    )
    with postgres.begin() as connection:
        for statement, sqlstate, constraint in invalid:
            with pytest.raises(IntegrityError) as error, connection.begin_nested():
                connection.execute(statement)
            assert error.value.orig.sqlstate == sqlstate
            assert error.value.orig.diag.constraint_name == constraint

        connection.execute(insert(Category), [
            {"name": "Shared label", "user_id": first}, {"name": "Shared label", "user_id": second},
        ])
        assert set(connection.scalars(select(Category.user_id).where(Category.name == "Shared label"))) == {first, second}
        assert connection.scalar(select(func.count()).select_from(PlayerProfile)) == 2


def test_postgresql_rls_blocks_an_unprivileged_role(postgres):
    owner = register_google_account("rls-owner", "rls-owner@example.com")
    with UserSession(bind=postgres, user_id=owner) as session:
        create_quest("Private task", session=session)

    with postgres.connect() as connection:
        with connection.begin() as transaction:
            schema = connection.exec_driver_sql("SELECT current_schema()").scalar_one()
            quote = connection.dialect.identifier_preparer.quote
            role = quote(f"hq_unprivileged_{uuid4().hex}")
            tables = connection.exec_driver_sql(
                """
                SELECT relname, relrowsecurity
                  FROM pg_class JOIN pg_namespace ON pg_class.relnamespace = pg_namespace.oid
                 WHERE nspname = current_schema() AND relkind = 'r'
                """
            ).all()
            assert {name for name, _ in tables} == {*Base.metadata.tables, "alembic_version"}
            assert all(enabled for name, enabled in tables if name in Base.metadata.tables)
            assert connection.scalar(select(func.count()).select_from(Quest)) == 1

            connection.exec_driver_sql(f"CREATE ROLE {role} NOLOGIN NOBYPASSRLS")
            connection.exec_driver_sql(f"GRANT USAGE ON SCHEMA {quote(schema)} TO {role}")
            connection.exec_driver_sql(f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA {quote(schema)} TO {role}")
            connection.exec_driver_sql(f"SET LOCAL ROLE {role}")
            for table in Base.metadata.tables.values():
                assert connection.scalar(select(func.count()).select_from(table)) == 0
            assert connection.execute(update(Quest).values(title="Changed")).rowcount == 0
            assert connection.execute(delete(Quest)).rowcount == 0
            with pytest.raises(DBAPIError) as error, connection.begin_nested():
                connection.execute(insert(Quest).values(id=1000, user_id=owner, title="Forbidden"))
            assert error.value.orig.sqlstate == "42501"
            assert "row-level security" in str(error.value.orig)
            # The rollback also removes the cluster-level role and its grants.
            transaction.rollback()

    with UserSession(bind=postgres, user_id=owner) as session:
        assert session.scalars(select(Quest.title)).all() == ["Private task"]


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


def test_postgresql_concurrent_google_registration_provisions_once(postgres):
    ids = _race(
        postgres, lambda statement: statement.startswith("INSERT INTO user_accounts"),
        lambda: register_google_account("same-subject", "synthetic@example.com"),
    )
    assert ids[0] == ids[1]
    with Session(postgres) as admin:
        assert admin.scalars(select(UserAccount.id)).all() == [ids[0]]
    with UserSession(bind=postgres, user_id=ids[0]) as session:
        assert len(get_categories(session=session)) == 5
        assert session.scalars(select(PlayerProfile.user_id)).all() == [ids[0]]


def test_postgresql_concurrent_checkin_completion_awards_xp_once(postgres):
    owner = register_google_account("checkin-owner", "synthetic@example.com")
    with UserSession(bind=postgres, user_id=owner) as session:
        quest = create_scheduled_quest("Task", planned_date=DAY, start_time=time(9), end_time=time(10), session=session)
        quest_id, xp = quest.id, quest.xp_reward

    def complete():
        with UserSession(bind=postgres, user_id=owner) as session:
            checkin = complete_checkin(quest_id, DAY, session=session)
            return checkin.id, checkin.completed_at, checkin.xp_awarded

    outcomes = _race(postgres, lambda statement: "FROM quests" in statement and "FOR UPDATE" in statement, complete)
    assert outcomes[0] == outcomes[1]
    with UserSession(bind=postgres, user_id=owner) as session:
        checkin = session.scalars(select(QuestCheckin)).one()
        assert (checkin.id, checkin.status, checkin.xp_awarded) == (outcomes[0][0], "Completed", xp)
        assert checkin.completed_at is not None


def test_postgresql_concurrent_routine_generation_rolls_back_the_loser(postgres):
    owner = register_google_account("routine-owner", "synthetic@example.com")
    with UserSession(bind=postgres, user_id=owner) as session:
        habit = create_recurring_habit(
            "Routine", None, 15, "selected_weekdays", [DAY.weekday()], DAY, end_date=DAY, session=session,
        )
        habit_id = habit.id

    def generate():
        with UserSession(bind=postgres, user_id=owner) as session:
            try:
                return generate_recurring_habit_for_month(habit_id, DAY.year, DAY.month, session=session)["generated_count"]
            except IntegrityError as error:
                assert error.orig.sqlstate == "23505"
                assert error.orig.diag.constraint_name == "uq_recurring_habit_date"
                return 0

    assert sorted(_race(postgres, lambda statement: statement.startswith("INSERT INTO recurring_habit_instances"), generate)) == [0, 1]
    with UserSession(bind=postgres, user_id=owner) as session:
        instance = session.scalars(select(RecurringHabitInstance)).one()
        quest = session.scalars(select(Quest)).one()
        checkin = session.scalars(select(QuestCheckin)).one()
        assert instance.recurring_habit_id == habit_id
        assert instance.quest_id == quest.id == checkin.quest_id
        assert (instance.scheduled_date, checkin.checkin_date, checkin.status, checkin.xp_awarded) == (DAY, DAY, "Planned", 0)
        retry = generate_recurring_habit_for_month(habit_id, DAY.year, DAY.month, session=session)
        assert (retry["generated_count"], retry["skipped_existing_count"]) == (0, 1)


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

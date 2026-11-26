from datetime import date, time, timedelta
from functools import partial
from pathlib import Path

import pytest
import streamlit as st
from sqlalchemy import create_engine, delete, event, func, insert, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload, selectinload

from src.auth import bind_account
from src.database import db
from src.database.models import (
    Achievement,
    Base,
    Category,
    Goal,
    PlayerProfile,
    Quest,
    QuestCheckin,
    RecurringHabit,
    RecurringHabitInstance,
    UnlockedAchievement,
    UserAccount,
)
from src.database.user_session import UserSession
from src.services.account_service import register_google_account
from src.services.analytics_service import get_character_profile_data, get_goal_analytics_summary, get_habit_analytics_data
from src.services.checklist_service import complete_checkin, fail_checkin, reset_checkin, skip_checkin
from src.services.command_center_service import get_command_center_data
from src.services.goal_service import create_goal, delete_goal, get_goal, get_goal_completion_forecast, list_goals, update_goal
from src.services.goal_session_planner_service import plan_goal_sessions
from src.services.profile_service import get_or_create_player_profile, remove_avatar, save_avatar
from src.services.quest_service import create_scheduled_quest, delete_one_time_quest_if_unresolved, get_all_quests, get_categories, update_planned_quest
from src.services.recurring_habit_service import (
    archive_recurring_habit,
    create_recurring_habit,
    delete_recurring_habit_if_unused,
    generate_recurring_habit_for_month,
    get_recurring_habit,
    list_recurring_habits,
    update_recurring_habit_template,
)


TODAY = date(2026, 11, 23)
OWNED_MODELS = (Category, Quest, QuestCheckin, Goal, RecurringHabit, RecurringHabitInstance, PlayerProfile, UnlockedAchievement)


@pytest.fixture(params=["sqlite", "postgresql"])
def accounts(request, monkeypatch):
    if request.param == "postgresql":
        yield request.getfixturevalue("postgres")
        return

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


@pytest.fixture
def account_data(accounts):
    with Session(accounts) as admin, admin.begin():
        achievement = Achievement(name="Synthetic shared definition")
        admin.add(achievement)
        admin.flush()
        achievement_id = achievement.id

    def seed(subject, category_name, minutes):
        user_id = register_google_account(subject, f"{subject}@example.com")
        with UserSession(bind=accounts, user_id=user_id) as session:
            category = session.scalars(select(Category).where(Category.name == category_name)).one()
            goal = create_goal(
                f"{subject} project", 180, category_id=category.id,
                target_end_date=TODAY + timedelta(days=10), session=session,
            )
            quest = create_scheduled_quest(
                "Session", category_id=category.id, goal_id=goal.id, planned_date=TODAY,
                start_time=time(9), end_time=time(10), estimated_minutes=minutes, session=session,
            )
            checkin = complete_checkin(quest.id, TODAY, session=session)
            routine = create_recurring_habit(
                f"{subject} routine", category.id, 15, "selected_weekdays", [TODAY.weekday()],
                TODAY, end_date=TODAY, session=session,
            )
            generate_recurring_habit_for_month(routine.id, TODAY.year, TODAY.month, session=session)
            profile = get_or_create_player_profile(session=session)
            profile.character_name = subject
            unlock = UnlockedAchievement(player_profile_id=profile.id, achievement_id=achievement_id)
            session.add(unlock)
            session.commit()
            return user_id, {
                Category: category.id, Quest: quest.id, QuestCheckin: checkin.id, Goal: goal.id,
                RecurringHabit: routine.id, RecurringHabitInstance: routine.instances[0].id,
                PlayerProfile: profile.id, UnlockedAchievement: unlock.id,
            }

    first = seed("account-a", "Work", 30)
    second = seed("account-b", "Health", 60)
    with Session(accounts) as admin, admin.begin():
        category = Category(name="Unassigned")
        goal = Goal(title="Unassigned project", planned_total_minutes=60, category=category)
        quest = Quest(title="Unassigned task", goal=goal, category=category, due_date=TODAY, xp_reward=999)
        checkin = QuestCheckin(quest=quest, checkin_date=TODAY, status="Completed", xp_awarded=999)
        linked_legacy = QuestCheckin(
            quest_id=first[1][Quest], checkin_date=TODAY - timedelta(days=1), status="Completed", xp_awarded=999,
        )
        routine = RecurringHabit(
            title="Unassigned routine", category=category, xp_reward=5, estimated_minutes=15,
            recurrence_type="selected_weekdays", start_date=TODAY,
        )
        occurrence = RecurringHabitInstance(recurring_habit=routine, quest=quest, scheduled_date=TODAY)
        profile = PlayerProfile(character_name="Unassigned")
        unlock = UnlockedAchievement(player_profile=profile, achievement_id=achievement_id)
        admin.add_all([goal, checkin, linked_legacy, occurrence, unlock])
        admin.flush()
        legacy_ids = {type(row): row.id for row in (category, goal, quest, checkin, routine, occurrence, profile, unlock)}
    return first, second, legacy_ids, achievement_id


def test_account_reads_relationships_and_aggregates_are_scoped(accounts, account_data, monkeypatch):
    first, second, legacy, achievement_id = account_data
    for visible, hidden, subject, minutes, stat in (
        (first, second, "account-a", 30, "Discipline"),
        (second, first, "account-b", 60, "Strength"),
    ):
        user_id, ids = visible
        foreign = hidden[1]
        monkeypatch.setattr(st, "session_state", {})
        monkeypatch.setattr(st, "user", {
            "is_logged_in": True, "iss": "https://accounts.google.com", "sub": subject,
            "email_verified": True, "email": f"{subject}@example.com",
        })
        bind_account(subject, user_id)
        with db.get_session() as session:
            assert session.user_id == user_id
            for model in OWNED_MODELS:
                assert session.get(model, ids[model]) is not None
                assert session.get(model, foreign[model]) is None
                assert session.get(model, legacy[model]) is None
                assert {row.user_id for row in session.scalars(select(model))} == {user_id}
            with pytest.raises(PermissionError, match="unavailable"):
                session.get(UserAccount, user_id)

            assert len(get_categories(session=session)) == 5
            assert {quest.title for quest in get_all_quests(session=session)} == {f"{subject} project Session 1", f"{subject} routine"}
            assert [goal.id for goal in list_goals(session=session)] == [ids[Goal]]
            assert get_goal(foreign[Goal], session=session) is None
            assert [habit.id for habit in list_recurring_habits(session=session)] == [ids[RecurringHabit]]
            assert get_recurring_habit(foreign[RecurringHabit], session=session) is None
            assert session.scalar(select(func.count(Quest.id))) == 2

            session.expire_all()
            goal = session.scalars(select(Goal).options(selectinload(Goal.quests))).one()
            assert [quest.id for quest in goal.quests] == [ids[Quest]]
            quest = session.get(Quest, ids[Quest])
            assert [checkin.id for checkin in quest.checkins] == [ids[QuestCheckin]]
            achievement = session.scalars(select(Achievement).options(joinedload(Achievement.unlocked_by))).unique().one()
            assert achievement.id == achievement_id
            assert [unlock.id for unlock in achievement.unlocked_by] == [ids[UnlockedAchievement]]
            assert achievement.unlocked_by[0].player_profile.id == ids[PlayerProfile]
            session.expire(achievement, ["unlocked_by"])
            assert [unlock.id for unlock in achievement.unlocked_by] == [ids[UnlockedAchievement]]
            instance = session.get(RecurringHabitInstance, ids[RecurringHabitInstance])
            assert instance.quest.user_id == instance.recurring_habit.user_id == user_id

            xp = minutes // 3
            dashboard = get_command_center_data(today=TODAY, session=session)
            assert (dashboard["total_quests"], dashboard["completed_today"], dashboard["weekly_xp"]) == (2, 1, xp)
            analytics = get_habit_analytics_data(today=TODAY, session=session)
            assert analytics["period_summary"]["xp_earned"] == xp
            assert analytics["routine_performance"]["Routine"].tolist() == [f"{subject} routine"]
            projects = get_goal_analytics_summary(session=session)
            assert projects["goal_table"]["Goal ID"].tolist() == [ids[Goal]]
            assert projects["completed_effort_minutes"] == minutes
            forecast = get_goal_completion_forecast(ids[Goal], today=TODAY, session=session)
            assert forecast["available"] and forecast["daily_completed_minutes"] == minutes
            with pytest.raises(ValueError, match="was not found"):
                get_goal_completion_forecast(foreign[Goal], today=TODAY, session=session)
            profile = get_character_profile_data(today=TODAY, session=session)
            assert profile["character_name"] == subject
            assert profile["total_xp"] == xp
            earned_stats = profile["rpg_stats"].query("XP > 0")
            assert earned_stats[["Stat", "XP"]].values.tolist() == [[stat, xp]]


def _snapshot(engine):
    with engine.connect() as connection:
        return {
            model.__tablename__: connection.execute(model.__table__.select().order_by(model.id)).all()
            for model in OWNED_MODELS
        }


def test_foreign_service_and_orm_writes_leave_owner_data_unchanged(accounts, account_data, tmp_path):
    (owner_id, foreign), (other_id, own), _, _ = account_data
    with UserSession(bind=accounts, user_id=owner_id) as session:
        first_avatar = save_avatar("avatar.png", b"first owner", upload_dir=tmp_path, session=session)
    before = _snapshot(accounts)

    with UserSession(bind=accounts, user_id=other_id) as session:
        quest_id, goal_id, routine_id = foreign[Quest], foreign[Goal], foreign[RecurringHabit]
        rejected = (
            partial(update_planned_quest, quest_id, "Changed", "", own[Category], TODAY, time(9), time(10)),
            partial(delete_one_time_quest_if_unresolved, quest_id),
            *(partial(action, quest_id, TODAY) for action in (complete_checkin, skip_checkin, fail_checkin, reset_checkin)),
            partial(update_goal, goal_id, title="Changed"),
            partial(delete_goal, goal_id),
            partial(plan_goal_sessions, goal_id, 30, TODAY, [TODAY.weekday()], time(9)),
            partial(update_recurring_habit_template, routine_id, "Changed", own[Category], 30, "selected_weekdays",
                    [TODAY.weekday()], TODAY),
            partial(archive_recurring_habit, routine_id),
            partial(delete_recurring_habit_if_unused, routine_id),
            partial(generate_recurring_habit_for_month, routine_id, TODAY.year, TODAY.month),
        )
        for action in rejected:
            with pytest.raises(ValueError, match="was not found"):
                action(session=session)

        assert session.get(PlayerProfile, foreign[PlayerProfile]) is None
        local_quest = session.get(Quest, own[Quest])
        local_quest.user_id = owner_id
        with pytest.raises(PermissionError, match="Cannot modify"):
            session.commit()
        session.rollback()

        session.add(Quest(title="Foreign owner", user_id=owner_id))
        with pytest.raises(PermissionError, match="Cannot create"):
            session.commit()
        session.rollback()

        for statement in (
            Quest.__table__.select(),
            update(Quest).where(Quest.id == quest_id).values(title="Changed"),
            delete(Quest).where(Quest.id == quest_id),
            update(PlayerProfile).where(PlayerProfile.id == foreign[PlayerProfile]).values(character_name="Changed"),
        ):
            with pytest.raises(PermissionError):
                session.execute(statement)
        session.rollback()

    assert _snapshot(accounts) == before
    with UserSession(bind=accounts, user_id=other_id) as session:
        second_avatar = save_avatar(first_avatar, b"second owner", upload_dir=tmp_path, session=session)
        assert Path(second_avatar).parent != Path(first_avatar).parent
        remove_avatar(upload_dir=tmp_path, session=session)
        assert not Path(second_avatar).exists()
    assert Path(first_avatar).read_bytes() == b"first owner"
    with UserSession(bind=accounts, user_id=owner_id) as session:
        quest = session.get(Quest, foreign[Quest])
        assert quest.checkins[0].status == "Completed"
        assert delete_goal(foreign[Goal], session=session) == 1
        assert quest.goal_id is None
        assert quest.checkins[0].xp_awarded == 10


def test_unsupported_account_session_apis_reject_unscoped_operations(accounts, account_data):
    (owner_id, foreign), (other_id, _), _, _ = account_data
    before = _snapshot(accounts)
    with UserSession(bind=accounts, user_id=other_id) as session:
        for action in (
            partial(session.bulk_insert_mappings, Quest, [{"title": "Outside scope", "user_id": owner_id}]),
            partial(session.bulk_update_mappings, Quest, [{"id": foreign[Quest], "title": "Changed"}]),
            partial(session.bulk_save_objects, [Quest(title="Outside scope", user_id=owner_id)]),
            partial(session.execute, select(Quest).from_statement(text("SELECT * FROM quests"))),
            partial(session.execute, select(Quest).from_statement(select(Quest.__table__))),
        ):
            with pytest.raises(PermissionError):
                action()
            session.rollback()
    assert _snapshot(accounts) == before


def test_owned_relationship_constraints_roll_back_on_invalid_reference(accounts, account_data):
    (user_id, own), (_, foreign), _, _ = account_data
    base_routine = {
        "title": "Invalid", "estimated_minutes": 15, "xp_reward": 5,
        "recurrence_type": "selected_weekdays", "start_date": TODAY,
    }
    next_day = TODAY + timedelta(days=1)
    with UserSession(bind=accounts, user_id=user_id) as session:
        spare_quest = create_scheduled_quest("Spare task", planned_date=next_day, start_time=time(9), end_time=time(10),
                                             session=session).id
    with Session(accounts) as admin, admin.begin():
        spare_achievement = Achievement(name="Unlinked definition")
        admin.add(spare_achievement)
        admin.flush()
        achievement_id = spare_achievement.id

    invalid_rows = (
        (Quest, {"title": "Invalid", "category_id": foreign[Category]}, "fk_quests_owned_category"),
        (Quest, {"title": "Invalid", "goal_id": foreign[Goal]}, "fk_quests_owned_goal"),
        (QuestCheckin, {"quest_id": foreign[Quest], "checkin_date": next_day}, "fk_checkins_owned_quest"),
        (Goal, {"title": "Invalid", "planned_total_minutes": 60, "category_id": foreign[Category]}, "fk_goals_owned_category"),
        (RecurringHabit, dict(base_routine, category_id=foreign[Category]), "fk_recurring_habits_owned_category"),
        (RecurringHabitInstance, {"recurring_habit_id": own[RecurringHabit], "quest_id": foreign[Quest],
                                  "scheduled_date": next_day}, "fk_instances_owned_quest"),
        (RecurringHabitInstance, {"recurring_habit_id": foreign[RecurringHabit], "quest_id": spare_quest,
                                  "scheduled_date": next_day}, "fk_instances_owned_habit"),
        (UnlockedAchievement, {"player_profile_id": foreign[PlayerProfile], "achievement_id": achievement_id},
         "fk_unlocks_owned_profile"),
    )
    before = _snapshot(accounts)
    for model, values, constraint in invalid_rows:
        with pytest.raises(IntegrityError) as error, accounts.begin() as connection:
            connection.execute(insert(Category).values(name="Rollback sentinel", user_id=user_id))
            connection.execute(insert(model).values(**values, user_id=user_id))
        if accounts.dialect.name == "postgresql":
            assert error.value.orig.sqlstate == "23503"
            assert error.value.orig.diag.constraint_name == constraint
    assert _snapshot(accounts) == before
    with accounts.begin() as connection:
        connection.execute(insert(Category).values(name="Rollback sentinel", user_id=user_id))
        connection.execute(insert(Quest).values(title="Valid", category_id=own[Category], user_id=user_id))

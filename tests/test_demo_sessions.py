from datetime import date, time
from pathlib import Path

import pytest
import streamlit as st
from sqlalchemy import event, select
from streamlit.testing.v1 import AppTest

from src import auth
from src.database import db
from src.database.models import Goal, Quest, QuestCheckin, RecurringHabit, RecurringHabitInstance
from src.services import demo_service
from src.services.analytics_service import get_character_profile_data, get_goal_analytics_summary, get_habit_analytics_data
from src.services.checklist_service import complete_checkin, reset_checkin
from src.services.command_center_service import get_command_center_data
from src.services.goal_service import create_goal
from src.services.goal_session_planner_service import plan_goal_sessions
from src.services.quest_service import create_scheduled_quest, get_categories, update_planned_quest
from src.services.recurring_habit_service import create_recurring_habit, generate_recurring_habit_for_month
from src.ui import THEME_MODE_KEY


APP_PATH = Path(__file__).resolve().parents[1] / "app" / "main.py"
DAY = date(2026, 11, 23)


@pytest.fixture
def demo_engines(monkeypatch):
    created = []
    disposed = []
    create_engine = demo_service.create_engine
    create_demo = demo_service.create_demo_database

    def track_demo_engine(*args, **kwargs):
        engine = create_engine(*args, **kwargs)
        event.listen(engine, "engine_disposed", disposed.append)
        created.append(engine)
        return engine

    monkeypatch.setattr(demo_service, "create_engine", track_demo_engine)
    monkeypatch.setattr(demo_service, "create_demo_database", lambda: create_demo(today=DAY))
    try:
        yield created, disposed
    finally:
        for engine in created:
            if engine not in disposed:
                engine.dispose()


def _guest_snapshot():
    with db.get_session() as session:
        profile = get_character_profile_data(today=DAY, session=session)
        summary = get_command_center_data(today=DAY, session=session)
        analytics = get_habit_analytics_data(today=DAY, session=session)
        return {
            "tasks": session.execute(select(Quest.id, Quest.title).order_by(Quest.id)).all(),
            "checkins": session.execute(select(
                QuestCheckin.quest_id, QuestCheckin.checkin_date, QuestCheckin.status, QuestCheckin.xp_awarded,
            ).order_by(QuestCheckin.id)).all(),
            "projects": session.execute(select(Goal.id, Goal.title).order_by(Goal.id)).all(),
            "routines": session.execute(select(RecurringHabit.id, RecurringHabit.title).order_by(RecurringHabit.id)).all(),
            "occurrences": session.execute(select(
                RecurringHabitInstance.recurring_habit_id, RecurringHabitInstance.quest_id,
                RecurringHabitInstance.scheduled_date,
            ).order_by(RecurringHabitInstance.id)).all(),
            "profile": (profile["character_name"], profile["total_xp"], profile["avatar_path"]),
            "summary": (summary["total_quests"], summary["completed_today"], summary["weekly_xp"]),
            "analytics": analytics["period_summary"],
            "project_effort": get_goal_analytics_summary(session=session)["planned_effort_minutes"],
        }


def _add_today_task(title, minutes, session=None):
    return create_scheduled_quest(
        title, planned_date=DAY, start_time=time(9), end_time=time(10), estimated_minutes=minutes, session=session,
    )


def test_two_guests_keep_interleaved_changes_and_resets_isolated(monkeypatch, demo_engines):
    created, disposed = demo_engines
    first, second = {}, {}
    monkeypatch.setattr(st, "user", {"is_logged_in": False})
    monkeypatch.setattr(st, "session_state", first)
    auth.start_demo()
    baseline = _guest_snapshot()
    monkeypatch.setattr(st, "session_state", second)
    auth.start_demo()
    assert _guest_snapshot() == baseline
    first_engine, second_engine = created
    assert first_engine is not second_engine

    monkeypatch.setattr(st, "session_state", first)
    first_quest = _add_today_task("Guest A draft", 90)
    update_planned_quest(first_quest.id, "Guest A edited task", "", None, DAY, time(9), time(10, 30))
    complete_checkin(first_quest.id, DAY)
    category_id = get_categories()[0].id
    goal = create_goal("Guest A project", 30, category_id=category_id)
    plan = plan_goal_sessions(goal.id, 30, DAY, [DAY.weekday()], time(10))
    routine = create_recurring_habit(
        "Guest A routine", category_id, 15, "selected_weekdays", [DAY.weekday()], DAY, end_date=DAY,
    )
    generate_recurring_habit_for_month(routine.id, DAY.year, DAY.month)
    changed = _guest_snapshot()
    assert (first_quest.id, "Guest A edited task") in changed["tasks"]
    assert plan["created_count"] == 1
    assert (goal.id, "Guest A project") in changed["projects"]
    assert (routine.id, "Guest A routine") in changed["routines"]
    assert len(changed["occurrences"]) == len(baseline["occurrences"]) + 1
    assert len(changed["checkins"]) == len(baseline["checkins"]) + 3
    assert changed["profile"][1] == baseline["profile"][1] + 30
    assert changed["summary"][1] == baseline["summary"][1] + 1
    assert changed["analytics"]["xp_earned"] == baseline["analytics"]["xp_earned"] + 30
    assert changed["project_effort"] == baseline["project_effort"] + 30

    monkeypatch.setattr(st, "session_state", second)
    assert _guest_snapshot() == baseline
    second_quest = _add_today_task("Guest B task", 30)
    assert second_quest.id == first_quest.id
    complete_checkin(second_quest.id, DAY)
    second_snapshot = _guest_snapshot()
    assert (second_quest.id, "Guest B task") in second_snapshot["tasks"]
    assert second_snapshot["profile"][1] == baseline["profile"][1] + 10

    monkeypatch.setattr(st, "session_state", first)
    assert _guest_snapshot() == changed
    reset_checkin(first_quest.id, DAY)
    assert _guest_snapshot()["profile"][1] == baseline["profile"][1]
    first.update({THEME_MODE_KEY: "Dark", "demo_avatar": b"guest image", "plan_title": "Unsaved draft"})
    for _ in range(2):
        replaced = first[auth.DEMO_STATE]
        auth.reset_demo()
        assert disposed.count(replaced) == 1
        assert first[auth.DEMO_STATE] is not replaced
        with db.get_session() as session:
            assert session.get_bind() is first[auth.DEMO_STATE]
        assert _guest_snapshot() == baseline
        assert first[THEME_MODE_KEY] == "Dark"
        assert "demo_avatar" not in first and "plan_title" not in first
    assert disposed[0] is first_engine
    assert second_engine not in disposed
    monkeypatch.setattr(st, "session_state", second)
    assert _guest_snapshot() == second_snapshot


def test_starting_an_active_demo_reuses_its_engine_and_changes(monkeypatch, demo_engines):
    created, disposed = demo_engines
    monkeypatch.setattr(st, "user", {"is_logged_in": False})
    monkeypatch.setattr(st, "session_state", {})
    auth.start_demo()
    _add_today_task("Keep this guest task", 30)
    snapshot = _guest_snapshot()

    auth.start_demo()

    assert len(created) == 1
    assert disposed == []
    assert _guest_snapshot() == snapshot


def test_failed_demo_start_and_reset_dispose_partial_engines(monkeypatch, demo_engines):
    created, disposed = demo_engines
    notices = []
    state = {}
    monkeypatch.setattr(st, "user", {"is_logged_in": False})
    monkeypatch.setattr(st, "session_state", state)
    monkeypatch.setattr(st, "error", notices.append)

    def fail_seed(_session, _day):
        raise RuntimeError("Synthetic demo seed failure")

    with monkeypatch.context() as patch:
        patch.setattr(demo_service, "_seed_demo_schedule", fail_seed)
        auth.start_demo()
    assert auth.DEMO_STATE not in state
    assert disposed == [created[0]]
    assert notices

    auth.start_demo()
    active = state[auth.DEMO_STATE]
    _add_today_task("Keep edits after failed reset", 30)
    state.update({THEME_MODE_KEY: "Dark", "demo_avatar": b"current guest avatar"})
    snapshot = _guest_snapshot()
    previous_state = state.copy()
    with monkeypatch.context() as patch:
        patch.setattr(demo_service, "_seed_demo_schedule", fail_seed)
        auth.reset_demo()
    assert state == previous_state
    assert disposed == [created[0], created[2]]
    assert active not in disposed
    with db.get_session() as session:
        assert session.get_bind() is active
    assert _guest_snapshot() == snapshot
    assert len(notices) == 2


def _click(app, label, *, sidebar=False):
    buttons = app.sidebar.button if sidebar else app.button
    matches = [button for button in buttons if button.label == label]
    assert len(matches) == 1, (label, [button.label for button in buttons])
    matches[0].click().run()
    assert not app.exception


def test_signed_in_fallback_can_still_enter_demo(monkeypatch, demo_engines):
    created, disposed = demo_engines
    monkeypatch.setattr(db, "engine", None)
    monkeypatch.setattr(st, "user", {
        "is_logged_in": True, "iss": "https://accounts.google.com", "email_verified": True,
        "sub": "synthetic", "email": "synthetic@example.com",
    })
    app = AppTest.from_file(APP_PATH).run()
    assert "DATABASE_URL" in app.error[0].value
    _click(app, "Try live demo")
    app.run()
    assert not app.exception and app.session_state[auth.DEMO_STATE] is created[0]
    _click(app, "Exit demo", sidebar=True)
    assert auth.DEMO_STATE not in app.session_state and disposed == created
    assert "DATABASE_URL" in app.error[0].value

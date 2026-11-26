from datetime import date, datetime, time, timedelta
from pathlib import Path

from sqlalchemy import create_engine

from app.components.checkin_actions import get_checkin_status_actions
from app.components.scheduling import duration_crosses_midnight, end_at_for_duration
from src.auth import DEMO_STATE
from src.constants import DEFAULT_CATEGORIES


APP_PATH = Path(__file__).resolve().parents[1] / "app" / "main.py"


def test_planned_checkin_actions_offer_resolve_choices():
    assert get_checkin_status_actions("Planned") == (
        ("Complete", "Completed", "primary"),
        ("Skip", "Skipped", "secondary"),
        ("Fail", "Failed", "secondary"),
    )


def test_resolved_checkin_actions_offer_only_reset():
    assert get_checkin_status_actions("Completed") == (("Reset", "Planned", "secondary"),)
    assert get_checkin_status_actions("Skipped") == (("Reset", "Planned", "secondary"),)
    assert get_checkin_status_actions("Failed") == (("Reset", "Planned", "secondary"),)


def test_unknown_checkin_status_has_no_action():
    assert get_checkin_status_actions(None) == ()


def test_scheduling_helpers_calculate_same_day_end_time():
    end_at = end_at_for_duration(date(2026, 7, 1), time(9, 30), 45)

    assert end_at == datetime(2026, 7, 1, 10, 15)
    assert duration_crosses_midnight(date(2026, 7, 1), time(9, 30), 45) is False


def test_scheduling_helpers_detect_midnight_crossing():
    assert duration_crosses_midnight(date(2026, 7, 1), time(23, 30), 60) is True


def test_planner_date_selection_and_inline_edit(monkeypatch):
    from streamlit.testing.v1 import AppTest

    from src.database import db

    monkeypatch.setattr(db, "engine", None)
    today = date.today()
    clicked_date = today + timedelta(days=1)
    app = AppTest.from_file(APP_PATH).run()
    next(button for button in app.button if button.label == "Try live demo").click().run()
    clicked_day_key = f"planner_day_{clicked_date.isoformat()}"
    if clicked_day_key not in {button.key for button in app.button}:
        app.button(key="planner_next_month").click().run()
    app.button(key=clicked_day_key).click().run()
    assert app.date_input(key="planner_manage_date").value == clicked_date
    assert any("Pick up groceries" in item.proto.body for item in app.get("html"))

    edit = next(button for button in app.button if button.label == "Edit" and button.key.startswith("agenda_"))
    edit.click().run()
    next(widget for widget in app.text_input if widget.label == "Title").set_value("Buy produce")
    next(button for button in app.button if button.label == "Save changes").click().run()
    assert any("<h3>Buy produce</h3>" in item.proto.body for item in app.get("html"))

    app.date_input(key="planner_manage_date").set_value(today).run()
    next(button for button in app.button if button.label == "Add item").click().run()
    assert not app.exception
    assert app.date_input(key="planner_manage_date").value == today
    assert app.date_input(key="plan_date").value == today
    assert set(app.selectbox(key="plan_category").options) == {name for name, _ in DEFAULT_CATEGORIES}


def test_reset_demo_restores_checkins_and_keeps_the_theme(monkeypatch):
    from streamlit.testing.v1 import AppTest

    from src.database import db

    monkeypatch.setattr(db, "engine", None)
    app = AppTest.from_file(APP_PATH).run()
    next(button for button in app.button if button.label == "Try live demo").click().run()
    engine = app.session_state[DEMO_STATE]
    app.toggle(key="hq_dark_mode").set_value(True).run()
    next(button for button in app.button if button.label == "Complete").click().run()
    assert "completed" in app.success[0].value
    app.run()
    assert app.session_state[DEMO_STATE] is engine
    assert sum(button.label == "Reset" for button in app.button) == 2
    app.session_state["demo_avatar"] = b"example avatar"

    app.sidebar.button(key="reset_demo").click().run()

    assert not app.exception
    assert app.session_state[DEMO_STATE] is not engine
    assert sum(button.label == "Reset" for button in app.button) == 1
    assert "demo_avatar" not in app.session_state
    assert app.toggle(key="hq_dark_mode").value is True


def test_app_offers_demo_when_postgresql_is_missing(monkeypatch):
    from streamlit.testing.v1 import AppTest

    from src.database import db

    monkeypatch.setattr(db, "engine", None)
    app = AppTest.from_file(APP_PATH).run()

    assert not app.exception
    assert [button.label for button in app.button] == ["Try live demo"]
    assert not app.sidebar.get("page_link")


def test_app_offers_google_or_demo_before_showing_navigation(monkeypatch):
    import streamlit as st
    from streamlit.testing.v1 import AppTest
    from src.database import db

    monkeypatch.setattr(db, "engine", object())
    monkeypatch.setattr(st, "user", {"is_logged_in": False})
    app = AppTest.from_file(APP_PATH)
    app.secrets["auth"] = {
        "redirect_uri": "http://localhost:8501/oauth2callback",
        "cookie_secret": "test-only",
        "client_id": "test-only",
        "client_secret": "test-only",
        "server_metadata_url": "https://accounts.google.com/.well-known/openid-configuration",
    }
    app.run()

    assert not app.exception
    assert [button.label for button in app.button] == ["Try live demo", "Log in with Google"]
    assert not app.sidebar.get("page_link")


def test_loading_screen_follows_page_navigation(monkeypatch, streamlit_navigation):
    from contextlib import contextmanager

    import streamlit as st
    from sqlalchemy.pool import StaticPool
    from streamlit.testing.v1 import AppTest

    from app.components import loading_screen as loading_component
    from src.database import db
    from src.database.models import Base
    from src.services import quest_service

    loads = []
    show_loading = loading_component.loading_screen
    @contextmanager
    def track_loading(title, *, enabled):
        if enabled:
            loads.append(title)
        with show_loading(title, enabled=enabled):
            yield

    monkeypatch.setattr(loading_component, "loading_screen", track_loading)
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    monkeypatch.setattr(db, "engine", engine)
    monkeypatch.setattr(st, "user", {
        "is_logged_in": True,
        "iss": "https://accounts.google.com",
        "sub": "loading-test",
        "email": "loading@example.com",
        "email_verified": True,
    })

    try:
        app = AppTest.from_file(APP_PATH).run()
        app.toggle(key="hq_dark_mode").set_value(True).run()
        assert not app.exception
        assert all(button.label != "Reset demo" for button in app.sidebar.button)
        assert loads == ["Loading Planner"]

        app.switch_page("pages/1_Dashboard.py").run()
        assert not app.exception
        assert loads == ["Loading Planner", "Loading Summary"]
        assert all('class="hq-loading-screen"' not in item.proto.body for item in app.get("html"))

        with monkeypatch.context() as patch:
            patch.setattr(quest_service, "get_categories", lambda: [])
            app.switch_page("pages/5_Projects_and_Routines.py").run()
            assert not app.exception
            assert app.warning[0].value == "Run python -m src.database.seed to create default categories."

        app.switch_page("pages/2_Quest_Log.py").run()
        assert not app.exception
        assert loads == ["Loading Planner", "Loading Summary", "Loading Projects & Routines", "Loading Planner"]
    finally:
        engine.dispose()

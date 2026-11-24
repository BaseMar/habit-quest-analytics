from datetime import date, datetime, time, timedelta
from pathlib import Path

import pytest
from sqlalchemy import create_engine

from app.components.checkin_actions import get_checkin_status_actions
from app.components.scheduling import duration_crosses_midnight, end_at_for_duration


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


def test_planner_add_item_uses_manually_selected_day_after_calendar_click(tmp_path, monkeypatch):
    pytest.importorskip("streamlit", minversion="1.66.1")
    from streamlit.testing.v1 import AppTest
    import streamlit as st
    import streamlit_calendar

    from src.database import db
    from src.database.models import Base

    db_path = tmp_path / "planner.db"
    db_url = f"sqlite:///{db_path.as_posix()}"
    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    monkeypatch.setattr(db, "engine", engine)
    monkeypatch.setattr(st, "user", {
        "is_logged_in": True,
        "iss": "https://accounts.google.com",
        "sub": "planner-test",
        "email": "planner@example.com",
        "email_verified": True,
    })

    clicked_date = date.today() - timedelta(days=1)
    manual_date = date.today() + timedelta(days=1)
    original_calendar_key = None

    def calendar_with_previous_click(*, key, **_):
        nonlocal original_calendar_key
        original_calendar_key = original_calendar_key or key
        if key == original_calendar_key:
            return {"dateClick": {"dateStr": clicked_date.isoformat()}}
        return {}

    monkeypatch.setattr(streamlit_calendar, "calendar", calendar_with_previous_click)
    try:
        main = Path(__file__).resolve().parents[1] / "app" / "main.py"
        app = AppTest.from_file(str(main)).run().switch_page("pages/2_Quest_Log.py").run()
        assert app.date_input(key="planner_manage_date").value == clicked_date

        app.date_input(key="planner_manage_date").set_value(manual_date).run()
        next(button for button in app.button if button.label == "Add item").click().run()

        assert not app.exception
        assert app.date_input(key="planner_manage_date").value == manual_date
        assert app.date_input(key="plan_date").value == manual_date
    finally:
        engine.dispose()


def test_app_explains_how_to_configure_postgresql_when_url_is_missing(monkeypatch):
    pytest.importorskip("streamlit", minversion="1.66.1")
    from streamlit.testing.v1 import AppTest

    from src.database import db

    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(db, "engine", None)
    main = Path(__file__).resolve().parents[1] / "app" / "main.py"

    app = AppTest.from_file(str(main)).run()

    assert not app.exception
    assert "DATABASE_URL" in app.error[0].value


def test_app_requires_login_before_showing_navigation(monkeypatch):
    import streamlit as st
    from streamlit.testing.v1 import AppTest
    from src.database import db

    monkeypatch.setattr(db, "engine", object())
    monkeypatch.setattr(st, "user", {"is_logged_in": False})
    main = Path(__file__).resolve().parents[1] / "app" / "main.py"
    app = AppTest.from_file(str(main))
    app.secrets["auth"] = {
        "redirect_uri": "http://localhost:8501/oauth2callback",
        "cookie_secret": "test-only",
        "client_id": "test-only",
        "client_secret": "test-only",
        "server_metadata_url": "https://accounts.google.com/.well-known/openid-configuration",
    }
    app.run()

    assert not app.exception
    assert [button.label for button in app.button] == ["Log in with Google"]
    assert not app.sidebar.get("page_link")


def test_loading_screen_follows_page_navigation(monkeypatch):
    from contextlib import contextmanager

    import streamlit as st
    from sqlalchemy.pool import StaticPool
    from streamlit.runtime.pages_manager import PagesManager
    from streamlit.testing.v1 import AppTest

    from app.components import loading_screen as loading_component
    from src.database import db
    from src.database.models import Base
    from src.services import quest_service

    loads = []
    show_loading = loading_component.loading_screen
    initialize_pages = PagesManager.__init__

    def initialize_navigation(*args, **kwargs):
        # AppTest resets this flag on every run. A live st.navigation session keeps it false.
        PagesManager.uses_pages_directory = False
        initialize_pages(*args, **kwargs)

    @contextmanager
    def track_loading(title, *, enabled):
        if enabled:
            loads.append(title)
        with show_loading(title, enabled=enabled):
            yield

    monkeypatch.setattr(loading_component, "loading_screen", track_loading)
    monkeypatch.setattr(PagesManager, "__init__", initialize_navigation)
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

    main = Path(__file__).resolve().parents[1] / "app" / "main.py"
    try:
        app = AppTest.from_file(str(main)).run()
        app.toggle(key="hq_dark_mode").set_value(True).run()
        assert not app.exception
        assert loads == ["Loading Command Center"]

        app.switch_page("pages/2_Quest_Log.py").run()
        assert not app.exception
        assert loads == ["Loading Command Center", "Loading Planner"]
        assert all('class="hq-loading-screen"' not in item.proto.body for item in app.get("html"))

        with monkeypatch.context() as patch:
            patch.setattr(quest_service, "get_categories", lambda: [])
            app.switch_page("pages/5_Projects_and_Routines.py").run()
            assert not app.exception
            assert app.warning[0].value == "Run python -m src.database.seed to create default categories."

        app.switch_page("pages/2_Quest_Log.py").run()
        assert not app.exception
        assert loads == ["Loading Command Center", "Loading Planner", "Loading Projects & Routines", "Loading Planner"]
    finally:
        engine.dispose()

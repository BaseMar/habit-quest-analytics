from datetime import date, datetime, time, timedelta
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

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
    import streamlit_calendar

    from src.database import db

    db_path = tmp_path / "planner.db"
    db_url = f"sqlite:///{db_path.as_posix()}"
    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    monkeypatch.setattr(db, "DEFAULT_DATABASE_PATH", db_path)
    monkeypatch.setattr(db, "DATABASE_URL", db_url)
    monkeypatch.setattr(db, "engine", engine)
    monkeypatch.setattr(db, "SessionLocal", sessionmaker(bind=engine))

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

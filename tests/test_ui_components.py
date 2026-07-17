from datetime import date, datetime, time

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

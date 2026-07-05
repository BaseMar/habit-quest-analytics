import pytest

from src.services.xp_service import (
    calculate_character_level,
    calculate_level,
    calculate_time_based_xp,
    calculate_xp,
    get_character_level_progress,
    total_xp_for_level,
    xp_to_next_level,
)


@pytest.mark.parametrize(
    ("difficulty", "expected_xp"),
    [
        ("Easy", 10),
        ("Medium", 30),
        ("Hard", 75),
        ("Boss", 150),
        (" easy ", 10),
    ],
)
def test_calculate_xp_by_difficulty(difficulty, expected_xp):
    assert calculate_xp(difficulty) == expected_xp


@pytest.mark.parametrize(
    ("planned_minutes", "expected_xp"),
    [
        (15, 5),
        (30, 10),
        (60, 20),
        (90, 30),
        (120, 40),
        (180, 60),
    ],
)
def test_calculate_time_based_xp(planned_minutes, expected_xp):
    assert calculate_time_based_xp(planned_minutes) == expected_xp


def test_calculate_time_based_xp_uses_minimum_xp():
    assert calculate_time_based_xp(1) == 5


@pytest.mark.parametrize("planned_minutes", [0, -1, None, ""])
def test_calculate_time_based_xp_rejects_invalid_planned_minutes(planned_minutes):
    with pytest.raises(ValueError, match="Planned minutes"):
        calculate_time_based_xp(planned_minutes)


@pytest.mark.parametrize(
    ("level", "expected_total_xp"),
    [
        (1, 0),
        (2, 100),
        (3, 264),
        (10, 2167),
    ],
)
def test_total_xp_for_level(level, expected_total_xp):
    assert total_xp_for_level(level) == expected_total_xp


@pytest.mark.parametrize(
    ("level", "expected_xp_to_next_level"),
    [
        (1, 100),
        (2, 164),
    ],
)
def test_xp_to_next_level(level, expected_xp_to_next_level):
    assert xp_to_next_level(level) == expected_xp_to_next_level


@pytest.mark.parametrize(
    ("total_xp", "expected_level"),
    [
        (0, 1),
        (99, 1),
        (100, 2),
        (263, 2),
        (264, 3),
    ],
)
def test_calculate_level(total_xp, expected_level):
    assert calculate_level(total_xp) == expected_level
    assert calculate_character_level(total_xp) == expected_level


@pytest.mark.parametrize(
    ("total_xp", "expected_progress"),
    [
        (
            0,
            {
                "level": 1,
                "total_xp": 0,
                "current_level_total_xp": 0,
                "next_level_total_xp": 100,
                "xp_into_current_level": 0,
                "xp_needed_for_next_level": 100,
                "xp_remaining_to_next_level": 100,
                "progress_percent": 0,
            },
        ),
        (
            50,
            {
                "level": 1,
                "total_xp": 50,
                "current_level_total_xp": 0,
                "next_level_total_xp": 100,
                "xp_into_current_level": 50,
                "xp_needed_for_next_level": 100,
                "xp_remaining_to_next_level": 50,
                "progress_percent": 50,
            },
        ),
        (
            100,
            {
                "level": 2,
                "total_xp": 100,
                "current_level_total_xp": 100,
                "next_level_total_xp": 264,
                "xp_into_current_level": 0,
                "xp_needed_for_next_level": 164,
                "xp_remaining_to_next_level": 164,
                "progress_percent": 0,
            },
        ),
        (
            182,
            {
                "level": 2,
                "total_xp": 182,
                "current_level_total_xp": 100,
                "next_level_total_xp": 264,
                "xp_into_current_level": 82,
                "xp_needed_for_next_level": 164,
                "xp_remaining_to_next_level": 82,
                "progress_percent": 50,
            },
        ),
    ],
)
def test_get_character_level_progress(total_xp, expected_progress):
    assert get_character_level_progress(total_xp) == expected_progress


def test_calculate_xp_rejects_unknown_difficulty():
    with pytest.raises(ValueError):
        calculate_xp("Legendary")


def test_calculate_level_rejects_negative_xp():
    with pytest.raises(ValueError):
        calculate_level(-1)


def test_level_helpers_reject_invalid_values():
    with pytest.raises(ValueError):
        total_xp_for_level(0)
    with pytest.raises(ValueError):
        xp_to_next_level(0)
    with pytest.raises(ValueError):
        get_character_level_progress(-1)

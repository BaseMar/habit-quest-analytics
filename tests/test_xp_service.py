import pytest

from src.services.xp_service import calculate_level, calculate_time_based_xp, calculate_xp


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
    ("total_xp", "expected_level"),
    [
        (0, 1),
        (499, 1),
        (500, 2),
        (999, 2),
        (1000, 3),
    ],
)
def test_calculate_level(total_xp, expected_level):
    assert calculate_level(total_xp) == expected_level


def test_calculate_xp_rejects_unknown_difficulty():
    with pytest.raises(ValueError):
        calculate_xp("Legendary")


def test_calculate_level_rejects_negative_xp():
    with pytest.raises(ValueError):
        calculate_level(-1)

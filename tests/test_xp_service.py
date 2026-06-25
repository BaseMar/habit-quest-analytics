import pytest

from src.services.xp_service import calculate_level, calculate_xp


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

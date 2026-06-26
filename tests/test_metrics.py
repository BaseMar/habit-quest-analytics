import pytest

from src.analysis.metrics import (
    calculate_completion_rate,
    calculate_consistency_score,
    calculate_xp_to_next_level,
)


def test_calculate_completion_rate():
    assert calculate_completion_rate(3, 4) == 75.0


def test_calculate_completion_rate_without_quests():
    assert calculate_completion_rate(0, 0) == 0.0


def test_calculate_consistency_score():
    assert calculate_consistency_score(5, 7) == 71.43


def test_calculate_consistency_score_without_tracked_days():
    assert calculate_consistency_score(0, 0) == 0.0


@pytest.mark.parametrize(
    ("total_xp", "expected"),
    [
        (0, 500),
        (1, 499),
        (499, 1),
        (500, 500),
        (875, 125),
    ],
)
def test_calculate_xp_to_next_level(total_xp, expected):
    assert calculate_xp_to_next_level(total_xp) == expected


def test_calculate_xp_to_next_level_rejects_negative_xp():
    with pytest.raises(ValueError):
        calculate_xp_to_next_level(-1)

from src.analysis.metrics import calculate_completion_rate, calculate_consistency_score


def test_calculate_completion_rate():
    assert calculate_completion_rate(3, 4) == 75.0


def test_calculate_completion_rate_without_quests():
    assert calculate_completion_rate(0, 0) == 0.0


def test_calculate_consistency_score():
    assert calculate_consistency_score(5, 7) == 71.43


def test_calculate_consistency_score_without_tracked_days():
    assert calculate_consistency_score(0, 0) == 0.0

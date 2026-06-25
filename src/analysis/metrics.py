def calculate_completion_rate(completed_count: int, total_count: int) -> float:
    """Return the completion rate as a percentage."""
    if total_count <= 0:
        return 0.0

    return round((completed_count / total_count) * 100, 2)


def calculate_consistency_score(completed_days: int, tracked_days: int) -> float:
    """Return habit consistency as a percentage of completed tracked days."""
    if tracked_days <= 0:
        return 0.0

    return round((completed_days / tracked_days) * 100, 2)

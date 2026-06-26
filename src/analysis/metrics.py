def calculate_completion_rate(completed_count: int, total_count: int) -> float:
    """Return the completion rate as a percentage."""
    if total_count <= 0:
        return 0.0

    return round((completed_count / total_count) * 100, 2)


def calculate_xp_to_next_level(total_xp: int) -> int:
    """Return XP needed to reach the next 500 XP level boundary."""
    if total_xp < 0:
        raise ValueError("Total XP cannot be negative.")

    remainder = total_xp % 500
    return 500 if remainder == 0 else 500 - remainder


def calculate_consistency_score(completed_days: int, tracked_days: int) -> float:
    """Return habit consistency as a percentage of completed tracked days."""
    if tracked_days <= 0:
        return 0.0

    return round((completed_days / tracked_days) * 100, 2)

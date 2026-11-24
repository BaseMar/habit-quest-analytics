from collections.abc import Iterable
from datetime import date

from src.services.xp_service import get_character_level_progress


def calculate_completion_rate(completed_count: int, total_count: int) -> float:
    """Return the completion rate as a percentage."""
    if total_count <= 0:
        return 0.0

    return round((completed_count / total_count) * 100, 2)


def calculate_xp_to_next_level(total_xp: int) -> int:
    """Return XP remaining to reach the next nonlinear character level."""
    return get_character_level_progress(total_xp)["xp_remaining_to_next_level"]


def calculate_consistency_score(completed_days: int, tracked_days: int) -> float:
    """Return habit consistency as a percentage of completed tracked days."""
    if tracked_days <= 0:
        return 0.0

    return round((completed_days / tracked_days) * 100, 2)


def calculate_routine_streaks(
    occurrences: Iterable[tuple[date, str]], today: date
) -> tuple[int, int]:
    """Return the current and best streak from scheduled occurrences in date order."""
    current = best = 0
    for scheduled_date, status in occurrences:
        if scheduled_date > today:
            break
        if status == "Completed":
            current += 1
            best = max(best, current)
        elif status != "Planned" or scheduled_date < today:
            current = 0
    return current, best

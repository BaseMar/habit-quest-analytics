DIFFICULTY_XP = {
    "easy": 10,
    "medium": 30,
    "hard": 75,
    "boss": 150,
}


def calculate_xp(difficulty: str) -> int:
    """Return XP for a quest difficulty."""
    if not difficulty:
        raise ValueError("Difficulty is required.")

    key = difficulty.strip().lower()
    if key not in DIFFICULTY_XP:
        valid = ", ".join(sorted(DIFFICULTY_XP))
        raise ValueError(f"Unknown difficulty '{difficulty}'. Valid values: {valid}.")

    return DIFFICULTY_XP[key]


def calculate_time_based_xp(planned_minutes: int) -> int:
    """Return XP from planned work duration."""
    try:
        minutes = int(planned_minutes)
    except (TypeError, ValueError) as error:
        raise ValueError("Planned minutes must be a positive integer.") from error

    if minutes <= 0:
        raise ValueError("Planned minutes must be greater than 0.")

    return max(5, round(minutes / 60 * 20))


def calculate_level(total_xp: int) -> int:
    """Calculate player level from total XP."""
    if total_xp < 0:
        raise ValueError("Total XP cannot be negative.")

    return total_xp // 500 + 1

DIFFICULTY_XP = {
    "easy": 10,
    "medium": 30,
    "hard": 75,
    "boss": 150,
}
CHARACTER_LEVEL_BASE_XP = 100
CHARACTER_LEVEL_EXPONENT = 1.4


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
    return calculate_character_level(total_xp)


def total_xp_for_level(level: int) -> int:
    """Return cumulative XP required to reach a character level."""
    if level < 1:
        raise ValueError("Level must be at least 1.")
    if level == 1:
        return 0

    return round(CHARACTER_LEVEL_BASE_XP * ((level - 1) ** CHARACTER_LEVEL_EXPONENT))


def xp_to_next_level(level: int) -> int:
    """Return XP required to move from level to the next level."""
    if level < 1:
        raise ValueError("Level must be at least 1.")

    return total_xp_for_level(level + 1) - total_xp_for_level(level)


def calculate_character_level(total_xp: int) -> int:
    """Return the highest character level reached by total awarded XP."""
    if total_xp < 0:
        raise ValueError("Total XP cannot be negative.")

    level = 1
    while total_xp >= total_xp_for_level(level + 1):
        level += 1
    return level


def get_character_level_progress(total_xp: int) -> dict:
    """Return nonlinear character level progress details."""
    if total_xp < 0:
        raise ValueError("Total XP cannot be negative.")

    level = calculate_character_level(total_xp)
    current_level_total_xp = total_xp_for_level(level)
    next_level_total_xp = total_xp_for_level(level + 1)
    xp_needed_for_next_level = next_level_total_xp - current_level_total_xp
    xp_into_current_level = total_xp - current_level_total_xp
    xp_remaining_to_next_level = next_level_total_xp - total_xp
    progress_percent = round((xp_into_current_level / xp_needed_for_next_level) * 100, 2)

    return {
        "level": level,
        "total_xp": total_xp,
        "current_level_total_xp": current_level_total_xp,
        "next_level_total_xp": next_level_total_xp,
        "xp_into_current_level": xp_into_current_level,
        "xp_needed_for_next_level": xp_needed_for_next_level,
        "xp_remaining_to_next_level": xp_remaining_to_next_level,
        "progress_percent": progress_percent,
    }

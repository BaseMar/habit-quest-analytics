from src.services.xp_service import calculate_xp


def get_quest_xp_reward(difficulty: str) -> int:
    """Return the XP reward for a quest difficulty."""
    return calculate_xp(difficulty)

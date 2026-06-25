import pandas as pd

from src.analysis.metrics import calculate_completion_rate


def build_quest_summary(quests: pd.DataFrame) -> dict:
    """Build a small summary from a quest dataframe."""
    if quests.empty:
        return {"total": 0, "completed": 0, "completion_rate": 0.0}

    completed = int((quests["status"] == "completed").sum())
    total = int(len(quests))

    return {
        "total": total,
        "completed": completed,
        "completion_rate": calculate_completion_rate(completed, total),
    }

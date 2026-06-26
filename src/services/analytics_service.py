from datetime import date, datetime, time, timedelta

import pandas as pd

from src.analysis.metrics import calculate_completion_rate, calculate_xp_to_next_level
from src.database.db import get_session
from src.database.models import Quest
from src.services.xp_service import calculate_level


def build_quest_summary(quests: pd.DataFrame) -> dict:
    """Build a small summary from a quest dataframe."""
    if quests.empty:
        return {"total": 0, "completed": 0, "completion_rate": 0.0}

    completed = int((quests["status"].str.lower() == "completed").sum())
    total = int(len(quests))

    return {
        "total": total,
        "completed": completed,
        "completion_rate": calculate_completion_rate(completed, total),
    }


def get_dashboard_kpis(today: date | None = None, session=None) -> dict:
    """Return dashboard KPI values based on persisted quests."""
    today = today or date.today()
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=7)
    week_start_at = datetime.combine(week_start, time.min)
    week_end_at = datetime.combine(week_end, time.min)

    owns_session = session is None
    session = session or get_session()
    try:
        quests = session.query(Quest).all()
        total_quests = len(quests)
        completed_quests = [quest for quest in quests if _is_completed(quest)]
        completed_count = len(completed_quests)
        total_xp = sum(quest.xp_reward or 0 for quest in completed_quests)
        weekly_xp = sum(
            quest.xp_reward or 0
            for quest in completed_quests
            if quest.completed_at is not None and week_start_at <= quest.completed_at < week_end_at
        )

        return {
            "total_quests": total_quests,
            "completed_quests": completed_count,
            "completion_rate": calculate_completion_rate(completed_count, total_quests),
            "total_xp": total_xp,
            "weekly_xp": weekly_xp,
            "current_level": calculate_level(total_xp),
            "xp_to_next_level": calculate_xp_to_next_level(total_xp),
        }
    finally:
        if owns_session:
            session.close()


def _is_completed(quest: Quest) -> bool:
    return (quest.status or "").strip().lower() == "completed"

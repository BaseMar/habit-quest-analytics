from datetime import date, datetime, time, timedelta

import pandas as pd
from sqlalchemy import and_, or_
from sqlalchemy.orm import joinedload

from src.analysis.metrics import calculate_completion_rate, calculate_xp_to_next_level
from src.constants import CATEGORY_TO_RPG_STAT, QUEST_STATUSES, RPG_STATS
from src.database.db import get_session
from src.database.models import Goal, PlayerProfile, Quest, QuestCheckin
from src.services.checklist_service import ensure_checkin
from src.services.goal_service import get_goal_progress
from src.services.xp_service import calculate_level, get_character_level_progress, get_stat_level_progress

STATUS_ORDER = QUEST_STATUSES
DEFAULT_GOAL_ANALYTICS_STATUSES = ("Active", "Completed")
GOAL_ANALYTICS_STATUSES = ("Active", "Completed", "Archived")


def build_quest_summary(quests: pd.DataFrame) -> dict:
    """Build a small summary from a quest dataframe."""
    if quests.empty or "status" not in quests:
        return {"total": 0, "completed": 0, "completion_rate": 0.0}

    completed = int((quests["status"].fillna("").str.lower() == "completed").sum())
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


def get_command_center_data(today: date | None = None, session=None) -> dict:
    """Return operational check-in metrics for the Command Center page."""
    today = today or date.today()
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=7)

    owns_session = session is None
    session = session or get_session()
    try:
        _ensure_legacy_command_center_checkins(session, today)

        quests = session.query(Quest).all()
        relevant_checkins = (
            session.query(QuestCheckin)
            .options(joinedload(QuestCheckin.quest).joinedload(Quest.category))
            .filter(QuestCheckin.checkin_date <= today)
            .all()
        )
        today_checkins = [checkin for checkin in relevant_checkins if checkin.checkin_date == today]
        weekly_checkins = [
            checkin
            for checkin in relevant_checkins
            if week_start <= checkin.checkin_date < week_end
        ]

        planned_today = [
            checkin
            for checkin in today_checkins
            if _normalize_status(checkin.status) == "Planned"
        ]
        completed_today = [
            checkin
            for checkin in today_checkins
            if _normalize_status(checkin.status) == "Completed"
        ]
        overdue_checkins = [
            checkin
            for checkin in relevant_checkins
            if checkin.checkin_date < today and _normalize_status(checkin.status) == "Planned"
        ]
        failed_checkins = [
            checkin
            for checkin in relevant_checkins
            if _normalize_status(checkin.status) == "Failed"
        ]
        skipped_checkins = [
            checkin
            for checkin in relevant_checkins
            if _normalize_status(checkin.status) == "Skipped"
        ]
        completed_checkins = [
            checkin
            for checkin in relevant_checkins
            if _normalize_status(checkin.status) == "Completed"
        ]
        completed_this_week = sum(
            1 for checkin in weekly_checkins if _normalize_status(checkin.status) == "Completed"
        )
        failed_this_week = sum(
            1 for checkin in weekly_checkins if _normalize_status(checkin.status) == "Failed"
        )
        weekly_xp = sum(
            _checkin_xp(checkin)
            for checkin in weekly_checkins
            if _normalize_status(checkin.status) == "Completed"
        )
        status_counts = {
            "Planned": len(planned_today),
            "Completed": len(completed_today),
            "Failed": len(failed_checkins),
            "Skipped": len(skipped_checkins),
        }

        return {
            "has_quests": bool(quests or relevant_checkins),
            "total_quests": len(relevant_checkins),
            "completed_quests": len(completed_checkins),
            "planned_quests": len(planned_today),
            "due_today": len(today_checkins),
            "overdue_quests": len(overdue_checkins),
            "completed_today": len(completed_today),
            "failed_quests": len(failed_checkins),
            "skipped_quests": len(skipped_checkins),
            "completion_rate": calculate_completion_rate(len(completed_checkins), len(relevant_checkins)),
            "weekly_xp": weekly_xp,
            "completed_this_week": completed_this_week,
            "failed_this_week": failed_this_week,
            "total_quests_this_week": len(weekly_checkins),
            "weekly_completion_rate": calculate_completion_rate(completed_this_week, len(weekly_checkins)),
            "status_counts": status_counts,
            "today_quests": build_today_focus_rows(today_checkins),
            "today_work_items": build_operational_checkin_rows(today_checkins),
            "attention_items": build_operational_checkin_rows(overdue_checkins),
        }
    finally:
        if owns_session:
            session.close()


def get_command_center_items_for_date(review_date: date, session=None) -> list[dict]:
    """Return action-ready check-ins for a single Command Center review date."""
    owns_session = session is None
    session = session or get_session()
    try:
        _ensure_legacy_command_center_checkins(session, date.today())
        checkins = (
            session.query(QuestCheckin)
            .options(joinedload(QuestCheckin.quest).joinedload(Quest.category))
            .filter(QuestCheckin.checkin_date == review_date)
            .all()
        )
        return build_operational_checkin_rows(checkins)
    finally:
        if owns_session:
            session.close()


def get_habit_analytics_data(today: date | None = None, session=None) -> dict:
    """Return prepared dataframes for the Habit Analytics page."""
    today = today or date.today()
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=7)
    week_start_at = datetime.combine(week_start, time.min)
    week_end_at = datetime.combine(week_end, time.min)

    owns_session = session is None
    session = session or get_session()
    try:
        quests = session.query(Quest).options(joinedload(Quest.category)).all()
        checkins = (
            session.query(QuestCheckin)
            .options(joinedload(QuestCheckin.quest).joinedload(Quest.category))
            .all()
        )
        if checkins:
            weekly_checkins = [
                checkin
                for checkin in checkins
                if week_start <= checkin.checkin_date < week_end
            ]
            completed_this_week = sum(
                1 for checkin in weekly_checkins if _normalize_status(checkin.status) == "Completed"
            )
            failed_this_week = sum(
                1 for checkin in weekly_checkins if _normalize_status(checkin.status) == "Failed"
            )
            resolved_this_week = completed_this_week + failed_this_week
            return {
                "has_quests": True,
                "weekly_pulse": {
                    "weekly_xp": sum(checkin.xp_awarded or 0 for checkin in weekly_checkins),
                    "completed_this_week": completed_this_week,
                    "failed_this_week": failed_this_week,
                    "weekly_completion_rate": calculate_completion_rate(completed_this_week, resolved_this_week),
                },
                "xp_by_day": build_xp_by_day_from_checkins(checkins),
                "quests_by_status": build_checkins_by_status(checkins),
                "quests_by_category": build_checkins_by_category(checkins),
                "completed_checkins_by_category": build_checkins_by_category(completed_checkins_from(checkins)),
                "completion_rate_by_weekday": build_completion_rate_by_weekday_from_checkins(checkins),
                "estimated_minutes_by_category": build_planned_minutes_by_category_from_checkins(checkins),
            }

        weekly_quests = build_quests_in_week(quests, week_start_at, week_end_at)
        completed_this_week = sum(1 for quest in weekly_quests if _is_completed(quest))
        failed_this_week = sum(1 for quest in weekly_quests if _normalize_status(quest.status) == "Failed")
        return {
            "has_quests": bool(quests),
            "weekly_pulse": {
                "weekly_xp": sum(quest.xp_reward or 0 for quest in weekly_quests if _is_completed(quest)),
                "completed_this_week": completed_this_week,
                "failed_this_week": failed_this_week,
                "weekly_completion_rate": calculate_completion_rate(completed_this_week, len(weekly_quests)),
            },
            "xp_by_day": build_xp_by_day(quests),
            "quests_by_status": build_quests_by_status(quests),
            "quests_by_category": build_quests_by_category(quests),
            "completion_rate_by_weekday": build_completion_rate_by_weekday(quests),
            "estimated_minutes_by_category": build_estimated_minutes_by_category(quests),
        }
    finally:
        if owns_session:
            session.close()


def get_goal_analytics_summary(
    statuses: list[str] | tuple[str, ...] | str | None = None,
    category_id: int | None = None,
    session=None,
) -> dict:
    """Return KPI and table-ready goal analytics derived from linked quest check-ins."""
    owns_session = session is None
    session = session or get_session()
    try:
        goals = _get_filtered_goals(session, statuses=statuses, category_id=category_id)
        rows = _build_goal_progress_rows(goals, session=session)

        planned_effort_minutes = sum(row["Planned Minutes"] for row in rows)
        completed_effort_minutes = sum(row["Completed Minutes"] for row in rows)
        overall_progress = _bounded_percent(completed_effort_minutes, planned_effort_minutes)

        return {
            "has_goals": bool(session.query(Goal.id).first()),
            "included_goals_count": len(rows),
            "active_goals": sum(1 for row in rows if row["Status"] == "Active"),
            "completed_goals": sum(1 for row in rows if row["Status"] == "Completed"),
            "archived_goals": sum(1 for row in rows if row["Status"] == "Archived"),
            "planned_effort_minutes": planned_effort_minutes,
            "completed_effort_minutes": completed_effort_minutes,
            "remaining_effort_minutes": sum(row["Remaining Minutes"] for row in rows),
            "overall_progress_percent": overall_progress,
            "goal_xp_earned": sum(row["Earned XP"] for row in rows),
            "expected_total_xp": sum(row["Expected Total XP"] for row in rows),
            "linked_sessions_count": sum(row["Linked Sessions"] for row in rows),
            "completed_sessions_count": sum(row["Completed Sessions"] for row in rows),
            "planned_sessions_count": sum(row["Planned Sessions"] for row in rows),
            "skipped_sessions_count": sum(row["Skipped Sessions"] for row in rows),
            "failed_sessions_count": sum(row["Failed Sessions"] for row in rows),
            "goal_rows": rows,
            "goal_table": pd.DataFrame(rows),
        }
    finally:
        if owns_session:
            session.close()


def get_goal_progress_dataset(
    statuses: list[str] | tuple[str, ...] | str | None = None,
    category_id: int | None = None,
    session=None,
) -> pd.DataFrame:
    """Return per-goal completed and remaining effort rows for comparison charts."""
    summary = get_goal_analytics_summary(statuses=statuses, category_id=category_id, session=session)
    rows = []
    for row in summary["goal_rows"]:
        rows.append(
            {
                "Goal ID": row["Goal ID"],
                "Goal": row["Goal"],
                "Status": row["Status"],
                "Category": row["Category"],
                "Completed Effort": row["Completed Minutes"],
                "Remaining Effort": row["Remaining Minutes"],
                "Progress Percent": row["Progress Percent"],
            }
        )
    if not rows:
        return pd.DataFrame(
            columns=[
                "Goal ID",
                "Goal",
                "Status",
                "Category",
                "Completed Effort",
                "Remaining Effort",
                "Progress Percent",
            ]
        )
    return (
        pd.DataFrame(rows)
        .sort_values(["Progress Percent", "Completed Effort", "Goal"], ascending=[False, False, True])
        .reset_index(drop=True)
    )


def get_goal_session_status_dataset(
    statuses: list[str] | tuple[str, ...] | str | None = None,
    category_id: int | None = None,
    session=None,
) -> pd.DataFrame:
    """Return linked goal session status counts for charting."""
    summary = get_goal_analytics_summary(statuses=statuses, category_id=category_id, session=session)
    rows = []
    for row in summary["goal_rows"]:
        rows.extend(
            [
                {"Goal": row["Goal"], "Status": "Completed", "Count": row["Completed Sessions"]},
                {"Goal": row["Goal"], "Status": "Planned", "Count": row["Planned Sessions"]},
                {"Goal": row["Goal"], "Status": "Skipped", "Count": row["Skipped Sessions"]},
                {"Goal": row["Goal"], "Status": "Failed", "Count": row["Failed Sessions"]},
            ]
        )
    return pd.DataFrame(rows, columns=["Goal", "Status", "Count"])


def get_goal_completed_minutes_by_week(
    statuses: list[str] | tuple[str, ...] | str | None = None,
    category_id: int | None = None,
    session=None,
) -> pd.DataFrame:
    """Return completed linked goal effort grouped by check-in week."""
    owns_session = session is None
    session = session or get_session()
    try:
        goals = _get_filtered_goals(session, statuses=statuses, category_id=category_id)
        goal_ids = [goal.id for goal in goals]
        if not goal_ids:
            return pd.DataFrame(columns=["Week", "Completed Minutes"])

        checkins = (
            session.query(QuestCheckin)
            .options(joinedload(QuestCheckin.quest))
            .join(Quest)
            .filter(Quest.goal_id.in_(goal_ids), QuestCheckin.status == "Completed")
            .all()
        )
        rows = []
        for checkin in checkins:
            if checkin.quest is None:
                continue
            week_start = checkin.checkin_date - timedelta(days=checkin.checkin_date.weekday())
            rows.append(
                {
                    "Week": week_start,
                    "Completed Minutes": _checkin_planned_minutes(checkin),
                }
            )
        if not rows:
            return pd.DataFrame(columns=["Week", "Completed Minutes"])
        return (
            pd.DataFrame(rows)
            .groupby("Week", as_index=False)["Completed Minutes"]
            .sum()
            .sort_values("Week")
            .reset_index(drop=True)
        )
    finally:
        if owns_session:
            session.close()


def get_character_profile_data(today: date | None = None, session=None) -> dict:
    """Return character progression data based on completed check-ins."""
    today = today or date.today()
    owns_session = session is None
    session = session or get_session()
    try:
        quests = session.query(Quest).options(joinedload(Quest.category)).all()
        checkins = (
            session.query(QuestCheckin)
            .options(joinedload(QuestCheckin.quest).joinedload(Quest.category))
            .all()
        )
        player_profile = session.query(PlayerProfile).order_by(PlayerProfile.id).first()
        character_name = player_profile.character_name if player_profile else "Adventurer"
        avatar_path = player_profile.avatar_path if player_profile else None

        if checkins:
            completed_checkins = [
                checkin for checkin in checkins if _normalize_status(checkin.status) == "Completed"
            ]
            total_xp = sum(checkin.xp_awarded or 0 for checkin in checkins)
            level_progress = get_character_level_progress(total_xp)
            current_level = level_progress["level"]
            xp_to_next_level = level_progress["xp_remaining_to_next_level"]
            completion_rate = calculate_completion_rate(len(completed_checkins), len(checkins))
            weekly_xp = calculate_weekly_checkin_xp(completed_checkins, today)
            rpg_stats = build_xp_by_rpg_stat_from_checkins(completed_checkins)
            activity_stats = build_character_checkin_activity_stats(
                completed_checkins=completed_checkins,
                all_checkins=checkins,
                rpg_stats=rpg_stats,
                completion_rate=completion_rate,
                weekly_xp=weekly_xp,
            )

            return {
                "character_name": character_name,
                "character_title": calculate_character_title(current_level),
                "avatar_path": avatar_path,
                "current_level": current_level,
                "total_xp": total_xp,
                "xp_to_next_level": xp_to_next_level,
                "level_progress": level_progress["progress_percent"] / 100,
                "has_completed_quests": bool(completed_checkins),
                "completed_quests": len(completed_checkins),
                "completed_quest_days": len(completed_checkins),
                "completion_rate": completion_rate,
                "weekly_xp": weekly_xp,
                "rpg_stats": rpg_stats,
                "stat_profile": build_stat_profile_rows(rpg_stats),
                "activity_stats": activity_stats,
            }

        completed_quests = [quest for quest in quests if _is_completed(quest)]
        total_xp = sum(quest.xp_reward or 0 for quest in completed_quests)
        level_progress = get_character_level_progress(total_xp)
        current_level = level_progress["level"]
        xp_to_next_level = level_progress["xp_remaining_to_next_level"]
        completion_rate = calculate_completion_rate(len(completed_quests), len(quests))
        weekly_xp = calculate_weekly_xp(completed_quests, today)
        rpg_stats = build_xp_by_rpg_stat(completed_quests)

        return {
            "character_name": character_name,
            "character_title": calculate_character_title(current_level),
            "avatar_path": avatar_path,
            "current_level": current_level,
            "total_xp": total_xp,
            "xp_to_next_level": xp_to_next_level,
            "level_progress": level_progress["progress_percent"] / 100,
            "has_completed_quests": bool(completed_quests),
            "completed_quests": len(completed_quests),
            "completed_quest_days": len(completed_quests),
            "completion_rate": completion_rate,
            "weekly_xp": weekly_xp,
            "rpg_stats": rpg_stats,
            "stat_profile": build_stat_profile_rows(rpg_stats),
            "activity_stats": build_character_activity_stats(
                completed_quests=completed_quests,
                rpg_stats=rpg_stats,
                completion_rate=completion_rate,
                weekly_xp=weekly_xp,
            ),
        }
    finally:
        if owns_session:
            session.close()


def calculate_character_title(level: int) -> str:
    """Return the RPG title for a character level."""
    if level < 1:
        raise ValueError("Level must be at least 1.")
    if level <= 2:
        return "Novice Adventurer"
    if level <= 5:
        return "Disciplined Apprentice"
    if level <= 10:
        return "Quest Grinder"
    return "Habit Champion"


def calculate_level_progress(total_xp: int) -> float:
    """Return nonlinear progress toward the next level as a 0.0 to 1.0 value."""
    return get_character_level_progress(total_xp)["progress_percent"] / 100


def build_xp_by_rpg_stat(quests: list[Quest]) -> pd.DataFrame:
    """Return completed quest XP grouped by RPG stat."""
    totals = {stat: 0 for stat in RPG_STATS}
    for quest in quests:
        if not _is_completed(quest):
            continue
        stat = _stat_for_category(_category_name(quest))
        totals[stat] += quest.xp_reward or 0

    return build_rpg_stat_dataframe(totals)


def build_xp_by_rpg_stat_from_checkins(checkins: list[QuestCheckin]) -> pd.DataFrame:
    """Return completed check-in XP grouped by parent quest category RPG stat."""
    totals = {stat: 0 for stat in RPG_STATS}
    for checkin in checkins:
        if _normalize_status(checkin.status) != "Completed":
            continue
        if (checkin.xp_awarded or 0) <= 0:
            continue
        quest = checkin.quest
        category_name = _category_name(quest) if quest is not None else "Uncategorized"
        stat = _stat_for_category(category_name)
        totals[stat] += checkin.xp_awarded or 0

    return build_rpg_stat_dataframe(totals)


def build_rpg_stat_dataframe(totals: dict[str, int]) -> pd.DataFrame:
    """Return RPG stat rows with XP, level, and progress data."""
    rows = []
    for stat in RPG_STATS:
        xp = int(totals.get(stat, 0))
        progress = get_stat_level_progress(xp)
        rows.append(
            {
                "Stat": stat,
                "Category": _category_for_stat(stat),
                "XP": xp,
                "Level": progress["level"],
                "Progress": progress["progress_percent"] / 100,
                "Progress Percent": progress["progress_percent"],
                "XP Into Current Level": progress["xp_into_current_level"],
                "XP Needed For Next Level": progress["xp_needed_for_next_level"],
                "XP Remaining To Next Level": progress["xp_remaining_to_next_level"],
                "Current Level Total XP": progress["current_level_total_xp"],
                "Next Level Total XP": progress["next_level_total_xp"],
            }
        )
    return pd.DataFrame(rows)


def build_stat_profile_rows(rpg_stats: pd.DataFrame) -> list[dict]:
    """Return stat profile data for Character Profile UI and radar chart."""
    if rpg_stats.empty:
        return [
            _stat_profile_row_from_progress(stat, _category_for_stat(stat), 0, get_stat_level_progress(0))
            for stat in RPG_STATS
        ]

    rows_by_stat = {row["Stat"]: row for row in rpg_stats.to_dict("records")}
    stat_rows = []
    for stat in RPG_STATS:
        row = rows_by_stat.get(stat, {})
        xp = int(row.get("XP", 0) or 0)
        progress = get_stat_level_progress(xp)
        stat_rows.append(
            _stat_profile_row_from_progress(
                stat=stat,
                category=str(row.get("Category") or _category_for_stat(stat)),
                xp=xp,
                progress=progress,
            )
        )
    return stat_rows


def _stat_profile_row_from_progress(stat: str, category: str, xp: int, progress: dict) -> dict:
    return {
        "stat": stat,
        "category": category,
        "xp": xp,
        "level": progress["level"],
        "progress_percent": progress["progress_percent"],
        "progress": progress["progress_percent"] / 100,
        "xp_into_current_level": progress["xp_into_current_level"],
        "xp_needed_for_next_level": progress["xp_needed_for_next_level"],
        "xp_remaining_to_next_level": progress["xp_remaining_to_next_level"],
        "current_level_total_xp": progress["current_level_total_xp"],
        "next_level_total_xp": progress["next_level_total_xp"],
    }


def calculate_weekly_xp(quests: list[Quest], today: date) -> int:
    """Return completed quest XP earned in the week containing today."""
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=7)
    week_start_at = datetime.combine(week_start, time.min)
    week_end_at = datetime.combine(week_end, time.min)

    return sum(
        quest.xp_reward or 0
        for quest in quests
        if _is_completed(quest)
        and quest.completed_at is not None
        and week_start_at <= quest.completed_at < week_end_at
    )


def calculate_weekly_checkin_xp(checkins: list[QuestCheckin], today: date) -> int:
    """Return completed check-in XP earned in the week containing today."""
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=7)

    return sum(
        checkin.xp_awarded or 0
        for checkin in checkins
        if _normalize_status(checkin.status) == "Completed"
        and week_start <= checkin.checkin_date < week_end
    )


def build_character_activity_stats(
    completed_quests: list[Quest],
    rpg_stats: pd.DataFrame,
    completion_rate: float,
    weekly_xp: int,
) -> list[dict]:
    """Return compact character activity stats for the profile sheet."""
    completed_count = len(completed_quests)
    total_xp = sum(quest.xp_reward or 0 for quest in completed_quests)
    average_xp = round(total_xp / completed_count, 1) if completed_count else 0

    return [
        {"label": "Completed Quests", "value": completed_count},
        {"label": "Completion Rate", "value": f"{completion_rate}%"},
        {"label": "Weekly XP", "value": weekly_xp},
        {"label": "Average XP / Completed Quest", "value": average_xp},
        {"label": "Most Active Category", "value": _most_active_category(completed_quests)},
        {"label": "Strongest RPG Stat", "value": _strongest_rpg_stat(rpg_stats)},
        {"label": "Most Productive Weekday", "value": _most_productive_weekday(completed_quests)},
    ]


def build_character_checkin_activity_stats(
    completed_checkins: list[QuestCheckin],
    all_checkins: list[QuestCheckin],
    rpg_stats: pd.DataFrame,
    completion_rate: float,
    weekly_xp: int,
) -> list[dict]:
    """Return compact character stats based on completed daily check-ins."""
    completed_count = len(completed_checkins)
    total_xp = sum(checkin.xp_awarded or 0 for checkin in completed_checkins)
    average_xp = round(total_xp / completed_count, 1) if completed_count else 0

    return [
        {"label": "Completed Quest Days", "value": completed_count},
        {"label": "Completion Rate", "value": f"{completion_rate}%"},
        {"label": "Weekly XP", "value": weekly_xp},
        {"label": "Average XP / Quest Day", "value": average_xp},
        {"label": "Most Active Category", "value": _most_active_checkin_category(completed_checkins)},
        {"label": "Strongest RPG Stat", "value": _strongest_rpg_stat(rpg_stats)},
        {"label": "Most Productive Weekday", "value": _most_productive_checkin_weekday(completed_checkins)},
    ]


def build_xp_by_day(quests: list[Quest]) -> pd.DataFrame:
    """Return completed quest XP grouped by completion or planned date."""
    rows = []
    for quest in quests:
        if not _is_completed(quest):
            continue

        activity_date = _quest_activity_date(quest)
        if activity_date is None:
            continue

        rows.append({"Date": activity_date, "XP": quest.xp_reward or 0})

    if not rows:
        return pd.DataFrame(columns=["Date", "XP"])

    return (
        pd.DataFrame(rows)
        .groupby("Date", as_index=False)["XP"]
        .sum()
        .sort_values("Date")
        .reset_index(drop=True)
    )


def build_xp_by_day_from_checkins(checkins: list[QuestCheckin]) -> pd.DataFrame:
    """Return check-in XP grouped by check-in date."""
    rows = [
        {"Date": checkin.checkin_date, "XP": checkin.xp_awarded or 0}
        for checkin in checkins
    ]
    if not rows:
        return pd.DataFrame(columns=["Date", "XP"])

    return (
        pd.DataFrame(rows)
        .groupby("Date", as_index=False)["XP"]
        .sum()
        .sort_values("Date")
        .reset_index(drop=True)
    )


def completed_checkins_from(checkins: list[QuestCheckin]) -> list[QuestCheckin]:
    """Return completed check-ins from a mixed check-in list."""
    return [checkin for checkin in checkins if _normalize_status(checkin.status) == "Completed"]


def build_quests_by_status(quests: list[Quest]) -> pd.DataFrame:
    """Return quest counts for the supported status values."""
    rows = [{"Status": _normalize_status(quest.status), "Count": 1} for quest in quests]
    counts = pd.DataFrame(rows).groupby("Status")["Count"].sum().to_dict() if rows else {}

    return pd.DataFrame(
        [{"Status": status, "Count": int(counts.get(status, 0))} for status in STATUS_ORDER]
    )


def build_checkins_by_status(checkins: list[QuestCheckin]) -> pd.DataFrame:
    """Return check-in counts for the supported status values."""
    rows = [{"Status": _normalize_status(checkin.status), "Count": 1} for checkin in checkins]
    counts = pd.DataFrame(rows).groupby("Status")["Count"].sum().to_dict() if rows else {}

    return pd.DataFrame(
        [{"Status": status, "Count": int(counts.get(status, 0))} for status in STATUS_ORDER]
    )


def build_status_counts(quests: list[Quest]) -> dict[str, int]:
    """Return quest counts keyed by supported status."""
    counts = {status: 0 for status in STATUS_ORDER}
    for quest in quests:
        counts[_normalize_status(quest.status)] += 1
    return counts


def build_quests_in_week(quests: list[Quest], week_start_at: datetime, week_end_at: datetime) -> list[Quest]:
    """Return quests with planned or completed activity inside a week window."""
    weekly_quests = []
    for quest in quests:
        activity_at = _quest_activity_datetime(quest)
        if activity_at is not None and week_start_at <= activity_at < week_end_at:
            weekly_quests.append(quest)
    return weekly_quests


def build_today_focus_rows(checkins: list[QuestCheckin]) -> list[dict]:
    """Return compact schedule rows for today's check-ins."""
    sorted_checkins = sorted(
        checkins,
        key=lambda checkin: (
            checkin.quest.planned_start_at is None,
            checkin.quest.planned_start_at or datetime.max,
            checkin.quest.title.lower(),
        ),
    )

    return [
        {
            "Time": _quest_time_range(checkin.quest),
            "Title": checkin.quest.title,
            "Category": _category_name(checkin.quest),
            "Status": _normalize_status(checkin.status),
            "XP": f"{_checkin_xp(checkin)} XP",
        }
        for checkin in sorted_checkins
    ]


def build_operational_checkin_rows(checkins: list[QuestCheckin]) -> list[dict]:
    """Return action-ready rows for the Command Center work lists."""
    sorted_checkins = sorted(
        checkins,
        key=lambda checkin: (
            checkin.checkin_date,
            checkin.quest.planned_start_at is None,
            checkin.quest.planned_start_at or datetime.max,
            checkin.quest.title.lower(),
        ),
    )

    return [
        {
            "quest_id": checkin.quest_id,
            "checkin_date": checkin.checkin_date,
            "time": _quest_time_range(checkin.quest),
            "title": checkin.quest.title,
            "category": _category_name(checkin.quest),
            "status": _normalize_status(checkin.status),
            "xp": _checkin_xp(checkin),
        }
        for checkin in sorted_checkins
    ]


def build_quests_by_category(quests: list[Quest]) -> pd.DataFrame:
    """Return quest counts grouped by category name."""
    rows = [{"Category": _category_name(quest), "Count": 1} for quest in quests]
    if not rows:
        return pd.DataFrame(columns=["Category", "Count"])

    return (
        pd.DataFrame(rows)
        .groupby("Category", as_index=False)["Count"]
        .sum()
        .sort_values(["Count", "Category"], ascending=[False, True])
        .reset_index(drop=True)
    )


def build_checkins_by_category(checkins: list[QuestCheckin]) -> pd.DataFrame:
    """Return check-in counts grouped by parent quest category name."""
    rows = [
        {
            "Category": _category_name(checkin.quest) if checkin.quest is not None else "Uncategorized",
            "Count": 1,
        }
        for checkin in checkins
    ]
    if not rows:
        return pd.DataFrame(columns=["Category", "Count"])

    return (
        pd.DataFrame(rows)
        .groupby("Category", as_index=False)["Count"]
        .sum()
        .sort_values(["Count", "Category"], ascending=[False, True])
        .reset_index(drop=True)
    )


def build_completion_rate_by_weekday(quests: list[Quest]) -> pd.DataFrame:
    """Return planned weekday completion rates."""
    rows = []
    for quest in quests:
        if quest.due_date is None:
            continue

        rows.append(
            {
                "Weekday": quest.due_date.strftime("%A"),
                "Weekday Number": quest.due_date.weekday(),
                "Completed": 1 if _is_completed(quest) else 0,
                "Total": 1,
            }
        )

    if not rows:
        return pd.DataFrame(columns=["Weekday", "Completed Quests", "Total Quests", "Completion Rate"])

    grouped = (
        pd.DataFrame(rows)
        .groupby(["Weekday", "Weekday Number"], as_index=False)
        .agg({"Completed": "sum", "Total": "sum"})
        .sort_values("Weekday Number")
    )
    grouped["Completion Rate"] = grouped.apply(
        lambda row: calculate_completion_rate(int(row["Completed"]), int(row["Total"])),
        axis=1,
    )

    return grouped.rename(
        columns={"Completed": "Completed Quests", "Total": "Total Quests"}
    )[["Weekday", "Completed Quests", "Total Quests", "Completion Rate"]].reset_index(drop=True)


def build_completion_rate_by_weekday_from_checkins(checkins: list[QuestCheckin]) -> pd.DataFrame:
    """Return weekday completion rates from completed and failed check-ins."""
    rows = []
    for checkin in checkins:
        status = _normalize_status(checkin.status)
        if status not in {"Completed", "Failed"}:
            continue

        rows.append(
            {
                "Weekday": checkin.checkin_date.strftime("%A"),
                "Weekday Number": checkin.checkin_date.weekday(),
                "Completed": 1 if status == "Completed" else 0,
                "Total": 1,
            }
        )

    if not rows:
        return pd.DataFrame(columns=["Weekday", "Completed Quest Days", "Resolved Quest Days", "Completion Rate"])

    grouped = (
        pd.DataFrame(rows)
        .groupby(["Weekday", "Weekday Number"], as_index=False)
        .agg({"Completed": "sum", "Total": "sum"})
        .sort_values("Weekday Number")
    )
    grouped["Completion Rate"] = grouped.apply(
        lambda row: calculate_completion_rate(int(row["Completed"]), int(row["Total"])),
        axis=1,
    )

    return grouped.rename(
        columns={"Completed": "Completed Quest Days", "Total": "Resolved Quest Days"}
    )[["Weekday", "Completed Quest Days", "Resolved Quest Days", "Completion Rate"]].reset_index(drop=True)


def build_estimated_minutes_by_category(quests: list[Quest]) -> pd.DataFrame:
    """Return estimated minutes grouped by category name."""
    rows = [
        {"Category": _category_name(quest), "Estimated Minutes": quest.estimated_minutes or 0}
        for quest in quests
    ]
    if not rows:
        return pd.DataFrame(columns=["Category", "Estimated Minutes"])

    return (
        pd.DataFrame(rows)
        .groupby("Category", as_index=False)["Estimated Minutes"]
        .sum()
        .sort_values(["Estimated Minutes", "Category"], ascending=[False, True])
        .reset_index(drop=True)
    )


def build_planned_minutes_by_category_from_checkins(checkins: list[QuestCheckin]) -> pd.DataFrame:
    """Return planned workload minutes grouped by parent quest category."""
    rows = [
        {
            "Category": _category_name(checkin.quest) if checkin.quest is not None else "Uncategorized",
            "Planned Minutes": _checkin_planned_minutes(checkin),
        }
        for checkin in checkins
    ]
    if not rows:
        return pd.DataFrame(columns=["Category", "Planned Minutes"])

    return (
        pd.DataFrame(rows)
        .groupby("Category", as_index=False)["Planned Minutes"]
        .sum()
        .sort_values(["Planned Minutes", "Category"], ascending=[False, True])
        .reset_index(drop=True)
    )


def _checkin_planned_minutes(checkin: QuestCheckin) -> int:
    if checkin.quest is None:
        return 0
    return checkin.quest.estimated_minutes or 0


def _get_filtered_goals(
    session,
    statuses: list[str] | tuple[str, ...] | str | None = None,
    category_id: int | None = None,
) -> list[Goal]:
    normalized_statuses = _normalize_goal_status_filter(statuses)
    query = session.query(Goal).options(joinedload(Goal.category))
    if normalized_statuses is not None:
        query = query.filter(Goal.status.in_(normalized_statuses))
    if category_id is not None:
        query = query.filter(Goal.category_id == category_id)
    return (
        query.order_by(
            Goal.status.asc(),
            Goal.target_end_date.is_(None),
            Goal.target_end_date.asc(),
            Goal.title.asc(),
            Goal.id.asc(),
        )
        .all()
    )


def _normalize_goal_status_filter(statuses: list[str] | tuple[str, ...] | str | None) -> tuple[str, ...] | None:
    if statuses is None:
        return DEFAULT_GOAL_ANALYTICS_STATUSES
    if isinstance(statuses, str):
        if statuses == "All":
            return None
        raw_statuses = [statuses]
    else:
        raw_statuses = list(statuses)
    if "All" in raw_statuses:
        return None

    lookup = {status.lower(): status for status in GOAL_ANALYTICS_STATUSES}
    normalized = []
    for status in raw_statuses:
        key = str(status).strip().lower()
        if key in lookup:
            normalized.append(lookup[key])
    return tuple(normalized)


def _build_goal_progress_rows(goals: list[Goal], session) -> list[dict]:
    rows = []
    for goal in goals:
        progress = get_goal_progress(goal.id, session=session)
        rows.append(
            {
                "Goal ID": goal.id,
                "Goal": goal.title,
                "Status": goal.status,
                "Category": goal.category.name if goal.category else "Uncategorized",
                "Planned Effort": progress["planned_total_minutes"],
                "Planned Minutes": progress["planned_total_minutes"],
                "Completed Effort": progress["completed_minutes"],
                "Completed Minutes": progress["completed_minutes"],
                "Remaining Effort": progress["remaining_minutes"],
                "Remaining Minutes": progress["remaining_minutes"],
                "Progress": round(float(progress["progress_percent"]), 1),
                "Progress Percent": round(float(progress["progress_percent"]), 1),
                "Earned XP": int(progress["earned_xp"]),
                "Expected Total XP": int(progress["expected_total_xp"]),
                "Linked Sessions": int(progress["linked_sessions_count"]),
                "Completed Sessions": int(progress["completed_sessions_count"]),
                "Planned Sessions": int(progress["planned_sessions_count"]),
                "Skipped Sessions": int(progress["skipped_sessions_count"]),
                "Failed Sessions": int(progress["failed_sessions_count"]),
                "Target Date": goal.target_end_date,
            }
        )
    return rows


def _bounded_percent(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(max(0.0, min((numerator / denominator) * 100, 100.0)), 1)


def _ensure_legacy_command_center_checkins(session, today: date) -> None:
    """Create missing planned check-ins for legacy scheduled quests up to today."""
    next_day_start = datetime.combine(today + timedelta(days=1), time.min)
    legacy_quests = (
        session.query(Quest)
        .filter(
            or_(
                and_(Quest.due_date.is_not(None), Quest.due_date <= today),
                and_(Quest.planned_start_at.is_not(None), Quest.planned_start_at < next_day_start),
            )
        )
        .all()
    )

    for quest in legacy_quests:
        scheduled_date = _quest_scheduled_date(quest)
        if scheduled_date is not None and scheduled_date <= today:
            ensure_checkin(quest.id, scheduled_date, session=session)


def _quest_scheduled_date(quest: Quest) -> date | None:
    if quest.planned_start_at is not None:
        return quest.planned_start_at.date()
    return quest.due_date


def _checkin_xp(checkin: QuestCheckin) -> int:
    if (checkin.xp_awarded or 0) > 0:
        return checkin.xp_awarded or 0
    if checkin.quest is not None:
        return checkin.quest.xp_reward or 0
    return 0


def _is_completed(quest: Quest) -> bool:
    return (quest.status or "").strip().lower() == "completed"


def _normalize_status(status: str | None) -> str:
    value = (status or "").strip().lower()
    for valid_status in STATUS_ORDER:
        if value == valid_status.lower():
            return valid_status
    return "Planned"


def _category_name(quest: Quest) -> str:
    return quest.category.name if quest.category else "Uncategorized"


def _quest_activity_date(quest: Quest) -> date | None:
    if quest.completed_at is not None:
        return quest.completed_at.date()
    return quest.due_date


def _quest_activity_datetime(quest: Quest) -> datetime | None:
    if quest.completed_at is not None:
        return quest.completed_at
    if quest.due_date is not None:
        return datetime.combine(quest.due_date, time.min)
    return None


def _quest_time_range(quest: Quest) -> str:
    if quest.planned_start_at is not None and quest.planned_end_at is not None:
        return f"{quest.planned_start_at:%H:%M} - {quest.planned_end_at:%H:%M}"
    if quest.planned_start_at is not None:
        return f"{quest.planned_start_at:%H:%M}"
    return "All day"


def _stat_for_category(category_name: str) -> str:
    return CATEGORY_TO_RPG_STAT.get(category_name.strip().lower(), "Recovery")


def _category_for_stat(stat: str) -> str:
    for category, mapped_stat in CATEGORY_TO_RPG_STAT.items():
        if mapped_stat == stat:
            return category.title()
    return "Uncategorized"


def _most_active_category(quests: list[Quest]) -> str:
    category_counts: dict[str, int] = {}
    for quest in quests:
        category = _category_name(quest)
        category_counts[category] = category_counts.get(category, 0) + 1

    if not category_counts:
        return "Not enough data"

    return sorted(category_counts.items(), key=lambda item: (-item[1], item[0]))[0][0]


def _most_active_checkin_category(checkins: list[QuestCheckin]) -> str:
    category_counts: dict[str, int] = {}
    for checkin in checkins:
        if checkin.quest is None:
            category = "Uncategorized"
        else:
            category = _category_name(checkin.quest)
        category_counts[category] = category_counts.get(category, 0) + 1

    if not category_counts:
        return "Not enough data"

    return sorted(category_counts.items(), key=lambda item: (-item[1], item[0]))[0][0]


def _strongest_rpg_stat(rpg_stats: pd.DataFrame) -> str:
    if rpg_stats.empty or int(rpg_stats["XP"].max()) == 0:
        return "Not enough data"

    strongest = rpg_stats.sort_values(["XP", "Stat"], ascending=[False, True]).iloc[0]
    return f"{strongest['Stat']} ({int(strongest['XP'])} XP)"


def _most_productive_weekday(quests: list[Quest]) -> str:
    weekday_counts: dict[tuple[int, str], int] = {}
    for quest in quests:
        activity_date = _quest_activity_date(quest)
        if activity_date is None:
            continue

        key = (activity_date.weekday(), activity_date.strftime("%A"))
        weekday_counts[key] = weekday_counts.get(key, 0) + 1

    if not weekday_counts:
        return "Not enough data"

    return sorted(weekday_counts.items(), key=lambda item: (-item[1], item[0][0]))[0][0][1]


def _most_productive_checkin_weekday(checkins: list[QuestCheckin]) -> str:
    weekday_counts: dict[tuple[int, str], int] = {}
    for checkin in checkins:
        activity_date = checkin.checkin_date
        key = (activity_date.weekday(), activity_date.strftime("%A"))
        weekday_counts[key] = weekday_counts.get(key, 0) + 1

    if not weekday_counts:
        return "Not enough data"

    return sorted(weekday_counts.items(), key=lambda item: (-item[1], item[0][0]))[0][0][1]

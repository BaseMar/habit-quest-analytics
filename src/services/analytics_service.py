from datetime import date, datetime, time, timedelta
from itertools import groupby

import pandas as pd
from sqlalchemy import and_, or_
from sqlalchemy.orm import joinedload

from src.analysis.metrics import (
    calculate_completion_rate,
    calculate_routine_streaks,
    calculate_xp_to_next_level,
)
from src.constants import CATEGORY_TO_RPG_STAT, QUEST_STATUSES, RPG_STATS
from src.database.db import get_session
from src.database.models import Goal, PlayerProfile, Quest, QuestCheckin, RecurringHabitInstance
from src.services.command_center_service import (
    build_operational_checkin_rows as build_operational_checkin_rows,
    build_today_focus_rows as build_today_focus_rows,
    get_command_center_data as get_command_center_data,
    get_command_center_items_for_date as get_command_center_items_for_date,
    get_quest_category_name as _category_name,
    normalize_status as _normalize_status,
)
from src.services.goal_service import get_goal_progress
from src.services.xp_service import calculate_level, get_character_level_progress, get_stat_level_progress

STATUS_ORDER = QUEST_STATUSES
DEFAULT_GOAL_ANALYTICS_STATUSES = ("Active", "Completed")
GOAL_ANALYTICS_STATUSES = ("Active", "Completed", "Archived")


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


def get_habit_analytics_data(
    today: date | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    category_id: int | None = None,
    work_type: str = "all",
    session=None,
) -> dict:
    """Return prepared dataframes for the Habit Analytics page."""
    today = today or date.today()
    start_date, end_date = _normalize_analytics_date_range(start_date, end_date, today)
    normalized_work_type = _normalize_analytics_work_type(work_type)
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=7)
    week_start_at = datetime.combine(week_start, time.min)
    week_end_at = datetime.combine(week_end, time.min)
    previous_start_date, previous_end_date = _previous_period(start_date, end_date)

    owns_session = session is None
    session = session or get_session()
    try:
        checkins = (
            session.query(QuestCheckin)
            .options(
                joinedload(QuestCheckin.quest).joinedload(Quest.category),
                joinedload(QuestCheckin.quest)
                .joinedload(Quest.recurring_habit_instance)
                .joinedload(RecurringHabitInstance.recurring_habit),
            )
            .filter(
                or_(
                    QuestCheckin.checkin_date.between(previous_start_date, end_date),
                    and_(QuestCheckin.checkin_date >= week_start, QuestCheckin.checkin_date < week_end),
                )
            )
            .all()
        )
        if checkins or session.query(QuestCheckin.id).first() is not None:
            filtered_checkins = _filter_analytics_checkins(
                checkins,
                start_date=start_date,
                end_date=end_date,
                category_id=category_id,
                work_type=normalized_work_type,
            )
            previous_checkins = _filter_analytics_checkins(
                checkins,
                start_date=previous_start_date,
                end_date=previous_end_date,
                category_id=category_id,
                work_type=normalized_work_type,
            )
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
            category_performance = build_category_performance_from_checkins(filtered_checkins)
            routine_ids = {
                instance.recurring_habit_id
                for checkin in filtered_checkins
                if checkin.quest is not None and (instance := checkin.quest.recurring_habit_instance) is not None
            }
            routine_streaks = _get_routine_streaks(session, routine_ids, today)
            routine_performance = build_routine_performance_from_checkins(filtered_checkins, end_date, routine_streaks)
            weekday_performance = build_completion_rate_by_weekday_from_checkins(filtered_checkins)
            return {
                "has_quests": bool(filtered_checkins),
                "date_range": {"start_date": start_date, "end_date": end_date},
                "period_summary": _build_analytics_period_summary(filtered_checkins),
                "previous_period_summary": _build_analytics_period_summary(previous_checkins),
                "period_highlights": build_period_highlights_from_checkins(filtered_checkins),
                "review_focus": build_review_focus(category_performance, routine_performance),
                "weekly_pulse": {
                    "weekly_xp": sum(checkin.xp_awarded or 0 for checkin in weekly_checkins),
                    "completed_this_week": completed_this_week,
                    "failed_this_week": failed_this_week,
                    "weekly_completion_rate": calculate_completion_rate(completed_this_week, resolved_this_week),
                },
                "xp_by_day": build_xp_by_day_from_checkins(filtered_checkins),
                "quests_by_status": build_checkins_by_status(filtered_checkins),
                "quests_by_category": build_checkins_by_category(filtered_checkins),
                "completed_checkins_by_category": build_checkins_by_category(completed_checkins_from(filtered_checkins)),
                "category_performance": category_performance,
                "routine_performance": routine_performance,
                "completion_rate_by_weekday": weekday_performance,
                "estimated_minutes_by_category": build_planned_minutes_by_category_from_checkins(filtered_checkins),
                "planned_vs_completed_by_week": build_planned_vs_completed_by_week_from_checkins(
                    filtered_checkins,
                    start_date,
                    end_date,
                ),
            }

        quests = (
            session.query(Quest)
            .options(joinedload(Quest.category), joinedload(Quest.recurring_habit_instance))
            .all()
        )
        filtered_quests = _filter_analytics_quests(
            quests,
            start_date=start_date,
            end_date=end_date,
            category_id=category_id,
            work_type=normalized_work_type,
        )
        previous_quests = _filter_analytics_quests(
            quests,
            start_date=previous_start_date,
            end_date=previous_end_date,
            category_id=category_id,
            work_type=normalized_work_type,
        )
        weekly_quests = build_quests_in_week(quests, week_start_at, week_end_at)
        completed_this_week = sum(1 for quest in weekly_quests if _is_completed(quest))
        failed_this_week = sum(1 for quest in weekly_quests if _normalize_status(quest.status) == "Failed")
        category_performance = build_category_performance_from_quests(filtered_quests)
        weekday_performance = build_completion_rate_by_weekday(filtered_quests)
        return {
            "has_quests": bool(filtered_quests),
            "date_range": {"start_date": start_date, "end_date": end_date},
            "period_summary": _build_analytics_quest_period_summary(filtered_quests),
            "previous_period_summary": _build_analytics_quest_period_summary(previous_quests),
            "period_highlights": build_period_highlights_from_quests(filtered_quests),
            "review_focus": build_review_focus(category_performance, _empty_routine_performance_dataset()),
            "weekly_pulse": {
                "weekly_xp": sum(quest.xp_reward or 0 for quest in weekly_quests if _is_completed(quest)),
                "completed_this_week": completed_this_week,
                "failed_this_week": failed_this_week,
                "weekly_completion_rate": calculate_completion_rate(completed_this_week, len(weekly_quests)),
            },
            "xp_by_day": build_xp_by_day(filtered_quests),
            "quests_by_status": build_quests_by_status(filtered_quests),
            "quests_by_category": build_quests_by_category(filtered_quests),
            "category_performance": category_performance,
            "routine_performance": _empty_routine_performance_dataset(),
            "completion_rate_by_weekday": weekday_performance,
            "estimated_minutes_by_category": build_estimated_minutes_by_category(filtered_quests),
            "planned_vs_completed_by_week": build_planned_vs_completed_by_week_from_quests(
                filtered_quests,
                start_date,
                end_date,
            ),
        }
    finally:
        if owns_session:
            session.close()


def _normalize_analytics_date_range(
    start_date: date | None,
    end_date: date | None,
    today: date,
) -> tuple[date, date]:
    normalized_end_date = end_date or today
    normalized_start_date = start_date or normalized_end_date - timedelta(days=29)
    if normalized_start_date > normalized_end_date:
        raise ValueError("Analytics start date must be on or before the end date.")
    return normalized_start_date, normalized_end_date


def _normalize_analytics_work_type(work_type: str) -> str:
    allowed_work_types = {"all", "one_time", "routine", "project_session"}
    if work_type not in allowed_work_types:
        raise ValueError("Unknown analytics work type.")
    return work_type


def _previous_period(start_date: date, end_date: date) -> tuple[date, date]:
    period_days = (end_date - start_date).days + 1
    previous_end_date = start_date - timedelta(days=1)
    return previous_end_date - timedelta(days=period_days - 1), previous_end_date


def _filter_analytics_checkins(
    checkins: list[QuestCheckin],
    start_date: date,
    end_date: date,
    category_id: int | None,
    work_type: str,
) -> list[QuestCheckin]:
    return [
        checkin
        for checkin in checkins
        if start_date <= checkin.checkin_date <= end_date
        and _matches_analytics_filters(checkin.quest, category_id, work_type)
    ]


def _filter_analytics_quests(
    quests: list[Quest],
    start_date: date,
    end_date: date,
    category_id: int | None,
    work_type: str,
) -> list[Quest]:
    return [
        quest
        for quest in quests
        if (scheduled_date := _quest_scheduled_date(quest)) is not None
        and start_date <= scheduled_date <= end_date
        and _matches_analytics_filters(quest, category_id, work_type)
    ]


def _matches_analytics_filters(quest: Quest | None, category_id: int | None, work_type: str) -> bool:
    if quest is None:
        return False
    if category_id is not None and quest.category_id != category_id:
        return False
    is_routine = quest.recurring_habit_instance is not None
    if work_type == "routine":
        return is_routine
    if work_type == "project_session":
        return not is_routine and quest.goal_id is not None
    if work_type == "one_time":
        return not is_routine and quest.goal_id is None
    return True


def _build_analytics_period_summary(checkins: list[QuestCheckin]) -> dict:
    completed_checkins = [checkin for checkin in checkins if _normalize_status(checkin.status) == "Completed"]
    failed_checkins = [checkin for checkin in checkins if _normalize_status(checkin.status) == "Failed"]
    skipped_checkins = [checkin for checkin in checkins if _normalize_status(checkin.status) == "Skipped"]
    planned_minutes = sum(_checkin_planned_minutes(checkin) for checkin in checkins)
    completed_planned_minutes = sum(_checkin_planned_minutes(checkin) for checkin in completed_checkins)
    return {
        "checkins_count": len(checkins),
        "completed_count": len(completed_checkins),
        "failed_count": len(failed_checkins),
        "skipped_count": len(skipped_checkins),
        "planned_minutes": planned_minutes,
        "completed_planned_minutes": completed_planned_minutes,
        "xp_earned": sum(checkin.xp_awarded or 0 for checkin in completed_checkins),
        "completion_rate": calculate_completion_rate(len(completed_checkins), len(completed_checkins) + len(failed_checkins)),
    }


def _build_analytics_quest_period_summary(quests: list[Quest]) -> dict:
    completed_quests = [quest for quest in quests if _is_completed(quest)]
    failed_quests = [quest for quest in quests if _normalize_status(quest.status) == "Failed"]
    skipped_quests = [quest for quest in quests if _normalize_status(quest.status) == "Skipped"]
    planned_minutes = sum(quest.estimated_minutes or 0 for quest in quests)
    completed_planned_minutes = sum(quest.estimated_minutes or 0 for quest in completed_quests)
    return {
        "checkins_count": len(quests),
        "completed_count": len(completed_quests),
        "failed_count": len(failed_quests),
        "skipped_count": len(skipped_quests),
        "planned_minutes": planned_minutes,
        "completed_planned_minutes": completed_planned_minutes,
        "xp_earned": sum(quest.xp_reward or 0 for quest in completed_quests),
        "completion_rate": calculate_completion_rate(len(completed_quests), len(completed_quests) + len(failed_quests)),
    }


def build_period_highlights_from_checkins(checkins: list[QuestCheckin]) -> dict:
    """Return compact, explainable consistency signals for a reporting period."""
    scheduled_days = {checkin.checkin_date for checkin in checkins}
    completed_days = {
        checkin.checkin_date
        for checkin in checkins
        if _normalize_status(checkin.status) == "Completed"
    }
    return _build_period_highlights(
        scheduled_days=scheduled_days,
        completed_days=completed_days,
    )


def build_period_highlights_from_quests(quests: list[Quest]) -> dict:
    """Return reporting-period highlights for legacy quest data without check-ins."""
    scheduled_days = {quest.due_date for quest in quests if quest.due_date is not None}
    completed_days = {
        quest.due_date
        for quest in quests
        if quest.due_date is not None and _is_completed(quest)
    }
    return _build_period_highlights(
        scheduled_days=scheduled_days,
        completed_days=completed_days,
    )


def _build_period_highlights(
    scheduled_days: set[date],
    completed_days: set[date],
) -> dict:
    scheduled_day_count = len(scheduled_days)
    completed_day_count = len(completed_days)
    return {
        "scheduled_days": scheduled_day_count,
        "completed_days": completed_day_count,
        "active_day_rate": calculate_completion_rate(completed_day_count, scheduled_day_count),
    }


def build_review_focus(category_performance: pd.DataFrame, routine_performance: pd.DataFrame) -> dict | None:
    """Return one deterministic focus item instead of a dashboard full of alerts."""
    attention_routines = routine_performance[routine_performance["Needs Attention"]]
    if not attention_routines.empty:
        routine = attention_routines.sort_values(
            ["Overdue Planned", "Failed", "Routine"], ascending=[False, False, True]
        ).iloc[0]
        return {
            "title": "Routine needs attention",
            "message": (
                f"{routine['Routine']}: {int(routine['Overdue Planned'])} overdue planned and "
                f"{int(routine['Failed'])} failed check-ins."
            ),
        }

    unresolved_categories = category_performance[category_performance["Planned"] > 0]
    if not unresolved_categories.empty:
        category = unresolved_categories.sort_values(
            ["Planned", "Planned Minutes", "Category"], ascending=[False, False, True]
        ).iloc[0]
        return {
            "title": "Unresolved workload",
            "message": f"{category['Category']} has {int(category['Planned'])} planned check-ins in this period.",
        }

    resolved_categories = category_performance[
        (category_performance["Completed"] + category_performance["Failed"]) > 0
    ]
    if not resolved_categories.empty:
        category = resolved_categories.sort_values(
            ["Completion Rate", "Planned Minutes", "Category"], ascending=[True, False, True]
        ).iloc[0]
        return {
            "title": "Category to review",
            "message": f"{category['Category']} completed {category['Completion Rate']:.0f}% of resolved check-ins.",
        }

    return None


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
            "has_goals": bool(goals or session.query(Goal.id).first()),
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
    return build_goal_progress_dataset(summary["goal_rows"])


def build_goal_progress_dataset(goal_rows: list[dict]) -> pd.DataFrame:
    """Build chart data from an already-loaded goal analytics summary."""
    rows = []
    for row in goal_rows:
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


def build_category_performance_from_checkins(checkins: list[QuestCheckin]) -> pd.DataFrame:
    """Return category-level workload, outcomes, and XP for a filtered check-in set."""
    rows_by_category: dict[str, dict] = {}
    for checkin in checkins:
        category = _category_name(checkin.quest) if checkin.quest is not None else "Uncategorized"
        row = rows_by_category.setdefault(
            category,
            {
                "Category": category,
                "Planned Minutes": 0,
                "Completed Planned Minutes": 0,
                "Completed": 0,
                "Failed": 0,
                "Skipped": 0,
                "Planned": 0,
                "XP Earned": 0,
            },
        )
        planned_minutes = _checkin_planned_minutes(checkin)
        status = _normalize_status(checkin.status)
        row["Planned Minutes"] += planned_minutes
        row[status] += 1
        if status == "Completed":
            row["Completed Planned Minutes"] += planned_minutes
            row["XP Earned"] += checkin.xp_awarded or 0

    return _finalize_category_performance(rows_by_category)


def build_category_performance_from_quests(quests: list[Quest]) -> pd.DataFrame:
    """Return legacy category performance for databases without check-ins."""
    rows_by_category: dict[str, dict] = {}
    for quest in quests:
        category = _category_name(quest)
        row = rows_by_category.setdefault(
            category,
            {
                "Category": category,
                "Planned Minutes": 0,
                "Completed Planned Minutes": 0,
                "Completed": 0,
                "Failed": 0,
                "Skipped": 0,
                "Planned": 0,
                "XP Earned": 0,
            },
        )
        planned_minutes = quest.estimated_minutes or 0
        status = _normalize_status(quest.status)
        row["Planned Minutes"] += planned_minutes
        row[status] += 1
        if status == "Completed":
            row["Completed Planned Minutes"] += planned_minutes
            row["XP Earned"] += quest.xp_reward or 0

    return _finalize_category_performance(rows_by_category)


def _finalize_category_performance(rows_by_category: dict[str, dict]) -> pd.DataFrame:
    if not rows_by_category:
        return pd.DataFrame(
            columns=[
                "Category",
                "Planned Minutes",
                "Completed Planned Minutes",
                "Completion Rate",
                "Completed",
                "Failed",
                "Skipped",
                "Planned",
                "XP Earned",
            ]
        )
    rows = list(rows_by_category.values())
    for row in rows:
        row["Completion Rate"] = calculate_completion_rate(row["Completed"], row["Completed"] + row["Failed"])
    return (
        pd.DataFrame(rows)
        .sort_values(["Planned Minutes", "Category"], ascending=[False, True])
        .reset_index(drop=True)
    )


def _get_routine_streaks(session, routine_ids: set[int], today: date) -> dict[int, tuple[int, int]]:
    if not routine_ids:
        return {}

    occurrences = (
        session.query(
            RecurringHabitInstance.recurring_habit_id,
            RecurringHabitInstance.scheduled_date,
            QuestCheckin.status,
        )
        .outerjoin(
            QuestCheckin,
            and_(
                QuestCheckin.quest_id == RecurringHabitInstance.quest_id,
                QuestCheckin.checkin_date == RecurringHabitInstance.scheduled_date,
            ),
        )
        .filter(
            RecurringHabitInstance.recurring_habit_id.in_(routine_ids),
            RecurringHabitInstance.scheduled_date <= today,
        )
        .order_by(RecurringHabitInstance.recurring_habit_id, RecurringHabitInstance.scheduled_date)
    )
    return {
        routine_id: calculate_routine_streaks(
            ((occurrence.scheduled_date, _normalize_status(occurrence.status)) for occurrence in history), today
        )
        for routine_id, history in groupby(occurrences, key=lambda occurrence: occurrence.recurring_habit_id)
    }


def build_routine_performance_from_checkins(
    checkins: list[QuestCheckin], as_of_date: date, streaks_by_routine: dict[int, tuple[int, int]]
) -> pd.DataFrame:
    """Return routine-level outcomes from generated recurring habit instances."""
    rows_by_routine: dict[int, dict] = {}
    for checkin in checkins:
        quest = checkin.quest
        instance = quest.recurring_habit_instance if quest is not None else None
        habit = instance.recurring_habit if instance is not None else None
        if habit is None:
            continue
        row = rows_by_routine.setdefault(
            habit.id,
            {
                "Routine": habit.title,
                "Category": _category_name(quest),
                "Active": habit.is_active,
                "Scheduled": 0,
                "Completed": 0,
                "Failed": 0,
                "Skipped": 0,
                "Planned": 0,
                "Last Scheduled": checkin.checkin_date,
                "Last Completed": None,
                "Overdue Planned": 0,
            },
        )
        status = _normalize_status(checkin.status)
        row["Scheduled"] += 1
        row[status] += 1
        row["Last Scheduled"] = max(row["Last Scheduled"], checkin.checkin_date)
        if status == "Completed":
            row["Last Completed"] = max(row["Last Completed"] or checkin.checkin_date, checkin.checkin_date)
        if status == "Planned" and checkin.checkin_date < as_of_date:
            row["Overdue Planned"] += 1

    if not rows_by_routine:
        return _empty_routine_performance_dataset()

    rows = list(rows_by_routine.values())
    for routine_id, row in rows_by_routine.items():
        row["Current Streak"], row["Best Streak"] = streaks_by_routine.get(routine_id, (0, 0))
        row["Completion Rate"] = calculate_completion_rate(row["Completed"], row["Completed"] + row["Failed"])
        row["Needs Attention"] = row["Active"] and (row["Failed"] > 0 or row["Overdue Planned"] > 0)
    return (
        pd.DataFrame(rows)
        .sort_values(["Needs Attention", "Completion Rate", "Routine"], ascending=[False, True, True])
        .reset_index(drop=True)
    )


def _empty_routine_performance_dataset() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "Routine",
            "Category",
            "Active",
            "Scheduled",
            "Completed",
            "Failed",
            "Skipped",
            "Planned",
            "Overdue Planned",
            "Current Streak",
            "Best Streak",
            "Completion Rate",
            "Last Scheduled",
            "Last Completed",
            "Needs Attention",
        ]
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


def build_planned_vs_completed_by_week_from_checkins(
    checkins: list[QuestCheckin],
    start_date: date,
    end_date: date,
) -> pd.DataFrame:
    """Return scheduled and completed planned minutes grouped by calendar week."""
    entries = [
        (
            checkin.checkin_date,
            _checkin_planned_minutes(checkin),
            _normalize_status(checkin.status) == "Completed",
        )
        for checkin in checkins
    ]
    return _build_weekly_planned_vs_completed_dataset(entries, start_date, end_date)


def build_planned_vs_completed_by_week_from_quests(
    quests: list[Quest],
    start_date: date,
    end_date: date,
) -> pd.DataFrame:
    """Return legacy scheduled and completed planned minutes grouped by calendar week."""
    entries = [
        (scheduled_date, quest.estimated_minutes or 0, _is_completed(quest))
        for quest in quests
        if (scheduled_date := _quest_scheduled_date(quest)) is not None
    ]
    return _build_weekly_planned_vs_completed_dataset(entries, start_date, end_date)


def _build_weekly_planned_vs_completed_dataset(
    entries: list[tuple[date, int, bool]],
    start_date: date,
    end_date: date,
) -> pd.DataFrame:
    week_start = start_date - timedelta(days=start_date.weekday())
    last_week_start = end_date - timedelta(days=end_date.weekday())
    rows_by_week = {}
    while week_start <= last_week_start:
        rows_by_week[week_start] = {
            "Week": week_start,
            "Planned Minutes": 0,
            "Completed Planned Minutes": 0,
        }
        week_start += timedelta(days=7)

    for entry_date, planned_minutes, is_completed in entries:
        entry_week_start = entry_date - timedelta(days=entry_date.weekday())
        row = rows_by_week.get(entry_week_start)
        if row is None:
            continue
        row["Planned Minutes"] += planned_minutes
        if is_completed:
            row["Completed Planned Minutes"] += planned_minutes

    rows = list(rows_by_week.values())
    for row in rows:
        row["Planned Completion Rate"] = _bounded_percent(
            row["Completed Planned Minutes"],
            row["Planned Minutes"],
        )
    return pd.DataFrame(
        rows,
        columns=["Week", "Planned Minutes", "Completed Planned Minutes", "Planned Completion Rate"],
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


def _quest_scheduled_date(quest: Quest) -> date | None:
    if quest.planned_start_at is not None:
        return quest.planned_start_at.date()
    return quest.due_date


def _is_completed(quest: Quest) -> bool:
    return (quest.status or "").strip().lower() == "completed"


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

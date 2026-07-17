from __future__ import annotations

from datetime import date, datetime, time, timedelta
from math import ceil

from src.database.db import get_session
from src.database.models import Goal, Quest, QuestCheckin
from src.services.quest_service import (
    build_goal_session_title,
    create_scheduled_quest,
    get_next_goal_session_number,
)
from src.services.xp_service import calculate_time_based_xp


def get_goal_session_planning_summary(
    goal_id: int,
    session_duration_minutes: int | None = None,
    session=None,
) -> dict:
    """Return scheduling effort for an active goal without using XP as effort."""
    owns_session = session is None
    session = session or get_session()
    try:
        goal = _get_goal_or_raise(session, goal_id)
        linked_quests = _get_linked_quests(session, goal.id)
        quests_by_id = {quest.id: quest for quest in linked_quests}
        checkins = _get_linked_checkins(session, list(quests_by_id))

        completed_minutes = 0
        currently_planned_minutes = 0
        failed_minutes = 0
        skipped_minutes = 0

        for checkin in checkins:
            quest = quests_by_id.get(checkin.quest_id)
            if quest is None:
                continue

            minutes = _get_quest_planned_minutes(quest)
            if checkin.status == "Completed":
                completed_minutes += minutes
            elif checkin.status == "Planned":
                currently_planned_minutes += minutes
            elif checkin.status == "Failed":
                failed_minutes += minutes
            elif checkin.status == "Skipped":
                skipped_minutes += minutes

        planned_total_minutes = int(goal.planned_total_minutes or 0)
        effort_to_schedule_minutes = max(
            planned_total_minutes - completed_minutes - currently_planned_minutes,
            0,
        )
        suggested_sessions_count = 0
        if session_duration_minutes is not None:
            duration = _validate_session_duration_minutes(session_duration_minutes)
            suggested_sessions_count = ceil(effort_to_schedule_minutes / duration) if effort_to_schedule_minutes else 0

        return {
            "goal_id": goal.id,
            "goal_status": goal.status,
            "can_plan_sessions": goal.status == "Active",
            "planned_total_minutes": planned_total_minutes,
            "completed_minutes": completed_minutes,
            "currently_planned_minutes": currently_planned_minutes,
            "failed_minutes": failed_minutes,
            "skipped_minutes": skipped_minutes,
            "effort_to_schedule_minutes": effort_to_schedule_minutes,
            "suggested_sessions_count": suggested_sessions_count,
        }
    finally:
        if owns_session:
            session.close()


def build_goal_session_plan_preview(
    goal_id: int,
    session_duration_minutes: int,
    start_date: date,
    selected_weekdays: list[int] | tuple[int, ...] | set[int],
    planned_start_time: time,
    target_end_date: date | None = None,
    allow_short_final_session: bool = True,
    session=None,
) -> dict:
    """Build a read-only preview for generated goal sessions."""
    duration = _validate_session_duration_minutes(session_duration_minutes)
    weekdays = _normalize_weekdays(selected_weekdays)
    _validate_start_date(start_date)
    _validate_start_time(planned_start_time)

    owns_session = session is None
    session = session or get_session()
    try:
        goal = _get_goal_or_raise(session, goal_id)
        _validate_goal_is_active(goal)
        _validate_goal_category(goal)
        effective_target_end_date = _resolve_effective_target_end_date(goal, start_date, target_end_date)
        summary = get_goal_session_planning_summary(
            goal.id,
            session_duration_minutes=duration,
            session=session,
        )
        effort_to_schedule_minutes = int(summary["effort_to_schedule_minutes"])
        requested_durations, unallocated_from_duration = _build_requested_session_durations(
            effort_to_schedule_minutes,
            duration,
            allow_short_final_session=allow_short_final_session,
        )
        candidate_dates = _build_eligible_dates(
            start_date=start_date,
            selected_weekdays=weekdays,
            required_count=len(requested_durations),
            target_end_date=effective_target_end_date,
        )

        next_session_number = get_next_goal_session_number(goal.id, session=session)
        sessions = []
        total_scheduled_minutes = 0
        date_shortage_minutes = sum(requested_durations[len(candidate_dates):])
        for index, (planned_date, planned_minutes) in enumerate(zip(candidate_dates, requested_durations)):
            start_at, end_at = _build_session_datetimes(planned_date, planned_start_time, planned_minutes)
            session_number = next_session_number + index
            total_scheduled_minutes += planned_minutes
            sessions.append(
                {
                    "session_number": session_number,
                    "title": build_goal_session_title(goal.title, session_number),
                    "date": planned_date,
                    "start_time": start_at.time(),
                    "end_time": end_at.time(),
                    "duration_minutes": planned_minutes,
                    "expected_quest_xp": calculate_time_based_xp(planned_minutes),
                }
            )

        remaining_unallocated_minutes = unallocated_from_duration + date_shortage_minutes
        date_range_complete = len(candidate_dates) >= len(requested_durations)
        blocked_reason = None
        if not date_range_complete:
            blocked_reason = "Not enough eligible dates are available before the target end date."

        return {
            "goal_id": goal.id,
            "goal_title": goal.title,
            "planning_summary": summary,
            "sessions": sessions,
            "total_sessions": len(sessions),
            "total_planned_minutes": total_scheduled_minutes,
            "remaining_unallocated_minutes": remaining_unallocated_minutes,
            "fully_covers_effort": remaining_unallocated_minutes == 0,
            "date_range_complete": date_range_complete,
            "blocked_reason": blocked_reason,
            "allow_short_final_session": bool(allow_short_final_session),
            "target_end_date": effective_target_end_date,
        }
    finally:
        if owns_session:
            session.close()


def plan_goal_sessions(
    goal_id: int,
    session_duration_minutes: int,
    start_date: date,
    selected_weekdays: list[int] | tuple[int, ...] | set[int],
    planned_start_time: time,
    target_end_date: date | None = None,
    allow_short_final_session: bool = True,
    session=None,
) -> dict:
    """Create normal one-time goal-linked scheduled quests from a fresh preview."""
    owns_session = session is None
    session = session or get_session()
    try:
        preview = build_goal_session_plan_preview(
            goal_id=goal_id,
            session_duration_minutes=session_duration_minutes,
            start_date=start_date,
            selected_weekdays=selected_weekdays,
            planned_start_time=planned_start_time,
            target_end_date=target_end_date,
            allow_short_final_session=allow_short_final_session,
            session=session,
        )
        if not preview["date_range_complete"]:
            raise ValueError(preview["blocked_reason"])

        goal = _get_goal_or_raise(session, goal_id)
        created_quests = []
        for row in preview["sessions"]:
            quest = create_scheduled_quest(
                title=row["title"],
                category_id=goal.category_id,
                goal_id=goal.id,
                planned_date=row["date"],
                start_time=row["start_time"],
                end_time=row["end_time"],
                estimated_minutes=row["duration_minutes"],
                session=session,
            )
            created_quests.append(quest)

        refreshed_summary = get_goal_session_planning_summary(
            goal_id,
            session_duration_minutes=session_duration_minutes,
            session=session,
        )
        return {
            "goal_id": goal_id,
            "created_count": len(created_quests),
            "created_quest_ids": [quest.id for quest in created_quests],
            "created_session_numbers": [quest.goal_session_number for quest in created_quests],
            "total_planned_minutes": sum(quest.estimated_minutes or 0 for quest in created_quests),
            "remaining_unallocated_minutes": preview["remaining_unallocated_minutes"],
            "fully_covers_effort": preview["fully_covers_effort"],
            "planning_summary": refreshed_summary,
        }
    except Exception:
        session.rollback()
        raise
    finally:
        if owns_session:
            session.close()


def _get_goal_or_raise(session, goal_id: int) -> Goal:
    goal = session.get(Goal, goal_id)
    if goal is None:
        raise ValueError(f"Goal with id {goal_id} was not found.")
    return goal


def _validate_goal_is_active(goal: Goal) -> None:
    if goal.status != "Active":
        raise ValueError("Only active goals can use the session planner.")


def _validate_goal_category(goal: Goal) -> None:
    if goal.category_id is None:
        raise ValueError("Goal sessions require a category.")


def _get_linked_quests(session, goal_id: int) -> list[Quest]:
    return session.query(Quest).filter(Quest.goal_id == goal_id).order_by(Quest.id).all()


def _get_linked_checkins(session, quest_ids: list[int]) -> list[QuestCheckin]:
    if not quest_ids:
        return []
    return (
        session.query(QuestCheckin)
        .filter(QuestCheckin.quest_id.in_(quest_ids))
        .order_by(QuestCheckin.checkin_date, QuestCheckin.id)
        .all()
    )


def _get_quest_planned_minutes(quest: Quest) -> int:
    if quest.estimated_minutes and quest.estimated_minutes > 0:
        return int(quest.estimated_minutes)
    if quest.planned_start_at is not None and quest.planned_end_at is not None:
        return max(int((quest.planned_end_at - quest.planned_start_at).total_seconds() // 60), 0)
    return 0


def _validate_session_duration_minutes(session_duration_minutes: int) -> int:
    try:
        duration = int(session_duration_minutes)
    except (TypeError, ValueError) as error:
        raise ValueError("Session duration must be a positive number of minutes.") from error
    if duration <= 0:
        raise ValueError("Session duration must be greater than 0.")
    return duration


def _validate_start_date(start_date: date) -> None:
    if not isinstance(start_date, date):
        raise ValueError("Start date is required.")


def _validate_start_time(planned_start_time: time) -> None:
    if not isinstance(planned_start_time, time):
        raise ValueError("Planned start time is required.")


def _normalize_weekdays(selected_weekdays) -> list[int]:
    weekdays = sorted({int(day) for day in selected_weekdays or []})
    if not weekdays:
        raise ValueError("Select at least one weekday.")
    invalid = [day for day in weekdays if day < 0 or day > 6]
    if invalid:
        raise ValueError("Weekdays must use Monday=0 through Sunday=6.")
    return weekdays


def _resolve_effective_target_end_date(
    goal: Goal,
    start_date: date,
    target_end_date: date | None,
) -> date | None:
    if target_end_date is not None and target_end_date < start_date:
        raise ValueError("Planning end date cannot be before the start date.")
    if target_end_date is not None and goal.target_end_date is not None and target_end_date > goal.target_end_date:
        raise ValueError("Planning end date cannot be after the goal target date.")
    return target_end_date or goal.target_end_date


def _build_requested_session_durations(
    effort_to_schedule_minutes: int,
    session_duration_minutes: int,
    allow_short_final_session: bool,
) -> tuple[list[int], int]:
    if effort_to_schedule_minutes <= 0:
        return [], 0

    full_sessions, remainder = divmod(effort_to_schedule_minutes, session_duration_minutes)
    durations = [session_duration_minutes] * full_sessions
    unallocated = 0
    if remainder:
        if allow_short_final_session:
            durations.append(remainder)
        else:
            unallocated = remainder
    return durations, unallocated


def _build_eligible_dates(
    start_date: date,
    selected_weekdays: list[int],
    required_count: int,
    target_end_date: date | None,
) -> list[date]:
    if required_count <= 0:
        return []

    dates = []
    current_date = start_date
    while len(dates) < required_count:
        if target_end_date is not None and current_date > target_end_date:
            break
        if current_date.weekday() in selected_weekdays:
            dates.append(current_date)
        current_date += timedelta(days=1)
    return dates


def _build_session_datetimes(
    planned_date: date,
    planned_start_time: time,
    duration_minutes: int,
) -> tuple[datetime, datetime]:
    start_at = datetime.combine(planned_date, planned_start_time)
    end_at = start_at + timedelta(minutes=duration_minutes)
    if end_at.date() != planned_date:
        raise ValueError("Planned sessions cannot cross midnight.")
    return start_at, end_at

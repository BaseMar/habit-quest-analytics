from datetime import date, timedelta
from math import ceil

from sqlalchemy.orm import joinedload

from src.database.db import get_session
from src.database.models import Category, Goal, Quest, QuestCheckin, utc_now
from src.services.goal_session_data import get_linked_goal_quests, get_quest_checkins, get_quest_planned_minutes
from src.services.xp_service import calculate_time_based_xp


GOAL_STATUSES = ("Active", "Completed", "Archived")


def create_goal(
    title: str,
    planned_total_minutes: int,
    description: str | None = None,
    category_id: int | None = None,
    start_date: date | None = None,
    target_end_date: date | None = None,
    status: str = "Active",
    session=None,
) -> Goal:
    """Create and persist a long-term goal/project."""
    normalized_title = _normalize_title(title)
    normalized_minutes = _normalize_planned_total_minutes(planned_total_minutes)
    normalized_status = _normalize_status(status)
    _validate_dates(start_date, target_end_date)

    owns_session = session is None
    session = session or get_session()
    try:
        normalized_category_id = _validate_required_category(session, category_id)
        goal = Goal(
            title=normalized_title,
            description=_normalize_description(description),
            category_id=normalized_category_id,
            planned_total_minutes=normalized_minutes,
            start_date=start_date,
            target_end_date=target_end_date,
            status=normalized_status,
        )
        session.add(goal)
        session.commit()
        session.refresh(goal)
        return goal
    except Exception:
        session.rollback()
        raise
    finally:
        if owns_session:
            session.close()


def list_goals(status: str | None = None, session=None) -> list[Goal]:
    """Return goals in deterministic display order."""
    normalized_status = _normalize_status(status) if status is not None else None
    owns_session = session is None
    session = session or get_session()
    try:
        query = session.query(Goal).options(joinedload(Goal.category))
        if normalized_status is not None:
            query = query.filter(Goal.status == normalized_status)
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
    finally:
        if owns_session:
            session.close()


def list_active_goals(session=None) -> list[Goal]:
    """Return active goals that can receive new one-time quest sessions."""
    return list_goals(status="Active", session=session)


def get_goal(goal_id: int, session=None) -> Goal | None:
    """Return a goal by id, or None when missing."""
    owns_session = session is None
    session = session or get_session()
    try:
        return session.get(Goal, goal_id)
    finally:
        if owns_session:
            session.close()


def update_goal(goal_id: int, session=None, **changes) -> Goal:
    """Update editable goal fields."""
    allowed_fields = {
        "title",
        "description",
        "category_id",
        "planned_total_minutes",
        "start_date",
        "target_end_date",
        "status",
    }
    unknown_fields = set(changes) - allowed_fields
    if unknown_fields:
        fields = ", ".join(sorted(unknown_fields))
        raise ValueError(f"Unknown goal field(s): {fields}.")

    owns_session = session is None
    session = session or get_session()
    try:
        goal = session.get(Goal, goal_id)
        if goal is None:
            raise ValueError(f"Goal with id {goal_id} was not found.")

        title = changes.get("title", goal.title)
        planned_total_minutes = changes.get("planned_total_minutes", goal.planned_total_minutes)
        start_date = changes.get("start_date", goal.start_date)
        target_end_date = changes.get("target_end_date", goal.target_end_date)
        status = changes.get("status", goal.status)

        goal.title = _normalize_title(title)
        goal.planned_total_minutes = _normalize_planned_total_minutes(planned_total_minutes)
        _validate_dates(start_date, target_end_date)
        goal.start_date = start_date
        goal.target_end_date = target_end_date
        goal.status = _normalize_status(status)

        if "description" in changes:
            goal.description = _normalize_description(changes["description"])
        if "category_id" in changes:
            goal.category_id = _validate_required_category(session, changes["category_id"])

        goal.updated_at = utc_now()
        session.commit()
        session.refresh(goal)
        return goal
    except Exception:
        session.rollback()
        raise
    finally:
        if owns_session:
            session.close()


def archive_goal(goal_id: int, session=None) -> Goal:
    """Archive a goal while preserving future linked history."""
    return _set_goal_status(goal_id, "Archived", session=session)


def complete_goal(goal_id: int, session=None) -> Goal:
    """Mark a goal as completed without awarding XP directly."""
    return _set_goal_status(goal_id, "Completed", session=session)


def reopen_goal(goal_id: int, session=None) -> Goal:
    """Return an archived or completed goal to active status."""
    return _set_goal_status(goal_id, "Active", session=session)


def delete_goal_if_unused(goal_id: int, session=None) -> dict:
    """Hard-delete a goal only when it has no linked quests."""
    owns_session = session is None
    session = session or get_session()
    try:
        goal = session.get(Goal, goal_id)
        if goal is None:
            raise ValueError(f"Goal with id {goal_id} was not found.")

        linked_quests_count = _get_linked_quests_count(session, goal_id)
        summary = {
            "goal_id": goal_id,
            "linked_quests_count": linked_quests_count,
            "deleted": False,
            "reason": None,
        }
        if linked_quests_count > 0:
            summary["reason"] = "This goal has linked quest sessions and cannot be deleted safely."
            return summary

        session.delete(goal)
        session.commit()
        summary["deleted"] = True
        return summary
    except Exception:
        session.rollback()
        raise
    finally:
        if owns_session:
            session.close()


def get_goal_progress(goal_id: int, session=None) -> dict:
    """Return goal progress derived from linked quest sessions and check-ins."""
    owns_session = session is None
    session = session or get_session()
    try:
        goal = session.get(Goal, goal_id)
        if goal is None:
            raise ValueError(f"Goal with id {goal_id} was not found.")

        return _build_goal_progress(session, goal)
    finally:
        if owns_session:
            session.close()


def get_goal_completion_forecast(goal_id: int, today: date | None = None, session=None) -> dict:
    """Estimate a project completion date from completed planned effort to date."""
    today = today or date.today()
    owns_session = session is None
    session = session or get_session()
    try:
        goal = session.get(Goal, goal_id)
        if goal is None:
            raise ValueError(f"Goal with id {goal_id} was not found.")

        progress = _build_goal_progress(session, goal)
        base_forecast = {
            "available": False,
            "reason": None,
            "target_end_date": goal.target_end_date,
            "projected_completion_date": None,
            "on_track": None,
            "daily_completed_minutes": 0.0,
            "required_daily_minutes": None,
            "observed_completed_days": 0,
            "remaining_minutes": progress["remaining_minutes"],
        }
        if (goal.planned_total_minutes or 0) <= 0:
            base_forecast["reason"] = "Set a target effort to forecast this project."
            return base_forecast
        if goal.target_end_date is None:
            base_forecast["reason"] = "Set a target date to forecast this project."
            return base_forecast
        if progress["remaining_minutes"] == 0:
            base_forecast.update(
                {
                    "available": True,
                    "projected_completion_date": today,
                    "on_track": True,
                    "required_daily_minutes": 0,
                }
            )
            return base_forecast

        linked_quests = get_linked_goal_quests(session, goal.id)
        checkins = get_quest_checkins(session, [quest.id for quest in linked_quests])
        completed_dates = sorted(
            checkin.checkin_date for checkin in checkins if checkin.status == "Completed" and checkin.checkin_date <= today
        )
        if not completed_dates:
            base_forecast["reason"] = "Complete at least one project session to calculate a forecast."
            return base_forecast

        first_completed_date = completed_dates[0]
        observed_days = max((today - first_completed_date).days + 1, 1)
        daily_completed_minutes = progress["completed_minutes"] / observed_days
        projected_days = ceil(progress["remaining_minutes"] / daily_completed_minutes)
        projected_completion_date = today + timedelta(days=max(projected_days - 1, 0))
        days_to_target = max((goal.target_end_date - today).days + 1, 1)
        base_forecast.update(
            {
                "available": True,
                "projected_completion_date": projected_completion_date,
                "on_track": projected_completion_date <= goal.target_end_date,
                "daily_completed_minutes": round(daily_completed_minutes, 1),
                "required_daily_minutes": ceil(progress["remaining_minutes"] / days_to_target),
                "observed_completed_days": observed_days,
            }
        )
        return base_forecast
    finally:
        if owns_session:
            session.close()


def get_goal_history_summary(goal_id: int, session=None) -> dict:
    """Return linked session status counts and earned XP for a goal."""
    owns_session = session is None
    session = session or get_session()
    try:
        goal = session.get(Goal, goal_id)
        if goal is None:
            raise ValueError(f"Goal with id {goal_id} was not found.")

        progress = _build_goal_progress(session, goal)
        return {
            "goal_id": goal.id,
            "linked_quests_count": progress["linked_sessions_count"],
            "completed_sessions_count": progress["completed_sessions_count"],
            "planned_sessions_count": progress["planned_sessions_count"],
            "skipped_sessions_count": progress["skipped_sessions_count"],
            "failed_sessions_count": progress["failed_sessions_count"],
            "earned_xp": progress["earned_xp"],
        }
    finally:
        if owns_session:
            session.close()


def _set_goal_status(goal_id: int, status: str, session=None) -> Goal:
    owns_session = session is None
    session = session or get_session()
    try:
        goal = session.get(Goal, goal_id)
        if goal is None:
            raise ValueError(f"Goal with id {goal_id} was not found.")

        goal.status = _normalize_status(status)
        goal.updated_at = utc_now()
        session.commit()
        session.refresh(goal)
        return goal
    except Exception:
        session.rollback()
        raise
    finally:
        if owns_session:
            session.close()


def _build_goal_progress(session, goal: Goal) -> dict:
    linked_quests = get_linked_goal_quests(session, goal.id)
    linked_quest_ids = [quest.id for quest in linked_quests]
    checkins = get_quest_checkins(session, linked_quest_ids)
    quests_by_id = {quest.id: quest for quest in linked_quests}

    completed_minutes = 0
    completed_sessions_count = 0
    planned_sessions_count = 0
    skipped_sessions_count = 0
    failed_sessions_count = 0
    earned_xp = 0

    for checkin in checkins:
        quest = quests_by_id.get(checkin.quest_id)
        if quest is None:
            continue

        earned_xp += checkin.xp_awarded or 0
        if checkin.status == "Completed":
            completed_sessions_count += 1
            completed_minutes += get_quest_planned_minutes(quest)
        elif checkin.status == "Planned":
            planned_sessions_count += 1
        elif checkin.status == "Skipped":
            skipped_sessions_count += 1
        elif checkin.status == "Failed":
            failed_sessions_count += 1

    planned_total_minutes = goal.planned_total_minutes or 0
    remaining_minutes = max(planned_total_minutes - completed_minutes, 0)
    raw_progress = completed_minutes / planned_total_minutes * 100 if planned_total_minutes > 0 else 0
    progress_percent = max(0, min(raw_progress, 100))

    return {
        "goal_id": goal.id,
        "title": goal.title,
        "planned_total_minutes": planned_total_minutes,
        "completed_minutes": completed_minutes,
        "remaining_minutes": remaining_minutes,
        "progress_percent": progress_percent,
        "linked_sessions_count": len(linked_quests),
        "completed_sessions_count": completed_sessions_count,
        "planned_sessions_count": planned_sessions_count,
        "skipped_sessions_count": skipped_sessions_count,
        "failed_sessions_count": failed_sessions_count,
        "earned_xp": earned_xp,
        "expected_total_xp": calculate_time_based_xp(planned_total_minutes) if planned_total_minutes > 0 else 0,
    }


def _get_linked_quests_count(session, goal_id: int) -> int:
    return session.query(Quest).filter(Quest.goal_id == goal_id).count()


def _normalize_title(title: str) -> str:
    if not title or not title.strip():
        raise ValueError("Goal title is required.")
    return title.strip()


def _normalize_description(description: str | None) -> str | None:
    return (description or "").strip() or None


def _normalize_planned_total_minutes(planned_total_minutes: int | None) -> int:
    if planned_total_minutes is None:
        return 0

    value = int(planned_total_minutes)
    if value < 0:
        raise ValueError("Goal planned total minutes cannot be negative.")
    return value


def _normalize_status(status: str) -> str:
    if not status or not status.strip():
        raise ValueError("Goal status is required.")

    lookup = {valid.lower(): valid for valid in GOAL_STATUSES}
    key = status.strip().lower()
    if key not in lookup:
        valid = ", ".join(GOAL_STATUSES)
        raise ValueError(f"Unknown goal status '{status}'. Valid values: {valid}.")
    return lookup[key]


def _validate_required_category(session, category_id: int | None) -> int:
    if category_id is None:
        raise ValueError("Goal category is required.")

    category = session.get(Category, category_id)
    if category is None:
        raise ValueError(f"Category with id {category_id} was not found.")
    return category.id


def _validate_dates(start_date: date | None, target_end_date: date | None) -> None:
    if start_date is not None and target_end_date is not None and target_end_date < start_date:
        raise ValueError("Goal target end date cannot be before start date.")

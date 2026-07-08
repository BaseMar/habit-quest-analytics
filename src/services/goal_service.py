from datetime import date

from src.database.db import get_session
from src.database.models import Goal, utc_now


GOAL_STATUSES = ("Active", "Completed", "Archived")
_UNSET = object()


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
        goal = Goal(
            title=normalized_title,
            description=_normalize_description(description),
            category_id=category_id,
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
        query = session.query(Goal)
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
            goal.category_id = changes["category_id"]

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
    """Hard-delete a goal that has no linked quest history in the current phase."""
    owns_session = session is None
    session = session or get_session()
    try:
        goal = session.get(Goal, goal_id)
        if goal is None:
            raise ValueError(f"Goal with id {goal_id} was not found.")

        summary = {
            "goal_id": goal_id,
            "linked_quests_count": 0,
            "deleted": False,
            "reason": None,
        }
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
    """Return placeholder goal progress until quest-to-goal linking exists."""
    owns_session = session is None
    session = session or get_session()
    try:
        goal = session.get(Goal, goal_id)
        if goal is None:
            raise ValueError(f"Goal with id {goal_id} was not found.")

        return {
            "goal_id": goal.id,
            "planned_total_minutes": goal.planned_total_minutes,
            "completed_minutes": 0,
            "remaining_minutes": goal.planned_total_minutes,
            "progress_percent": 0,
            "earned_xp": 0,
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


def _normalize_title(title: str) -> str:
    if not title or not title.strip():
        raise ValueError("Goal title is required.")
    return title.strip()


def _normalize_description(description: str | None) -> str | None:
    return (description or "").strip() or None


def _normalize_planned_total_minutes(planned_total_minutes: int) -> int:
    value = int(planned_total_minutes)
    if value <= 0:
        raise ValueError("Goal planned total minutes must be positive.")
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


def _validate_dates(start_date: date | None, target_end_date: date | None) -> None:
    if start_date is not None and target_end_date is not None and target_end_date < start_date:
        raise ValueError("Goal target end date cannot be before start date.")

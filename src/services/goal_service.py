from datetime import date

from sqlalchemy.orm import joinedload

from src.database.db import get_session
from src.database.models import Goal, Quest, QuestCheckin, utc_now
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
    linked_quests = _get_linked_quests(session, goal.id)
    linked_quest_ids = [quest.id for quest in linked_quests]
    checkins = _get_linked_checkins(session, linked_quest_ids)
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
            completed_minutes += _get_quest_planned_minutes(quest)
        elif checkin.status == "Planned":
            planned_sessions_count += 1
        elif checkin.status == "Skipped":
            skipped_sessions_count += 1
        elif checkin.status == "Failed":
            failed_sessions_count += 1

    remaining_minutes = max(goal.planned_total_minutes - completed_minutes, 0)
    raw_progress = completed_minutes / goal.planned_total_minutes * 100
    progress_percent = max(0, min(raw_progress, 100))

    return {
        "goal_id": goal.id,
        "title": goal.title,
        "planned_total_minutes": goal.planned_total_minutes,
        "completed_minutes": completed_minutes,
        "remaining_minutes": remaining_minutes,
        "progress_percent": progress_percent,
        "linked_sessions_count": len(linked_quests),
        "completed_sessions_count": completed_sessions_count,
        "planned_sessions_count": planned_sessions_count,
        "skipped_sessions_count": skipped_sessions_count,
        "failed_sessions_count": failed_sessions_count,
        "earned_xp": earned_xp,
        "expected_total_xp": calculate_time_based_xp(goal.planned_total_minutes),
    }


def _get_linked_quests(session, goal_id: int) -> list[Quest]:
    return session.query(Quest).filter(Quest.goal_id == goal_id).order_by(Quest.id).all()


def _get_linked_quests_count(session, goal_id: int) -> int:
    return session.query(Quest).filter(Quest.goal_id == goal_id).count()


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
        return quest.estimated_minutes
    if quest.planned_start_at is not None and quest.planned_end_at is not None:
        return max(int((quest.planned_end_at - quest.planned_start_at).total_seconds() // 60), 0)
    return 0


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

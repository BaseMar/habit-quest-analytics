from datetime import date, datetime, time, timedelta

from sqlalchemy import and_, or_
from sqlalchemy.orm import joinedload, selectinload

from src.database.db import get_session
from src.database.models import Category, Goal, Quest, QuestCheckin, RecurringHabitInstance, utc_now
from src.constants import QUEST_STATUSES
from src.services.checklist_service import ensure_checkin
from src.services.xp_service import calculate_time_based_xp


VALID_QUEST_STATUSES = QUEST_STATUSES
STATUS_COLORS = {
    "Planned": "#38bdf8",
    "Completed": "#22c55e",
    "Failed": "#ef4444",
    "Skipped": "#f59e0b",
}

def create_quest(
    title: str,
    description: str = "",
    category_id: int | None = None,
    planned_date: date | None = None,
    estimated_minutes: int | None = None,
    goal_id: int | None = None,
    session=None,
) -> Quest:
    """Create and persist a quest."""
    estimated_minutes = _normalize_estimated_minutes(estimated_minutes)
    xp_reward = calculate_time_based_xp(estimated_minutes) if estimated_minutes is not None else 0

    owns_session = session is None
    session = session or get_session()
    try:
        normalized_goal_id = _validate_goal_for_link(session, goal_id)
        quest = Quest(
            title=_normalize_title(title),
            description=(description or "").strip() or None,
            category_id=category_id,
            goal_id=normalized_goal_id,
            status="Planned",
            xp_reward=xp_reward,
            due_date=planned_date,
            estimated_minutes=estimated_minutes,
        )
        session.add(quest)
        session.commit()
        session.refresh(quest)
        return quest
    except Exception:
        session.rollback()
        raise
    finally:
        if owns_session:
            session.close()


def create_scheduled_quest(
    title: str,
    description: str = "",
    category_id: int | None = None,
    planned_date: date | None = None,
    start_time: time | None = None,
    end_time: time | None = None,
    estimated_minutes: int | None = None,
    goal_id: int | None = None,
    session=None,
) -> Quest:
    """Create a quest planned for a specific day and time window."""
    if planned_date is None:
        raise ValueError("Planned date is required.")
    if start_time is None or end_time is None:
        raise ValueError("Start time and end time are required.")

    planned_start_at, planned_end_at = validate_schedule_times(planned_date, start_time, end_time)
    estimated_minutes = _normalize_estimated_minutes(estimated_minutes)
    if estimated_minutes is None:
        estimated_minutes = int((planned_end_at - planned_start_at).total_seconds() // 60)

    owns_session = session is None
    session = session or get_session()
    try:
        normalized_goal_id = _validate_goal_for_link(session, goal_id)
        quest = Quest(
            title=_normalize_title(title),
            description=(description or "").strip() or None,
            category_id=category_id,
            goal_id=normalized_goal_id,
            status="Planned",
            xp_reward=calculate_time_based_xp(estimated_minutes),
            due_date=planned_date,
            planned_start_at=planned_start_at,
            planned_end_at=planned_end_at,
            estimated_minutes=estimated_minutes,
        )
        session.add(quest)
        session.commit()
        session.refresh(quest)
        ensure_checkin(quest.id, planned_date, session=session)
        session.refresh(quest)
        return quest
    except Exception:
        session.rollback()
        raise
    finally:
        if owns_session:
            session.close()


def get_all_quests(session=None) -> list[Quest]:
    """Return all quests ordered by planned date and creation date."""
    owns_session = session is None
    session = session or get_session()
    try:
        return (
            session.query(Quest)
            .options(joinedload(Quest.category))
            .order_by(
                Quest.due_date.is_(None),
                Quest.due_date,
                Quest.planned_start_at.is_(None),
                Quest.planned_start_at,
                Quest.created_at.desc(),
            )
            .all()
        )
    finally:
        if owns_session:
            session.close()


def get_quests_by_date(planned_date: date, session=None) -> list[Quest]:
    """Return quests planned for a specific date."""
    return get_quests_by_planned_date(planned_date, session=session)


def get_quests_by_planned_date(planned_date: date, session=None) -> list[Quest]:
    """Return quests planned for a specific date."""
    return get_quests_for_day(planned_date, session=session)


def get_quests_for_day(planned_date: date, session=None) -> list[Quest]:
    """Return quests for a day, ordered by scheduled start time then creation time."""
    owns_session = session is None
    session = session or get_session()
    day_start = datetime.combine(planned_date, time.min)
    day_end = day_start + timedelta(days=1)
    try:
        quests = (
            session.query(Quest)
            .options(joinedload(Quest.category), selectinload(Quest.checkins))
            .filter(
                or_(
                    Quest.due_date == planned_date,
                    and_(Quest.planned_start_at >= day_start, Quest.planned_start_at < day_end),
                    Quest.checkins.any(QuestCheckin.checkin_date == planned_date),
                )
            )
            .all()
        )
        statuses_by_quest_id = _get_checkin_statuses_for_date(
            session,
            [quest.id for quest in quests],
            planned_date,
        )
        for quest in quests:
            quest.display_status = statuses_by_quest_id.get(quest.id, _normalize_status(quest.status))
        return sorted(
            quests,
            key=lambda quest: (
                quest.planned_start_at is None,
                quest.planned_start_at or quest.created_at or datetime.min,
            ),
        )
    finally:
        if owns_session:
            session.close()


def get_quests_for_calendar(session=None) -> list[dict]:
    """Return persisted quests as FullCalendar-compatible event dictionaries."""
    owns_session = session is None
    session = session or get_session()
    try:
        quests = (
            session.query(Quest)
            .options(joinedload(Quest.category), selectinload(Quest.checkins))
            .filter(
                or_(
                    Quest.planned_start_at.is_not(None),
                    Quest.due_date.is_not(None),
                )
            )
            .order_by(
                Quest.due_date.is_(None),
                Quest.due_date,
                Quest.planned_start_at.is_(None),
                Quest.planned_start_at,
            )
            .all()
        )
        statuses_by_quest_and_date = _get_checkin_statuses_for_quest_dates(
            session,
            [(quest.id, _quest_event_date(quest)) for quest in quests],
        )
        return [
            quest_to_calendar_event(
                quest,
                status_override=statuses_by_quest_and_date.get((quest.id, _quest_event_date(quest))),
            )
            for quest in quests
        ]
    finally:
        if owns_session:
            session.close()


def update_quest_status(quest_id: int, status: str, session=None) -> Quest:
    """Update quest status and set completion time when first completed."""
    normalized_status = _normalize_status(status)

    owns_session = session is None
    session = session or get_session()
    try:
        quest = session.get(Quest, quest_id)
        if quest is None:
            raise ValueError(f"Quest with id {quest_id} was not found.")

        quest.status = normalized_status
        if normalized_status == "Completed" and quest.completed_at is None:
            quest.completed_at = utc_now()

        session.commit()
        session.refresh(quest)
        return quest
    except Exception:
        session.rollback()
        raise
    finally:
        if owns_session:
            session.close()


def get_one_time_quest_deletion_summary(quest_id: int, session=None) -> dict:
    """Return whether a non-recurring quest can be safely hard-deleted."""
    owns_session = session is None
    session = session or get_session()
    try:
        quest = session.get(Quest, quest_id)
        if quest is None:
            raise ValueError(f"Quest with id {quest_id} was not found.")
        return _build_one_time_quest_deletion_summary(session, quest)
    finally:
        if owns_session:
            session.close()


def delete_one_time_quest_if_unresolved(quest_id: int, session=None) -> dict:
    """Delete a non-recurring quest only when all related check-ins are unresolved Planned rows."""
    owns_session = session is None
    session = session or get_session()
    try:
        quest = session.get(Quest, quest_id)
        if quest is None:
            raise ValueError(f"Quest with id {quest_id} was not found.")

        summary = _build_one_time_quest_deletion_summary(session, quest)
        if not summary["can_delete"]:
            return summary

        checkins = _get_quest_checkins(session, quest.id)
        for checkin in checkins:
            session.delete(checkin)
        session.delete(quest)
        session.commit()

        summary["deleted"] = True
        summary["deleted_checkins_count"] = len(checkins)
        summary["deleted_quest_count"] = 1
        return summary
    except Exception:
        session.rollback()
        raise
    finally:
        if owns_session:
            session.close()


def get_categories(session=None) -> list[Category]:
    """Return categories ordered by name."""
    owns_session = session is None
    session = session or get_session()
    try:
        return session.query(Category).order_by(Category.name).all()
    finally:
        if owns_session:
            session.close()


def validate_schedule_times(planned_date: date, start_time: time, end_time: time) -> tuple[datetime, datetime]:
    """Return planned start/end datetimes or raise when the time range is invalid."""
    planned_start_at = datetime.combine(planned_date, start_time)
    planned_end_at = datetime.combine(planned_date, end_time)
    if planned_end_at <= planned_start_at:
        raise ValueError("End time must be after start time.")

    return planned_start_at, planned_end_at


def quest_to_calendar_event(quest: Quest, status_override: str | None = None) -> dict:
    """Convert a quest record to a calendar event dictionary."""
    start = quest.planned_start_at or quest.due_date
    event_date = _quest_event_date(quest)
    status = (
        _normalize_status(status_override)
        if status_override is not None
        else get_quest_status_for_date(quest, event_date)
        if event_date is not None
        else _normalize_status(quest.status)
    )
    end = quest.planned_end_at
    color = STATUS_COLORS.get(status, STATUS_COLORS["Planned"])
    category = quest.category.name if quest.category else "Uncategorized"
    event = {
        "id": str(quest.id),
        "title": quest.title,
        "start": _format_calendar_datetime(start),
        "end": _format_calendar_datetime(end),
        "status": status,
        "category": category,
        "xp_reward": quest.xp_reward or 0,
        "color": color,
        "backgroundColor": color,
        "borderColor": color,
        "extendedProps": {
            "status": status,
            "category": category,
            "xp_reward": quest.xp_reward or 0,
        },
    }
    if quest.planned_start_at is None and quest.due_date is not None:
        event["allDay"] = True
    return event


def get_quest_status_for_date(quest: Quest, target_date: date) -> str:
    """Return the check-in status for a quest on a date, falling back to quest status."""
    for checkin in getattr(quest, "checkins", []) or []:
        if checkin.checkin_date == target_date:
            return _normalize_status(checkin.status)
    return _normalize_status(quest.status)


def _get_checkin_statuses_for_date(session, quest_ids: list[int], target_date: date) -> dict[int, str]:
    if not quest_ids:
        return {}

    checkins = (
        session.query(QuestCheckin)
        .filter(
            QuestCheckin.quest_id.in_(quest_ids),
            QuestCheckin.checkin_date == target_date,
        )
        .all()
    )
    return {checkin.quest_id: _normalize_status(checkin.status) for checkin in checkins}


def _get_checkin_statuses_for_quest_dates(
    session,
    quest_date_pairs: list[tuple[int, date | None]],
) -> dict[tuple[int, date], str]:
    normalized_pairs = [(quest_id, target_date) for quest_id, target_date in quest_date_pairs if target_date is not None]
    if not normalized_pairs:
        return {}

    quest_ids = {quest_id for quest_id, _ in normalized_pairs}
    target_dates = {target_date for _, target_date in normalized_pairs}
    checkins = (
        session.query(QuestCheckin)
        .filter(
            QuestCheckin.quest_id.in_(quest_ids),
            QuestCheckin.checkin_date.in_(target_dates),
        )
        .all()
    )
    requested_pairs = set(normalized_pairs)
    return {
        (checkin.quest_id, checkin.checkin_date): _normalize_status(checkin.status)
        for checkin in checkins
        if (checkin.quest_id, checkin.checkin_date) in requested_pairs
    }


def _build_one_time_quest_deletion_summary(session, quest: Quest) -> dict:
    summary = {
        "quest_id": quest.id,
        "can_delete": False,
        "deleted": False,
        "reason": None,
        "checkins_count": 0,
        "deleted_checkins_count": 0,
        "deleted_quest_count": 0,
    }

    if _get_recurring_instance_for_quest(session, quest.id) is not None:
        summary["reason"] = "Recurring generated quests must be removed through the recurring occurrence workflow."
        return summary

    checkins = _get_quest_checkins(session, quest.id)
    summary["checkins_count"] = len(checkins)
    if any(not _is_unresolved_planned_checkin(checkin) for checkin in checkins):
        summary["reason"] = "This quest has historical status or awarded XP and cannot be deleted safely."
        return summary

    summary["can_delete"] = True
    return summary


def _get_recurring_instance_for_quest(session, quest_id: int) -> RecurringHabitInstance | None:
    return session.query(RecurringHabitInstance).filter(RecurringHabitInstance.quest_id == quest_id).one_or_none()


def _get_quest_checkins(session, quest_id: int) -> list[QuestCheckin]:
    return session.query(QuestCheckin).filter(QuestCheckin.quest_id == quest_id).order_by(QuestCheckin.id).all()


def _is_unresolved_planned_checkin(checkin: QuestCheckin) -> bool:
    return (
        checkin.status == "Planned"
        and checkin.xp_awarded == 0
        and checkin.completed_at is None
        and checkin.skipped_at is None
        and checkin.failed_at is None
    )


def _normalize_status(status: str) -> str:
    if not status:
        raise ValueError("Quest status is required.")

    lookup = {valid.lower(): valid for valid in VALID_QUEST_STATUSES}
    key = status.strip().lower()
    if key not in lookup:
        valid = ", ".join(VALID_QUEST_STATUSES)
        raise ValueError(f"Unknown quest status '{status}'. Valid values: {valid}.")

    return lookup[key]


def _normalize_title(title: str) -> str:
    if not title or not title.strip():
        raise ValueError("Quest title is required.")
    return title.strip()


def _normalize_estimated_minutes(estimated_minutes: int | None) -> int | None:
    if estimated_minutes is None:
        return None

    value = int(estimated_minutes)
    if value <= 0:
        return None

    return value


def _validate_goal_for_link(session, goal_id: int | None) -> int | None:
    if goal_id is None:
        return None

    goal = session.get(Goal, goal_id)
    if goal is None:
        raise ValueError(f"Goal with id {goal_id} was not found.")
    if goal.status != "Active":
        raise ValueError("Only active goals can receive new quest sessions.")
    return goal.id


def _quest_event_date(quest: Quest) -> date | None:
    if quest.planned_start_at is not None:
        return quest.planned_start_at.date()
    return quest.due_date


def _format_calendar_datetime(value: date | datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()

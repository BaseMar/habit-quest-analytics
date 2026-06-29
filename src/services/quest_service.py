from datetime import date, datetime, time, timedelta

from sqlalchemy import and_, or_
from sqlalchemy.orm import joinedload

from src.database.db import get_session
from src.database.models import Category, Quest, utc_now
from src.constants import QUEST_STATUSES
from src.services.xp_service import calculate_xp


VALID_QUEST_STATUSES = QUEST_STATUSES
STATUS_COLORS = {
    "Planned": "#38bdf8",
    "Completed": "#22c55e",
    "Failed": "#ef4444",
    "Skipped": "#f59e0b",
}


def get_quest_xp_reward(difficulty: str) -> int:
    """Return the XP reward for a quest difficulty."""
    return calculate_xp(difficulty)


def create_quest(
    title: str,
    description: str = "",
    category_id: int | None = None,
    difficulty: str = "Easy",
    planned_date: date | None = None,
    estimated_minutes: int | None = None,
    session=None,
) -> Quest:
    """Create and persist a quest."""
    xp_reward = calculate_xp(difficulty)
    estimated_minutes = _normalize_estimated_minutes(estimated_minutes)

    owns_session = session is None
    session = session or get_session()
    try:
        quest = Quest(
            title=_normalize_title(title),
            description=(description or "").strip() or None,
            category_id=category_id,
            difficulty=difficulty.strip().title(),
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
    difficulty: str = "Easy",
    planned_date: date | None = None,
    start_time: time | None = None,
    end_time: time | None = None,
    estimated_minutes: int | None = None,
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
        quest = Quest(
            title=_normalize_title(title),
            description=(description or "").strip() or None,
            category_id=category_id,
            difficulty=difficulty.strip().title(),
            status="Planned",
            xp_reward=calculate_xp(difficulty),
            due_date=planned_date,
            planned_start_at=planned_start_at,
            planned_end_at=planned_end_at,
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
            .options(joinedload(Quest.category))
            .filter(
                or_(
                    Quest.due_date == planned_date,
                    and_(Quest.planned_start_at >= day_start, Quest.planned_start_at < day_end),
                )
            )
            .all()
        )
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
            .options(joinedload(Quest.category))
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
        return [quest_to_calendar_event(quest) for quest in quests]
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


def quest_to_calendar_event(quest: Quest) -> dict:
    """Convert a quest record to a calendar event dictionary."""
    status = _normalize_status(quest.status)
    start = quest.planned_start_at or quest.due_date
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
        "difficulty": quest.difficulty,
        "xp_reward": quest.xp_reward or 0,
        "color": color,
        "backgroundColor": color,
        "borderColor": color,
        "extendedProps": {
            "status": status,
            "category": category,
            "difficulty": quest.difficulty,
            "xp_reward": quest.xp_reward or 0,
        },
    }
    if quest.planned_start_at is None and quest.due_date is not None:
        event["allDay"] = True
    return event


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


def _format_calendar_datetime(value: date | datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()

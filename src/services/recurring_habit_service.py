import json
from datetime import date

from src.database.db import get_session
from src.database.models import RecurringHabit, utc_now
from src.services.xp_service import calculate_xp


SUPPORTED_RECURRENCE_TYPES = ("selected_weekdays",)


def create_recurring_habit(
    title: str,
    category_id: int | None,
    difficulty: str,
    estimated_minutes: int,
    recurrence_type: str,
    weekdays: list[int] | None,
    start_date: date,
    end_date: date | None = None,
    description: str | None = None,
    is_active: bool = True,
    session=None,
) -> RecurringHabit:
    """Create and persist a recurring habit template."""
    normalized_title = _normalize_title(title)
    normalized_difficulty = _normalize_difficulty(difficulty)
    normalized_estimated_minutes = _normalize_estimated_minutes(estimated_minutes)
    normalized_recurrence_type = _normalize_recurrence_type(recurrence_type)
    _validate_dates(start_date, end_date)
    serialized_weekdays = (
        serialize_weekdays(weekdays)
        if normalized_recurrence_type == "selected_weekdays"
        else None
    )

    owns_session = session is None
    session = session or get_session()
    try:
        habit = RecurringHabit(
            title=normalized_title,
            description=(description or "").strip() or None,
            category_id=category_id,
            difficulty=normalized_difficulty,
            xp_reward=calculate_xp(normalized_difficulty),
            estimated_minutes=normalized_estimated_minutes,
            recurrence_type=normalized_recurrence_type,
            weekdays=serialized_weekdays,
            start_date=start_date,
            end_date=end_date,
            is_active=bool(is_active),
        )
        session.add(habit)
        session.commit()
        session.refresh(habit)
        return habit
    except Exception:
        session.rollback()
        raise
    finally:
        if owns_session:
            session.close()


def list_recurring_habits(active_only: bool = False, session=None) -> list[RecurringHabit]:
    """Return recurring habit templates in deterministic display order."""
    owns_session = session is None
    session = session or get_session()
    try:
        query = session.query(RecurringHabit)
        if active_only:
            query = query.filter(RecurringHabit.is_active.is_(True))
        return (
            query.order_by(
                RecurringHabit.is_active.desc(),
                RecurringHabit.title.asc(),
                RecurringHabit.id.asc(),
            )
            .all()
        )
    finally:
        if owns_session:
            session.close()


def get_recurring_habit(habit_id: int, session=None) -> RecurringHabit | None:
    """Return a recurring habit template by id, or None when missing."""
    owns_session = session is None
    session = session or get_session()
    try:
        return session.get(RecurringHabit, habit_id)
    finally:
        if owns_session:
            session.close()


def set_recurring_habit_active(
    habit_id: int,
    is_active: bool,
    session=None,
) -> RecurringHabit:
    """Activate or deactivate a recurring habit template."""
    owns_session = session is None
    session = session or get_session()
    try:
        habit = session.get(RecurringHabit, habit_id)
        if habit is None:
            raise ValueError(f"Recurring habit with id {habit_id} was not found.")

        habit.is_active = bool(is_active)
        habit.updated_at = utc_now()
        session.commit()
        session.refresh(habit)
        return habit
    except Exception:
        session.rollback()
        raise
    finally:
        if owns_session:
            session.close()


def serialize_weekdays(weekdays: list[int]) -> str:
    """Return a stable JSON representation of a weekday list."""
    return json.dumps(validate_weekdays(weekdays))


def deserialize_weekdays(weekdays_text: str | None) -> list[int]:
    """Return a weekday list from serialized JSON text."""
    if not weekdays_text:
        return []

    try:
        parsed = json.loads(weekdays_text)
    except json.JSONDecodeError as error:
        raise ValueError("Weekdays must be serialized JSON.") from error

    if not isinstance(parsed, list):
        raise ValueError("Weekdays must be a JSON list.")
    return validate_weekdays(parsed)


def validate_weekdays(weekdays: list[int] | None) -> list[int]:
    """Validate, de-duplicate, and sort weekday numbers."""
    if not weekdays:
        raise ValueError("At least one weekday is required for selected_weekdays recurrence.")

    normalized: set[int] = set()
    for weekday in weekdays:
        if isinstance(weekday, bool) or not isinstance(weekday, int):
            raise ValueError("Weekday values must be integers from 0 to 6.")
        if weekday < 0 or weekday > 6:
            raise ValueError("Weekday values must be integers from 0 to 6.")
        normalized.add(weekday)

    return sorted(normalized)


def _normalize_title(title: str) -> str:
    if not title or not title.strip():
        raise ValueError("Recurring habit title is required.")
    return title.strip()


def _normalize_difficulty(difficulty: str) -> str:
    calculate_xp(difficulty)
    return difficulty.strip().title()


def _normalize_estimated_minutes(estimated_minutes: int) -> int:
    try:
        value = int(estimated_minutes)
    except (TypeError, ValueError) as error:
        raise ValueError("Estimated minutes must be a positive integer.") from error

    if value <= 0:
        raise ValueError("Estimated minutes must be greater than 0.")
    return value


def _normalize_recurrence_type(recurrence_type: str) -> str:
    normalized = (recurrence_type or "").strip().lower()
    if normalized not in SUPPORTED_RECURRENCE_TYPES:
        valid = ", ".join(SUPPORTED_RECURRENCE_TYPES)
        raise ValueError(f"Unsupported recurrence type '{recurrence_type}'. Valid values: {valid}.")
    return normalized


def _validate_dates(start_date: date, end_date: date | None) -> None:
    if start_date is None:
        raise ValueError("Start date is required.")
    if end_date is not None and end_date < start_date:
        raise ValueError("End date must be on or after start date.")

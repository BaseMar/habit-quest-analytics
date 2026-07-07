import json
from calendar import monthrange
from datetime import date, datetime, time

from src.database.db import get_session
from src.database.models import Quest, QuestCheckin, RecurringHabit, RecurringHabitInstance, utc_now
from src.services.xp_service import calculate_time_based_xp, calculate_xp


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
    planned_start_time: time | None = None,
    planned_end_time: time | None = None,
    session=None,
) -> RecurringHabit:
    """Create and persist a recurring habit template."""
    normalized_title = _normalize_title(title)
    normalized_difficulty = _normalize_difficulty(difficulty)
    normalized_estimated_minutes = _normalize_estimated_minutes(estimated_minutes)
    normalized_recurrence_type = _normalize_recurrence_type(recurrence_type)
    _validate_dates(start_date, end_date)
    _validate_planned_times(planned_start_time, planned_end_time)
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
            xp_reward=calculate_time_based_xp(normalized_estimated_minutes),
            estimated_minutes=normalized_estimated_minutes,
            recurrence_type=normalized_recurrence_type,
            weekdays=serialized_weekdays,
            start_date=start_date,
            end_date=end_date,
            planned_start_time=planned_start_time,
            planned_end_time=planned_end_time,
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


def get_recurring_habit_history_summary(
    recurring_habit_id: int,
    session=None,
    today: date | None = None,
) -> dict:
    """Return generated history and removable planned-day counts for a recurring habit."""
    current_date = today or date.today()
    owns_session = session is None
    session = session or get_session()
    try:
        habit = session.get(RecurringHabit, recurring_habit_id)
        if habit is None:
            raise ValueError(f"Recurring habit with id {recurring_habit_id} was not found.")

        instances = _get_recurring_habit_instances(session, recurring_habit_id)
        summary = {
            "recurring_habit_id": recurring_habit_id,
            "generated_instances_count": len(instances),
            "completed_count": 0,
            "skipped_count": 0,
            "failed_count": 0,
            "planned_count": 0,
            "removable_future_planned_count": 0,
        }

        for instance in instances:
            checkin = _get_instance_scheduled_checkin(session, instance)
            if checkin is not None:
                if checkin.status == "Completed":
                    summary["completed_count"] += 1
                elif checkin.status == "Skipped":
                    summary["skipped_count"] += 1
                elif checkin.status == "Failed":
                    summary["failed_count"] += 1
                elif checkin.status == "Planned":
                    summary["planned_count"] += 1

            if _is_removable_future_planned_instance(session, instance, current_date):
                summary["removable_future_planned_count"] += 1

        return summary
    finally:
        if owns_session:
            session.close()


def delete_recurring_habit_if_unused(recurring_habit_id: int, session=None) -> dict:
    """Hard-delete a recurring habit only when it has no generated instances."""
    owns_session = session is None
    session = session or get_session()
    try:
        habit = session.get(RecurringHabit, recurring_habit_id)
        if habit is None:
            raise ValueError(f"Recurring habit with id {recurring_habit_id} was not found.")

        instances_count = (
            session.query(RecurringHabitInstance)
            .filter(RecurringHabitInstance.recurring_habit_id == recurring_habit_id)
            .count()
        )
        summary = {
            "recurring_habit_id": recurring_habit_id,
            "generated_instances_count": instances_count,
            "deleted": False,
        }
        if instances_count > 0:
            return summary

        session.delete(habit)
        session.commit()
        summary["deleted"] = True
        return summary
    except Exception:
        session.rollback()
        raise
    finally:
        if owns_session:
            session.close()


def archive_recurring_habit(recurring_habit_id: int, session=None) -> dict:
    """Deactivate a recurring habit while preserving generated history."""
    owns_session = session is None
    session = session or get_session()
    try:
        habit = session.get(RecurringHabit, recurring_habit_id)
        if habit is None:
            raise ValueError(f"Recurring habit with id {recurring_habit_id} was not found.")

        habit.is_active = False
        habit.updated_at = utc_now()
        session.commit()
        return get_recurring_habit_history_summary(recurring_habit_id, session=session)
    except Exception:
        session.rollback()
        raise
    finally:
        if owns_session:
            session.close()


def remove_future_planned_recurring_instances(
    recurring_habit_id: int,
    today: date | None = None,
    session=None,
) -> dict:
    """Remove future generated recurring days only when they are unresolved planned rows."""
    current_date = today or date.today()
    owns_session = session is None
    session = session or get_session()
    try:
        habit = session.get(RecurringHabit, recurring_habit_id)
        if habit is None:
            raise ValueError(f"Recurring habit with id {recurring_habit_id} was not found.")

        instances = _get_recurring_habit_instances(session, recurring_habit_id)
        removable_instances = [
            instance
            for instance in instances
            if _is_removable_future_planned_instance(session, instance, current_date)
        ]
        summary = {
            "recurring_habit_id": recurring_habit_id,
            "generated_instances_count": len(instances),
            "completed_count": 0,
            "skipped_count": 0,
            "failed_count": 0,
            "planned_count": 0,
            "removable_future_planned_count": len(removable_instances),
            "removed_instances_count": 0,
            "removed_checkins_count": 0,
            "removed_quests_count": 0,
        }

        for instance in instances:
            checkin = _get_instance_scheduled_checkin(session, instance)
            if checkin is None:
                continue
            if checkin.status == "Completed":
                summary["completed_count"] += 1
            elif checkin.status == "Skipped":
                summary["skipped_count"] += 1
            elif checkin.status == "Failed":
                summary["failed_count"] += 1
            elif checkin.status == "Planned":
                summary["planned_count"] += 1

        for instance in removable_instances:
            quest = instance.quest
            checkin = _get_instance_scheduled_checkin(session, instance)
            if checkin is None or quest is None:
                continue

            session.delete(checkin)
            summary["removed_checkins_count"] += 1
            session.delete(instance)
            summary["removed_instances_count"] += 1
            session.flush()

            if not _quest_has_checkins(session, quest.id):
                session.delete(quest)
                summary["removed_quests_count"] += 1

        session.commit()
        return summary
    except Exception:
        session.rollback()
        raise
    finally:
        if owns_session:
            session.close()


def build_recurring_habit_dates_for_month(
    habit: RecurringHabit,
    year: int,
    month: int,
) -> list[date]:
    """Return eligible recurring habit dates in a selected month without writing data."""
    days = _build_month_days(year, month)
    if not habit.is_active:
        return []

    recurrence_type = _normalize_recurrence_type(habit.recurrence_type)
    if recurrence_type != "selected_weekdays":
        return []

    weekdays = set(deserialize_weekdays(habit.weekdays))
    return [
        day
        for day in days
        if day.weekday() in weekdays
        and day >= habit.start_date
        and (habit.end_date is None or day <= habit.end_date)
    ]


def generate_recurring_habit_for_month(
    habit_id: int,
    year: int,
    month: int,
    session=None,
) -> dict:
    """Generate planned quest days and check-ins for one recurring habit in a month."""
    _build_month_days(year, month)

    owns_session = session is None
    session = session or get_session()
    try:
        habit = session.get(RecurringHabit, habit_id)
        if habit is None:
            raise ValueError(f"Recurring habit with id {habit_id} was not found.")

        eligible_dates = build_recurring_habit_dates_for_month(habit, year, month)
        generated_count = 0
        skipped_existing_count = 0

        for scheduled_date in eligible_dates:
            existing_instance = _get_recurring_habit_instance(session, habit.id, scheduled_date)
            if existing_instance is not None:
                skipped_existing_count += 1
                continue

            quest = Quest(
                title=habit.title,
                description=habit.description,
                category_id=habit.category_id,
                difficulty=habit.difficulty,
                status="Planned",
                xp_reward=habit.xp_reward,
                due_date=scheduled_date,
                planned_start_at=_combine_date_time(scheduled_date, habit.planned_start_time),
                planned_end_at=_combine_date_time(scheduled_date, habit.planned_end_time),
                estimated_minutes=habit.estimated_minutes,
            )
            session.add(quest)
            session.flush()

            checkin = QuestCheckin(
                quest_id=quest.id,
                checkin_date=scheduled_date,
                status="Planned",
                xp_awarded=0,
            )
            instance = RecurringHabitInstance(
                recurring_habit_id=habit.id,
                scheduled_date=scheduled_date,
                quest_id=quest.id,
            )
            session.add(checkin)
            session.add(instance)
            session.commit()
            generated_count += 1

        return {
            "habit_id": habit.id,
            "year": year,
            "month": month,
            "generated_count": generated_count,
            "skipped_existing_count": skipped_existing_count,
            "eligible_count": len(eligible_dates),
        }
    except Exception:
        session.rollback()
        raise
    finally:
        if owns_session:
            session.close()


def generate_all_recurring_habits_for_month(
    year: int,
    month: int,
    active_only: bool = True,
    session=None,
) -> dict:
    """Generate planned quest days and check-ins for recurring habits in a month."""
    _build_month_days(year, month)

    owns_session = session is None
    session = session or get_session()
    try:
        habits = list_recurring_habits(active_only=active_only, session=session)
        habit_summaries = [
            generate_recurring_habit_for_month(habit.id, year, month, session=session)
            for habit in habits
        ]
        return {
            "year": year,
            "month": month,
            "habit_summaries": habit_summaries,
            "total_generated": sum(summary["generated_count"] for summary in habit_summaries),
            "total_skipped_existing": sum(summary["skipped_existing_count"] for summary in habit_summaries),
            "total_eligible": sum(summary["eligible_count"] for summary in habit_summaries),
        }
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


def _validate_planned_times(planned_start_time: time | None, planned_end_time: time | None) -> None:
    if planned_start_time is None and planned_end_time is None:
        return
    if planned_start_time is None or planned_end_time is None:
        raise ValueError("Start time and end time must both be provided for timed recurring habits.")
    if planned_end_time <= planned_start_time:
        raise ValueError("End time must be after start time.")


def _combine_date_time(scheduled_date: date, scheduled_time: time | None) -> datetime | None:
    if scheduled_time is None:
        return None
    return datetime.combine(scheduled_date, scheduled_time)


def _build_month_days(year: int, month: int) -> list[date]:
    if month < 1 or month > 12:
        raise ValueError("month must be between 1 and 12.")
    if year < 1:
        raise ValueError("year must be 1 or greater.")

    day_count = monthrange(year, month)[1]
    return [date(year, month, day) for day in range(1, day_count + 1)]


def _get_recurring_habit_instance(
    session,
    habit_id: int,
    scheduled_date: date,
) -> RecurringHabitInstance | None:
    return (
        session.query(RecurringHabitInstance)
        .filter(
            RecurringHabitInstance.recurring_habit_id == habit_id,
            RecurringHabitInstance.scheduled_date == scheduled_date,
        )
        .one_or_none()
    )


def _get_recurring_habit_instances(session, habit_id: int) -> list[RecurringHabitInstance]:
    return (
        session.query(RecurringHabitInstance)
        .filter(RecurringHabitInstance.recurring_habit_id == habit_id)
        .order_by(RecurringHabitInstance.scheduled_date, RecurringHabitInstance.id)
        .all()
    )


def _get_instance_scheduled_checkin(session, instance: RecurringHabitInstance) -> QuestCheckin | None:
    return (
        session.query(QuestCheckin)
        .filter(
            QuestCheckin.quest_id == instance.quest_id,
            QuestCheckin.checkin_date == instance.scheduled_date,
        )
        .one_or_none()
    )


def _is_removable_future_planned_instance(
    session,
    instance: RecurringHabitInstance,
    today: date,
) -> bool:
    if instance.scheduled_date < today or instance.quest is None:
        return False

    checkins = (
        session.query(QuestCheckin)
        .filter(QuestCheckin.quest_id == instance.quest_id)
        .all()
    )
    if len(checkins) != 1:
        return False

    checkin = checkins[0]
    return (
        checkin.checkin_date == instance.scheduled_date
        and checkin.status == "Planned"
        and checkin.xp_awarded == 0
        and checkin.completed_at is None
        and checkin.skipped_at is None
        and checkin.failed_at is None
    )


def _quest_has_checkins(session, quest_id: int) -> bool:
    return session.query(QuestCheckin).filter(QuestCheckin.quest_id == quest_id).count() > 0

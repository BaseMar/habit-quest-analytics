from datetime import date, datetime, time, timedelta

from sqlalchemy import and_, or_
from sqlalchemy.orm import joinedload

from src.database.db import get_session
from src.database.models import Goal, RecurringHabit, RecurringHabitInstance, Quest, QuestCheckin, utc_now
from src.services.schedule_service import build_month_days


VALID_CHECKIN_STATUSES = ("Planned", "Completed", "Skipped", "Failed")


def get_month_checklist(year: int, month: int, session=None) -> dict:
    """Build quest rows and daily check-in cells for a selected month."""
    days = build_month_days(year, month)
    month_start = days[0]
    month_end = days[-1]
    month_start_at = datetime.combine(month_start, time.min)
    next_month_start_at = datetime.combine(month_end + timedelta(days=1), time.min)

    owns_session = session is None
    session = session or get_session()
    try:
        quests = (
            session.query(Quest)
            .options(
                joinedload(Quest.category),
                joinedload(Quest.goal).joinedload(Goal.category),
                joinedload(Quest.recurring_habit_instance)
                .joinedload(RecurringHabitInstance.recurring_habit)
                .joinedload(RecurringHabit.category),
            )
            .filter(
                or_(
                    and_(Quest.due_date >= month_start, Quest.due_date <= month_end),
                    and_(
                        Quest.planned_start_at >= month_start_at,
                        Quest.planned_start_at < next_month_start_at,
                    ),
                    Quest.checkins.any(
                        and_(
                            QuestCheckin.checkin_date >= month_start,
                            QuestCheckin.checkin_date <= month_end,
                        )
                    ),
                )
            )
            .order_by(
                Quest.due_date.is_(None),
                Quest.due_date,
                Quest.planned_start_at.is_(None),
                Quest.planned_start_at,
                Quest.created_at,
                Quest.id,
            )
            .all()
        )

        for quest in quests:
            scheduled_date = _get_scheduled_date_in_month(quest, month_start, month_end)
            if scheduled_date is not None:
                ensure_checkin(quest.id, scheduled_date, session=session)

        quest_ids = [quest.id for quest in quests]
        checkins_by_quest_and_date = _get_month_checkins_by_quest_and_date(
            session,
            quest_ids,
            month_start,
            month_end,
        )

        return {
            "year": year,
            "month": month,
            "days": days,
            "rows": [
                _build_month_row(quest, days, checkins_by_quest_and_date.get(quest.id, {}))
                for quest in quests
                if quest.recurring_habit_instance is None and quest.goal_id is None
            ]
            + _build_goal_month_rows(quests, days, checkins_by_quest_and_date, month_start, month_end)
            + _build_recurring_month_rows(quests, days, checkins_by_quest_and_date, month_start, month_end),
        }
    finally:
        if owns_session:
            session.close()


def ensure_checkin(quest_id: int, checkin_date: date, session=None) -> QuestCheckin:
    """Return an existing daily quest check-in or create a planned one."""
    owns_session = session is None
    session = session or get_session()
    try:
        quest = _get_quest_or_raise(session, quest_id)
        checkin = _get_checkin(session, quest.id, checkin_date)
        if checkin is None:
            checkin = QuestCheckin(
                quest_id=quest.id,
                checkin_date=checkin_date,
                status="Planned",
                xp_awarded=0,
            )
            session.add(checkin)
            session.commit()
            session.refresh(checkin)
        return checkin
    except Exception:
        session.rollback()
        raise
    finally:
        if owns_session:
            session.close()


def update_checkin_status(
    quest_id: int,
    checkin_date: date,
    status: str,
    actual_minutes: int | None = None,
    session=None,
) -> QuestCheckin:
    """Update a daily check-in status and apply timestamp/XP rules."""
    normalized_status = _normalize_checkin_status(status)
    normalized_actual_minutes = _normalize_actual_minutes(actual_minutes)
    if normalized_actual_minutes is not None and normalized_status != "Completed":
        raise ValueError("Actual minutes can only be recorded for completed check-ins.")

    owns_session = session is None
    session = session or get_session()
    try:
        quest = _get_quest_or_raise(session, quest_id)
        checkin = _get_checkin(session, quest.id, checkin_date)
        if checkin is None:
            checkin = QuestCheckin(
                quest_id=quest.id,
                checkin_date=checkin_date,
                status="Planned",
                xp_awarded=0,
            )
            session.add(checkin)

        _apply_status(checkin, quest, normalized_status, normalized_actual_minutes)
        session.commit()
        session.refresh(checkin)
        return checkin
    except Exception:
        session.rollback()
        raise
    finally:
        if owns_session:
            session.close()


def get_checklist_cell_for_date(row: dict, checkin_date: date) -> dict | None:
    """Return the checklist cell for a row/date from a built monthly checklist row."""
    return row.get("cells", {}).get(checkin_date)


def is_checklist_cell_editable(row: dict, checkin_date: date) -> bool:
    """Return whether a checklist row/date has a scheduled quest day to update."""
    cell = get_checklist_cell_for_date(row, checkin_date)
    if cell is None:
        return False
    if cell.get("entries"):
        return any(entry.get("quest_id") is not None and entry.get("checkin_id") is not None for entry in cell["entries"])
    return cell.get("quest_id") is not None and cell.get("checkin_id") is not None


def update_checklist_cell_status(
    row: dict,
    checkin_date: date,
    status: str,
    quest_id: int | None = None,
    checkin_id: int | None = None,
    session=None,
) -> QuestCheckin:
    """Update status only for a scheduled/generated checklist cell."""
    if not is_checklist_cell_editable(row, checkin_date):
        raise ValueError("This quest is not scheduled for the selected date.")

    cell = get_checklist_cell_for_date(row, checkin_date)
    entry = _resolve_checklist_update_entry(cell, quest_id=quest_id, checkin_id=checkin_id)
    return update_checkin_status(entry["quest_id"], checkin_date, status, session=session)


def complete_checkin(
    quest_id: int,
    checkin_date: date,
    actual_minutes: int | None = None,
    session=None,
) -> QuestCheckin:
    """Mark a daily quest check-in as completed."""
    return update_checkin_status(
        quest_id,
        checkin_date,
        "Completed",
        actual_minutes=actual_minutes,
        session=session,
    )


def skip_checkin(quest_id: int, checkin_date: date, session=None) -> QuestCheckin:
    """Mark a daily quest check-in as skipped."""
    return update_checkin_status(quest_id, checkin_date, "Skipped", session=session)


def fail_checkin(quest_id: int, checkin_date: date, session=None) -> QuestCheckin:
    """Mark a daily quest check-in as failed."""
    return update_checkin_status(quest_id, checkin_date, "Failed", session=session)


def reset_checkin(quest_id: int, checkin_date: date, session=None) -> QuestCheckin:
    """Reset a daily quest check-in to planned."""
    return update_checkin_status(quest_id, checkin_date, "Planned", session=session)


def mark_stale_planned_checkins_failed(today: date, grace_days: int = 3, session=None) -> int:
    """Mark unresolved planned check-ins older than the grace window as failed."""
    if grace_days < 0:
        raise ValueError("grace_days must be zero or greater.")

    cutoff_date = today - timedelta(days=grace_days)
    owns_session = session is None
    session = session or get_session()
    try:
        stale_checkins = (
            session.query(QuestCheckin)
            .filter(
                QuestCheckin.status == "Planned",
                QuestCheckin.checkin_date <= cutoff_date,
            )
            .all()
        )

        now = utc_now()
        for checkin in stale_checkins:
            checkin.status = "Failed"
            checkin.failed_at = now
            checkin.completed_at = None
            checkin.skipped_at = None
            checkin.xp_awarded = 0

        session.commit()
        return len(stale_checkins)
    except Exception:
        session.rollback()
        raise
    finally:
        if owns_session:
            session.close()


def _get_quest_or_raise(session, quest_id: int) -> Quest:
    quest = session.get(Quest, quest_id)
    if quest is None:
        raise ValueError(f"Quest with id {quest_id} was not found.")
    return quest


def _get_checkin(session, quest_id: int, checkin_date: date) -> QuestCheckin | None:
    return (
        session.query(QuestCheckin)
        .filter(
            QuestCheckin.quest_id == quest_id,
            QuestCheckin.checkin_date == checkin_date,
        )
        .one_or_none()
    )


def _get_month_checkins_by_quest_and_date(
    session,
    quest_ids: list[int],
    month_start: date,
    month_end: date,
) -> dict[int, dict[date, QuestCheckin]]:
    if not quest_ids:
        return {}

    checkins = (
        session.query(QuestCheckin)
        .filter(
            QuestCheckin.quest_id.in_(quest_ids),
            QuestCheckin.checkin_date >= month_start,
            QuestCheckin.checkin_date <= month_end,
        )
        .all()
    )
    grouped: dict[int, dict[date, QuestCheckin]] = {}
    for checkin in checkins:
        grouped.setdefault(checkin.quest_id, {})[checkin.checkin_date] = checkin
    return grouped


def _build_month_row(
    quest: Quest,
    days: list[date],
    checkins_by_date: dict[date, QuestCheckin],
) -> dict:
    return {
        "row_id": f"quest:{quest.id}",
        "row_type": "quest",
        "quest_id": quest.id,
        "recurring_habit_id": None,
        "title": quest.title,
        "category": quest.category.name if quest.category else None,
        "xp_reward": quest.xp_reward,
        "estimated_minutes": quest.estimated_minutes,
        "cells": {
            day: _build_month_cell(day, checkins_by_date.get(day))
            for day in days
        },
    }


def _build_month_cell(day: date, checkin: QuestCheckin | None) -> dict:
    if checkin is None:
        return {
            "date": day,
            "checkin_date": day,
            "quest_id": None,
            "checkin_id": None,
            "status": None,
            "xp_awarded": 0,
            "completed_at": None,
            "skipped_at": None,
            "failed_at": None,
            "entries": [],
        }

    return {
        "date": day,
        "checkin_date": checkin.checkin_date,
        "quest_id": checkin.quest_id,
        "checkin_id": checkin.id,
        "status": checkin.status,
        "xp_awarded": checkin.xp_awarded,
        "completed_at": checkin.completed_at,
        "skipped_at": checkin.skipped_at,
        "failed_at": checkin.failed_at,
        "entries": [],
    }


def _build_goal_month_rows(
    quests: list[Quest],
    days: list[date],
    checkins_by_quest_and_date: dict[int, dict[date, QuestCheckin]],
    month_start: date,
    month_end: date,
) -> list[dict]:
    quests_by_goal_id: dict[int, list[Quest]] = {}
    for quest in quests:
        if quest.goal_id is None or quest.recurring_habit_instance is not None or quest.goal is None:
            continue
        scheduled_date = _get_scheduled_date_in_month(quest, month_start, month_end)
        if scheduled_date is not None or checkins_by_quest_and_date.get(quest.id):
            quests_by_goal_id.setdefault(quest.goal_id, []).append(quest)

    rows = []
    for goal_id in sorted(
        quests_by_goal_id,
        key=lambda current_id: (
            quests_by_goal_id[current_id][0].goal.title.lower(),
            current_id,
        ),
    ):
        goal_quests = sorted(quests_by_goal_id[goal_id], key=_goal_row_quest_sort_key)
        rows.append(_build_goal_month_row(goal_quests, days, checkins_by_quest_and_date))
    return rows


def _build_goal_month_row(
    quests: list[Quest],
    days: list[date],
    checkins_by_quest_and_date: dict[int, dict[date, QuestCheckin]],
) -> dict:
    goal = quests[0].goal
    category = goal.category.name if goal.category else quests[0].category.name if quests[0].category else None
    return {
        "row_id": f"goal:{goal.id}",
        "row_type": "goal",
        "quest_id": None,
        "goal_id": goal.id,
        "recurring_habit_id": None,
        "title": goal.title,
        "category": category,
        "xp_reward": sum(quest.xp_reward or 0 for quest in quests),
        "estimated_minutes": sum(quest.estimated_minutes or 0 for quest in quests),
        "cells": {
            day: _build_goal_month_cell(day, quests, checkins_by_quest_and_date)
            for day in days
        },
    }


def _build_goal_month_cell(
    day: date,
    quests: list[Quest],
    checkins_by_quest_and_date: dict[int, dict[date, QuestCheckin]],
) -> dict:
    entries = []
    for quest in quests:
        checkin = checkins_by_quest_and_date.get(quest.id, {}).get(day)
        if checkin is None:
            continue
        entry = _build_month_cell(day, checkin)
        entry.update(
            {
                "title": quest.title,
                "goal_session_number": quest.goal_session_number,
                "planned_start_at": quest.planned_start_at,
                "planned_end_at": quest.planned_end_at,
                "xp_reward": quest.xp_reward,
                "estimated_minutes": quest.estimated_minutes,
            }
        )
        entries.append(entry)

    entries.sort(key=_goal_cell_entry_sort_key)
    if not entries:
        return _build_month_cell(day, None)

    cell = _build_month_cell(day, None)
    cell["entries"] = entries
    cell["xp_awarded"] = sum(entry.get("xp_awarded", 0) or 0 for entry in entries)
    if len(entries) == 1:
        cell.update({key: value for key, value in entries[0].items() if key != "entries"})
        cell["entries"] = entries
    return cell


def _build_recurring_month_rows(
    quests: list[Quest],
    days: list[date],
    checkins_by_quest_and_date: dict[int, dict[date, QuestCheckin]],
    month_start: date,
    month_end: date,
) -> list[dict]:
    instances_by_habit_id: dict[int, list[RecurringHabitInstance]] = {}
    for quest in quests:
        instance = quest.recurring_habit_instance
        if instance is None or instance.recurring_habit is None:
            continue
        if month_start <= instance.scheduled_date <= month_end:
            instances_by_habit_id.setdefault(instance.recurring_habit_id, []).append(instance)

    rows = []
    for habit_id in sorted(
        instances_by_habit_id,
        key=lambda current_id: (
            instances_by_habit_id[current_id][0].recurring_habit.title.lower(),
            current_id,
        ),
    ):
        instances = sorted(instances_by_habit_id[habit_id], key=lambda instance: instance.scheduled_date)
        rows.append(_build_recurring_month_row(instances, days, checkins_by_quest_and_date))
    return rows


def _build_recurring_month_row(
    instances: list[RecurringHabitInstance],
    days: list[date],
    checkins_by_quest_and_date: dict[int, dict[date, QuestCheckin]],
) -> dict:
    habit = instances[0].recurring_habit
    instances_by_date = {instance.scheduled_date: instance for instance in instances}
    return {
        "row_id": f"recurring_habit:{habit.id}",
        "row_type": "recurring_habit",
        "quest_id": None,
        "recurring_habit_id": habit.id,
        "title": habit.title,
        "category": habit.category.name if habit.category else None,
        "xp_reward": habit.xp_reward,
        "estimated_minutes": habit.estimated_minutes,
        "cells": {
            day: _build_recurring_month_cell(
                day,
                instances_by_date.get(day),
                checkins_by_quest_and_date,
            )
            for day in days
        },
    }


def _build_recurring_month_cell(
    day: date,
    instance: RecurringHabitInstance | None,
    checkins_by_quest_and_date: dict[int, dict[date, QuestCheckin]],
) -> dict:
    if instance is None:
        return _build_month_cell(day, None)

    checkin = checkins_by_quest_and_date.get(instance.quest_id, {}).get(day)
    return _build_month_cell(day, checkin)


def _get_scheduled_date_in_month(
    quest: Quest,
    month_start: date,
    month_end: date,
) -> date | None:
    if quest.planned_start_at is not None:
        scheduled_date = quest.planned_start_at.date()
        if month_start <= scheduled_date <= month_end:
            return scheduled_date

    if quest.due_date is not None and month_start <= quest.due_date <= month_end:
        return quest.due_date

    return None


def _resolve_checklist_update_entry(
    cell: dict,
    quest_id: int | None = None,
    checkin_id: int | None = None,
) -> dict:
    entries = cell.get("entries") or []
    if not entries:
        return cell

    if quest_id is None and checkin_id is None:
        if len(entries) == 1:
            return entries[0]
        raise ValueError("Select a goal session for the selected date.")

    for entry in entries:
        if quest_id is not None and entry.get("quest_id") != quest_id:
            continue
        if checkin_id is not None and entry.get("checkin_id") != checkin_id:
            continue
        return entry

    raise ValueError("Selected goal session is not scheduled for the selected date.")


def _goal_row_quest_sort_key(quest: Quest) -> tuple:
    if quest.planned_start_at is not None:
        scheduled_value = quest.planned_start_at
    elif quest.due_date is not None:
        scheduled_value = datetime.combine(quest.due_date, time.min)
    else:
        scheduled_value = datetime.max
    return (
        quest.planned_start_at is None,
        scheduled_value,
        quest.goal_session_number or 0,
        quest.created_at or datetime.min,
        quest.id or 0,
    )


def _goal_cell_entry_sort_key(entry: dict) -> tuple:
    return (
        entry.get("planned_start_at") is None,
        entry.get("planned_start_at") or datetime.max,
        entry.get("goal_session_number") or 0,
        entry.get("quest_id") or 0,
    )


def _normalize_checkin_status(status: str) -> str:
    value = (status or "").strip().lower()
    lookup = {valid_status.lower(): valid_status for valid_status in VALID_CHECKIN_STATUSES}
    if value not in lookup:
        valid = ", ".join(VALID_CHECKIN_STATUSES)
        raise ValueError(f"Unknown check-in status '{status}'. Valid values: {valid}.")
    return lookup[value]


def _normalize_actual_minutes(actual_minutes: int | None) -> int | None:
    if actual_minutes is None:
        return None
    try:
        value = int(actual_minutes)
    except (TypeError, ValueError) as error:
        raise ValueError("Actual minutes must be a positive integer.") from error
    if value <= 0:
        raise ValueError("Actual minutes must be greater than 0.")
    return value


def _apply_status(
    checkin: QuestCheckin,
    quest: Quest,
    status: str,
    actual_minutes: int | None = None,
) -> None:
    now = utc_now()
    checkin.status = status

    if status == "Planned":
        checkin.completed_at = None
        checkin.skipped_at = None
        checkin.failed_at = None
        checkin.xp_awarded = 0
        checkin.actual_minutes = None
        return

    if status == "Completed":
        if checkin.completed_at is None:
            checkin.completed_at = now
        checkin.skipped_at = None
        checkin.failed_at = None
        if actual_minutes is not None:
            checkin.actual_minutes = actual_minutes
        if checkin.xp_awarded == 0:
            checkin.xp_awarded = quest.xp_reward or 0
        return

    if status == "Skipped":
        checkin.completed_at = None
        checkin.skipped_at = now
        checkin.failed_at = None
        checkin.xp_awarded = 0
        checkin.actual_minutes = None
        return

    if status == "Failed":
        checkin.completed_at = None
        checkin.skipped_at = None
        checkin.failed_at = now
        checkin.xp_awarded = 0
        checkin.actual_minutes = None

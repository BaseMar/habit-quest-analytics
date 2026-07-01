from datetime import date, timedelta

from src.database.db import get_session
from src.database.models import Quest, QuestCheckin, utc_now


VALID_CHECKIN_STATUSES = ("Planned", "Completed", "Skipped", "Failed")


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
    session=None,
) -> QuestCheckin:
    """Update a daily check-in status and apply timestamp/XP rules."""
    normalized_status = _normalize_checkin_status(status)

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

        _apply_status(checkin, quest, normalized_status)
        session.commit()
        session.refresh(checkin)
        return checkin
    except Exception:
        session.rollback()
        raise
    finally:
        if owns_session:
            session.close()


def complete_checkin(quest_id: int, checkin_date: date, session=None) -> QuestCheckin:
    """Mark a daily quest check-in as completed."""
    return update_checkin_status(quest_id, checkin_date, "Completed", session=session)


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


def _normalize_checkin_status(status: str) -> str:
    value = (status or "").strip().lower()
    lookup = {valid_status.lower(): valid_status for valid_status in VALID_CHECKIN_STATUSES}
    if value not in lookup:
        valid = ", ".join(VALID_CHECKIN_STATUSES)
        raise ValueError(f"Unknown check-in status '{status}'. Valid values: {valid}.")
    return lookup[value]


def _apply_status(checkin: QuestCheckin, quest: Quest, status: str) -> None:
    now = utc_now()
    checkin.status = status

    if status == "Planned":
        checkin.completed_at = None
        checkin.skipped_at = None
        checkin.failed_at = None
        checkin.xp_awarded = 0
        return

    if status == "Completed":
        if checkin.completed_at is None:
            checkin.completed_at = now
        checkin.skipped_at = None
        checkin.failed_at = None
        if checkin.xp_awarded == 0:
            checkin.xp_awarded = quest.xp_reward or 0
        return

    if status == "Skipped":
        checkin.completed_at = None
        checkin.skipped_at = now
        checkin.failed_at = None
        checkin.xp_awarded = 0
        return

    if status == "Failed":
        checkin.completed_at = None
        checkin.skipped_at = None
        checkin.failed_at = now
        checkin.xp_awarded = 0

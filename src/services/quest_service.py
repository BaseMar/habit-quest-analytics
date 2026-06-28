from datetime import date

from sqlalchemy.orm import joinedload

from src.database.db import get_session
from src.database.models import Category, Quest, utc_now
from src.constants import QUEST_STATUSES
from src.services.xp_service import calculate_xp


VALID_QUEST_STATUSES = QUEST_STATUSES


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
    if not title or not title.strip():
        raise ValueError("Quest title is required.")

    xp_reward = calculate_xp(difficulty)
    estimated_minutes = _normalize_estimated_minutes(estimated_minutes)

    owns_session = session is None
    session = session or get_session()
    try:
        quest = Quest(
            title=title.strip(),
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


def get_all_quests(session=None) -> list[Quest]:
    """Return all quests ordered by planned date and creation date."""
    owns_session = session is None
    session = session or get_session()
    try:
        return (
            session.query(Quest)
            .options(joinedload(Quest.category))
            .order_by(Quest.due_date.is_(None), Quest.due_date, Quest.created_at.desc())
            .all()
        )
    finally:
        if owns_session:
            session.close()


def get_quests_by_date(planned_date: date, session=None) -> list[Quest]:
    """Return quests planned for a specific date."""
    owns_session = session is None
    session = session or get_session()
    try:
        return (
            session.query(Quest)
            .options(joinedload(Quest.category))
            .filter(Quest.due_date == planned_date)
            .order_by(Quest.created_at.desc())
            .all()
        )
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


def _normalize_status(status: str) -> str:
    if not status:
        raise ValueError("Quest status is required.")

    lookup = {valid.lower(): valid for valid in VALID_QUEST_STATUSES}
    key = status.strip().lower()
    if key not in lookup:
        valid = ", ".join(VALID_QUEST_STATUSES)
        raise ValueError(f"Unknown quest status '{status}'. Valid values: {valid}.")

    return lookup[key]


def _normalize_estimated_minutes(estimated_minutes: int | None) -> int | None:
    if estimated_minutes is None:
        return None

    value = int(estimated_minutes)
    if value <= 0:
        return None

    return value

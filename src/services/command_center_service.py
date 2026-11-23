from collections import Counter
from datetime import date, datetime, timedelta

from sqlalchemy import Date, and_, case, func, or_, type_coerce
from sqlalchemy.orm import joinedload

from src.analysis.metrics import calculate_completion_rate
from src.constants import QUEST_STATUSES
from src.database.db import get_session
from src.database.models import Quest, QuestCheckin
from src.services.checklist_service import ensure_checkin


def get_command_center_data(today: date | None = None, session=None) -> dict:
    """Return operational check-in metrics for the Command Center page."""
    today = today or date.today()
    week_start = today - timedelta(days=today.weekday())

    owns_session = session is None
    session = session or get_session()
    try:
        _ensure_legacy_command_center_checkins(session, today)

        checkin_date = QuestCheckin.checkin_date
        on_today = checkin_date == today
        in_week = checkin_date >= week_start
        xp = case(
            (QuestCheckin.xp_awarded > 0, QuestCheckin.xp_awarded),
            else_=func.coalesce(Quest.xp_reward, 0),
        )
        counts = (
            session.query(
                QuestCheckin.status,
                func.count().label("total"),
                func.count().filter(on_today).label("today_count"),
                func.count().filter(in_week).label("weekly_count"),
                func.sum(xp).filter(in_week).label("weekly_xp"),
            )
            .outerjoin(QuestCheckin.quest)
            .filter(checkin_date <= today)
            .group_by(QuestCheckin.status)
            .all()
        )
        total_by_status = Counter()
        today_by_status = Counter()
        weekly_by_status = Counter()
        planned_statuses = []
        weekly_xp = 0
        for raw_status, total, today_count, weekly_count, xp_sum in counts:
            status = normalize_status(raw_status)
            total_by_status[status] += total
            today_by_status[status] += today_count
            weekly_by_status[status] += weekly_count
            if status == "Planned":
                planned_statuses.append(raw_status)
            elif status == "Completed":
                weekly_xp += xp_sum or 0

        actionable_checkins = (
            session.query(QuestCheckin)
            .options(joinedload(QuestCheckin.quest).joinedload(Quest.category))
            .filter(or_(on_today, and_(checkin_date < today, QuestCheckin.status.in_(planned_statuses))))
            .all()
        )
        today_checkins = [checkin for checkin in actionable_checkins if checkin.checkin_date == today]
        overdue_checkins = [checkin for checkin in actionable_checkins if checkin.checkin_date < today]
        total_count = sum(total_by_status.values())
        weekly_total = sum(weekly_by_status.values())

        return {
            "has_quests": bool(total_count or session.query(Quest.id).first()),
            "total_quests": total_count,
            "completed_quests": total_by_status["Completed"],
            "planned_quests": today_by_status["Planned"],
            "due_today": sum(today_by_status.values()),
            "overdue_quests": total_by_status["Planned"] - today_by_status["Planned"],
            "completed_today": today_by_status["Completed"],
            "failed_quests": total_by_status["Failed"],
            "skipped_quests": total_by_status["Skipped"],
            "completion_rate": calculate_completion_rate(total_by_status["Completed"], total_count),
            "weekly_xp": weekly_xp,
            "completed_this_week": weekly_by_status["Completed"],
            "failed_this_week": weekly_by_status["Failed"],
            "total_quests_this_week": weekly_total,
            "weekly_completion_rate": calculate_completion_rate(weekly_by_status["Completed"], weekly_total),
            "status_counts": {
                "Planned": today_by_status["Planned"],
                "Completed": today_by_status["Completed"],
                "Failed": total_by_status["Failed"],
                "Skipped": total_by_status["Skipped"],
            },
            "today_quests": build_today_focus_rows(today_checkins),
            "today_work_items": build_operational_checkin_rows(today_checkins),
            "attention_items": build_operational_checkin_rows(overdue_checkins),
        }
    finally:
        if owns_session:
            session.close()


def get_command_center_items_for_date(review_date: date, session=None) -> list[dict]:
    """Return action-ready check-ins for a single Command Center review date."""
    owns_session = session is None
    session = session or get_session()
    try:
        _ensure_legacy_command_center_checkins(session, date.today())
        checkins = (
            session.query(QuestCheckin)
            .options(joinedload(QuestCheckin.quest).joinedload(Quest.category))
            .filter(QuestCheckin.checkin_date == review_date)
            .all()
        )
        return build_operational_checkin_rows(checkins)
    finally:
        if owns_session:
            session.close()


def build_today_focus_rows(checkins: list[QuestCheckin]) -> list[dict]:
    """Return compact schedule rows for today's check-ins."""
    sorted_checkins = sorted(
        checkins,
        key=lambda checkin: (
            checkin.quest.planned_start_at is None,
            checkin.quest.planned_start_at or datetime.max,
            checkin.quest.title.lower(),
        ),
    )

    return [
        {
            "Time": _quest_time_range(checkin.quest),
            "Title": checkin.quest.title,
            "Category": get_quest_category_name(checkin.quest),
            "Status": normalize_status(checkin.status),
            "XP": f"{_checkin_xp(checkin)} XP",
        }
        for checkin in sorted_checkins
    ]


def build_operational_checkin_rows(checkins: list[QuestCheckin]) -> list[dict]:
    """Return action-ready rows for the Command Center work lists."""
    sorted_checkins = sorted(
        checkins,
        key=lambda checkin: (
            checkin.checkin_date,
            checkin.quest.planned_start_at is None,
            checkin.quest.planned_start_at or datetime.max,
            checkin.quest.title.lower(),
        ),
    )

    return [
        {
            "quest_id": checkin.quest_id,
            "checkin_date": checkin.checkin_date,
            "time": _quest_time_range(checkin.quest),
            "title": checkin.quest.title,
            "category": get_quest_category_name(checkin.quest),
            "status": normalize_status(checkin.status),
            "xp": _checkin_xp(checkin),
        }
        for checkin in sorted_checkins
    ]


def _ensure_legacy_command_center_checkins(session, today: date) -> None:
    """Create missing planned check-ins for legacy scheduled quests up to today."""
    scheduled_date = type_coerce(func.coalesce(func.date(Quest.planned_start_at), Quest.due_date), Date)
    missing_checkins = (
        session.query(Quest.id, scheduled_date)
        .filter(
            scheduled_date <= today,
            ~Quest.checkins.any(QuestCheckin.checkin_date == scheduled_date),
        )
        .all()
    )

    for quest_id, checkin_date in missing_checkins:
        ensure_checkin(quest_id, checkin_date, session=session)


def _checkin_xp(checkin: QuestCheckin) -> int:
    if (checkin.xp_awarded or 0) > 0:
        return checkin.xp_awarded or 0
    if checkin.quest is not None:
        return checkin.quest.xp_reward or 0
    return 0


def normalize_status(status: str | None) -> str:
    value = (status or "").strip().lower()
    for valid_status in QUEST_STATUSES:
        if value == valid_status.lower():
            return valid_status
    return "Planned"


def get_quest_category_name(quest: Quest) -> str:
    return quest.category.name if quest.category else "Uncategorized"


def _quest_time_range(quest: Quest) -> str:
    if quest.planned_start_at is not None and quest.planned_end_at is not None:
        return f"{quest.planned_start_at:%H:%M} - {quest.planned_end_at:%H:%M}"
    if quest.planned_start_at is not None:
        return f"{quest.planned_start_at:%H:%M}"
    return "All day"

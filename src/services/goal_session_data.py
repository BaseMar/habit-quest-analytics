from src.database.models import Quest, QuestCheckin


def get_linked_goal_quests(session, goal_id: int) -> list[Quest]:
    """Return a project's linked sessions in stable order."""
    return session.query(Quest).filter(Quest.goal_id == goal_id).order_by(Quest.id).all()


def get_quest_checkins(session, quest_ids: list[int]) -> list[QuestCheckin]:
    """Return check-ins for a known set of sessions in stable order."""
    if not quest_ids:
        return []
    return (
        session.query(QuestCheckin)
        .filter(QuestCheckin.quest_id.in_(quest_ids))
        .order_by(QuestCheckin.checkin_date, QuestCheckin.id)
        .all()
    )


def get_quest_planned_minutes(quest: Quest) -> int:
    """Return planned effort from an explicit estimate or the scheduled time window."""
    if quest.estimated_minutes and quest.estimated_minutes > 0:
        return int(quest.estimated_minutes)
    if quest.planned_start_at is not None and quest.planned_end_at is not None:
        return max(int((quest.planned_end_at - quest.planned_start_at).total_seconds() // 60), 0)
    return 0

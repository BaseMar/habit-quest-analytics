from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    Time,
    UniqueConstraint,
)
from sqlalchemy.orm import declarative_base, relationship


Base = declarative_base()


def utc_now() -> datetime:
    """Return a UTC timestamp compatible with the current naive SQLite DateTime columns."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)
    description = Column(Text, nullable=True)

    quests = relationship("Quest", back_populates="category")
    recurring_habits = relationship("RecurringHabit", back_populates="category")
    goals = relationship("Goal", back_populates="category")


class Goal(Base):
    __tablename__ = "goals"
    __table_args__ = (
        CheckConstraint("planned_total_minutes > 0", name="ck_goal_planned_total_minutes_positive"),
        CheckConstraint(
            "status IN ('Active', 'Completed', 'Archived')",
            name="ck_goal_status_valid",
        ),
        CheckConstraint(
            "target_end_date IS NULL OR start_date IS NULL OR target_end_date >= start_date",
            name="ck_goal_target_end_after_start",
        ),
    )

    id = Column(Integer, primary_key=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    planned_total_minutes = Column(Integer, nullable=False)
    start_date = Column(Date, nullable=True)
    target_end_date = Column(Date, nullable=True)
    status = Column(String(30), nullable=False, default="Active")
    created_at = Column(DateTime, nullable=False, default=utc_now)
    updated_at = Column(DateTime, nullable=False, default=utc_now, onupdate=utc_now)

    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    category = relationship("Category", back_populates="goals")
    quests = relationship("Quest", back_populates="goal")


class Quest(Base):
    __tablename__ = "quests"

    id = Column(Integer, primary_key=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(30), nullable=False, default="active")
    is_habit = Column(Boolean, nullable=False, default=False)
    xp_reward = Column(Integer, nullable=False, default=0)
    due_date = Column(Date, nullable=True)
    planned_start_at = Column(DateTime, nullable=True)
    planned_end_at = Column(DateTime, nullable=True)
    estimated_minutes = Column(Integer, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=utc_now)

    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    goal_id = Column(Integer, ForeignKey("goals.id"), nullable=True)
    category = relationship("Category", back_populates="quests")
    goal = relationship("Goal", back_populates="quests")
    checkins = relationship("QuestCheckin", back_populates="quest")
    recurring_habit_instance = relationship(
        "RecurringHabitInstance",
        back_populates="quest",
        uselist=False,
    )


class RecurringHabit(Base):
    __tablename__ = "recurring_habits"

    id = Column(Integer, primary_key=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    xp_reward = Column(Integer, nullable=False)
    estimated_minutes = Column(Integer, nullable=False)
    recurrence_type = Column(String(50), nullable=False)
    weekdays = Column(Text, nullable=True)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=True)
    planned_start_time = Column(Time, nullable=True)
    planned_end_time = Column(Time, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=utc_now)
    updated_at = Column(DateTime, nullable=False, default=utc_now, onupdate=utc_now)

    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    category = relationship("Category", back_populates="recurring_habits")
    instances = relationship("RecurringHabitInstance", back_populates="recurring_habit")


class RecurringHabitInstance(Base):
    __tablename__ = "recurring_habit_instances"
    __table_args__ = (
        UniqueConstraint("recurring_habit_id", "scheduled_date", name="uq_recurring_habit_date"),
        UniqueConstraint("quest_id", name="uq_recurring_habit_instance_quest"),
    )

    id = Column(Integer, primary_key=True)
    recurring_habit_id = Column(Integer, ForeignKey("recurring_habits.id"), nullable=False)
    scheduled_date = Column(Date, nullable=False)
    quest_id = Column(Integer, ForeignKey("quests.id"), nullable=False)
    created_at = Column(DateTime, nullable=False, default=utc_now)

    recurring_habit = relationship("RecurringHabit", back_populates="instances")
    quest = relationship("Quest", back_populates="recurring_habit_instance")


class QuestCheckin(Base):
    __tablename__ = "quest_checkins"
    __table_args__ = (
        UniqueConstraint("quest_id", "checkin_date", name="uq_quest_checkin_date"),
    )

    id = Column(Integer, primary_key=True)
    quest_id = Column(Integer, ForeignKey("quests.id"), nullable=False)
    checkin_date = Column(Date, nullable=False)
    status = Column(String(30), nullable=False, default="Planned")
    xp_awarded = Column(Integer, nullable=False, default=0)
    completed_at = Column(DateTime, nullable=True)
    skipped_at = Column(DateTime, nullable=True)
    failed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=utc_now)
    updated_at = Column(DateTime, nullable=False, default=utc_now, onupdate=utc_now)

    quest = relationship("Quest", back_populates="checkins")


class PlayerProfile(Base):
    __tablename__ = "player_profiles"

    id = Column(Integer, primary_key=True)
    character_name = Column(String(100), nullable=False, default="Adventurer")
    total_xp = Column(Integer, nullable=False, default=0)
    avatar_path = Column(String(255), nullable=True)
    created_at = Column(DateTime, nullable=False, default=utc_now)
    updated_at = Column(DateTime, nullable=False, default=utc_now, onupdate=utc_now)

    unlocked_achievements = relationship("UnlockedAchievement", back_populates="player_profile")


class Achievement(Base):
    __tablename__ = "achievements"

    id = Column(Integer, primary_key=True)
    name = Column(String(150), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    xp_required = Column(Integer, nullable=False, default=0)

    unlocked_by = relationship("UnlockedAchievement", back_populates="achievement")


class UnlockedAchievement(Base):
    __tablename__ = "unlocked_achievements"
    __table_args__ = (
        UniqueConstraint("player_profile_id", "achievement_id", name="uq_player_achievement"),
    )

    id = Column(Integer, primary_key=True)
    player_profile_id = Column(Integer, ForeignKey("player_profiles.id"), nullable=False)
    achievement_id = Column(Integer, ForeignKey("achievements.id"), nullable=False)
    unlocked_at = Column(DateTime, nullable=False, default=utc_now)

    player_profile = relationship("PlayerProfile", back_populates="unlocked_achievements")
    achievement = relationship("Achievement", back_populates="unlocked_by")

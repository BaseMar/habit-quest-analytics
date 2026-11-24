from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Identity,
    Index,
    Integer,
    String,
    Text,
    Time,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import declarative_base, relationship


Base = declarative_base()


def utc_now() -> datetime:
    """Return UTC in the schema's timezone-naive timestamp format."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class UserAccount(Base):
    __tablename__ = "user_accounts"

    id = Column(Integer, Identity(), primary_key=True)
    google_subject = Column(String(255), nullable=False, unique=True)
    email = Column(String(320), nullable=False)


class UserOwned:
    # NULL keeps single-user history out of account sessions until explicitly claimed.
    user_id = Column(Integer, ForeignKey("user_accounts.id"), index=True)


def owned_reference(column: str, table: str, name: str) -> ForeignKeyConstraint:
    """Require related rows with an assigned owner to belong to the same account."""
    return ForeignKeyConstraint(
        ["user_id", column], [f"{table}.user_id", f"{table}.id"],
        name=name, deferrable=True, initially="IMMEDIATE",
    )


class Category(UserOwned, Base):
    __tablename__ = "categories"
    __table_args__ = (
        UniqueConstraint("user_id", "id", name="uq_categories_owner_id"),
        UniqueConstraint("user_id", "name", name="uq_categories_owner_name"),
        Index(
            "uq_categories_unassigned_name", "name", unique=True,
            postgresql_where=text("user_id IS NULL"), sqlite_where=text("user_id IS NULL"),
        ),
    )

    id = Column(Integer, Identity(), primary_key=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)

    quests = relationship("Quest", back_populates="category", foreign_keys="Quest.category_id")
    recurring_habits = relationship("RecurringHabit", back_populates="category", foreign_keys="RecurringHabit.category_id")
    goals = relationship("Goal", back_populates="category", foreign_keys="Goal.category_id")


class Goal(UserOwned, Base):
    __tablename__ = "goals"
    __table_args__ = (
        UniqueConstraint("user_id", "id", name="uq_goals_owner_id"),
        owned_reference("category_id", "categories", "fk_goals_owned_category"),
        CheckConstraint("planned_total_minutes >= 0", name="ck_goal_planned_total_minutes_nonnegative"),
        CheckConstraint(
            "status IN ('Active', 'Completed', 'Archived')",
            name="ck_goal_status_valid",
        ),
        CheckConstraint(
            "target_end_date IS NULL OR start_date IS NULL OR target_end_date >= start_date",
            name="ck_goal_target_end_after_start",
        ),
    )

    id = Column(Integer, Identity(), primary_key=True)
    title = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    planned_total_minutes = Column(Integer, nullable=False)
    start_date = Column(Date, nullable=True)
    target_end_date = Column(Date, nullable=True)
    status = Column(String(30), nullable=False, default="Active")
    created_at = Column(DateTime, nullable=False, default=utc_now)
    updated_at = Column(DateTime, nullable=False, default=utc_now, onupdate=utc_now)

    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    category = relationship("Category", back_populates="goals", foreign_keys=[category_id])
    quests = relationship("Quest", back_populates="goal", foreign_keys="Quest.goal_id")


class Quest(UserOwned, Base):
    __tablename__ = "quests"
    __table_args__ = (
        UniqueConstraint("user_id", "id", name="uq_quests_owner_id"),
        owned_reference("category_id", "categories", "fk_quests_owned_category"),
        owned_reference("goal_id", "goals", "fk_quests_owned_goal"),
    )

    id = Column(Integer, Identity(), primary_key=True)
    title = Column(Text, nullable=False)
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
    goal_session_number = Column(Integer, nullable=True)
    category = relationship("Category", back_populates="quests", foreign_keys=[category_id])
    goal = relationship("Goal", back_populates="quests", foreign_keys=[goal_id])
    checkins = relationship("QuestCheckin", back_populates="quest", foreign_keys="QuestCheckin.quest_id")
    recurring_habit_instance = relationship(
        "RecurringHabitInstance",
        back_populates="quest",
        uselist=False,
        foreign_keys="RecurringHabitInstance.quest_id",
    )


class RecurringHabit(UserOwned, Base):
    __tablename__ = "recurring_habits"
    __table_args__ = (
        UniqueConstraint("user_id", "id", name="uq_recurring_habits_owner_id"),
        owned_reference("category_id", "categories", "fk_recurring_habits_owned_category"),
    )

    id = Column(Integer, Identity(), primary_key=True)
    title = Column(Text, nullable=False)
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
    category = relationship("Category", back_populates="recurring_habits", foreign_keys=[category_id])
    instances = relationship(
        "RecurringHabitInstance", back_populates="recurring_habit",
        foreign_keys="RecurringHabitInstance.recurring_habit_id",
    )


class RecurringHabitInstance(UserOwned, Base):
    __tablename__ = "recurring_habit_instances"
    __table_args__ = (
        owned_reference("recurring_habit_id", "recurring_habits", "fk_instances_owned_habit"),
        owned_reference("quest_id", "quests", "fk_instances_owned_quest"),
        UniqueConstraint("recurring_habit_id", "scheduled_date", name="uq_recurring_habit_date"),
        UniqueConstraint("quest_id", name="uq_recurring_habit_instance_quest"),
    )

    id = Column(Integer, Identity(), primary_key=True)
    recurring_habit_id = Column(Integer, ForeignKey("recurring_habits.id"), nullable=False)
    scheduled_date = Column(Date, nullable=False)
    quest_id = Column(Integer, ForeignKey("quests.id"), nullable=False)
    created_at = Column(DateTime, nullable=False, default=utc_now)

    recurring_habit = relationship("RecurringHabit", back_populates="instances", foreign_keys=[recurring_habit_id])
    quest = relationship("Quest", back_populates="recurring_habit_instance", foreign_keys=[quest_id])


class QuestCheckin(UserOwned, Base):
    __tablename__ = "quest_checkins"
    __table_args__ = (
        owned_reference("quest_id", "quests", "fk_checkins_owned_quest"),
        UniqueConstraint("quest_id", "checkin_date", name="uq_quest_checkin_date"),
    )

    id = Column(Integer, Identity(), primary_key=True)
    quest_id = Column(Integer, ForeignKey("quests.id"), nullable=False)
    checkin_date = Column(Date, nullable=False)
    status = Column(String(30), nullable=False, default="Planned")
    xp_awarded = Column(Integer, nullable=False, default=0)
    completed_at = Column(DateTime, nullable=True)
    skipped_at = Column(DateTime, nullable=True)
    failed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=utc_now)
    updated_at = Column(DateTime, nullable=False, default=utc_now, onupdate=utc_now)

    quest = relationship("Quest", back_populates="checkins", foreign_keys=[quest_id])


class PlayerProfile(UserOwned, Base):
    __tablename__ = "player_profiles"
    __table_args__ = (
        UniqueConstraint("user_id", "id", name="uq_player_profiles_owner_id"),
        UniqueConstraint("user_id", name="uq_player_profiles_owner"),
    )

    id = Column(Integer, Identity(), primary_key=True)
    character_name = Column(String(100), nullable=False, default="Adventurer")
    total_xp = Column(Integer, nullable=False, default=0)
    avatar_path = Column(String(255), nullable=True)
    created_at = Column(DateTime, nullable=False, default=utc_now)
    updated_at = Column(DateTime, nullable=False, default=utc_now, onupdate=utc_now)

    unlocked_achievements = relationship(
        "UnlockedAchievement", back_populates="player_profile", foreign_keys="UnlockedAchievement.player_profile_id",
    )


class Achievement(Base):
    __tablename__ = "achievements"

    id = Column(Integer, Identity(), primary_key=True)
    name = Column(String(150), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    xp_required = Column(Integer, nullable=False, default=0)

    unlocked_by = relationship("UnlockedAchievement", back_populates="achievement")


class UnlockedAchievement(UserOwned, Base):
    __tablename__ = "unlocked_achievements"
    __table_args__ = (
        owned_reference("player_profile_id", "player_profiles", "fk_unlocks_owned_profile"),
        UniqueConstraint("player_profile_id", "achievement_id", name="uq_player_achievement"),
    )

    id = Column(Integer, Identity(), primary_key=True)
    player_profile_id = Column(Integer, ForeignKey("player_profiles.id"), nullable=False)
    achievement_id = Column(Integer, ForeignKey("achievements.id"), nullable=False)
    unlocked_at = Column(DateTime, nullable=False, default=utc_now)

    player_profile = relationship("PlayerProfile", back_populates="unlocked_achievements", foreign_keys=[player_profile_id])
    achievement = relationship("Achievement", back_populates="unlocked_by")

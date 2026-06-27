from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import declarative_base, relationship


Base = declarative_base()


class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)
    description = Column(Text, nullable=True)

    quests = relationship("Quest", back_populates="category")


class Quest(Base):
    __tablename__ = "quests"

    id = Column(Integer, primary_key=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    difficulty = Column(String(20), nullable=False, default="Easy")
    status = Column(String(30), nullable=False, default="active")
    is_habit = Column(Boolean, nullable=False, default=False)
    xp_reward = Column(Integer, nullable=False, default=10)
    due_date = Column(Date, nullable=True)
    estimated_minutes = Column(Integer, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    category = relationship("Category", back_populates="quests")


class PlayerProfile(Base):
    __tablename__ = "player_profiles"

    id = Column(Integer, primary_key=True)
    character_name = Column(String(100), nullable=False, default="Adventurer")
    total_xp = Column(Integer, nullable=False, default=0)
    avatar_path = Column(String(255), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

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
    unlocked_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    player_profile = relationship("PlayerProfile", back_populates="unlocked_achievements")
    achievement = relationship("Achievement", back_populates="unlocked_by")

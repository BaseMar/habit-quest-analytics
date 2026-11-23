"""Initial PostgreSQL schema."""

from alembic import op
import sqlalchemy as sa


revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "categories",
        sa.Column("id", sa.Integer(), sa.Identity(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.UniqueConstraint("name"),
    )
    op.create_table(
        "achievements",
        sa.Column("id", sa.Integer(), sa.Identity(), primary_key=True),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("xp_required", sa.Integer(), nullable=False),
        sa.UniqueConstraint("name"),
    )
    op.create_table(
        "player_profiles",
        sa.Column("id", sa.Integer(), sa.Identity(), primary_key=True),
        sa.Column("character_name", sa.String(100), nullable=False),
        sa.Column("total_xp", sa.Integer(), nullable=False),
        sa.Column("avatar_path", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "goals",
        sa.Column("id", sa.Integer(), sa.Identity(), primary_key=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("planned_total_minutes", sa.Integer(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("target_end_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("category_id", sa.Integer(), sa.ForeignKey("categories.id"), nullable=True),
        sa.CheckConstraint("planned_total_minutes >= 0", name="ck_goal_planned_total_minutes_nonnegative"),
        sa.CheckConstraint("status IN ('Active', 'Completed', 'Archived')", name="ck_goal_status_valid"),
        sa.CheckConstraint(
            "target_end_date IS NULL OR start_date IS NULL OR target_end_date >= start_date",
            name="ck_goal_target_end_after_start",
        ),
    )
    op.create_table(
        "recurring_habits",
        sa.Column("id", sa.Integer(), sa.Identity(), primary_key=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("xp_reward", sa.Integer(), nullable=False),
        sa.Column("estimated_minutes", sa.Integer(), nullable=False),
        sa.Column("recurrence_type", sa.String(50), nullable=False),
        sa.Column("weekdays", sa.Text(), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("planned_start_time", sa.Time(), nullable=True),
        sa.Column("planned_end_time", sa.Time(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("category_id", sa.Integer(), sa.ForeignKey("categories.id"), nullable=True),
    )
    op.create_table(
        "quests",
        sa.Column("id", sa.Integer(), sa.Identity(), primary_key=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("is_habit", sa.Boolean(), nullable=False),
        sa.Column("xp_reward", sa.Integer(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("planned_start_at", sa.DateTime(), nullable=True),
        sa.Column("planned_end_at", sa.DateTime(), nullable=True),
        sa.Column("estimated_minutes", sa.Integer(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("category_id", sa.Integer(), sa.ForeignKey("categories.id"), nullable=True),
        sa.Column("goal_id", sa.Integer(), sa.ForeignKey("goals.id"), nullable=True),
        sa.Column("goal_session_number", sa.Integer(), nullable=True),
    )
    op.create_table(
        "recurring_habit_instances",
        sa.Column("id", sa.Integer(), sa.Identity(), primary_key=True),
        sa.Column("recurring_habit_id", sa.Integer(), sa.ForeignKey("recurring_habits.id"), nullable=False),
        sa.Column("scheduled_date", sa.Date(), nullable=False),
        sa.Column("quest_id", sa.Integer(), sa.ForeignKey("quests.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("recurring_habit_id", "scheduled_date", name="uq_recurring_habit_date"),
        sa.UniqueConstraint("quest_id", name="uq_recurring_habit_instance_quest"),
    )
    op.create_table(
        "quest_checkins",
        sa.Column("id", sa.Integer(), sa.Identity(), primary_key=True),
        sa.Column("quest_id", sa.Integer(), sa.ForeignKey("quests.id"), nullable=False),
        sa.Column("checkin_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("xp_awarded", sa.Integer(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("skipped_at", sa.DateTime(), nullable=True),
        sa.Column("failed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("quest_id", "checkin_date", name="uq_quest_checkin_date"),
    )
    op.create_table(
        "unlocked_achievements",
        sa.Column("id", sa.Integer(), sa.Identity(), primary_key=True),
        sa.Column("player_profile_id", sa.Integer(), sa.ForeignKey("player_profiles.id"), nullable=False),
        sa.Column("achievement_id", sa.Integer(), sa.ForeignKey("achievements.id"), nullable=False),
        sa.Column("unlocked_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("player_profile_id", "achievement_id", name="uq_player_achievement"),
    )


def downgrade() -> None:
    op.drop_table("unlocked_achievements")
    op.drop_table("quest_checkins")
    op.drop_table("recurring_habit_instances")
    op.drop_table("quests")
    op.drop_table("recurring_habits")
    op.drop_table("goals")
    op.drop_table("player_profiles")
    op.drop_table("achievements")
    op.drop_table("categories")

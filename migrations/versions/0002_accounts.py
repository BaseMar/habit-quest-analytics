"""Add Google accounts and constrain personal rows to the same owner."""

from alembic import op
import sqlalchemy as sa


revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

OWNED_TABLES = (
    "categories", "goals", "quests", "recurring_habits", "recurring_habit_instances",
    "quest_checkins", "player_profiles", "unlocked_achievements",
)
APP_TABLES = (*OWNED_TABLES, "achievements", "user_accounts")
REFERENCE_TARGETS = ("categories", "goals", "quests", "recurring_habits", "player_profiles")
OWNED_REFERENCES = (
    ("goals", "category_id", "categories", "fk_goals_owned_category"),
    ("quests", "category_id", "categories", "fk_quests_owned_category"),
    ("quests", "goal_id", "goals", "fk_quests_owned_goal"),
    ("recurring_habits", "category_id", "categories", "fk_recurring_habits_owned_category"),
    ("recurring_habit_instances", "recurring_habit_id", "recurring_habits", "fk_instances_owned_habit"),
    ("recurring_habit_instances", "quest_id", "quests", "fk_instances_owned_quest"),
    ("quest_checkins", "quest_id", "quests", "fk_checkins_owned_quest"),
    ("unlocked_achievements", "player_profile_id", "player_profiles", "fk_unlocks_owned_profile"),
)


def upgrade() -> None:
    op.create_table(
        "user_accounts",
        sa.Column("id", sa.Integer(), sa.Identity(), primary_key=True),
        sa.Column("google_subject", sa.String(255), nullable=False, unique=True),
        sa.Column("email", sa.String(320), nullable=False),
    )
    for table in OWNED_TABLES:
        op.add_column(table, sa.Column("user_id", sa.Integer(), nullable=True))
        op.create_foreign_key(f"fk_{table}_user_id", table, "user_accounts", ["user_id"], ["id"])
        op.create_index(f"ix_{table}_user_id", table, ["user_id"])
    for table in REFERENCE_TARGETS:
        op.create_unique_constraint(f"uq_{table}_owner_id", table, ["user_id", "id"])
    for table, column, target, name in OWNED_REFERENCES:
        op.create_foreign_key(
            name, table, target, ["user_id", column], ["user_id", "id"],
            deferrable=True, initially="IMMEDIATE",
        )
    op.drop_constraint("categories_name_key", "categories", type_="unique")
    op.create_unique_constraint("uq_categories_owner_name", "categories", ["user_id", "name"])
    op.create_index(
        "uq_categories_unassigned_name", "categories", ["name"],
        unique=True, postgresql_where=sa.text("user_id IS NULL"),
    )
    op.create_unique_constraint("uq_player_profiles_owner", "player_profiles", ["user_id"])
    for table in APP_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM user_accounts) THEN
                RAISE EXCEPTION 'Cannot downgrade to a shared database while accounts exist';
            END IF;
        END $$
    """)
    op.drop_constraint("uq_player_profiles_owner", "player_profiles", type_="unique")
    op.drop_index("uq_categories_unassigned_name", table_name="categories")
    op.drop_constraint("uq_categories_owner_name", "categories", type_="unique")
    op.create_unique_constraint("categories_name_key", "categories", ["name"])
    for table, _, _, name in reversed(OWNED_REFERENCES):
        op.drop_constraint(name, table, type_="foreignkey")
    for table in REFERENCE_TARGETS:
        op.drop_constraint(f"uq_{table}_owner_id", table, type_="unique")
    for table in OWNED_TABLES:
        op.drop_index(f"ix_{table}_user_id", table_name=table)
        op.drop_constraint(f"fk_{table}_user_id", table, type_="foreignkey")
        op.drop_column(table, "user_id")
    op.drop_table("user_accounts")

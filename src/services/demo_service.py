from datetime import date, time, timedelta

from sqlalchemy import create_engine, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from src.database.db import DEMO_ENGINE_OPTION
from src.database.models import Base, PlayerProfile, RecurringHabitInstance, UserAccount
from src.database.seed import add_missing_default_categories
from src.database.user_session import UserSession
from src.services.checklist_service import update_checkin_status
from src.services.goal_service import create_goal
from src.services.quest_service import create_scheduled_quest, get_categories
from src.services.recurring_habit_service import create_recurring_habit, generate_recurring_habit_for_month


DEMO_USER_ID = 1
DEMO_NAME = "Alex Morgan"


def create_demo_database(today: date | None = None) -> Engine:
    """Build a fresh sample account in a database owned by one browser session."""
    today = today or date.today()
    engine = create_engine(
        "sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False},
        execution_options={DEMO_ENGINE_OPTION: True},
    )
    try:
        Base.metadata.create_all(engine)
        with Session(engine) as session, session.begin():
            session.add(UserAccount(id=DEMO_USER_ID, google_subject="demo", email="alex@example.com"))
            session.flush()
            add_missing_default_categories(session, DEMO_USER_ID)
            session.add(PlayerProfile(user_id=DEMO_USER_ID, character_name=DEMO_NAME))

        with UserSession(bind=engine, user_id=DEMO_USER_ID, autoflush=False) as session:
            _seed_demo_schedule(session, today)
    except Exception:
        engine.dispose()
        raise
    return engine


def _seed_demo_schedule(session: UserSession, today: date) -> None:
    categories = {category.name: category.id for category in get_categories(session=session)}
    goal = create_goal(
        "Build a photography portfolio",
        planned_total_minutes=480,
        description="Select, edit, and publish a collection of ten photos.",
        category_id=categories["Learning"],
        start_date=today - timedelta(days=22),
        target_end_date=today + timedelta(days=21),
        session=session,
    )
    samples = (
        (-22, "Portfolio session", "Learning", 17, 0, 45, "Completed", goal.id),
        (-17, "Review monthly budget", "Home", 18, 0, 30, "Completed", None),
        (-14, "Portfolio session", "Learning", 17, 0, 45, "Completed", goal.id),
        (-11, "Read two chapters", "Learning", 19, 0, 30, "Skipped", None),
        (-9, "Plan the next sprint", "Work", 10, 0, 60, "Completed", None),
        (-6, "Portfolio session", "Learning", 17, 0, 45, "Completed", goal.id),
        (-3, "Prep weekday lunches", "Home", 17, 30, 45, "Failed", None),
        (-1, "Evening stretch", "Health", 18, 0, 30, "Planned", None),
        (0, "Focus block", "Work", 9, 0, 60, "Planned", None),
        (0, "Walk around the park", "Health", 12, 30, 30, "Completed", None),
        (0, "Portfolio session", "Learning", 17, 0, 45, "Planned", goal.id),
        (1, "Pick up groceries", "Home", 17, 30, 30, "Planned", None),
        (3, "Coffee with Maya", "Social", 11, 0, 45, "Planned", None),
        (6, "Portfolio session", "Learning", 17, 0, 45, "Planned", goal.id),
    )
    for offset, title, category, hour, minute, duration, status, goal_id in samples:
        day = today + timedelta(days=offset)
        end_hour, end_minute = divmod(hour * 60 + minute + duration, 60)
        quest = create_scheduled_quest(
            title=title,
            category_id=categories[category],
            planned_date=day,
            start_time=time(hour, minute),
            end_time=time(end_hour, end_minute),
            goal_id=goal_id,
            session=session,
        )
        if status != "Planned":
            update_checkin_status(quest.id, day, status, session=session)

    first_day = today - timedelta(days=21)
    last_day = today + timedelta(days=10)
    habit = create_recurring_habit(
        "Morning journal", categories["Home"], 15, "selected_weekdays",
        [(today.weekday() + offset) % 7 for offset in (0, 2, 4)], first_day, end_date=last_day,
        planned_start_time=time(8), planned_end_time=time(8, 15), session=session,
    )
    habit_id = habit.id
    months = {(day.year, day.month) for day in (first_day, today, last_day)}
    for year, month in sorted(months):
        generate_recurring_habit_for_month(habit_id, year, month, session=session)
    completed = session.execute(
        select(RecurringHabitInstance.quest_id, RecurringHabitInstance.scheduled_date).where(
            RecurringHabitInstance.recurring_habit_id == habit_id,
            RecurringHabitInstance.scheduled_date < today,
        )
    ).all()
    for quest_id, day in completed:
        update_checkin_status(quest_id, day, "Completed", session=session)

from datetime import date, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.models import Base, Quest
from src.services.analytics_service import (
    build_character_activity_stats,
    build_today_focus_rows,
    build_status_counts,
    build_xp_by_rpg_stat,
    build_completion_rate_by_weekday,
    build_quests_by_status,
    calculate_weekly_xp,
    build_xp_by_day,
    calculate_character_title,
    get_command_center_data,
    get_character_profile_data,
    get_dashboard_kpis,
    get_habit_analytics_data,
)


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()


def test_get_dashboard_kpis_counts_completed_quests_and_xp(session):
    session.add_all(
        [
            Quest(
                title="Workout",
                status="Completed",
                xp_reward=75,
                completed_at=datetime(2026, 6, 23, 9, 0),
            ),
            Quest(
                title="Read",
                status="Completed",
                xp_reward=30,
                completed_at=datetime(2026, 6, 15, 9, 0),
            ),
            Quest(title="Plan meals", status="Planned", xp_reward=10),
        ]
    )
    session.commit()

    kpis = get_dashboard_kpis(today=date(2026, 6, 26), session=session)

    assert kpis == {
        "total_quests": 3,
        "completed_quests": 2,
        "completion_rate": 66.67,
        "total_xp": 105,
        "weekly_xp": 75,
        "current_level": 1,
        "xp_to_next_level": 395,
    }


def test_get_dashboard_kpis_handles_empty_database(session):
    kpis = get_dashboard_kpis(today=date(2026, 6, 26), session=session)

    assert kpis == {
        "total_quests": 0,
        "completed_quests": 0,
        "completion_rate": 0.0,
        "total_xp": 0,
        "weekly_xp": 0,
        "current_level": 1,
        "xp_to_next_level": 500,
    }


def test_get_habit_analytics_data_includes_weekly_pulse(session):
    session.add_all(
        [
            Quest(
                title="Completed this week",
                status="Completed",
                xp_reward=75,
                due_date=date(2026, 6, 22),
                completed_at=datetime(2026, 6, 23, 9, 0),
            ),
            Quest(
                title="Failed this week",
                status="Failed",
                xp_reward=30,
                due_date=date(2026, 6, 24),
            ),
            Quest(
                title="Completed last week",
                status="Completed",
                xp_reward=150,
                due_date=date(2026, 6, 15),
                completed_at=datetime(2026, 6, 15, 9, 0),
            ),
        ]
    )
    session.commit()

    result = get_habit_analytics_data(today=date(2026, 6, 26), session=session)

    assert result["weekly_pulse"] == {
        "weekly_xp": 75,
        "completed_this_week": 1,
        "failed_this_week": 1,
        "weekly_completion_rate": 50.0,
    }


def test_get_habit_analytics_data_returns_empty_safe_weekly_pulse(session):
    result = get_habit_analytics_data(today=date(2026, 6, 26), session=session)

    assert result["has_quests"] is False
    assert result["weekly_pulse"] == {
        "weekly_xp": 0,
        "completed_this_week": 0,
        "failed_this_week": 0,
        "weekly_completion_rate": 0.0,
    }


def test_build_xp_by_day_uses_completed_or_planned_date(session):
    quests = [
        Quest(
            title="Workout",
            status="Completed",
            xp_reward=75,
            completed_at=datetime(2026, 6, 26, 9, 0),
            due_date=date(2026, 6, 25),
        ),
        Quest(
            title="Read",
            status="Completed",
            xp_reward=30,
            due_date=date(2026, 6, 26),
        ),
        Quest(
            title="Plan",
            status="Planned",
            xp_reward=10,
            due_date=date(2026, 6, 26),
        ),
    ]

    result = build_xp_by_day(quests)

    assert result.to_dict("records") == [{"Date": date(2026, 6, 26), "XP": 105}]


def test_build_quests_by_status_counts_supported_statuses(session):
    quests = [
        Quest(title="One", status="Planned"),
        Quest(title="Two", status="Completed"),
        Quest(title="Three", status="Completed"),
        Quest(title="Four", status="Failed"),
        Quest(title="Five", status="Skipped"),
    ]

    result = build_quests_by_status(quests)

    assert result.to_dict("records") == [
        {"Status": "Planned", "Count": 1},
        {"Status": "Completed", "Count": 2},
        {"Status": "Failed", "Count": 1},
        {"Status": "Skipped", "Count": 1},
    ]


def test_build_status_counts_returns_supported_status_counts(session):
    quests = [
        Quest(title="One", status="Planned"),
        Quest(title="Two", status="Completed"),
        Quest(title="Three", status="Completed"),
        Quest(title="Four", status="Failed"),
        Quest(title="Five", status="Skipped"),
        Quest(title="Unknown status", status=""),
    ]

    assert build_status_counts(quests) == {
        "Planned": 2,
        "Completed": 2,
        "Failed": 1,
        "Skipped": 1,
    }


def test_get_command_center_data_returns_operational_quest_metrics(session):
    session.add_all(
        [
            Quest(
                title="Workout",
                status="Completed",
                xp_reward=75,
                due_date=date(2026, 6, 22),
                completed_at=datetime(2026, 6, 23, 9, 0),
            ),
            Quest(
                title="Report",
                status="Completed",
                xp_reward=150,
                due_date=date(2026, 6, 24),
                completed_at=datetime(2026, 6, 26, 14, 0),
            ),
            Quest(title="Plan meals", status="Planned", xp_reward=10, due_date=date(2026, 6, 25)),
            Quest(title="Missed task", status="Failed", xp_reward=30, due_date=date(2026, 6, 26)),
            Quest(title="Skipped task", status="Skipped", xp_reward=10, due_date=date(2026, 6, 15)),
        ]
    )
    session.commit()

    result = get_command_center_data(today=date(2026, 6, 26), session=session)

    assert result["has_quests"] is True
    assert result["total_quests"] == 5
    assert result["completed_quests"] == 2
    assert result["planned_quests"] == 1
    assert result["due_today"] == 1
    assert result["overdue_quests"] == 1
    assert result["completed_today"] == 1
    assert result["failed_quests"] == 1
    assert result["skipped_quests"] == 1
    assert result["completion_rate"] == 40.0
    assert result["weekly_xp"] == 225
    assert result["completed_this_week"] == 2
    assert result["failed_this_week"] == 1
    assert result["total_quests_this_week"] == 4
    assert result["weekly_completion_rate"] == 50.0
    assert result["status_counts"] == {
        "Planned": 1,
        "Completed": 2,
        "Failed": 1,
        "Skipped": 1,
    }
    assert result["today_quests"] == [
        {
            "Time": "All day",
            "Title": "Missed task",
            "Category": "Uncategorized",
            "Difficulty": "Easy",
            "Status": "Failed",
            "XP": "30 XP",
        }
    ]


def test_build_today_focus_rows_sorts_scheduled_quests_before_legacy_due_date_only():
    quests = [
        Quest(
            title="Legacy all day",
            status="Planned",
            xp_reward=10,
            due_date=date(2026, 6, 26),
            created_at=datetime(2026, 6, 20, 8, 0),
        ),
        Quest(
            title="Later scheduled",
            status="Planned",
            difficulty="Medium",
            xp_reward=30,
            due_date=date(2026, 6, 26),
            planned_start_at=datetime(2026, 6, 26, 13, 0),
            planned_end_at=datetime(2026, 6, 26, 14, 0),
        ),
        Quest(
            title="Earlier scheduled",
            status="Completed",
            difficulty="Hard",
            xp_reward=75,
            due_date=date(2026, 6, 26),
            planned_start_at=datetime(2026, 6, 26, 9, 0),
            planned_end_at=datetime(2026, 6, 26, 11, 0),
        ),
        Quest(
            title="Other day",
            status="Planned",
            xp_reward=10,
            due_date=date(2026, 6, 27),
        ),
    ]

    result = build_today_focus_rows(quests, date(2026, 6, 26))

    assert result == [
        {
            "Time": "09:00 - 11:00",
            "Title": "Earlier scheduled",
            "Category": "Uncategorized",
            "Difficulty": "Hard",
            "Status": "Completed",
            "XP": "75 XP",
        },
        {
            "Time": "13:00 - 14:00",
            "Title": "Later scheduled",
            "Category": "Uncategorized",
            "Difficulty": "Medium",
            "Status": "Planned",
            "XP": "30 XP",
        },
        {
            "Time": "All day",
            "Title": "Legacy all day",
            "Category": "Uncategorized",
            "Difficulty": "Easy",
            "Status": "Planned",
            "XP": "10 XP",
        },
    ]


def test_build_completion_rate_by_weekday(session):
    quests = [
        Quest(title="Monday done", status="Completed", due_date=date(2026, 6, 22)),
        Quest(title="Monday planned", status="Planned", due_date=date(2026, 6, 22)),
        Quest(title="Tuesday failed", status="Failed", due_date=date(2026, 6, 23)),
        Quest(title="No planned date", status="Completed"),
    ]

    result = build_completion_rate_by_weekday(quests)

    assert result.to_dict("records") == [
        {
            "Weekday": "Monday",
            "Completed Quests": 1,
            "Total Quests": 2,
            "Completion Rate": 50.0,
        },
        {
            "Weekday": "Tuesday",
            "Completed Quests": 0,
            "Total Quests": 1,
            "Completion Rate": 0.0,
        },
    ]


@pytest.mark.parametrize(
    ("level", "expected_title"),
    [
        (1, "Novice Adventurer"),
        (2, "Novice Adventurer"),
        (3, "Disciplined Apprentice"),
        (5, "Disciplined Apprentice"),
        (6, "Quest Grinder"),
        (10, "Quest Grinder"),
        (11, "Habit Champion"),
    ],
)
def test_calculate_character_title(level, expected_title):
    assert calculate_character_title(level) == expected_title


def test_build_xp_by_rpg_stat_counts_completed_quest_xp_by_category(session):
    from src.database.models import Category

    learning = Category(name="Learning")
    health = Category(name="Health")
    work = Category(name="Work")
    social = Category(name="Social")
    home = Category(name="Home")

    quests = [
        Quest(title="Study", status="Completed", xp_reward=30, category=learning),
        Quest(title="Lift", status="Completed", xp_reward=75, category=health),
        Quest(title="Report", status="Completed", xp_reward=150, category=work),
        Quest(title="Call friend", status="Completed", xp_reward=10, category=social),
        Quest(title="Home reset", status="Completed", xp_reward=10, category=home),
        Quest(title="Planned study", status="Planned", xp_reward=150, category=learning),
    ]

    result = build_xp_by_rpg_stat(quests)

    assert result[["Stat", "XP"]].to_dict("records") == [
        {"Stat": "Knowledge", "XP": 30},
        {"Stat": "Strength", "XP": 75},
        {"Stat": "Discipline", "XP": 150},
        {"Stat": "Creativity", "XP": 10},
        {"Stat": "Recovery", "XP": 10},
    ]


def test_calculate_weekly_xp_counts_current_week_completed_quests(session):
    quests = [
        Quest(
            title="This week",
            status="Completed",
            xp_reward=75,
            completed_at=datetime(2026, 6, 23, 9, 0),
        ),
        Quest(
            title="Last week",
            status="Completed",
            xp_reward=150,
            completed_at=datetime(2026, 6, 15, 9, 0),
        ),
        Quest(title="No completion date", status="Completed", xp_reward=30),
    ]

    assert calculate_weekly_xp(quests, today=date(2026, 6, 26)) == 75


def test_build_character_activity_stats_returns_compact_profile_metrics(session):
    from src.database.models import Category

    learning = Category(name="Learning")
    work = Category(name="Work")
    quests = [
        Quest(
            title="Read",
            status="Completed",
            difficulty="Easy",
            xp_reward=10,
            due_date=date(2026, 6, 22),
            category=learning,
        ),
        Quest(
            title="Ship report",
            status="Completed",
            difficulty="Boss",
            xp_reward=150,
            due_date=date(2026, 6, 23),
            category=work,
        ),
        Quest(
            title="Deep work",
            status="Completed",
            difficulty="Hard",
            xp_reward=75,
            due_date=date(2026, 6, 23),
            category=work,
        ),
    ]
    rpg_stats = build_xp_by_rpg_stat(quests)

    result = build_character_activity_stats(
        completed_quests=quests,
        rpg_stats=rpg_stats,
        completion_rate=80.0,
        weekly_xp=225,
    )

    assert result == [
        {"label": "Completed Quests", "value": 3},
        {"label": "Completion Rate", "value": "80.0%"},
        {"label": "Weekly XP", "value": 225},
        {"label": "Boss Quests Completed", "value": 1},
        {"label": "Average XP / Completed Quest", "value": 78.3},
        {"label": "Most Active Category", "value": "Work"},
        {"label": "Strongest RPG Stat", "value": "Discipline (225 XP)"},
        {"label": "Most Productive Weekday", "value": "Tuesday"},
    ]


def test_get_character_profile_data_summarizes_completed_quest_progress(session):
    from src.database.models import Category

    category = Category(name="Learning")
    session.add(category)
    session.commit()
    session.add_all(
        [
            Quest(title="Read", status="Completed", xp_reward=300, category_id=category.id),
            Quest(title="Course", status="Completed", xp_reward=250, category_id=category.id),
            Quest(title="Plan", status="Planned", xp_reward=150, category_id=category.id),
        ]
    )
    session.commit()

    profile = get_character_profile_data(today=date(2026, 6, 26), session=session)

    assert profile["character_name"] == "Adventurer"
    assert profile["avatar_path"] is None
    assert profile["current_level"] == 2
    assert profile["character_title"] == "Novice Adventurer"
    assert profile["total_xp"] == 550
    assert profile["xp_to_next_level"] == 450
    assert profile["level_progress"] == 0.1
    assert profile["has_completed_quests"] is True
    assert profile["completed_quests"] == 2
    assert profile["completion_rate"] == 66.67
    assert profile["weekly_xp"] == 0
    assert profile["activity_stats"][0] == {"label": "Completed Quests", "value": 2}
    assert profile["rpg_stats"][["Stat", "XP"]].to_dict("records")[0] == {
        "Stat": "Knowledge",
        "XP": 550,
    }

from datetime import date, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.models import Base, Category, Goal, Quest, QuestCheckin
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
    get_goal_analytics_summary,
    get_goal_completed_minutes_by_week,
    get_goal_progress_dataset,
    get_goal_session_status_dataset,
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


def _add_category(session, name: str = "Health") -> Category:
    category = Category(name=name)
    session.add(category)
    session.commit()
    return category


def _add_quest(
    session,
    title: str,
    status: str = "Planned",
    xp_reward: int = 10,
    due_date: date | None = None,
    planned_start_at: datetime | None = None,
    planned_end_at: datetime | None = None,
    estimated_minutes: int | None = None,
    category: Category | None = None,
    goal: Goal | None = None,
) -> Quest:
    quest = Quest(
        title=title,
        status=status,
        xp_reward=xp_reward,
        due_date=due_date,
        planned_start_at=planned_start_at,
        planned_end_at=planned_end_at,
        estimated_minutes=estimated_minutes,
        category=category,
        goal=goal,
    )
    session.add(quest)
    session.commit()
    return quest


def _add_checkin(
    session,
    quest: Quest,
    checkin_date: date,
    status: str = "Planned",
    xp_awarded: int = 0,
) -> QuestCheckin:
    checkin = QuestCheckin(
        quest_id=quest.id,
        checkin_date=checkin_date,
        status=status,
        xp_awarded=xp_awarded,
    )
    session.add(checkin)
    session.commit()
    return checkin


def _add_goal(
    session,
    title: str = "Portfolio Project",
    status: str = "Active",
    planned_total_minutes: int = 1200,
    category: Category | None = None,
    target_end_date: date | None = None,
) -> Goal:
    goal = Goal(
        title=title,
        status=status,
        planned_total_minutes=planned_total_minutes,
        category=category,
        target_end_date=target_end_date,
    )
    session.add(goal)
    session.commit()
    return goal


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
        "current_level": 2,
        "xp_to_next_level": 159,
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
        "xp_to_next_level": 100,
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


def test_get_habit_analytics_data_uses_checkins_for_weekly_pulse(session):
    today = date(2026, 6, 26)
    completed = _add_quest(session, "Completed", xp_reward=75)
    failed = _add_quest(session, "Failed", xp_reward=30)
    skipped = _add_quest(session, "Skipped", xp_reward=10)
    future_planned = _add_quest(session, "Future planned", xp_reward=10)
    last_week = _add_quest(session, "Last week", xp_reward=150)
    _add_checkin(session, completed, date(2026, 6, 26), "Completed", xp_awarded=75)
    _add_checkin(session, failed, date(2026, 6, 25), "Failed")
    _add_checkin(session, skipped, date(2026, 6, 24), "Skipped")
    _add_checkin(session, future_planned, date(2026, 6, 28), "Planned")
    _add_checkin(session, last_week, date(2026, 6, 19), "Completed", xp_awarded=150)

    result = get_habit_analytics_data(today=today, session=session)

    assert result["weekly_pulse"] == {
        "weekly_xp": 75,
        "completed_this_week": 1,
        "failed_this_week": 1,
        "weekly_completion_rate": 50.0,
    }


def test_get_habit_analytics_data_groups_checkin_xp_by_checkin_date(session):
    first = _add_quest(session, "First", xp_reward=30)
    second = _add_quest(session, "Second", xp_reward=75)
    failed = _add_quest(session, "Failed", xp_reward=10)
    _add_checkin(session, first, date(2026, 6, 25), "Completed", xp_awarded=30)
    _add_checkin(session, second, date(2026, 6, 25), "Completed", xp_awarded=75)
    _add_checkin(session, failed, date(2026, 6, 26), "Failed", xp_awarded=0)

    result = get_habit_analytics_data(today=date(2026, 6, 26), session=session)

    assert result["xp_by_day"].to_dict("records") == [
        {"Date": date(2026, 6, 25), "XP": 105},
        {"Date": date(2026, 6, 26), "XP": 0},
    ]


def test_get_habit_analytics_data_counts_checkin_statuses(session):
    statuses = ["Planned", "Completed", "Completed", "Failed", "Skipped"]
    for index, status in enumerate(statuses):
        quest = _add_quest(session, f"Quest {index}")
        _add_checkin(session, quest, date(2026, 6, 20 + index), status, xp_awarded=10 if status == "Completed" else 0)

    result = get_habit_analytics_data(today=date(2026, 6, 26), session=session)

    assert result["quests_by_status"].to_dict("records") == [
        {"Status": "Planned", "Count": 1},
        {"Status": "Completed", "Count": 2},
        {"Status": "Failed", "Count": 1},
        {"Status": "Skipped", "Count": 1},
    ]


def test_get_habit_analytics_data_counts_checkins_by_parent_category(session):
    health = _add_category(session, "Health")
    work = _add_category(session, "Work")
    lift = _add_quest(session, "Lift", category=health)
    report = _add_quest(session, "Report", category=work)
    _add_checkin(session, lift, date(2026, 6, 25), "Completed", xp_awarded=30)
    _add_checkin(session, lift, date(2026, 6, 26), "Skipped")
    _add_checkin(session, report, date(2026, 6, 26), "Completed", xp_awarded=75)

    result = get_habit_analytics_data(today=date(2026, 6, 26), session=session)

    assert result["quests_by_category"].to_dict("records") == [
        {"Category": "Health", "Count": 2},
        {"Category": "Work", "Count": 1},
    ]
    assert result["completed_checkins_by_category"].to_dict("records") == [
        {"Category": "Health", "Count": 1},
        {"Category": "Work", "Count": 1},
    ]


def test_get_habit_analytics_data_uses_checkins_for_weekday_completion_rate(session):
    completed = _add_quest(session, "Completed")
    failed = _add_quest(session, "Failed")
    skipped = _add_quest(session, "Skipped")
    planned = _add_quest(session, "Planned")
    _add_checkin(session, completed, date(2026, 6, 22), "Completed", xp_awarded=10)
    _add_checkin(session, failed, date(2026, 6, 22), "Failed")
    _add_checkin(session, skipped, date(2026, 6, 22), "Skipped")
    _add_checkin(session, planned, date(2026, 6, 22), "Planned")

    result = get_habit_analytics_data(today=date(2026, 6, 26), session=session)

    assert result["completion_rate_by_weekday"].to_dict("records") == [
        {
            "Weekday": "Monday",
            "Completed Quest Days": 1,
            "Resolved Quest Days": 2,
            "Completion Rate": 50.0,
        }
    ]


def test_get_habit_analytics_data_uses_checkins_for_planned_minutes_by_category(session):
    health = _add_category(session, "Health")
    work = _add_category(session, "Work")
    lift = _add_quest(session, "Lift", estimated_minutes=45, category=health)
    report = _add_quest(session, "Report", estimated_minutes=60, category=work)
    _add_checkin(session, lift, date(2026, 6, 25), "Completed", xp_awarded=30)
    _add_checkin(session, lift, date(2026, 6, 26), "Failed")
    _add_checkin(session, report, date(2026, 6, 26), "Planned")

    result = get_habit_analytics_data(today=date(2026, 6, 26), session=session)

    assert result["estimated_minutes_by_category"].to_dict("records") == [
        {"Category": "Health", "Planned Minutes": 90},
        {"Category": "Work", "Planned Minutes": 60},
    ]


def test_get_habit_analytics_data_does_not_double_count_legacy_quests_when_checkins_exist(session):
    quest = _add_quest(session, "Legacy completed", status="Completed", xp_reward=150)
    _add_checkin(session, quest, date(2026, 6, 26), "Completed", xp_awarded=30)

    result = get_habit_analytics_data(today=date(2026, 6, 26), session=session)

    assert result["weekly_pulse"]["weekly_xp"] == 30
    assert result["xp_by_day"].to_dict("records") == [{"Date": date(2026, 6, 26), "XP": 30}]


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


def test_get_command_center_data_counts_checkin_status_kpis(session):
    today = date(2026, 6, 26)
    completed_quest = _add_quest(session, "Completed today", status="Planned", xp_reward=75)
    planned_quest = _add_quest(session, "Planned today", xp_reward=10)
    overdue_quest = _add_quest(session, "Old planned", xp_reward=30)
    failed_quest = _add_quest(session, "Failed old", xp_reward=10)
    skipped_quest = _add_quest(session, "Skipped today", xp_reward=150)

    _add_checkin(session, completed_quest, today, "Completed", xp_awarded=75)
    _add_checkin(session, planned_quest, today, "Planned")
    _add_checkin(session, overdue_quest, date(2026, 6, 25), "Planned")
    _add_checkin(session, failed_quest, date(2026, 6, 24), "Failed")
    _add_checkin(session, skipped_quest, today, "Skipped")

    result = get_command_center_data(today=today, session=session)

    assert result["completed_today"] == 1
    assert result["planned_quests"] == 1
    assert result["overdue_quests"] == 1
    assert result["failed_quests"] == 1
    assert result["skipped_quests"] == 1
    assert result["status_counts"] == {
        "Planned": 1,
        "Completed": 1,
        "Failed": 1,
        "Skipped": 1,
    }


def test_command_center_skipped_checkins_do_not_count_as_operational_kpis(session):
    quest = _add_quest(session, "Skipped task")
    _add_checkin(session, quest, date(2026, 6, 25), "Skipped")

    result = get_command_center_data(today=date(2026, 6, 26), session=session)

    assert result["completed_today"] == 0
    assert result["planned_quests"] == 0
    assert result["overdue_quests"] == 0
    assert result["failed_quests"] == 0


def test_command_center_today_focus_uses_checkin_status_and_parent_quest_metadata(session):
    category = _add_category(session, "Work")
    quest = _add_quest(
        session,
        "Ship report",
        status="Planned",
        xp_reward=150,
        due_date=date(2026, 6, 26),
        planned_start_at=datetime(2026, 6, 26, 9, 0),
        planned_end_at=datetime(2026, 6, 26, 11, 0),
        category=category,
    )
    _add_checkin(session, quest, date(2026, 6, 26), "Completed", xp_awarded=150)

    result = get_command_center_data(today=date(2026, 6, 26), session=session)

    assert result["today_quests"] == [
        {
            "Time": "09:00 - 11:00",
            "Title": "Ship report",
            "Category": "Work",
            "Status": "Completed",
            "XP": "150 XP",
        }
    ]


def test_build_today_focus_rows_sorts_by_planned_start_at_then_title(session):
    later = _add_quest(
        session,
        "Later scheduled",
        planned_start_at=datetime(2026, 6, 26, 13, 0),
        planned_end_at=datetime(2026, 6, 26, 14, 0),
    )
    earlier = _add_quest(
        session,
        "Earlier scheduled",
        xp_reward=75,
        planned_start_at=datetime(2026, 6, 26, 9, 0),
        planned_end_at=datetime(2026, 6, 26, 11, 0),
    )
    all_day = _add_quest(session, "All day task")
    alpha = _add_quest(session, "Alpha all day")
    checkins = [
        _add_checkin(session, later, date(2026, 6, 26), "Planned"),
        _add_checkin(session, all_day, date(2026, 6, 26), "Planned"),
        _add_checkin(session, earlier, date(2026, 6, 26), "Completed", xp_awarded=75),
        _add_checkin(session, alpha, date(2026, 6, 26), "Planned"),
    ]

    result = build_today_focus_rows(checkins)

    assert [row["Title"] for row in result] == [
        "Earlier scheduled",
        "Later scheduled",
        "All day task",
        "Alpha all day",
    ]


def test_command_center_legacy_quest_status_does_not_override_existing_checkin_status(session):
    quest = _add_quest(
        session,
        "Legacy status mismatch",
        status="Completed",
        due_date=date(2026, 6, 26),
    )
    _add_checkin(session, quest, date(2026, 6, 26), "Planned")

    result = get_command_center_data(today=date(2026, 6, 26), session=session)

    assert result["planned_quests"] == 1
    assert result["completed_today"] == 0
    assert result["today_quests"][0]["Status"] == "Planned"


def test_command_center_ensures_missing_checkin_for_legacy_scheduled_quest(session):
    quest = _add_quest(
        session,
        "Legacy scheduled",
        status="Failed",
        due_date=date(2026, 6, 26),
        planned_start_at=datetime(2026, 6, 26, 10, 0),
        planned_end_at=datetime(2026, 6, 26, 11, 0),
    )

    result = get_command_center_data(today=date(2026, 6, 26), session=session)
    checkin = session.query(QuestCheckin).filter_by(quest_id=quest.id).one()

    assert checkin.status == "Planned"
    assert checkin.checkin_date == date(2026, 6, 26)
    assert result["planned_quests"] == 1
    assert result["today_quests"][0]["Status"] == "Planned"


def test_command_center_does_not_auto_fail_stale_planned_checkins(session):
    quest = _add_quest(session, "Old planned")
    checkin = _add_checkin(session, quest, date(2026, 6, 20), "Planned")

    result = get_command_center_data(today=date(2026, 6, 26), session=session)
    session.refresh(checkin)

    assert result["overdue_quests"] == 1
    assert result["failed_quests"] == 0
    assert checkin.status == "Planned"
    assert checkin.failed_at is None


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
        {"Stat": "Strength", "XP": 75},
        {"Stat": "Discipline", "XP": 150},
        {"Stat": "Knowledge", "XP": 30},
        {"Stat": "Recovery", "XP": 10},
        {"Stat": "Creativity", "XP": 10},
    ]
    assert result[["Stat", "Level"]].to_dict("records") == [
        {"Stat": "Strength", "Level": 2},
        {"Stat": "Discipline", "Level": 2},
        {"Stat": "Knowledge", "Level": 1},
        {"Stat": "Recovery", "Level": 1},
        {"Stat": "Creativity", "Level": 1},
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
            xp_reward=10,
            due_date=date(2026, 6, 22),
            category=learning,
        ),
        Quest(
            title="Ship report",
            status="Completed",
            xp_reward=150,
            due_date=date(2026, 6, 23),
            category=work,
        ),
        Quest(
            title="Deep work",
            status="Completed",
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
    assert profile["current_level"] == 4
    assert profile["character_title"] == "Disciplined Apprentice"
    assert profile["total_xp"] == 550
    assert profile["xp_to_next_level"] == 146
    assert profile["level_progress"] == pytest.approx(0.3652)
    assert profile["has_completed_quests"] is True
    assert profile["completed_quests"] == 2
    assert profile["completion_rate"] == 66.67
    assert profile["weekly_xp"] == 0
    assert profile["activity_stats"][0] == {"label": "Completed Quests", "value": 2}
    knowledge = profile["rpg_stats"].set_index("Stat").loc["Knowledge"]
    assert int(knowledge["XP"]) == 550
    assert int(knowledge["Level"]) == 6


def test_get_character_profile_data_sums_checkin_xp_and_level_progress(session):
    category = _add_category(session, "Learning")
    quest = _add_quest(session, "Study", xp_reward=300, category=category)
    _add_checkin(session, quest, date(2026, 6, 26), "Completed", xp_awarded=550)

    profile = get_character_profile_data(today=date(2026, 6, 26), session=session)

    assert profile["total_xp"] == 550
    assert profile["current_level"] == 4
    assert profile["xp_to_next_level"] == 146
    assert profile["level_progress"] == pytest.approx(0.3652)
    assert profile["completed_quests"] == 1
    assert profile["completed_quest_days"] == 1
    assert profile["activity_stats"][0] == {"label": "Completed Quest Days", "value": 1}


def test_get_character_profile_data_groups_checkin_xp_by_parent_quest_category(session):
    health = _add_category(session, "Health")
    work = _add_category(session, "Work")
    lift = _add_quest(session, "Lift", category=health)
    report = _add_quest(session, "Report", category=work)
    _add_checkin(session, lift, date(2026, 6, 25), "Completed", xp_awarded=30)
    _add_checkin(session, report, date(2026, 6, 26), "Completed", xp_awarded=75)

    profile = get_character_profile_data(today=date(2026, 6, 26), session=session)

    stat_rows = profile["rpg_stats"][["Stat", "XP"]].to_dict("records")
    assert {"Stat": "Strength", "XP": 30} in stat_rows
    assert {"Stat": "Discipline", "XP": 75} in stat_rows
    stat_profile = {row["stat"]: row for row in profile["stat_profile"]}
    assert stat_profile["Strength"]["category"] == "Health"
    assert stat_profile["Discipline"]["category"] == "Work"


def test_get_character_profile_data_counts_repeated_completed_checkins_for_same_quest(session):
    category = _add_category(session, "Health")
    quest = _add_quest(session, "Workout", category=category)
    _add_checkin(session, quest, date(2026, 6, 25), "Completed", xp_awarded=30)
    _add_checkin(session, quest, date(2026, 6, 26), "Completed", xp_awarded=30)

    profile = get_character_profile_data(today=date(2026, 6, 26), session=session)

    assert profile["total_xp"] == 60
    assert profile["completed_quest_days"] == 2
    strength = profile["rpg_stats"].set_index("Stat").loc["Strength"]
    assert int(strength["XP"]) == 60
    assert int(strength["Level"]) == 2
    strength_profile = next(row for row in profile["stat_profile"] if row["stat"] == "Strength")
    assert strength_profile["level"] == 2
    assert strength_profile["xp"] == 60


def test_get_character_profile_data_ignores_non_completed_checkins_for_activity_and_xp(session):
    category = _add_category(session, "Health")
    skipped = _add_quest(session, "Skipped", category=category)
    failed = _add_quest(session, "Failed", category=category)
    planned = _add_quest(session, "Planned", category=category)
    _add_checkin(session, skipped, date(2026, 6, 24), "Skipped", xp_awarded=0)
    _add_checkin(session, failed, date(2026, 6, 25), "Failed", xp_awarded=0)
    _add_checkin(session, planned, date(2026, 6, 26), "Planned", xp_awarded=0)

    profile = get_character_profile_data(today=date(2026, 6, 26), session=session)

    assert profile["total_xp"] == 0
    assert profile["completed_quest_days"] == 0
    assert profile["has_completed_quests"] is False
    assert int(profile["rpg_stats"]["XP"].sum()) == 0
    assert all(row["level"] == 1 for row in profile["stat_profile"])
    assert all(row["progress_percent"] == 0 for row in profile["stat_profile"])


def test_get_character_profile_data_reset_checkin_with_zero_xp_no_longer_contributes(session):
    category = _add_category(session, "Health")
    quest = _add_quest(session, "Workout", category=category)
    _add_checkin(session, quest, date(2026, 6, 26), "Planned", xp_awarded=0)

    profile = get_character_profile_data(today=date(2026, 6, 26), session=session)

    assert profile["total_xp"] == 0
    assert profile["completed_quest_days"] == 0
    assert int(profile["rpg_stats"]["XP"].sum()) == 0
    assert all(row["xp"] == 0 for row in profile["stat_profile"])


def test_get_character_profile_data_does_not_double_count_legacy_completed_quest_with_checkin(session):
    category = _add_category(session, "Learning")
    quest = _add_quest(session, "Legacy completed", status="Completed", xp_reward=300, category=category)
    _add_checkin(session, quest, date(2026, 6, 26), "Completed", xp_awarded=30)

    profile = get_character_profile_data(today=date(2026, 6, 26), session=session)

    assert profile["total_xp"] == 30
    assert profile["completed_quest_days"] == 1
    knowledge = profile["rpg_stats"].set_index("Stat").loc["Knowledge"]
    assert int(knowledge["XP"]) == 30


def test_get_character_profile_data_builds_default_stat_profile_without_checkins(session):
    profile = get_character_profile_data(today=date(2026, 6, 26), session=session)

    assert profile["total_xp"] == 0
    assert profile["stat_profile"] == [
        {
            "stat": "Strength",
            "category": "Health",
            "xp": 0,
            "level": 1,
            "progress_percent": 0,
            "progress": 0,
            "xp_into_current_level": 0,
            "xp_needed_for_next_level": 60,
            "xp_remaining_to_next_level": 60,
            "current_level_total_xp": 0,
            "next_level_total_xp": 60,
        },
        {
            "stat": "Discipline",
            "category": "Work",
            "xp": 0,
            "level": 1,
            "progress_percent": 0,
            "progress": 0,
            "xp_into_current_level": 0,
            "xp_needed_for_next_level": 60,
            "xp_remaining_to_next_level": 60,
            "current_level_total_xp": 0,
            "next_level_total_xp": 60,
        },
        {
            "stat": "Knowledge",
            "category": "Learning",
            "xp": 0,
            "level": 1,
            "progress_percent": 0,
            "progress": 0,
            "xp_into_current_level": 0,
            "xp_needed_for_next_level": 60,
            "xp_remaining_to_next_level": 60,
            "current_level_total_xp": 0,
            "next_level_total_xp": 60,
        },
        {
            "stat": "Recovery",
            "category": "Home",
            "xp": 0,
            "level": 1,
            "progress_percent": 0,
            "progress": 0,
            "xp_into_current_level": 0,
            "xp_needed_for_next_level": 60,
            "xp_remaining_to_next_level": 60,
            "current_level_total_xp": 0,
            "next_level_total_xp": 60,
        },
        {
            "stat": "Creativity",
            "category": "Social",
            "xp": 0,
            "level": 1,
            "progress_percent": 0,
            "progress": 0,
            "xp_into_current_level": 0,
            "xp_needed_for_next_level": 60,
            "xp_remaining_to_next_level": 60,
            "current_level_total_xp": 0,
            "next_level_total_xp": 60,
        },
    ]


def test_get_character_profile_data_maps_checkin_xp_to_all_stat_levels(session):
    health = _add_category(session, "Health")
    work = _add_category(session, "Work")
    learning = _add_category(session, "Learning")
    home = _add_category(session, "Home")
    social = _add_category(session, "Social")

    rows = [
        ("Lift", health, 60),
        ("Report", work, 90),
        ("Study", learning, 153),
        ("Clean", home, 30),
        ("Call", social, 75),
    ]
    for title, category, xp in rows:
        quest = _add_quest(session, title, category=category)
        _add_checkin(session, quest, date(2026, 6, 26), "Completed", xp_awarded=xp)

    profile = get_character_profile_data(today=date(2026, 6, 26), session=session)
    stat_profile = {row["stat"]: row for row in profile["stat_profile"]}

    assert stat_profile["Strength"]["xp"] == 60
    assert stat_profile["Strength"]["level"] == 2
    assert stat_profile["Discipline"]["xp"] == 90
    assert stat_profile["Discipline"]["level"] == 2
    assert stat_profile["Knowledge"]["xp"] == 153
    assert stat_profile["Knowledge"]["level"] == 3
    assert stat_profile["Recovery"]["xp"] == 30
    assert stat_profile["Recovery"]["level"] == 1
    assert stat_profile["Creativity"]["xp"] == 75
    assert stat_profile["Creativity"]["level"] == 2


def test_get_character_profile_data_stat_levels_ignore_non_completed_zero_xp_checkins(session):
    health = _add_category(session, "Health")
    completed = _add_quest(session, "Completed", category=health)
    planned = _add_quest(session, "Planned", category=health)
    skipped = _add_quest(session, "Skipped", category=health)
    failed = _add_quest(session, "Failed", category=health)

    _add_checkin(session, completed, date(2026, 6, 23), "Completed", xp_awarded=60)
    _add_checkin(session, planned, date(2026, 6, 24), "Planned", xp_awarded=0)
    _add_checkin(session, skipped, date(2026, 6, 25), "Skipped", xp_awarded=0)
    _add_checkin(session, failed, date(2026, 6, 26), "Failed", xp_awarded=0)

    profile = get_character_profile_data(today=date(2026, 6, 26), session=session)
    strength = next(row for row in profile["stat_profile"] if row["stat"] == "Strength")

    assert strength["xp"] == 60
    assert strength["level"] == 2


def test_character_profile_radar_source_uses_stat_levels_not_raw_xp(session):
    health = _add_category(session, "Health")
    quest = _add_quest(session, "Workout", category=health)
    _add_checkin(session, quest, date(2026, 6, 26), "Completed", xp_awarded=60)

    profile = get_character_profile_data(today=date(2026, 6, 26), session=session)
    strength_profile = next(row for row in profile["stat_profile"] if row["stat"] == "Strength")
    strength_stats = profile["rpg_stats"].set_index("Stat").loc["Strength"]

    assert strength_stats["XP"] == 60
    assert strength_profile["level"] == 2
    assert strength_profile["level"] != strength_profile["xp"]


def test_get_goal_analytics_summary_empty(session):
    summary = get_goal_analytics_summary(session=session)

    assert summary["has_goals"] is False
    assert summary["included_goals_count"] == 0
    assert summary["planned_effort_minutes"] == 0
    assert summary["completed_effort_minutes"] == 0
    assert summary["overall_progress_percent"] == 0
    assert summary["goal_xp_earned"] == 0
    assert summary["goal_table"].empty


def test_goal_analytics_handles_goal_without_planned_time_target(session):
    category = _add_category(session, "Work")
    _add_goal(session, planned_total_minutes=0, category=category)

    summary = get_goal_analytics_summary(session=session)
    progress_row = get_goal_progress_dataset(session=session).iloc[0]

    assert summary["planned_effort_minutes"] == 0
    assert summary["remaining_effort_minutes"] == 0
    assert summary["expected_total_xp"] == 0
    assert summary["overall_progress_percent"] == 0
    assert progress_row["Progress Percent"] == 0


def test_get_goal_analytics_summary_filters_statuses(session):
    active = _add_goal(session, "Active goal", status="Active")
    completed = _add_goal(session, "Completed goal", status="Completed")
    archived = _add_goal(session, "Archived goal", status="Archived")

    default_summary = get_goal_analytics_summary(session=session)
    archived_summary = get_goal_analytics_summary(statuses=["Archived"], session=session)
    all_summary = get_goal_analytics_summary(statuses="All", session=session)

    assert {row["Goal ID"] for row in default_summary["goal_rows"]} == {active.id, completed.id}
    assert [row["Goal ID"] for row in archived_summary["goal_rows"]] == [archived.id]
    assert {row["Goal ID"] for row in all_summary["goal_rows"]} == {active.id, completed.id, archived.id}


def test_get_goal_analytics_summary_filters_category(session):
    work = _add_category(session, "Work")
    health = _add_category(session, "Health")
    work_goal = _add_goal(session, "Work goal", category=work)
    _add_goal(session, "Health goal", category=health)

    summary = get_goal_analytics_summary(category_id=work.id, session=session)

    assert [row["Goal ID"] for row in summary["goal_rows"]] == [work_goal.id]


def test_goal_analytics_weighted_overall_progress(session):
    first = _add_goal(session, "Small", planned_total_minutes=100)
    second = _add_goal(session, "Large", planned_total_minutes=900)
    first_quest = _add_quest(session, "Small session", estimated_minutes=100, goal=first)
    second_quest = _add_quest(session, "Large session", estimated_minutes=450, goal=second)
    _add_checkin(session, first_quest, date(2026, 7, 1), "Completed", xp_awarded=20)
    _add_checkin(session, second_quest, date(2026, 7, 2), "Completed", xp_awarded=150)

    summary = get_goal_analytics_summary(session=session)

    assert summary["planned_effort_minutes"] == 1000
    assert summary["completed_effort_minutes"] == 550
    assert summary["overall_progress_percent"] == 55.0


def test_goal_analytics_planned_session_does_not_increase_completed_effort(session):
    goal = _add_goal(session)
    quest = _add_quest(session, "Planned session", estimated_minutes=120, goal=goal)
    _add_checkin(session, quest, date(2026, 7, 1), "Planned", xp_awarded=0)

    summary = get_goal_analytics_summary(session=session)

    assert summary["linked_sessions_count"] == 1
    assert summary["planned_sessions_count"] == 1
    assert summary["completed_effort_minutes"] == 0
    assert summary["goal_xp_earned"] == 0


def test_goal_analytics_completed_session_adds_effort_and_checkin_xp(session):
    goal = _add_goal(session)
    quest = _add_quest(session, "Completed session", estimated_minutes=120, xp_reward=999, goal=goal)
    _add_checkin(session, quest, date(2026, 7, 1), "Completed", xp_awarded=40)

    summary = get_goal_analytics_summary(session=session)

    assert summary["completed_sessions_count"] == 1
    assert summary["completed_effort_minutes"] == 120
    assert summary["goal_xp_earned"] == 40


@pytest.mark.parametrize("status", ["Skipped", "Failed"])
def test_goal_analytics_skipped_failed_sessions_do_not_add_effort_or_xp(session, status):
    goal = _add_goal(session)
    quest = _add_quest(session, f"{status} session", estimated_minutes=120, goal=goal)
    _add_checkin(session, quest, date(2026, 7, 1), status, xp_awarded=0)

    summary = get_goal_analytics_summary(session=session)

    assert summary["completed_effort_minutes"] == 0
    assert summary["goal_xp_earned"] == 0
    assert summary[f"{status.lower()}_sessions_count"] == 1


def test_goal_analytics_reset_session_removes_completed_effort_and_xp(session):
    goal = _add_goal(session)
    quest = _add_quest(session, "Reset session", estimated_minutes=120, goal=goal)
    _add_checkin(session, quest, date(2026, 7, 1), "Planned", xp_awarded=0)

    summary = get_goal_analytics_summary(session=session)

    assert summary["completed_effort_minutes"] == 0
    assert summary["goal_xp_earned"] == 0
    assert summary["planned_sessions_count"] == 1


def test_goal_analytics_progress_capped_and_remaining_not_negative(session):
    goal = _add_goal(session, planned_total_minutes=60)
    quest = _add_quest(session, "Oversized session", estimated_minutes=120, goal=goal)
    _add_checkin(session, quest, date(2026, 7, 1), "Completed", xp_awarded=40)

    summary = get_goal_analytics_summary(session=session)
    progress_row = get_goal_progress_dataset(session=session).iloc[0]

    assert summary["overall_progress_percent"] == 100.0
    assert summary["remaining_effort_minutes"] == 0
    assert progress_row["Progress Percent"] == 100.0
    assert progress_row["Remaining Effort"] == 0


def test_goal_completed_minutes_by_week_groups_by_checkin_date(session):
    goal = _add_goal(session)
    first = _add_quest(session, "First", estimated_minutes=60, goal=goal)
    second = _add_quest(session, "Second", estimated_minutes=90, goal=goal)
    planned = _add_quest(session, "Planned", estimated_minutes=120, goal=goal)
    _add_checkin(session, first, date(2026, 7, 6), "Completed", xp_awarded=20)
    _add_checkin(session, second, date(2026, 7, 12), "Completed", xp_awarded=30)
    _add_checkin(session, planned, date(2026, 7, 13), "Planned", xp_awarded=0)

    result = get_goal_completed_minutes_by_week(session=session)

    assert result.to_dict("records") == [{"Week": date(2026, 7, 6), "Completed Minutes": 150}]


def test_goal_session_status_dataset_counts_by_goal(session):
    goal = _add_goal(session)
    completed = _add_quest(session, "Completed", estimated_minutes=60, goal=goal)
    skipped = _add_quest(session, "Skipped", estimated_minutes=60, goal=goal)
    _add_checkin(session, completed, date(2026, 7, 1), "Completed", xp_awarded=20)
    _add_checkin(session, skipped, date(2026, 7, 2), "Skipped", xp_awarded=0)

    result = get_goal_session_status_dataset(session=session)

    assert result.to_dict("records") == [
        {"Goal": "Portfolio Project", "Status": "Completed", "Count": 1},
        {"Goal": "Portfolio Project", "Status": "Planned", "Count": 0},
        {"Goal": "Portfolio Project", "Status": "Skipped", "Count": 1},
        {"Goal": "Portfolio Project", "Status": "Failed", "Count": 0},
    ]


def test_goal_analytics_excludes_quests_without_goal_id(session):
    goal = _add_goal(session)
    linked = _add_quest(session, "Linked session", estimated_minutes=60, goal=goal)
    unlinked = _add_quest(session, "Recurring generated standalone", estimated_minutes=180)
    _add_checkin(session, linked, date(2026, 7, 1), "Completed", xp_awarded=20)
    _add_checkin(session, unlinked, date(2026, 7, 1), "Completed", xp_awarded=999)

    summary = get_goal_analytics_summary(session=session)

    assert summary["completed_effort_minutes"] == 60
    assert summary["goal_xp_earned"] == 20

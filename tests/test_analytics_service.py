from datetime import date, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.models import Base, Category, Quest, QuestCheckin
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
    quest.difficulty = "Boss"
    _add_checkin(session, quest, date(2026, 6, 26), "Completed", xp_awarded=150)

    result = get_command_center_data(today=date(2026, 6, 26), session=session)

    assert result["today_quests"] == [
        {
            "Time": "09:00 - 11:00",
            "Title": "Ship report",
            "Category": "Work",
            "Difficulty": "Boss",
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


def test_get_character_profile_data_sums_checkin_xp_and_level_progress(session):
    category = _add_category(session, "Learning")
    quest = _add_quest(session, "Study", xp_reward=300, category=category)
    _add_checkin(session, quest, date(2026, 6, 26), "Completed", xp_awarded=550)

    profile = get_character_profile_data(today=date(2026, 6, 26), session=session)

    assert profile["total_xp"] == 550
    assert profile["current_level"] == 2
    assert profile["xp_to_next_level"] == 450
    assert profile["level_progress"] == 0.1
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


def test_get_character_profile_data_reset_checkin_with_zero_xp_no_longer_contributes(session):
    category = _add_category(session, "Health")
    quest = _add_quest(session, "Workout", category=category)
    _add_checkin(session, quest, date(2026, 6, 26), "Planned", xp_awarded=0)

    profile = get_character_profile_data(today=date(2026, 6, 26), session=session)

    assert profile["total_xp"] == 0
    assert profile["completed_quest_days"] == 0
    assert int(profile["rpg_stats"]["XP"].sum()) == 0


def test_get_character_profile_data_does_not_double_count_legacy_completed_quest_with_checkin(session):
    category = _add_category(session, "Learning")
    quest = _add_quest(session, "Legacy completed", status="Completed", xp_reward=300, category=category)
    _add_checkin(session, quest, date(2026, 6, 26), "Completed", xp_awarded=30)

    profile = get_character_profile_data(today=date(2026, 6, 26), session=session)

    assert profile["total_xp"] == 30
    assert profile["completed_quest_days"] == 1
    knowledge = profile["rpg_stats"].set_index("Stat").loc["Knowledge"]
    assert int(knowledge["XP"]) == 30

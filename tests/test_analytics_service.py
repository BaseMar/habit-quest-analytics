from datetime import date, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.models import Base, Quest
from src.services.analytics_service import (
    build_completion_rate_by_weekday,
    build_quests_by_status,
    build_xp_by_day,
    get_dashboard_kpis,
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

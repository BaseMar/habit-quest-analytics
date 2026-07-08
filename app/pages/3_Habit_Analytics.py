import sys
from pathlib import Path

import plotly.express as px
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.database.db import init_db
from src.services.analytics_service import get_habit_analytics_data
from src.ui import (
    apply_theme,
    get_theme_tokens,
    render_empty_state,
    render_page_header,
    render_section_title,
    style_chart,
)


def render_weekly_pulse(weekly_pulse: dict) -> None:
    metric_cols = st.columns(4)
    metrics = (
        ("Weekly XP", weekly_pulse["weekly_xp"]),
        ("Completed This Week", weekly_pulse["completed_this_week"]),
        ("Failed This Week", weekly_pulse["failed_this_week"]),
        ("Weekly Completion", f"{weekly_pulse['weekly_completion_rate']}%"),
    )
    for column, (label, value) in zip(metric_cols, metrics):
        with column:
            st.metric(label, value)


def render_xp_by_day(xp_by_day) -> None:
    if xp_by_day.empty:
        render_empty_state("No completed quest days yet", "Complete quest days to see XP trends by day.")
        return

    tokens = get_theme_tokens()
    chart_data = _format_date_labels(xp_by_day)
    fig = px.line(
        chart_data,
        x="Date",
        y="XP",
        title="XP Trend by Day",
        markers=True,
        color_discrete_sequence=[tokens["accent"]],
    )
    fig.update_layout(xaxis_title="Check-in Date", yaxis_title="XP Earned", showlegend=False, height=360)
    fig.update_xaxes(type="category")
    fig.update_traces(line={"width": 3}, marker={"size": 8})
    st.plotly_chart(style_chart(fig, height=360), width="stretch")


def render_status_chart(quests_by_status) -> None:
    if quests_by_status.empty:
        render_empty_state("No status data", "Update quest days to see the status breakdown.")
        return

    tokens = get_theme_tokens()
    fig = px.bar(
        quests_by_status,
        x="Status",
        y="Count",
        title="Check-ins by Status",
        category_orders={"Status": quests_by_status["Status"].tolist()},
        color_discrete_sequence=[tokens["info"]],
    )
    fig.update_layout(xaxis_title="Check-in Status", yaxis_title="Check-in Count", showlegend=False, height=320)
    st.plotly_chart(style_chart(fig), width="stretch")


def render_category_chart(quests_by_category) -> None:
    if quests_by_category.empty:
        render_empty_state("No category data", "Add categorized quest days to see category balance.")
        return

    tokens = get_theme_tokens()
    fig = px.bar(
        quests_by_category,
        x="Category",
        y="Count",
        title="Check-ins by Category",
        color_discrete_sequence=[tokens["success"]],
    )
    fig.update_layout(xaxis_title="Category", yaxis_title="Check-in Count", showlegend=False, height=320)
    st.plotly_chart(style_chart(fig), width="stretch")


def render_weekday_chart(completion_rate_by_weekday) -> None:
    if completion_rate_by_weekday.empty:
        render_empty_state("No resolved quest days found", "Complete or fail quest days to see weekday consistency.")
        return
    tokens = get_theme_tokens()
    hover_columns = [
        column
        for column in ("Completed Quest Days", "Resolved Quest Days", "Completed Quests", "Total Quests")
        if column in completion_rate_by_weekday.columns
    ]

    fig = px.bar(
        completion_rate_by_weekday,
        x="Weekday",
        y="Completion Rate",
        title="Completion Rate by Weekday",
        hover_data=hover_columns,
        color_discrete_sequence=[tokens["warning"]],
        category_orders={
            "Weekday": [
                "Monday",
                "Tuesday",
                "Wednesday",
                "Thursday",
                "Friday",
                "Saturday",
                "Sunday",
            ]
        },
    )
    fig.update_layout(xaxis_title="Check-in Weekday", yaxis_title="Completion Rate (%)", showlegend=False, height=320)
    st.plotly_chart(style_chart(fig), width="stretch")


def render_estimated_minutes_chart(estimated_minutes_by_category) -> None:
    minutes_column = "Planned Minutes" if "Planned Minutes" in estimated_minutes_by_category.columns else "Estimated Minutes"
    if estimated_minutes_by_category.empty or estimated_minutes_by_category[minutes_column].sum() == 0:
        render_empty_state("No estimated time recorded", "Schedule quests with duration to compare planned effort.")
        return

    tokens = get_theme_tokens()
    fig = px.bar(
        estimated_minutes_by_category,
        x="Category",
        y=minutes_column,
        title="Planned Minutes by Category",
        color_discrete_sequence=[tokens["accent"]],
    )
    fig.update_layout(xaxis_title="Category", yaxis_title="Planned Minutes", showlegend=False, height=320)
    st.plotly_chart(style_chart(fig), width="stretch")


def render_insights(analytics: dict) -> None:
    insights = _build_insights(analytics)
    if not insights:
        return

    render_section_title("Insights", "Small readouts derived from current checklist history.")
    insight_cols = st.columns(len(insights))
    for column, (label, value) in zip(insight_cols, insights):
        with column:
            st.metric(label, value)


def _format_date_labels(dataframe):
    chart_data = dataframe.copy()
    chart_data["Date"] = chart_data["Date"].map(
        lambda value: value.strftime("%Y-%m-%d") if hasattr(value, "strftime") else str(value)
    )
    return chart_data


def _build_insights(analytics: dict) -> list[tuple[str, str]]:
    insights: list[tuple[str, str]] = []

    completion_rate_by_weekday = analytics["completion_rate_by_weekday"]
    if not completion_rate_by_weekday.empty:
        completed_column = (
            "Completed Quest Days"
            if "Completed Quest Days" in completion_rate_by_weekday.columns
            else "Completed Quests"
        )
        strongest_weekday = completion_rate_by_weekday.sort_values(
            [completed_column, "Completion Rate", "Weekday"],
            ascending=[False, False, True],
        ).iloc[0]
        insights.append(("Strongest Weekday", str(strongest_weekday["Weekday"])))

    quests_by_category = analytics.get("completed_checkins_by_category", analytics["quests_by_category"])
    if not quests_by_category.empty:
        top_category = quests_by_category.sort_values(["Count", "Category"], ascending=[False, True]).iloc[0]
        insights.append(("Most Active Category", str(top_category["Category"])))

    quests_by_status = analytics["quests_by_status"]
    if not quests_by_status.empty:
        failed_rows = quests_by_status[quests_by_status["Status"] == "Failed"]
        failed_count = int(failed_rows["Count"].iloc[0]) if not failed_rows.empty else 0
        insights.append(("Failed Quest Days", str(failed_count)))

    return insights[:3]


apply_theme()
render_page_header(
    "Analytics",
    "Habit Analytics",
    "Review quest trends, consistency, categories, and weekly performance.",
)

init_db()
analytics = get_habit_analytics_data()

if not analytics["has_quests"]:
    render_empty_state(
        "No checklist data yet",
        "Plan quests in Quest Planner and update them in Monthly Checklist to generate analytics.",
    )
else:
    render_section_title("Weekly Pulse", "Compact performance readout for the current week.")
    render_weekly_pulse(analytics["weekly_pulse"])

    render_section_title("Trend Overview", "Time-based progress from completed quest-day XP.")
    with st.container(border=True):
        render_xp_by_day(analytics["xp_by_day"])

    render_section_title("Performance Breakdown", "How quest days are distributed by state and category.")
    status_col, category_col = st.columns(2, gap="large")
    with status_col:
        with st.container(border=True):
            render_status_chart(analytics["quests_by_status"])
    with category_col:
        with st.container(border=True):
            render_category_chart(analytics["quests_by_category"])

    render_section_title("Consistency & Time", "Checklist consistency and planned workload by category.")
    weekday_col, minutes_col = st.columns(2, gap="large")
    with weekday_col:
        with st.container(border=True):
            render_weekday_chart(analytics["completion_rate_by_weekday"])
    with minutes_col:
        with st.container(border=True):
            render_estimated_minutes_chart(analytics["estimated_minutes_by_category"])

    render_insights(analytics)

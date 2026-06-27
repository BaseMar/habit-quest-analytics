import sys
from pathlib import Path

import plotly.express as px
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.database.db import init_db
from src.services.analytics_service import get_habit_analytics_data
from src.ui import apply_theme, render_empty_state, render_page_header, render_section_title, style_chart


st.set_page_config(page_title="Habit Analytics", page_icon="HQ", layout="wide")


def _render_centered_chart(fig):
    _, chart_col, _ = st.columns([1, 5, 1])
    with chart_col:
        st.plotly_chart(fig, width="stretch")


def _format_date_labels(dataframe):
    chart_data = dataframe.copy()
    chart_data["Date"] = chart_data["Date"].map(
        lambda value: value.strftime("%Y-%m-%d") if hasattr(value, "strftime") else str(value)
    )
    return chart_data


apply_theme()
render_page_header(
    "Analytics",
    "Habit Analytics",
    "Analyze your quest history, XP rhythm, category balance, and habit consistency.",
)

init_db()
analytics = get_habit_analytics_data()

if not analytics["has_quests"]:
    render_empty_state("No analytics data yet", "Add your first quests in Quest Log to unlock charts.")
else:
    xp_by_day = analytics["xp_by_day"]
    quests_by_status = analytics["quests_by_status"]
    quests_by_category = analytics["quests_by_category"]
    completion_rate_by_weekday = analytics["completion_rate_by_weekday"]
    estimated_minutes_by_category = analytics["estimated_minutes_by_category"]

    render_section_title("Progress", "XP earned from completed quests, grouped by day.")
    if xp_by_day.empty:
        render_empty_state("No completed quests yet", "Complete quests to see XP by day.")
    else:
        xp_by_day_chart = _format_date_labels(xp_by_day)
        fig = px.bar(xp_by_day_chart, x="Date", y="XP", title="XP by Day", color_discrete_sequence=["#8B5CF6"])
        fig.update_layout(xaxis_title="Quest Date", yaxis_title="XP Earned", showlegend=False, height=320)
        fig.update_xaxes(type="category")
        _render_centered_chart(style_chart(fig))

    render_section_title("Quest Breakdown", "Status and category distribution across your quest ledger.")
    _, col1, col2, _ = st.columns([1, 4, 4, 1])

    with col1:
        if quests_by_status.empty:
            render_empty_state("No status data", "Add quests to see the status breakdown.")
        else:
            fig = px.bar(
                quests_by_status,
                x="Status",
                y="Count",
                title="Quests by Status",
                category_orders={"Status": quests_by_status["Status"].tolist()},
                color_discrete_sequence=["#38BDF8"],
            )
            fig.update_layout(xaxis_title="Quest Status", yaxis_title="Quest Count", showlegend=False, height=320)
            st.plotly_chart(style_chart(fig), width="stretch")

    with col2:
        if quests_by_category.empty:
            render_empty_state("No category data", "Add categorized quests to see category balance.")
        else:
            fig = px.bar(
                quests_by_category,
                x="Category",
                y="Count",
                title="Quests by Category",
                color_discrete_sequence=["#22C55E"],
            )
            fig.update_layout(xaxis_title="Category", yaxis_title="Quest Count", showlegend=False, height=320)
            st.plotly_chart(style_chart(fig), width="stretch")

    render_section_title("Consistency", "Completion rate by the weekday originally planned for each quest.")
    if completion_rate_by_weekday.empty:
        render_empty_state("No planned dates found", "Add planned dates to see completion rate by weekday.")
    else:
        fig = px.bar(
            completion_rate_by_weekday,
            x="Weekday",
            y="Completion Rate",
            title="Completion Rate by Weekday",
            hover_data=["Completed Quests", "Total Quests"],
            color_discrete_sequence=["#F59E0B"],
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
        fig.update_layout(xaxis_title="Planned Weekday", yaxis_title="Completion Rate (%)", showlegend=False, height=320)
        _render_centered_chart(style_chart(fig))

    render_section_title("Planning", "Estimated effort grouped by quest category.")
    if estimated_minutes_by_category.empty or estimated_minutes_by_category["Estimated Minutes"].sum() == 0:
        render_empty_state(
            "No estimated time recorded",
            "Add estimated minutes to compare planned effort by category.",
        )
    else:
        fig = px.bar(
            estimated_minutes_by_category,
            x="Category",
            y="Estimated Minutes",
            title="Estimated Minutes by Category",
            color_discrete_sequence=["#8B5CF6"],
        )
        fig.update_layout(xaxis_title="Category", yaxis_title="Estimated Minutes", showlegend=False, height=320)
        _render_centered_chart(style_chart(fig))

import sys
from pathlib import Path

import plotly.express as px
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.database.db import init_db
from src.services.analytics_service import get_habit_analytics_data


st.title("Habit Analytics")
st.write("Analyze quest history, XP patterns, and habit consistency using persisted quest data.")

init_db()
analytics = get_habit_analytics_data()

if not analytics["has_quests"]:
    st.info("No quests yet. Create quests in the Quest Log page to unlock analytics charts.")
else:
    xp_by_day = analytics["xp_by_day"]
    quests_by_status = analytics["quests_by_status"]
    quests_by_category = analytics["quests_by_category"]
    completion_rate_by_weekday = analytics["completion_rate_by_weekday"]
    estimated_minutes_by_category = analytics["estimated_minutes_by_category"]

    st.header("Progress")
    if xp_by_day.empty:
        st.info("Complete quests to see XP by day.")
    else:
        fig = px.bar(xp_by_day, x="Date", y="XP", title="XP by Day")
        fig.update_layout(xaxis_title="Date", yaxis_title="XP", showlegend=False)
        st.plotly_chart(fig, width="stretch")

    st.header("Quest Breakdown")
    col1, col2 = st.columns(2)

    with col1:
        if quests_by_status.empty:
            st.info("No status data available yet.")
        else:
            fig = px.bar(
                quests_by_status,
                x="Status",
                y="Count",
                title="Quests by Status",
                category_orders={"Status": ["Planned", "Completed", "Failed", "Skipped"]},
            )
            fig.update_layout(xaxis_title="Status", yaxis_title="Quests", showlegend=False)
            st.plotly_chart(fig, width="stretch")

    with col2:
        if quests_by_category.empty:
            st.info("No category data available yet.")
        else:
            fig = px.bar(quests_by_category, x="Category", y="Count", title="Quests by Category")
            fig.update_layout(xaxis_title="Category", yaxis_title="Quests", showlegend=False)
            st.plotly_chart(fig, width="stretch")

    st.header("Consistency")
    if completion_rate_by_weekday.empty:
        st.info("Add planned dates to quests to see completion rate by weekday.")
    else:
        fig = px.bar(
            completion_rate_by_weekday,
            x="Weekday",
            y="Completion Rate",
            title="Completion Rate by Weekday",
            hover_data=["Completed Quests", "Total Quests"],
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
        fig.update_layout(xaxis_title="Planned Weekday", yaxis_title="Completion Rate (%)", showlegend=False)
        st.plotly_chart(fig, width="stretch")

    st.header("Planning")
    if estimated_minutes_by_category.empty or estimated_minutes_by_category["Estimated Minutes"].sum() == 0:
        st.info("Add estimated minutes to quests to see planning effort by category.")
    else:
        fig = px.bar(
            estimated_minutes_by_category,
            x="Category",
            y="Estimated Minutes",
            title="Estimated Minutes by Category",
        )
        fig.update_layout(xaxis_title="Category", yaxis_title="Estimated Minutes", showlegend=False)
        st.plotly_chart(fig, width="stretch")

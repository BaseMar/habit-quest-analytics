import sys
from datetime import date, timedelta
from pathlib import Path

import plotly.express as px
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.services.analytics_service import (
    get_habit_analytics_data,
)
from src.services.quest_service import get_categories
from src.ui import (
    get_theme_tokens,
    render_empty_state,
    render_metric_card,
    render_page_header,
    render_section_title,
    style_chart,
)

WORK_TYPE_OPTIONS = {
    "All work": "all",
    "One-time tasks": "one_time",
    "Routines": "routine",
    "Project sessions": "project_session",
}


def render_analytics_filters(categories: list, today: date) -> dict:
    period_col, category_col, type_col = st.container(key="hq_analytics_filters").columns(
        [1, 1, 1], vertical_alignment="bottom"
    )
    with period_col:
        period = st.selectbox("Period", ["7 days", "30 days", "90 days", "Custom"], index=1, key="analytics_period")

    category_options = {"All categories": None} | {category.name: category.id for category in categories}
    with category_col:
        category_name = st.selectbox("Category", list(category_options), key="analytics_category")
    with type_col:
        work_type_label = st.selectbox("Work type", list(WORK_TYPE_OPTIONS), key="analytics_work_type")

    if period == "Custom":
        start_col, end_col = st.columns(2)
        with start_col:
            start_date = st.date_input(
                "From",
                value=today - timedelta(days=29),
                max_value=today,
                key="analytics_start_date",
            )
        with end_col:
            end_date = st.date_input(
                "To",
                value=today,
                min_value=start_date,
                max_value=today,
                key="analytics_end_date",
            )
    else:
        days = int(period.split()[0])
        start_date = today - timedelta(days=days - 1)
        end_date = today

    return {
        "start_date": start_date,
        "end_date": end_date,
        "category_id": category_options[category_name],
        "work_type": WORK_TYPE_OPTIONS[work_type_label],
    }


def render_period_summary(period_summary: dict, previous_period_summary: dict, period_highlights: dict) -> None:
    metric_cols = st.columns(3)
    metrics = (
        (
            "Completion",
            f"{period_summary['completion_rate']}%",
            f"{_format_delta(period_summary['completion_rate'], previous_period_summary['completion_rate'], 'pp')} vs previous period",
        ),
        (
            "Completed",
            period_summary["completed_count"],
            (
                f"of {period_summary['checkins_count']} check-ins; "
                f"{_format_delta(period_summary['completed_count'], previous_period_summary['completed_count'])} vs previous period"
            ),
        ),
        (
            "Consistency",
            f"{period_highlights['active_day_rate']:.0f}%",
            f"{period_highlights['completed_days']} of {period_highlights['scheduled_days']} scheduled days included completed work",
        ),
    )
    for column, (label, value, caption) in zip(metric_cols, metrics):
        with column:
            render_metric_card(label, value, caption)


def render_planned_vs_completed_by_week(weekly_effort) -> None:
    if weekly_effort.empty or weekly_effort["Planned Minutes"].sum() == 0:
        render_empty_state("No planned time in this period", "Schedule work with a duration to compare plan and completion.")
        return

    tokens = get_theme_tokens()
    chart_data = weekly_effort.melt(
        id_vars=["Week", "Planned Completion Rate"],
        value_vars=["Planned Minutes", "Completed Planned Minutes"],
        var_name="Effort",
        value_name="Minutes",
    )
    fig = px.bar(
        chart_data,
        x="Week",
        y="Minutes",
        color="Effort",
        barmode="group",
        hover_data={"Planned Completion Rate": ":.1f", "Minutes": True},
        color_discrete_map={
            "Planned Minutes": tokens["info"],
            "Completed Planned Minutes": tokens["accent"],
        },
        title="Scheduled Effort Completed",
    )
    fig.update_layout(xaxis_title="Week starting", yaxis_title="Planned minutes", height=360)
    st.plotly_chart(style_chart(fig, height=360), width="stretch", config={"displayModeBar": False})


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
        color_discrete_sequence=[tokens["accent"]],
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


def render_category_performance(category_performance) -> None:
    if category_performance.empty:
        render_empty_state("No category data", "Complete or resolve planned work to compare category performance.")
        return

    tokens = get_theme_tokens()
    chart_data = category_performance.melt(
        id_vars=["Category", "Completion Rate"],
        value_vars=["Planned Minutes", "Completed Planned Minutes"],
        var_name="Effort",
        value_name="Minutes",
    )
    fig = px.bar(
        chart_data,
        x="Minutes",
        y="Category",
        color="Effort",
        orientation="h",
        barmode="group",
        hover_data={"Completion Rate": ":.1f", "Minutes": True},
        color_discrete_map={
            "Planned Minutes": tokens["info"],
            "Completed Planned Minutes": tokens["accent"],
        },
        title="Planned vs Completed Time by Category",
    )
    fig.update_layout(xaxis_title="Planned minutes", yaxis_title="Category", height=360)
    fig.update_yaxes(categoryorder="array", categoryarray=category_performance["Category"].tolist()[::-1])
    st.plotly_chart(style_chart(fig, height=360), width="stretch", config={"displayModeBar": False})

    table_data = category_performance[
        [
            "Category",
            "Planned Minutes",
            "Completed Planned Minutes",
            "Completion Rate",
            "Completed",
            "Failed",
            "Skipped",
            "Planned",
            "XP Earned",
        ]
    ].copy()
    table_data["Planned Minutes"] = table_data["Planned Minutes"].map(_format_minutes)
    table_data["Completed Planned Minutes"] = table_data["Completed Planned Minutes"].map(_format_minutes)
    table_data["Completion Rate"] = table_data["Completion Rate"].map(lambda value: f"{value:.1f}%")
    table_data["XP Earned"] = table_data["XP Earned"].map(lambda value: f"{value} XP")
    with st.expander("View category data"):
        st.dataframe(table_data, hide_index=True, width="stretch")


def render_routine_performance(routine_performance) -> None:
    if routine_performance.empty:
        render_empty_state("No routine data", "Generate routine days to review their completion history.")
        return

    tokens = get_theme_tokens()
    fig = px.bar(
        routine_performance,
        x="Completion Rate",
        y="Routine",
        orientation="h",
        hover_data=["Scheduled", "Completed", "Failed", "Skipped", "Planned", "Overdue Planned"],
        color_discrete_sequence=[tokens["accent"]],
        title="Routine Completion Rate",
    )
    fig.update_layout(xaxis_title="Completion rate (%)", yaxis_title="Routine", showlegend=False, height=360)
    fig.update_xaxes(range=[0, 100])
    fig.update_yaxes(categoryorder="array", categoryarray=routine_performance["Routine"].tolist()[::-1])
    st.plotly_chart(style_chart(fig, height=360), width="stretch", config={"displayModeBar": False})

    table_data = routine_performance[
        [
            "Routine",
            "Category",
            "Active",
            "Completion Rate",
            "Scheduled",
            "Completed",
            "Failed",
            "Skipped",
            "Planned",
            "Overdue Planned",
            "Last Completed",
        ]
    ].copy()
    table_data["Active"] = table_data["Active"].map(lambda value: "Active" if value else "Stopped")
    table_data["Completion Rate"] = table_data["Completion Rate"].map(lambda value: f"{value:.1f}%")
    table_data["Last Completed"] = table_data["Last Completed"].map(
        lambda value: value.isoformat() if value is not None else "Not completed"
    )
    with st.expander("View routine data"):
        st.dataframe(table_data, hide_index=True, width="stretch")


def render_review_focus(review_focus: dict | None) -> None:
    if review_focus is None:
        return

    st.info(f"{review_focus['title']}: {review_focus['message']}")


def _format_minutes(minutes: int) -> str:
    if minutes <= 0:
        return "0 min"
    hours, remainder = divmod(int(minutes), 60)
    if hours and remainder:
        return f"{hours}h {remainder}m"
    if hours:
        return f"{hours}h"
    return f"{remainder} min"


def _format_delta(current_value: float | int, previous_value: float | int, suffix: str = "") -> str:
    difference = current_value - previous_value
    if isinstance(difference, float):
        return f"{difference:+.1f}{suffix}"
    return f"{difference:+d}{suffix}"


def render_activity_overview(analytics: dict) -> None:
    if not analytics["has_quests"]:
        render_empty_state(
            "No checklist data yet",
            "Schedule work in Planner and record check-ins in Command Center.",
        )
        return

    date_range = analytics["date_range"]
    render_section_title(
        "Period review",
        (
            f"{date_range['start_date']:%d %b %Y} to {date_range['end_date']:%d %b %Y}. "
            "Every KPI is compared with the preceding period of the same length."
        ),
    )
    render_period_summary(
        analytics["period_summary"],
        analytics["previous_period_summary"],
        analytics["period_highlights"],
    )
    st.markdown('<div class="hq-content-gap"></div>', unsafe_allow_html=True)
    render_review_focus(analytics["review_focus"])

    workload_col, consistency_col = st.container(key="hq_analytics_charts").columns(2)
    with workload_col:
        render_section_title("Workload execution", "Scheduled workload compared with completed planned time each week.")
        render_planned_vs_completed_by_week(analytics["planned_vs_completed_by_week"])
    with consistency_col:
        render_section_title("Weekly consistency", "Completion rate for resolved check-ins, grouped by weekday.")
        render_weekday_chart(analytics["completion_rate_by_weekday"])

render_page_header(
    "Habit Analytics",
    "Review your workload, consistency, and completion rates.",
)

today = date.today()
filters = render_analytics_filters(get_categories(), today)
analytics = get_habit_analytics_data(today=today, **filters)
overview_tab, categories_tab, routines_tab = st.tabs(
    ["Overview", "Categories", "Routines"], key="analytics_tab", on_change="rerun"
)
if overview_tab.open:
    with overview_tab:
        render_activity_overview(analytics)
if categories_tab.open:
    with categories_tab:
        render_category_performance(analytics["category_performance"])
if routines_tab.open:
    with routines_tab:
        render_routine_performance(analytics["routine_performance"])

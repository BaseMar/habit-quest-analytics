import sys
from datetime import date, timedelta
from pathlib import Path

import plotly.express as px
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.database.db import init_db
from src.services.analytics_service import (
    get_habit_analytics_data,
)
from src.services.quest_service import get_categories
from src.ui import (
    apply_theme,
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
    period_col, category_col, type_col = st.columns([0.46, 0.27, 0.27], vertical_alignment="bottom")
    with period_col:
        if hasattr(st, "segmented_control"):
            period = st.segmented_control(
                "Period",
                ["7 days", "30 days", "90 days", "Custom"],
                default="30 days",
                key="analytics_period",
            )
        else:
            period = st.radio(
                "Period",
                ["7 days", "30 days", "90 days", "Custom"],
                horizontal=True,
                key="analytics_period",
            )
        period = period or "30 days"

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


def render_period_summary(period_summary: dict, previous_period_summary: dict) -> None:
    metric_cols = st.columns(4)
    metrics = (
        (
            "Completion",
            f"{period_summary['completion_rate']}%",
            _format_delta(period_summary["completion_rate"], previous_period_summary["completion_rate"], "pp"),
        ),
        (
            "Completed",
            f"{period_summary['completed_count']} / {period_summary['checkins_count']}",
            _format_delta(period_summary["completed_count"], previous_period_summary["completed_count"]),
        ),
        (
            "Completed planned time",
            _format_minutes(period_summary["completed_planned_minutes"]),
            _format_delta(period_summary["completed_planned_minutes"], previous_period_summary["completed_planned_minutes"], " min"),
        ),
        (
            "XP earned",
            period_summary["xp_earned"],
            _format_delta(period_summary["xp_earned"], previous_period_summary["xp_earned"], " XP"),
        ),
    )
    for column, (label, value, delta) in zip(metric_cols, metrics):
        with column:
            render_metric_card(label, value, f"vs previous period: {delta}")
    if period_summary["actual_time_entries_count"]:
        st.caption(
            "Recorded actual time: "
            f"{_format_minutes(period_summary['actual_minutes'])} across "
            f"{period_summary['actual_time_entries_count']} completed item(s)."
        )


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
        title="Planned vs Completed Time",
    )
    fig.update_layout(xaxis_title="Week starting", yaxis_title="Planned minutes", height=360)
    st.plotly_chart(style_chart(fig, height=360), width="stretch", config={"displayModeBar": False})


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
            "Actual Minutes",
        ]
    ].copy()
    table_data["Planned Minutes"] = table_data["Planned Minutes"].map(_format_minutes)
    table_data["Completed Planned Minutes"] = table_data["Completed Planned Minutes"].map(_format_minutes)
    table_data["Completion Rate"] = table_data["Completion Rate"].map(lambda value: f"{value:.1f}%")
    table_data["XP Earned"] = table_data["XP Earned"].map(lambda value: f"{value} XP")
    table_data["Actual Minutes"] = table_data["Actual Minutes"].map(_format_minutes)
    st.dataframe(table_data, hide_index=True, width="stretch")


def render_routine_performance(routine_performance) -> None:
    if routine_performance.empty:
        render_empty_state("No routine data", "Generate routine days to review their completion history.")
        return

    attention_rows = routine_performance[routine_performance["Needs Attention"]]
    if not attention_rows.empty:
        attention_labels = [
            f"{row['Routine']} ({int(row['Failed'])} failed, {int(row['Overdue Planned'])} overdue)"
            for _, row in attention_rows.iterrows()
        ]
        st.warning("Needs attention: " + ", ".join(attention_labels))

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
    st.dataframe(table_data, hide_index=True, width="stretch")


def render_insights(analytics: dict) -> None:
    insights = _build_insights(analytics["category_performance"])
    if not insights:
        return

    render_section_title("Focus points", "Signals from workload and resolved check-ins in the selected period.")
    insight_cols = st.columns(len(insights))
    for column, (label, value) in zip(insight_cols, insights):
        with column:
            render_metric_card(label, value)


def _format_date_labels(dataframe):
    chart_data = dataframe.copy()
    chart_data["Date"] = chart_data["Date"].map(
        lambda value: value.strftime("%Y-%m-%d") if hasattr(value, "strftime") else str(value)
    )
    return chart_data


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


def _build_insights(category_performance) -> list[tuple[str, str]]:
    insights: list[tuple[str, str]] = []
    if category_performance.empty:
        return insights

    resolved_categories = category_performance[
        (category_performance["Completed"] + category_performance["Failed"]) > 0
    ]
    if not resolved_categories.empty:
        category_to_improve = resolved_categories.sort_values(
            ["Completion Rate", "Planned Minutes", "Category"],
            ascending=[True, False, True],
        ).iloc[0]
        insights.append(
            (
                "Category to improve",
                f"{category_to_improve['Category']}: {category_to_improve['Completion Rate']:.0f}% complete",
            )
        )

    planned_categories = category_performance[category_performance["Planned"] > 0]
    if not planned_categories.empty:
        largest_unresolved = planned_categories.sort_values(
            ["Planned", "Planned Minutes", "Category"],
            ascending=[False, False, True],
        ).iloc[0]
        insights.append(
            (
                "Largest unresolved workload",
                f"{largest_unresolved['Category']}: {int(largest_unresolved['Planned'])} planned",
            )
        )

    completed_categories = category_performance[category_performance["Completed Planned Minutes"] > 0]
    if not completed_categories.empty:
        largest_completed = completed_categories.sort_values(
            ["Completed Planned Minutes", "Category"],
            ascending=[False, True],
        ).iloc[0]
        insights.append(
            (
                "Most completed focus",
                f"{largest_completed['Category']}: {_format_minutes(largest_completed['Completed Planned Minutes'])}",
            )
        )

    return insights


def render_activity_overview(analytics: dict) -> None:
    if not analytics["has_quests"]:
        render_empty_state(
            "No checklist data yet",
            "Plan quests in Quest Planner and update them in Monthly Checklist to generate analytics.",
        )
        return

    overview_tab, patterns_tab, categories_tab, routines_tab = st.tabs(
        ["Overview", "Patterns", "Categories", "Routines"]
    )
    with overview_tab:
        date_range = analytics["date_range"]
        render_section_title(
            "Period overview",
            f"{date_range['start_date']:%d %b %Y} to {date_range['end_date']:%d %b %Y}.",
        )
        render_period_summary(analytics["period_summary"], analytics["previous_period_summary"])

        render_section_title("Plan and completion", "Scheduled workload compared with completed planned time each week.")
        render_planned_vs_completed_by_week(analytics["planned_vs_completed_by_week"])

        render_section_title("XP trend", "XP awarded for completed check-ins in the selected period.")
        render_xp_by_day(analytics["xp_by_day"])
        render_insights(analytics)

    with patterns_tab:
        status_col, consistency_col = st.columns(2)
        with status_col:
            render_section_title("Performance breakdown", "How quest days are distributed by state.")
            render_status_chart(analytics["quests_by_status"])
        with consistency_col:
            render_section_title("Consistency", "Resolved check-in outcomes grouped by weekday.")
            render_weekday_chart(analytics["completion_rate_by_weekday"])

    with categories_tab:
        render_section_title("Category performance", "Planned and completed planned time, outcomes, and XP by category.")
        render_category_performance(analytics["category_performance"])

    with routines_tab:
        render_section_title("Routine performance", "Completion, misses, and recent routine history in the selected period.")
        render_routine_performance(analytics["routine_performance"])


apply_theme()
render_page_header(
    "Review progress",
    "Habit Analytics",
    "See current consistency, time allocation, and recent habit performance.",
)

init_db()
today = date.today()
filters = render_analytics_filters(get_categories(), today)
analytics = get_habit_analytics_data(today=today, **filters)
render_activity_overview(analytics)

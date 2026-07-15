import sys
from pathlib import Path
from html import escape

import pandas as pd
import plotly.express as px
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.database.db import init_db
from src.services.analytics_service import (
    get_goal_analytics_summary,
    get_goal_completed_minutes_by_week,
    get_goal_progress_dataset,
    get_goal_session_status_dataset,
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


GOAL_STATUS_FILTERS = {
    "Active + Completed": ("Active", "Completed"),
    "Active": ("Active",),
    "Completed": ("Completed",),
    "Archived": ("Archived",),
    "All": "All",
}


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
            render_metric_card(label, value)


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


def _format_optional_minutes(minutes: int) -> str:
    return _format_minutes(minutes) if int(minutes or 0) > 0 else "No time target"


def _format_percent(value: float) -> str:
    rounded = round(float(value), 1)
    if rounded.is_integer():
        return f"{int(rounded)}%"
    return f"{rounded}%"


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


def render_activity_overview(analytics: dict) -> None:
    if not analytics["has_quests"]:
        render_empty_state(
            "No checklist data yet",
            "Plan quests in Quest Planner and update them in Monthly Checklist to generate analytics.",
        )
        return

    render_section_title("Weekly Pulse", "Compact performance readout for the current week.")
    render_weekly_pulse(analytics["weekly_pulse"])

    render_section_title("Trend Overview", "Time-based progress from completed quest-day XP.")
    with st.container():
        render_xp_by_day(analytics["xp_by_day"])

    render_section_title("Performance Breakdown", "How quest days are distributed by state and category.")
    status_col, category_col = st.columns(2, gap="large")
    with status_col:
        with st.container():
            render_status_chart(analytics["quests_by_status"])
    with category_col:
        with st.container():
            render_category_chart(analytics["quests_by_category"])

    render_section_title("Consistency & Time", "Checklist consistency and planned workload by category.")
    weekday_col, minutes_col = st.columns(2, gap="large")
    with weekday_col:
        with st.container():
            render_weekday_chart(analytics["completion_rate_by_weekday"])
    with minutes_col:
        with st.container():
            render_estimated_minutes_chart(analytics["estimated_minutes_by_category"])

    render_insights(analytics)


def render_goal_analytics_filters() -> tuple[tuple[str, ...] | str, int | None]:
    filter_cols = st.columns(2, gap="medium")
    with filter_cols[0]:
        status_label = st.selectbox(
            "Goal status",
            list(GOAL_STATUS_FILTERS.keys()),
            index=0,
            key="goal_analytics_status_filter",
        )
    categories = get_categories()
    category_options = {"All categories": None} | {category.name: category.id for category in categories}
    with filter_cols[1]:
        category_label = st.selectbox(
            "Category",
            list(category_options.keys()),
            key="goal_analytics_category_filter",
        )
    st.caption("Default view includes Active and Completed goals. Archived goals are excluded unless selected.")
    return GOAL_STATUS_FILTERS[status_label], category_options[category_label]


def render_goal_kpis(summary: dict) -> None:
    metric_cols = st.columns(6)
    metrics = (
        ("Active Goals", summary["active_goals"]),
        ("Completed Goals", summary["completed_goals"]),
        ("Planned Effort", _format_minutes(summary["planned_effort_minutes"])),
        ("Completed Effort", _format_minutes(summary["completed_effort_minutes"])),
        ("Overall Progress", _format_percent(summary["overall_progress_percent"])),
        ("Goal XP Earned", f"{summary['goal_xp_earned']} XP"),
    )
    for column, (label, value) in zip(metric_cols, metrics):
        with column:
            render_metric_card(label, value)


def render_compact_goal_empty_state(title: str, message: str) -> None:
    st.markdown(
        f"""
        <div class="hq-empty-compact">
            <strong>{escape(title)}</strong>
            <span>{escape(message)}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_single_goal_progress_card(goal_row: dict) -> None:
    progress = max(0, min(float(goal_row["Progress Percent"]), 100))
    target = goal_row["Target Date"]
    target_label = target.isoformat() if hasattr(target, "isoformat") else "No target date"
    planned_minutes = int(goal_row["Planned Minutes"])
    progress_effort_label = (
        f"{_format_minutes(int(goal_row['Completed Minutes']))} / {_format_optional_minutes(planned_minutes)}"
    )
    sessions = (
        f"{int(goal_row['Completed Sessions'])} completed / "
        f"{int(goal_row['Planned Sessions'])} planned"
        + (f" / {int(goal_row['Skipped Sessions'])} skipped" if int(goal_row["Skipped Sessions"]) else "")
        + (f" / {int(goal_row['Failed Sessions'])} failed" if int(goal_row["Failed Sessions"]) else "")
    )
    st.markdown(
        f"""
        <div class="hq-progress-card">
            <div class="hq-progress-card-header">
                <div>
                    <div class="hq-progress-title">{escape(str(goal_row["Goal"]))}</div>
                    <div class="hq-progress-meta">
                        {escape(str(goal_row["Status"]))} / {escape(str(goal_row["Category"]))} / Target: {escape(target_label)}
                    </div>
                </div>
                <div>
                    <div class="hq-progress-value">
                        {escape(progress_effort_label)}
                    </div>
                    <div class="hq-progress-caption">{escape(_format_percent(progress))} complete</div>
                </div>
            </div>
            <div class="hq-progress-track">
                <div class="hq-progress-fill" style="width: {progress:.2f}%"></div>
            </div>
            <div class="hq-progress-footer">
                <div class="hq-progress-caption">
                    {escape(_format_minutes(int(goal_row["Remaining Minutes"])))} remaining / {int(goal_row["Earned XP"])} XP earned
                </div>
                <div>
                    <span class="hq-progress-pill">{escape(sessions)}</span>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_goal_progress_visual(goal_table: pd.DataFrame, progress_dataset: pd.DataFrame) -> None:
    if len(goal_table) == 1:
        render_single_goal_progress_card(goal_table.iloc[0].to_dict())
        return

    if progress_dataset.empty:
        render_compact_goal_empty_state(
            "No goals match these filters",
            "Adjust the status or category filters to include goals.",
        )
        return

    chart_data = progress_dataset.melt(
        id_vars=["Goal", "Progress Percent"],
        value_vars=["Completed Effort", "Remaining Effort"],
        var_name="Effort",
        value_name="Minutes",
    )
    tokens = get_theme_tokens()
    remaining_color = "rgba(8, 145, 178, 0.28)" if tokens["mode"] == "Light" else "rgba(148, 163, 184, 0.28)"
    chart_data["Label"] = chart_data["Minutes"].map(lambda value: _format_minutes(int(value)) if int(value) else "")
    fig = px.bar(
        chart_data,
        x="Minutes",
        y="Goal",
        color="Effort",
        orientation="h",
        title="Goal Progress by Effort",
        color_discrete_map={
            "Completed Effort": tokens["accent"],
            "Remaining Effort": remaining_color,
        },
        hover_data={"Progress Percent": ":.1f", "Minutes": True},
        text="Label",
    )
    fig.update_layout(xaxis_title="Minutes", yaxis_title="Goal", barmode="stack", height=360)
    fig.update_yaxes(categoryorder="array", categoryarray=progress_dataset["Goal"].tolist()[::-1])
    fig.update_traces(texttemplate="%{text}", textposition="inside", insidetextanchor="middle", cliponaxis=False)
    st.plotly_chart(style_chart(fig, height=360), width="stretch", config={"displayModeBar": False})


def render_goal_xp_chart(goal_table: pd.DataFrame) -> None:
    if len(goal_table) < 2:
        return
    if goal_table.empty or int(goal_table["Earned XP"].sum()) == 0:
        render_compact_goal_empty_state(
            "No goal XP earned yet",
            "Complete linked goal sessions to see XP by goal.",
        )
        return

    tokens = get_theme_tokens()
    chart_data = goal_table.sort_values(["Earned XP", "Goal"], ascending=[False, True])
    fig = px.bar(
        chart_data,
        x="Earned XP",
        y="Goal",
        orientation="h",
        title="XP Earned by Goal",
        color_discrete_sequence=[tokens["accent"]],
        text="Earned XP",
    )
    fig.update_layout(xaxis_title="XP Earned", yaxis_title="Goal", showlegend=False, height=320)
    fig.update_yaxes(categoryorder="array", categoryarray=chart_data["Goal"].tolist()[::-1])
    fig.update_traces(texttemplate="%{text} XP", textposition="outside", cliponaxis=False)
    st.plotly_chart(style_chart(fig, height=320), width="stretch", config={"displayModeBar": False})


def render_goal_session_outcomes(status_dataset: pd.DataFrame) -> None:
    if status_dataset.empty or int(status_dataset["Count"].sum()) == 0:
        render_compact_goal_empty_state(
            "No linked sessions yet",
            "Add sessions from Quest Planner to see goal outcomes.",
        )
        return

    tokens = get_theme_tokens()
    chart_data = (
        status_dataset.groupby("Status", as_index=False)["Count"]
        .sum()
        .query("Count > 0")
        .reset_index(drop=True)
    )
    if chart_data.empty:
        render_compact_goal_empty_state(
            "No linked sessions yet",
            "Add sessions from Quest Planner to see goal outcomes.",
        )
        return

    fig = px.pie(
        chart_data,
        names="Status",
        values="Count",
        hole=0.56,
        color="Status",
        title="Session Outcomes",
        category_orders={"Status": ["Completed", "Planned", "Skipped", "Failed"]},
        color_discrete_map={
            "Completed": tokens["success"],
            "Planned": tokens["info"],
            "Skipped": tokens["warning"],
            "Failed": tokens["danger"],
        },
    )
    fig.update_traces(textinfo="percent+label", hovertemplate="%{label}: %{value} sessions (%{percent})<extra></extra>")
    fig.update_layout(height=320, legend_title_text="Status")
    st.plotly_chart(style_chart(fig, height=320), width="stretch", config={"displayModeBar": False})


def render_goal_effort_trend(trend_dataset: pd.DataFrame) -> None:
    if trend_dataset.empty or trend_dataset["Week"].nunique() < 2:
        render_compact_goal_empty_state(
            "Not enough weekly data yet",
            "Complete linked sessions in at least two different weeks to display a trend.",
        )
        return

    tokens = get_theme_tokens()
    chart_data = trend_dataset.copy()
    chart_data["Week Label"] = chart_data["Week"].map(
        lambda value: f"{value:%b} {value.day}" if hasattr(value, "strftime") else str(value)
    )
    chart_data["Completed Hours"] = chart_data["Completed Minutes"] / 60
    fig = px.line(
        chart_data,
        x="Week Label",
        y="Completed Hours",
        title="Completed Goal Effort by Week",
        markers=True,
        color_discrete_sequence=[tokens["accent"]],
    )
    max_hours = max(float(chart_data["Completed Hours"].max()), 1)
    fig.update_layout(
        xaxis_title="Week",
        yaxis_title="Completed Hours",
        showlegend=False,
        height=320,
        yaxis_range=[0, max_hours * 1.18],
    )
    fig.update_traces(line={"width": 3}, marker={"size": 8})
    st.plotly_chart(style_chart(fig, height=320), width="stretch", config={"displayModeBar": False})


def render_goal_comparison_table(goal_table: pd.DataFrame) -> None:
    if len(goal_table) < 2:
        return

    display_table = goal_table.copy()
    display_table["Progress"] = display_table["Progress Percent"].map(_format_percent)
    display_table["Completed / Planned"] = (
        display_table["Completed Minutes"].map(_format_minutes)
        + " / "
        + display_table["Planned Minutes"].map(_format_optional_minutes)
    )
    display_table["Sessions"] = display_table.apply(
        lambda row: (
            f"{int(row['Completed Sessions'])} completed"
            + (f"  {int(row['Planned Sessions'])} planned" if int(row["Planned Sessions"]) else "")
            + (f"  {int(row['Skipped Sessions'])} skipped" if int(row["Skipped Sessions"]) else "")
            + (f"  {int(row['Failed Sessions'])} failed" if int(row["Failed Sessions"]) else "")
        ),
        axis=1,
    )
    display_table["Target Date"] = display_table["Target Date"].map(
        lambda value: value.isoformat() if hasattr(value, "isoformat") else "No target"
    )
    columns = [
        "Goal",
        "Status",
        "Progress",
        "Completed / Planned",
        "Earned XP",
        "Sessions",
        "Target Date",
    ]
    header_cells = "".join(f"<th>{escape(column)}</th>" for column in columns)
    body_rows = "\n".join(
        "<tr>"
        + "".join(f"<td>{escape(str(row[column]))}</td>" for column in columns)
        + "</tr>"
        for row in display_table[columns].to_dict("records")
    )
    with st.expander("View goal comparison table", expanded=False):
        st.markdown(
            f"""
            <div class="hq-table-scroll">
                <table class="hq-data-table">
                    <thead><tr>{header_cells}</tr></thead>
                    <tbody>{body_rows}</tbody>
                </table>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_goal_analytics() -> None:
    render_section_title(
        "Goal Analytics",
        "Long-term goal progress derived from linked one-time quest sessions and check-in XP.",
    )
    statuses, category_id = render_goal_analytics_filters()
    summary = get_goal_analytics_summary(statuses=statuses, category_id=category_id)

    if not summary["has_goals"]:
        render_empty_state(
            "No goals yet",
            "Create goals in Quest Planner > Goals / Projects, then add linked sessions to track analytics.",
        )
        return

    render_goal_kpis(summary)

    progress_dataset = get_goal_progress_dataset(statuses=statuses, category_id=category_id)
    status_dataset = get_goal_session_status_dataset(statuses=statuses, category_id=category_id)
    trend_dataset = get_goal_completed_minutes_by_week(statuses=statuses, category_id=category_id)
    goal_table = summary["goal_table"]

    render_section_title("Progress", "Completed and remaining effort for the selected goals.")

    if len(goal_table) == 1:
        layout_col, outcome_col = st.columns([0.6, 0.4], gap="large")
        with layout_col:
            render_goal_progress_visual(goal_table, progress_dataset)
        with outcome_col:
            render_goal_session_outcomes(status_dataset)
    else:
        render_goal_progress_visual(goal_table, progress_dataset)

    if summary["linked_sessions_count"] == 0:
        render_compact_goal_empty_state(
            "No linked sessions yet",
            "Goal KPIs and details are visible. Add sessions in Quest Planner to populate XP, outcomes, and weekly trend charts.",
        )
    else:
        if len(goal_table) > 1:
            chart_col, status_col = st.columns(2, gap="large")
            with chart_col:
                render_goal_xp_chart(goal_table)
            with status_col:
                render_goal_session_outcomes(status_dataset)

        render_section_title("Effort Trend", "Completed linked goal effort grouped by check-in week.")
        render_goal_effort_trend(trend_dataset)

    render_goal_comparison_table(goal_table)


apply_theme()
render_page_header(
    "Analytics",
    "Habit Analytics",
    "Review quest trends, goal progress, consistency, categories, and weekly performance.",
)

init_db()
analytics = get_habit_analytics_data()

activity_tab, goals_tab = st.tabs(["Activity Overview", "Goals / Projects"])

with activity_tab:
    render_activity_overview(analytics)

with goals_tab:
    render_goal_analytics()

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time

import streamlit as st

WEEKDAY_OPTIONS = {
    "Monday": 0,
    "Tuesday": 1,
    "Wednesday": 2,
    "Thursday": 3,
    "Friday": 4,
    "Saturday": 5,
    "Sunday": 6,
}
RECURRENCE_PRESETS = {
    "Every day": [0, 1, 2, 3, 4, 5, 6],
    "Weekdays": [0, 1, 2, 3, 4],
}


@dataclass(frozen=True)
class PlanDraft:
    """Validated values from the unified planning form."""

    title: str
    category_id: int
    planned_date: date
    start_time: time
    end_time: time
    estimated_minutes: int
    notes: str
    goal_id: int | None
    weekdays: list[int] | None = None
    end_date: date | None = None

    @property
    def is_recurring(self) -> bool:
        return self.weekdays is not None


def render_plan_form(
    category_options: dict[str, int],
    active_goals: list,
    selected_date: date,
    goal_title_by_id: dict[int, str],
    key_prefix: str = "plan",
) -> PlanDraft | None:
    """Render one planning form for one-time tasks, routines, and project sessions."""
    project_options = [None] + [goal.id for goal in active_goals]
    project_selection_disabled = st.session_state.get(f"{key_prefix}_type") == "Repeat"
    selected_goal_id = st.selectbox(
        "Project",
        project_options,
        format_func=lambda value: "No project" if value is None else goal_title_by_id[value],
        key=f"{key_prefix}_goal",
        disabled=project_selection_disabled,
    )

    if hasattr(st, "segmented_control"):
        planning_type = st.segmented_control(
            "Schedule",
            ["One time", "Repeat"],
            default="One time",
            key=f"{key_prefix}_type",
        )
    else:
        planning_type = st.radio(
            "Schedule",
            ["One time", "Repeat"],
            horizontal=True,
            key=f"{key_prefix}_type",
        )
    planning_type = planning_type or "One time"
    is_recurring = planning_type == "Repeat"
    goal_id = selected_goal_id if not is_recurring else None
    selected_goal = next((goal for goal in active_goals if goal.id == goal_id), None)
    category_names_by_id = {category_id: name for name, category_id in category_options.items()}
    locked_category_name = (
        category_names_by_id.get(selected_goal.category_id)
        if selected_goal is not None and selected_goal.category_id is not None
        else None
    )

    if locked_category_name is not None:
        st.session_state[f"{key_prefix}_category"] = locked_category_name
        category_name = st.selectbox(
            "Category",
            list(category_options.keys()),
            key=f"{key_prefix}_category",
            disabled=True,
        )
    else:
        category_name = st.selectbox(
            "Category",
            list(category_options.keys()),
            key=f"{key_prefix}_category",
        )
    category_id = category_options[category_name]

    if selected_goal is None:
        title = st.text_input("Title", placeholder="What do you want to plan?", key=f"{key_prefix}_title")
    else:
        title = goal_title_by_id[selected_goal.id]
        st.session_state[f"{key_prefix}_title"] = title
        st.text_input("Title", key=f"{key_prefix}_title", disabled=True)

    st.divider()
    planned_date = st.date_input(
        "Starts on" if is_recurring else "Date",
        value=selected_date,
        key=f"{key_prefix}_date",
    )
    time_col, end_time_col = st.columns(2)
    with time_col:
        start_time = st.time_input(
            "Start time",
            value=time(9, 0),
            step=300,
            key=f"{key_prefix}_start_time",
        )
    with end_time_col:
        end_time = st.time_input(
            "End time",
            value=time(10, 0),
            step=300,
            key=f"{key_prefix}_end_time",
        )

    estimated_minutes = int(
        (datetime.combine(planned_date, end_time) - datetime.combine(planned_date, start_time)).total_seconds() // 60
    )
    has_valid_time_range = estimated_minutes > 0
    if not has_valid_time_range:
        st.error("End time must be after start time.")

    weekdays = None
    end_date = None
    if is_recurring:
        recurrence_preset = st.radio(
            "Repeat",
            ["Every day", "Weekdays", "Custom days"],
            horizontal=True,
            key=f"{key_prefix}_recurrence",
        )
        if recurrence_preset == "Custom days":
            selected_weekday_names = st.multiselect(
                "Days",
                list(WEEKDAY_OPTIONS.keys()),
                default=["Monday", "Wednesday", "Friday"],
                key=f"{key_prefix}_weekdays",
            )
            weekdays = [WEEKDAY_OPTIONS[name] for name in selected_weekday_names]
        else:
            weekdays = RECURRENCE_PRESETS[recurrence_preset]

        set_end_date = st.checkbox("Set an end date", key=f"{key_prefix}_set_end_date")
        if set_end_date:
            end_date = st.date_input(
                "Ends on",
                value=planned_date,
                min_value=planned_date,
                key=f"{key_prefix}_end_date",
            )
    notes = st.text_area(
        "Notes (optional)",
        height=72,
        placeholder="Optional details",
        key=f"{key_prefix}_notes",
    )

    action_label = "Create routine" if is_recurring else "Add to plan"
    if not st.button(action_label, type="primary", use_container_width=True, key=f"{key_prefix}_submit"):
        return None

    if not title.strip() and goal_id is None:
        st.error("A title is required.")
        return None
    if not has_valid_time_range:
        return None
    if is_recurring and not weekdays:
        st.error("Choose at least one day for the routine.")
        return None

    return PlanDraft(
        title=title,
        category_id=category_id,
        planned_date=planned_date,
        start_time=start_time,
        end_time=end_time,
        estimated_minutes=estimated_minutes,
        notes=notes,
        goal_id=goal_id,
        weekdays=weekdays,
        end_date=end_date,
    )

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, time

import streamlit as st

from app.components.scheduling import duration_crosses_midnight, end_at_for_duration


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


@dataclass(frozen=True)
class NewProjectDraft:
    """Minimal project input created while planning a task."""

    title: str
    category_id: int
    planned_total_minutes: int
    target_end_date: date | None


@dataclass(frozen=True)
class PlanFormResult:
    """One submitted action from the shared planning surface."""

    plan: PlanDraft | None = None
    new_project: NewProjectDraft | None = None


def render_plan_form(
    category_options: dict[str, int],
    active_goals: list,
    selected_date: date,
    goal_title_by_id: dict[int, str],
    key_prefix: str = "plan",
) -> PlanFormResult | None:
    """Render one planning form for one-time quests, routines, and goal sessions."""
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

    category_name = st.selectbox(
        "Category",
        list(category_options.keys()),
        key=f"{key_prefix}_category",
    )
    category_id = category_options[category_name]

    goal_id = None
    if not is_recurring:
        with st.expander(
            "Project session",
            expanded=bool(st.session_state.get(f"{key_prefix}_creating_project")),
        ):
            goal_options = [None] + [goal.id for goal in active_goals]
            goal_id = st.selectbox(
                "Project",
                goal_options,
                format_func=lambda value: "No project" if value is None else goal_title_by_id[value],
                key=f"{key_prefix}_goal",
            )
            if st.button("New project", use_container_width=True, key=f"{key_prefix}_new_project"):
                st.session_state[f"{key_prefix}_creating_project"] = True

            if st.session_state.get(f"{key_prefix}_creating_project"):
                project_title = st.text_input(
                    "Project name",
                    placeholder="Portfolio project",
                    key=f"{key_prefix}_new_project_title",
                )
                planned_total_minutes = int(
                    st.number_input(
                        "Target effort (min)",
                        min_value=0,
                        value=0,
                        step=30,
                        key=f"{key_prefix}_new_project_effort",
                    )
                )
                set_target_date = st.checkbox(
                    "Set a target date",
                    key=f"{key_prefix}_new_project_set_target_date",
                )
                target_end_date = (
                    st.date_input(
                        "Target date",
                        value=selected_date,
                        min_value=selected_date,
                        key=f"{key_prefix}_new_project_target_date",
                    )
                    if set_target_date
                    else None
                )
                project_actions = st.columns(2)
                with project_actions[0]:
                    if st.button("Save project", type="primary", use_container_width=True, key=f"{key_prefix}_save_project"):
                        if not project_title.strip():
                            st.error("A project name is required.")
                        else:
                            return PlanFormResult(
                                new_project=NewProjectDraft(
                                    title=project_title,
                                    category_id=category_id,
                                    planned_total_minutes=planned_total_minutes,
                                    target_end_date=target_end_date,
                                )
                            )
                with project_actions[1]:
                    if st.button("Cancel", use_container_width=True, key=f"{key_prefix}_cancel_project"):
                        st.session_state.pop(f"{key_prefix}_creating_project", None)
                        st.rerun()

    if goal_id is None:
        title = st.text_input("Title", placeholder="What do you want to plan?", key=f"{key_prefix}_title")
    else:
        title = goal_title_by_id[goal_id]
        st.caption(f"A new session will be added to {title}.")

    with st.expander("Schedule details", expanded=is_recurring):
        date_col, time_col, duration_col = st.columns([0.42, 0.29, 0.29])
        with date_col:
            planned_date = st.date_input(
                "Starts on" if is_recurring else "Date",
                value=selected_date,
                key=f"{key_prefix}_date",
            )
        with time_col:
            start_time = st.time_input(
                "Start time",
                value=time(9, 0),
                step=300,
                key=f"{key_prefix}_start_time",
            )
        with duration_col:
            estimated_minutes = int(
                st.number_input(
                    "Duration (min)",
                    min_value=5,
                    max_value=720,
                    value=60,
                    step=5,
                    key=f"{key_prefix}_duration",
                )
            )

    end_at = end_at_for_duration(planned_date, start_time, estimated_minutes)
    end_time = end_at.time()
    if duration_crosses_midnight(planned_date, start_time, estimated_minutes):
        st.error("The selected duration cannot cross midnight.")

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
    with st.expander("Notes", expanded=False):
        notes = st.text_area(
            "Notes",
            height=64,
            placeholder="Optional details",
            key=f"{key_prefix}_notes",
            label_visibility="collapsed",
        )

    action_label = "Create routine" if is_recurring else "Add to plan"
    if not st.button(action_label, type="primary", use_container_width=True, key=f"{key_prefix}_submit"):
        return None

    if not title.strip() and goal_id is None:
        st.error("A title is required.")
        return None
    if duration_crosses_midnight(planned_date, start_time, estimated_minutes):
        return None
    if is_recurring and not weekdays:
        st.error("Choose at least one day for the routine.")
        return None

    return PlanFormResult(
        plan=PlanDraft(
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
    )

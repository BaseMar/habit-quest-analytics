from __future__ import annotations

from calendar import month_name
from datetime import date, time
from html import escape

import streamlit as st

from app.components.plan_form import WEEKDAY_OPTIONS
from app.components.scheduling import duration_crosses_midnight, end_at_for_duration
from src.services.goal_service import (
    archive_goal,
    complete_goal,
    delete_goal_if_unused,
    get_goal_history_summary,
    get_goal_progress,
    list_goals,
    reopen_goal,
)
from src.services.goal_session_planner_service import (
    build_goal_session_plan_preview,
    get_goal_session_planning_summary,
    plan_goal_sessions,
)
from src.services.recurring_habit_service import (
    delete_recurring_habit_if_unused,
    deserialize_weekdays,
    generate_all_recurring_habits_for_month,
    get_recurring_habit_history_summary,
    list_recurring_habits,
    set_recurring_habit_active,
    stop_recurring_habit,
    update_recurring_habit_template,
)
from src.ui import render_empty_state, render_section_title


def render_project_routine_workspace(category_options: dict[str, int], selected_date: date) -> None:
    """Render management of existing projects, routines, and routine generation."""
    projects_tab, routines_tab = st.tabs(["Projects", "Routines"])

    with projects_tab:
        st.caption("Review one project at a time, then manage its sessions and lifecycle in the same workspace.")
        render_section_title("Projects", "Track project progress and schedule linked one-time sessions.")
        _render_project_workspace(category_options, selected_date)

    with routines_tab:
        st.caption("Create routines in Planner, then manage templates and future planned days here.")
        render_section_title("Routine schedule", "Generate missing days only for the month you select.")
        _render_routine_generation_controls()
        st.divider()
        render_section_title("Routines", "Edit a template or change its lifecycle without changing history.")
        _render_recurring_habits(category_options)


def _render_project_workspace(category_options: dict[str, int], selected_date: date) -> None:
    status_message = st.session_state.pop("goal_status_message", None)
    if status_message:
        st.success(status_message)

    goals = list_goals()
    if not goals:
        render_empty_state(
            "No projects yet",
            "Create a project from Add to plan, then link one-time sessions to track progress.",
        )
        return

    category_names_by_id = {category_id: name for name, category_id in category_options.items()}
    goals_by_id = {goal.id: goal for goal in goals}
    selected_goal_id = st.session_state.get("project_workspace_id")
    if selected_goal_id not in goals_by_id:
        active_goal = next((goal for goal in goals if goal.status == "Active"), goals[0])
        st.session_state["project_workspace_id"] = active_goal.id

    selected_goal_id = st.selectbox(
        "Project",
        list(goals_by_id),
        format_func=lambda goal_id: f"{goals_by_id[goal_id].title} / {goals_by_id[goal_id].status}",
        key="project_workspace_id",
    )
    goal = goals_by_id[selected_goal_id]
    progress = get_goal_progress(goal.id)
    history = get_goal_history_summary(goal.id)
    _render_project_progress_card(goal, progress, category_names_by_id)

    if goal.status == "Active":
        _render_goal_session_planner(goal, selected_date)
    else:
        st.caption("Only active projects can receive new sessions.")
    _render_goal_lifecycle(goal, history)


def _render_project_progress_card(goal, progress: dict, category_names_by_id: dict[int, str]) -> None:
    progress_percent = float(progress["progress_percent"])
    progress_label = _format_percent(progress_percent)
    progress_width = max(0, min(100, progress_percent))
    planned_label = _format_minutes(progress["planned_total_minutes"]) if int(progress["planned_total_minutes"]) > 0 else "No time target"
    xp_label = (
        f"{int(progress['earned_xp'])} / {int(progress['expected_total_xp'])} XP earned"
        if int(progress["expected_total_xp"]) > 0
        else f"{int(progress['earned_xp'])} XP earned"
    )
    category = category_names_by_id.get(goal.category_id, "Uncategorized")
    target = goal.target_end_date.isoformat() if goal.target_end_date else "No target date"
    skipped_failed = progress["skipped_sessions_count"] + progress["failed_sessions_count"]

    st.markdown(
        f"""
        <div class="hq-progress-card">
            <div class="hq-progress-card-header">
                <div>
                    <div class="hq-progress-title">{escape(str(goal.title))}</div>
                    <div class="hq-progress-meta">{escape(str(goal.status))} / {escape(str(category))} / Target: {escape(str(target))}</div>
                </div>
                <div>
                    <div class="hq-progress-value">{_format_minutes(progress['completed_minutes'])} / {escape(planned_label)}</div>
                    <div class="hq-progress-caption">{progress_label} complete</div>
                </div>
            </div>
            <div class="hq-progress-track"><div class="hq-progress-fill" style="width: {progress_width:.2f}%"></div></div>
            <div class="hq-progress-footer">
                <div class="hq-progress-caption">{escape(xp_label)}</div>
                <div>
                    <span class="hq-progress-pill">{int(progress['completed_sessions_count'])} completed</span>
                    <span class="hq-progress-pill">{int(progress['planned_sessions_count'])} planned</span>
                    <span class="hq-progress-pill">{int(skipped_failed)} skipped/failed</span>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_goal_session_planner(goal, selected_date: date) -> None:
    planner_key = f"goal_session_planner_{goal.id}"
    preview_key = f"{planner_key}_preview"
    config_key = f"{planner_key}_config"

    with st.expander("Plan Multiple Sessions", expanded=False):
        session_duration_minutes = int(st.number_input("Session duration (min)", min_value=5, max_value=720, value=120, step=5, key=f"{planner_key}_duration"))
        try:
            planning_summary = get_goal_session_planning_summary(goal.id, session_duration_minutes=session_duration_minutes)
        except ValueError as error:
            st.error(str(error))
            return

        metric_cols = st.columns(4)
        metric_cols[0].metric("Goal Effort", _format_minutes(planning_summary["planned_total_minutes"]))
        metric_cols[1].metric("Completed", _format_minutes(planning_summary["completed_minutes"]))
        metric_cols[2].metric("Already Planned", _format_minutes(planning_summary["currently_planned_minutes"]))
        metric_cols[3].metric("Still To Schedule", _format_minutes(planning_summary["effort_to_schedule_minutes"]))

        start_date = st.date_input("Start Date", value=max(selected_date, goal.start_date or date.min), key=f"{planner_key}_start_date")
        selected_weekday_names = st.multiselect("Selected Weekdays", list(WEEKDAY_OPTIONS), default=["Monday", "Wednesday", "Friday"], key=f"{planner_key}_weekdays")
        selected_weekdays = [WEEKDAY_OPTIONS[name] for name in selected_weekday_names]
        planned_start_time = st.time_input("Start Time", value=time(18, 0), step=300, key=f"{planner_key}_start_time")
        use_planning_end_date = st.checkbox("Use Planning End Date", value=goal.target_end_date is not None, key=f"{planner_key}_use_end_date")
        planning_end_date = None
        if use_planning_end_date:
            end_date_kwargs = {"max_value": goal.target_end_date} if goal.target_end_date is not None else {}
            default_end_date = goal.target_end_date or start_date
            planning_end_date = st.date_input("Planning End Date", value=default_end_date if default_end_date < start_date else max(start_date, default_end_date), key=f"{planner_key}_end_date", **end_date_kwargs)
        allow_short_final_session = st.checkbox("Allow shorter final session", value=True, key=f"{planner_key}_allow_short_final")
        current_config = {
            "goal_id": goal.id,
            "session_duration_minutes": session_duration_minutes,
            "start_date": start_date,
            "selected_weekdays": tuple(selected_weekdays),
            "planned_start_time": planned_start_time,
            "target_end_date": planning_end_date,
            "allow_short_final_session": allow_short_final_session,
        }
        preview = st.session_state.get(preview_key)
        if preview is not None and st.session_state.get(config_key) != current_config:
            preview = None
            st.session_state.pop(preview_key, None)
            st.session_state.pop(config_key, None)

        preview_disabled = goal.category_id is None or not selected_weekdays or planning_summary["effort_to_schedule_minutes"] <= 0
        if goal.category_id is None:
            st.error("This goal needs a category before sessions can be planned.")
        if planning_summary["effort_to_schedule_minutes"] <= 0:
            st.info("This goal has no unscheduled effort right now.")
        if st.button("Preview", use_container_width=True, key=f"{planner_key}_preview_button", disabled=preview_disabled):
            try:
                preview = build_goal_session_plan_preview(**current_config)
            except ValueError as error:
                st.error(str(error))
            else:
                st.session_state[preview_key] = preview
                st.session_state[config_key] = current_config
        if preview is None:
            return

        if preview["blocked_reason"]:
            st.warning(preview["blocked_reason"])
        _render_goal_session_plan_preview(preview)
        if preview["remaining_unallocated_minutes"] > 0:
            st.warning(f"{_format_minutes(preview['remaining_unallocated_minutes'])} will remain unallocated.")

        confirmed = st.checkbox("Confirm bulk session generation", key=f"{planner_key}_confirm_generate", disabled=not preview["date_range_complete"] or preview["total_sessions"] == 0)
        if st.button("Generate Planned Sessions", type="primary", use_container_width=True, key=f"{planner_key}_generate_button", disabled=not confirmed or not preview["date_range_complete"] or preview["total_sessions"] == 0):
            try:
                summary = plan_goal_sessions(**st.session_state[config_key])
            except ValueError as error:
                st.error(str(error))
            else:
                st.session_state.pop(preview_key, None)
                st.session_state.pop(config_key, None)
                st.session_state["goal_status_message"] = f"Generated {summary['created_count']} planned goal sessions."
                st.rerun()


def _render_goal_session_plan_preview(preview: dict) -> None:
    rows = [
        {"Session": f"Session {row['session_number']}", "Date": row["date"].strftime("%b %d"), "Time": f"{row['start_time']:%H:%M}-{row['end_time']:%H:%M}", "Duration": _format_minutes(row["duration_minutes"]), "Expected XP": f"{row['expected_quest_xp']} XP"}
        for row in preview["sessions"]
    ]
    if rows:
        st.table(rows)
    else:
        st.info("No sessions are proposed for this preview.")
    total_cols = st.columns(3)
    total_cols[0].metric("Total Sessions", preview["total_sessions"])
    total_cols[1].metric("Scheduled Effort", _format_minutes(preview["total_planned_minutes"]))
    total_cols[2].metric("Remaining Unallocated", _format_minutes(preview["remaining_unallocated_minutes"]))


def _render_goal_lifecycle(goal, history: dict) -> None:
    with st.expander("Project lifecycle", expanded=False):
        can_delete = history["linked_quests_count"] == 0
        if goal.status == "Active":
            complete_col, archive_col = st.columns(2)
            with complete_col:
                if st.button("Mark complete", use_container_width=True, key=f"goal_complete_{goal.id}"):
                    complete_goal(goal.id)
                    st.session_state["goal_status_message"] = "Project marked as completed."
                    st.rerun()
            with archive_col:
                if st.button("Archive project", use_container_width=True, key=f"goal_archive_{goal.id}"):
                    archive_goal(goal.id)
                    st.session_state["goal_status_message"] = "Project archived. Linked session history was preserved."
                    st.rerun()
        elif goal.status == "Completed":
            reopen_col, archive_col = st.columns(2)
            with reopen_col:
                if st.button("Reopen project", type="primary", use_container_width=True, key=f"goal_reopen_completed_{goal.id}"):
                    reopen_goal(goal.id)
                    st.session_state["goal_status_message"] = "Project reopened."
                    st.rerun()
            with archive_col:
                if st.button("Archive project", use_container_width=True, key=f"goal_archive_{goal.id}"):
                    archive_goal(goal.id)
                    st.session_state["goal_status_message"] = "Project archived. Linked session history was preserved."
                    st.rerun()
        elif st.button("Reopen project", type="primary", use_container_width=True, key=f"goal_reopen_{goal.id}"):
            reopen_goal(goal.id)
            st.session_state["goal_status_message"] = "Project reopened."
            st.rerun()

        if can_delete:
            st.caption("This project has no linked sessions and can be deleted.")
            confirmed = st.checkbox("Confirm delete project", key=f"goal_confirm_delete_{goal.id}")
            if st.button("Delete project", use_container_width=True, disabled=not confirmed, key=f"goal_delete_{goal.id}"):
                delete_goal_if_unused(goal.id)
                st.session_state["goal_status_message"] = "Unused project deleted."
                st.rerun()
        else:
            st.caption("Projects with linked sessions keep their history and cannot be deleted.")


def _render_routine_generation_controls() -> None:
    today = date.today()
    summary = st.session_state.pop("routine_generation_summary", None)
    if summary:
        st.success(f"Generated {summary['total_generated']} planned days. {summary['total_skipped_existing']} already existed.")
    month_col, year_col, generate_col = st.columns([0.42, 0.23, 0.35], vertical_alignment="bottom")
    with month_col:
        selected_month_name = st.selectbox("Month", list(month_name)[1:], index=today.month - 1, key="routine_generation_month")
        selected_month = list(month_name).index(selected_month_name)
    with year_col:
        selected_year = int(st.number_input("Year", min_value=2000, max_value=2100, value=today.year, step=1, key="routine_generation_year"))
    with generate_col:
        if st.button("Generate missing routines", use_container_width=True, key="generate_routines_for_management_month"):
            try:
                summary = generate_all_recurring_habits_for_month(selected_year, selected_month)
            except ValueError as error:
                st.error(str(error))
            else:
                st.session_state["routine_generation_summary"] = summary
                st.rerun()
    st.caption("Generation adds only missing days for active routines and never changes existing history.")


def _render_recurring_habits(category_options: dict[str, int]) -> None:
    category_names_by_id = {category_id: name for name, category_id in category_options.items()}
    status_message = st.session_state.pop("recurring_habit_status_message", None)
    if status_message:
        st.success(status_message)
    habits = list_recurring_habits()
    if not habits:
        render_empty_state("No routines yet.", "Create a repeating routine from Add to plan in the Planner.")
        return

    _render_recurring_habit_template_list(habits, category_names_by_id)
    st.divider()
    selected_habit = st.selectbox("Manage recurring habit", habits, format_func=lambda habit: f"{habit.title} | {_format_habit_pattern(habit)} | {_active_label(habit)}", key="recurring_habit_manage")
    history_summary = get_recurring_habit_history_summary(selected_habit.id)
    st.markdown(
        f"""
        <div class="hq-meta-pills">
            <span class="hq-meta-pill"><strong>{int(history_summary['generated_instances_count'])}</strong> scheduled days</span>
            <span class="hq-meta-pill"><strong>{int(history_summary['planned_count'])}</strong> planned</span>
            <span class="hq-meta-pill"><strong>{int(history_summary['completed_count'])}</strong> completed</span>
            <span class="hq-meta-pill"><strong>{int(history_summary['skipped_count'])}</strong> skipped</span>
            <span class="hq-meta-pill"><strong>{int(history_summary['failed_count'])}</strong> failed</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button("Edit routine", use_container_width=True, key=f"edit_recurring_habit_{selected_habit.id}"):
        st.session_state["editing_recurring_habit_id"] = selected_habit.id
        st.rerun()
    if st.session_state.get("editing_recurring_habit_id") == selected_habit.id:
        _render_recurring_habit_editor(selected_habit, category_options)
    _render_recurring_habit_lifecycle(selected_habit, history_summary)


def _render_recurring_habit_editor(habit, category_options: dict[str, int]) -> None:
    category_names = list(category_options)
    current_category_name = next((name for name, category_id in category_options.items() if category_id == habit.category_id), category_names[0])
    current_weekdays = deserialize_weekdays(habit.weekdays)
    current_recurrence = "Every day" if current_weekdays == [0, 1, 2, 3, 4, 5, 6] else "Weekdays" if current_weekdays == [0, 1, 2, 3, 4] else "Custom days"
    key_prefix = f"recurring_habit_editor_{habit.id}"
    with st.expander("Edit routine", expanded=True):
        st.caption("Changes apply to future routine days. Existing scheduled days and history stay unchanged.")
        title = st.text_input("Title", value=habit.title, key=f"{key_prefix}_title")
        category_name = st.selectbox("Category", category_names, index=category_names.index(current_category_name), key=f"{key_prefix}_category")
        start_date = st.date_input("Starts on", value=habit.start_date, key=f"{key_prefix}_start_date")
        estimated_minutes = int(st.number_input("Duration (min)", min_value=5, max_value=720, value=int(habit.estimated_minutes), step=5, key=f"{key_prefix}_duration"))
        set_time = st.checkbox("Set a time", value=habit.planned_start_time is not None, key=f"{key_prefix}_set_time")
        planned_start_time = None
        planned_end_time = None
        if set_time:
            planned_start_time = st.time_input("Start time", value=habit.planned_start_time or time(9, 0), step=300, key=f"{key_prefix}_start_time")
            planned_end_time = end_at_for_duration(start_date, planned_start_time, estimated_minutes).time()
            if duration_crosses_midnight(start_date, planned_start_time, estimated_minutes):
                st.error("The selected duration cannot cross midnight.")
        recurrence = st.radio("Repeat", ["Every day", "Weekdays", "Custom days"], index=["Every day", "Weekdays", "Custom days"].index(current_recurrence), horizontal=True, key=f"{key_prefix}_recurrence")
        if recurrence == "Custom days":
            selected_weekday_names = st.multiselect("Days", list(WEEKDAY_OPTIONS), default=[name for name, value in WEEKDAY_OPTIONS.items() if value in current_weekdays], key=f"{key_prefix}_weekdays")
            weekdays = [WEEKDAY_OPTIONS[name] for name in selected_weekday_names]
        elif recurrence == "Every day":
            weekdays = [0, 1, 2, 3, 4, 5, 6]
        else:
            weekdays = [0, 1, 2, 3, 4]
        set_end_date = st.checkbox("Set an end date", value=habit.end_date is not None, key=f"{key_prefix}_set_end_date")
        end_date = st.date_input("Ends on", value=habit.end_date or start_date, key=f"{key_prefix}_end_date") if set_end_date else None
        notes = st.text_area("Notes", value=habit.description or "", height=64, key=f"{key_prefix}_notes")
        save_col, cancel_col = st.columns(2)
        with save_col:
            save_clicked = st.button("Save routine", type="primary", use_container_width=True, key=f"{key_prefix}_save")
        with cancel_col:
            cancel_clicked = st.button("Cancel", use_container_width=True, key=f"{key_prefix}_cancel")
        if cancel_clicked:
            st.session_state.pop("editing_recurring_habit_id", None)
            st.rerun()
        if not save_clicked:
            return
        if set_time and duration_crosses_midnight(start_date, planned_start_time, estimated_minutes):
            st.error("The selected duration cannot cross midnight.")
        elif not weekdays:
            st.error("Choose at least one day for the routine.")
        else:
            try:
                update_recurring_habit_template(habit.id, title=title, category_id=category_options[category_name], estimated_minutes=estimated_minutes, recurrence_type="selected_weekdays", weekdays=weekdays, start_date=start_date, end_date=end_date, description=notes, planned_start_time=planned_start_time, planned_end_time=planned_end_time)
            except ValueError as error:
                st.error(str(error))
            else:
                st.session_state.pop("editing_recurring_habit_id", None)
                st.session_state["recurring_habit_status_message"] = "Routine updated. Existing scheduled days were not changed."
                st.rerun()


def _render_recurring_habit_lifecycle(habit, history_summary: dict) -> None:
    key_prefix = f"recurring_habit_lifecycle_{habit.id}"
    with st.expander("Routine lifecycle", expanded=False):
        if history_summary["generated_instances_count"] == 0:
            st.caption("This routine has no scheduled days and can be deleted.")
            confirmed = st.checkbox("Confirm delete routine", key=f"{key_prefix}_confirm_delete")
            if st.button("Delete routine", use_container_width=True, disabled=not confirmed, key=f"{key_prefix}_delete"):
                summary = delete_recurring_habit_if_unused(habit.id)
                st.session_state["recurring_habit_status_message"] = "Routine deleted." if summary["deleted"] else "Routine was not deleted because scheduled history exists."
                st.rerun()
            return
        removable_count = int(history_summary["removable_future_planned_count"])
        if habit.is_active:
            st.caption("Stopping prevents new generation. Existing history is always preserved.")
            remove_future_planned = st.checkbox(f"Also remove {removable_count} future unresolved planned days", value=False, disabled=removable_count == 0, key=f"{key_prefix}_remove_future")
            confirmed = st.checkbox("Confirm stop routine", key=f"{key_prefix}_confirm_stop")
            if st.button("Stop routine", type="primary", use_container_width=True, disabled=not confirmed, key=f"{key_prefix}_stop"):
                summary = stop_recurring_habit(habit.id, remove_future_planned=remove_future_planned)
                removed_count = summary["removed_instances_count"]
                st.session_state["recurring_habit_status_message"] = f"Routine stopped and {removed_count} future planned days removed." if remove_future_planned else "Routine stopped. Existing scheduled days were kept."
                st.rerun()
            return
        st.caption("This routine is stopped and will not generate new days.")
        if st.button("Resume routine", type="primary", use_container_width=True, key=f"{key_prefix}_resume"):
            set_recurring_habit_active(habit.id, True)
            st.session_state["recurring_habit_status_message"] = "Routine resumed."
            st.rerun()
        if removable_count:
            st.caption(f"{removable_count} future unresolved planned days remain.")
            confirmed = st.checkbox("Confirm remove remaining future planned days", key=f"{key_prefix}_confirm_cleanup")
            if st.button("Remove future planned days", use_container_width=True, disabled=not confirmed, key=f"{key_prefix}_cleanup"):
                summary = stop_recurring_habit(habit.id, remove_future_planned=True)
                st.session_state["recurring_habit_status_message"] = f"Removed {summary['removed_instances_count']} future planned days."
                st.rerun()


def _render_recurring_habit_template_list(habits: list, category_names_by_id: dict[int, str]) -> None:
    rows = []
    for habit in habits:
        category = category_names_by_id.get(habit.category_id, "Uncategorized")
        end_date = habit.end_date.isoformat() if habit.end_date else "No end"
        rows.append(
            "<div class=\"hq-list-row\">"
            f"<div><div class=\"hq-list-title\">{escape(str(habit.title))}</div>"
            f"<div class=\"hq-list-meta\">{escape(str(category))} / {escape(_format_habit_pattern(habit))} / {escape(_format_habit_time_window(habit))}</div></div>"
            f"<div class=\"hq-list-meta\">{escape(_active_label(habit))} / Ends: {escape(end_date)}</div>"
            "</div>"
        )
    st.markdown(f'<div class="hq-list-panel">{"".join(rows)}</div>', unsafe_allow_html=True)


def _format_habit_pattern(habit) -> str:
    try:
        weekdays = deserialize_weekdays(habit.weekdays)
    except ValueError:
        return "Custom"
    if weekdays == [0, 1, 2, 3, 4, 5, 6]:
        return "Every day"
    if weekdays == [0, 1, 2, 3, 4]:
        return "Weekdays"
    weekday_names = [name[:3] for name, value in WEEKDAY_OPTIONS.items() if value in weekdays]
    return ", ".join(weekday_names) if weekday_names else "Custom"


def _active_label(habit) -> str:
    return "Active" if habit.is_active else "Inactive"


def _format_habit_time_window(habit) -> str:
    if habit.planned_start_time is not None and habit.planned_end_time is not None:
        return f"{habit.planned_start_time:%H:%M} - {habit.planned_end_time:%H:%M}"
    return "All day"


def _format_minutes(minutes: int) -> str:
    if minutes <= 0:
        return "0 min"
    hours, remainder = divmod(minutes, 60)
    if hours and remainder:
        return f"{hours}h {remainder}m"
    if hours:
        return f"{hours}h"
    return f"{remainder} min"


def _format_percent(value: float) -> str:
    rounded = round(value, 1)
    return f"{int(rounded)}%" if rounded.is_integer() else f"{rounded}%"

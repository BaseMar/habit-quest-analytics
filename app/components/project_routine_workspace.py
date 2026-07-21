from __future__ import annotations

from calendar import month_name
from datetime import date, datetime, time, timedelta
from html import escape

import plotly.express as px
import streamlit as st

from app.components.plan_form import WEEKDAY_OPTIONS
from src.services.goal_service import (
    archive_goal,
    complete_goal,
    create_goal,
    delete_goal_if_unused,
    get_goal_completion_forecast,
    get_goal_history_summary,
    get_goal_progress,
    list_goals,
    reopen_goal,
    update_goal,
)
from src.services.analytics_service import get_goal_analytics_summary, get_goal_progress_dataset
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
from src.ui import get_theme_tokens, render_empty_state, render_metric_card, render_section_title, style_chart


def render_project_routine_workspace(category_options: dict[str, int], selected_date: date) -> None:
    """Render management of existing projects, routines, and routine generation."""
    projects_tab, routines_tab = st.tabs(["Projects", "Routines"])

    with projects_tab:
        render_section_title("Projects", "Create, review, and maintain the projects behind your planned sessions.")
        _render_project_workspace(category_options, selected_date)
        with st.expander("Portfolio overview", expanded=False):
            _render_project_comparison()

    with routines_tab:
        heading_col, action_col = st.columns([0.72, 0.28], vertical_alignment="bottom")
        with heading_col:
            render_section_title("Routines", "Edit a template or change its lifecycle without changing history.")
        with action_col:
            generator_open = st.session_state.get("routine_generation_open", False)
            if st.button(
                "Hide generator" if generator_open else "Generate days",
                use_container_width=True,
                key="toggle_routine_generation",
            ):
                st.session_state["routine_generation_open"] = not generator_open
                st.rerun()
        if st.session_state.get("routine_generation_open", False):
            _render_routine_generation_controls()
        _render_recurring_habits(category_options)


def _render_project_workspace(category_options: dict[str, int], selected_date: date) -> None:
    status_message = st.session_state.pop("goal_status_message", None)
    if status_message:
        st.success(status_message)

    if st.button("New project", type="primary", key="create_project"):
        st.session_state.pop("editing_project_id", None)
        st.session_state["creating_project"] = True
        st.rerun()

    if st.session_state.get("creating_project"):
        _render_project_editor(None, category_options, selected_date)
        return

    goals = list_goals()
    if not goals:
        render_empty_state(
            "No projects yet",
            "Create a project here, then link its sessions in Planner.",
        )
        return

    category_names_by_id = {category_id: name for name, category_id in category_options.items()}
    goals_by_id = {goal.id: goal for goal in goals}
    selected_goal_id = st.session_state.get("project_workspace_id")
    if selected_goal_id not in goals_by_id:
        active_goal = next((goal for goal in goals if goal.status == "Active"), goals[0])
        st.session_state["project_workspace_id"] = active_goal.id

    project_col, edit_col, options_col = st.columns([0.58, 0.21, 0.21], vertical_alignment="bottom")
    with project_col:
        selected_goal_id = st.selectbox(
            "Project",
            list(goals_by_id),
            format_func=lambda goal_id: f"{goals_by_id[goal_id].title} / {goals_by_id[goal_id].status}",
            key="project_workspace_id",
        )
    with edit_col:
        if st.button("Edit project", use_container_width=True, key=f"edit_project_{selected_goal_id}"):
            st.session_state["editing_project_id"] = selected_goal_id
            st.rerun()

    goal = goals_by_id[selected_goal_id]
    history = get_goal_history_summary(goal.id)
    with options_col:
        with st.popover("Project actions", use_container_width=True):
            _render_goal_lifecycle(goal, history)

    if st.session_state.get("editing_project_id") == goal.id:
        _render_project_editor(goal, category_options, selected_date)
        return

    progress = get_goal_progress(goal.id)
    _render_project_progress_card(goal, progress, category_names_by_id)
    _render_goal_completion_forecast(goal)

    if goal.status == "Active":
        _render_goal_session_planner(goal, selected_date)
    else:
        st.caption("Only active projects can receive new sessions.")


def _render_project_editor(goal, category_options: dict[str, int], selected_date: date) -> None:
    is_new_project = goal is None
    key_prefix = "create_project_form" if is_new_project else f"edit_project_form_{goal.id}"
    category_names = list(category_options)
    default_category_name = (
        next((name for name, category_id in category_options.items() if category_id == goal.category_id), category_names[0])
        if goal is not None
        else category_names[0]
    )
    default_start_date = goal.start_date if goal is not None and goal.start_date is not None else selected_date
    default_target_date = goal.target_end_date if goal is not None else None

    st.divider()
    st.subheader("Create project" if is_new_project else "Edit project")
    with st.container(border=True):
        title = st.text_input(
            "Project name",
            value="" if is_new_project else goal.title,
            placeholder="Portfolio project",
            key=f"{key_prefix}_title",
        )
        category_name = st.selectbox(
            "Category",
            category_names,
            index=category_names.index(default_category_name),
            key=f"{key_prefix}_category",
        )
        description = st.text_area(
            "Description (optional)",
            value="" if is_new_project else goal.description or "",
            height=72,
            key=f"{key_prefix}_description",
        )
        planned_total_minutes = int(
            st.number_input(
                "Target effort (min)",
                min_value=0,
                value=0 if is_new_project else int(goal.planned_total_minutes or 0),
                step=30,
                key=f"{key_prefix}_effort",
            )
        )
        set_start_date = st.checkbox(
            "Set a start date",
            value=True if is_new_project else goal.start_date is not None,
            key=f"{key_prefix}_set_start_date",
        )
        start_date = (
            st.date_input("Start date", value=default_start_date, key=f"{key_prefix}_start_date")
            if set_start_date
            else None
        )
        set_target_date = st.checkbox(
            "Set a target date",
            value=default_target_date is not None,
            key=f"{key_prefix}_set_target_date",
        )
        target_date_kwargs = {"min_value": start_date} if start_date is not None else {}
        target_end_date = (
            st.date_input(
                "Target date",
                value=max(default_target_date or start_date or selected_date, start_date or selected_date),
                key=f"{key_prefix}_target_date",
                **target_date_kwargs,
            )
            if set_target_date
            else None
        )
        save_col, cancel_col = st.columns(2)
        with save_col:
            save_clicked = st.button(
                "Create project" if is_new_project else "Save project",
                type="primary",
                use_container_width=True,
                key=f"{key_prefix}_save",
            )
        with cancel_col:
            cancel_clicked = st.button("Cancel", use_container_width=True, key=f"{key_prefix}_cancel")

    if cancel_clicked:
        st.session_state.pop("creating_project", None)
        st.session_state.pop("editing_project_id", None)
        st.rerun()
    if not save_clicked:
        return

    try:
        if is_new_project:
            saved_goal = create_goal(
                title=title,
                description=description,
                category_id=category_options[category_name],
                planned_total_minutes=planned_total_minutes,
                start_date=start_date,
                target_end_date=target_end_date,
            )
            message = "Project created. Add its sessions in Planner."
        else:
            saved_goal = update_goal(
                goal.id,
                title=title,
                description=description,
                category_id=category_options[category_name],
                planned_total_minutes=planned_total_minutes,
                start_date=start_date,
                target_end_date=target_end_date,
            )
            message = "Project updated."
    except ValueError as error:
        st.error(str(error))
        return

    st.session_state.pop("creating_project", None)
    st.session_state.pop("editing_project_id", None)
    st.session_state["project_workspace_id"] = saved_goal.id
    st.session_state["goal_status_message"] = message
    st.rerun()


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


def _render_goal_completion_forecast(goal) -> None:
    if (goal.planned_total_minutes or 0) <= 0 or goal.target_end_date is None:
        return

    forecast = get_goal_completion_forecast(goal.id)
    st.subheader("Completion forecast")
    if not forecast["available"]:
        st.info(forecast["reason"])
        return

    projected_date = forecast["projected_completion_date"]
    target_date = forecast["target_end_date"]
    metric_cols = st.columns(3)
    with metric_cols[0]:
        render_metric_card("Projected completion", projected_date.strftime("%b %d, %Y"))
    with metric_cols[1]:
        render_metric_card("Target date", target_date.strftime("%b %d, %Y"))
    with metric_cols[2]:
        render_metric_card("Required daily effort", _format_minutes(forecast["required_daily_minutes"]))

    pace = _format_minutes(round(forecast["daily_completed_minutes"]))
    target_status = "On track" if forecast["on_track"] else "At risk"
    st.caption(
        f"{target_status}. Current pace: {pace} per observed day across "
        f"{forecast['observed_completed_days']} day(s)."
    )


def _render_project_comparison() -> None:
    goals = list_goals()
    if len(goals) < 2:
        render_empty_state(
            "Not enough projects to compare",
            "Create at least two active or completed projects to view a portfolio comparison.",
        )
        return

    summary = get_goal_analytics_summary(statuses=("Active", "Completed"))
    if summary["included_goals_count"] < 2:
        render_empty_state(
            "No comparable projects",
            "Keep at least two projects active or completed to compare their progress.",
        )
        return

    metric_cols = st.columns(4)
    metrics = (
        ("Active", summary["active_goals"]),
        ("Completed effort", _format_minutes(summary["completed_effort_minutes"])),
        ("Remaining effort", _format_minutes(summary["remaining_effort_minutes"])),
        ("Overall progress", _format_percent(summary["overall_progress_percent"])),
    )
    for column, (label, value) in zip(metric_cols, metrics):
        with column:
            render_metric_card(label, value)

    progress_dataset = get_goal_progress_dataset(statuses=("Active", "Completed"))
    if progress_dataset.empty:
        return

    chart_data = progress_dataset.melt(
        id_vars=["Goal", "Progress Percent"],
        value_vars=["Completed Effort", "Remaining Effort"],
        var_name="Effort",
        value_name="Minutes",
    )
    tokens = get_theme_tokens()
    remaining_color = "#CBD5E1" if tokens["mode"] == "Light" else "#475569"
    fig = px.bar(
        chart_data,
        x="Minutes",
        y="Goal",
        color="Effort",
        orientation="h",
        color_discrete_map={
            "Completed Effort": tokens["accent"],
            "Remaining Effort": remaining_color,
        },
        hover_data={"Progress Percent": ":.1f", "Minutes": True},
    )
    fig.update_layout(xaxis_title="Minutes", yaxis_title="Project", barmode="stack", height=340)
    fig.update_yaxes(categoryorder="array", categoryarray=progress_dataset["Goal"].tolist()[::-1])
    st.plotly_chart(style_chart(fig, height=340), width="stretch", config={"displayModeBar": False})


def _render_goal_session_planner(goal, selected_date: date) -> None:
    planner_key = f"goal_session_planner_{goal.id}"
    preview_key = f"{planner_key}_preview"
    config_key = f"{planner_key}_config"

    with st.expander("Plan sessions", expanded=False):
        session_duration_minutes = int(st.number_input("Session duration (min)", min_value=5, max_value=720, value=120, step=5, key=f"{planner_key}_duration"))
        try:
            planning_summary = get_goal_session_planning_summary(goal.id, session_duration_minutes=session_duration_minutes)
        except ValueError as error:
            st.error(str(error))
            return

        first_metric_row = st.columns(2)
        first_metric_row[0].metric("Goal Effort", _format_minutes(planning_summary["planned_total_minutes"]))
        first_metric_row[1].metric("Completed", _format_minutes(planning_summary["completed_minutes"]))
        second_metric_row = st.columns(2)
        second_metric_row[0].metric("Already Planned", _format_minutes(planning_summary["currently_planned_minutes"]))
        second_metric_row[1].metric("Still To Schedule", _format_minutes(planning_summary["effort_to_schedule_minutes"]))

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
        if planning_summary["planned_total_minutes"] <= 0:
            st.info(
                "Set a target effort to use automatic session planning. "
                "You can still add individual project sessions manually in Planner."
            )
        elif planning_summary["effort_to_schedule_minutes"] <= 0:
            st.info("This project has no unscheduled effort right now.")
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
    with st.container():
        st.caption("Project lifecycle")
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
        set_time = st.checkbox(
            "Set a time",
            value=habit.planned_start_time is not None and habit.planned_end_time is not None,
            key=f"{key_prefix}_set_time",
        )
        planned_start_time = None
        planned_end_time = None
        if set_time:
            default_start_time = habit.planned_start_time or time(9, 0)
            default_end_time = habit.planned_end_time or (
                datetime.combine(start_date, default_start_time) + timedelta(minutes=int(habit.estimated_minutes))
            ).time()
            start_col, end_col = st.columns(2)
            with start_col:
                planned_start_time = st.time_input(
                    "Start time",
                    value=default_start_time,
                    step=300,
                    key=f"{key_prefix}_start_time",
                )
            with end_col:
                planned_end_time = st.time_input(
                    "End time",
                    value=default_end_time,
                    step=300,
                    key=f"{key_prefix}_end_time",
                )
            estimated_minutes = int(
                (datetime.combine(start_date, planned_end_time) - datetime.combine(start_date, planned_start_time)).total_seconds()
                // 60
            )
            has_valid_time_range = estimated_minutes > 0
            if not has_valid_time_range:
                st.error("End time must be after start time.")
        else:
            estimated_minutes = int(
                st.number_input(
                    "Duration (min)",
                    min_value=5,
                    max_value=720,
                    value=int(habit.estimated_minutes),
                    step=5,
                    key=f"{key_prefix}_duration",
                )
            )
            has_valid_time_range = True
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
        if not has_valid_time_range:
            st.error("End time must be after start time.")
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

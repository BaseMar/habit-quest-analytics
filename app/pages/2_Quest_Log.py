from calendar import month_name
from datetime import date, datetime, time, timedelta
import hashlib
from html import escape
import sys
from pathlib import Path

import streamlit as st

try:
    from streamlit_calendar import calendar
except ImportError:
    calendar = None

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.components.plan_form import WEEKDAY_OPTIONS, render_plan_form
from src.database.db import init_db
from src.database.seed import ensure_default_categories
from src.services.checklist_service import (
    get_month_checklist,
    is_checklist_cell_editable,
    update_checkin_status,
    update_checklist_cell_status,
)
from src.services.goal_service import (
    archive_goal,
    complete_goal,
    create_goal,
    delete_goal_if_unused,
    get_goal_history_summary,
    get_goal_progress,
    list_active_goals,
    list_goals,
    reopen_goal,
)
from src.services.goal_session_planner_service import (
    build_goal_session_plan_preview,
    get_goal_session_planning_summary,
    plan_goal_sessions,
)
from src.services.quest_service import (
    create_scheduled_quest,
    delete_one_time_quest_if_unresolved,
    get_categories,
    get_quests_for_calendar,
    get_quests_for_day,
    update_one_time_quest_if_unresolved,
)
from src.services.recurring_habit_service import (
    create_recurring_habit,
    delete_recurring_habit_if_unused,
    delete_recurring_generated_occurrence_if_unresolved,
    deserialize_weekdays,
    generate_all_recurring_habits_for_month,
    generate_recurring_habit_for_month,
    get_recurring_habit_history_summary,
    list_recurring_habits,
    set_recurring_habit_active,
    stop_recurring_habit,
    update_recurring_habit_template,
)
from src.ui import apply_theme, get_theme_tokens, render_empty_state, render_page_header, render_section_title


CHECKLIST_STATUS_LABELS = {
    None: "Empty / not scheduled",
    "Planned": "Planned",
    "Completed": "Completed",
    "Skipped": "Skipped",
    "Failed": "Failed",
}
CHECKLIST_STATUS_MARKERS = {
    None: "",
    "Planned": "P",
    "Completed": "C",
    "Skipped": "S",
    "Failed": "F",
}
CALENDAR_VIEW_OPTIONS = {
    "Month": {"view": "dayGridMonth", "height": 650, "content_height": 590},
    "Week": {"view": "timeGridWeek", "height": 760, "content_height": 700},
    "Day": {"view": "timeGridDay", "height": 720, "content_height": 660},
    "List": {"view": "listWeek", "height": 420, "content_height": 360},
}


def render_calendar(calendar_events: list[dict], selected_date: date) -> None:
    if calendar is None:
        st.info("Calendar component unavailable. Use the selected date field below to plan quests.")
        return

    tokens = get_theme_tokens()
    if "quest_calendar_view" not in st.session_state:
        st.session_state["quest_calendar_view"] = "Week"

    if hasattr(st, "segmented_control"):
        selected_view_label = st.segmented_control(
            "Calendar view",
            list(CALENDAR_VIEW_OPTIONS.keys()),
            key="quest_calendar_view",
            label_visibility="collapsed",
        )
    else:
        selected_view_label = st.radio(
            "Calendar view",
            list(CALENDAR_VIEW_OPTIONS.keys()),
            horizontal=True,
            key="quest_calendar_view",
            label_visibility="collapsed",
        )
    selected_view_label = selected_view_label or "Week"
    view_config = CALENDAR_VIEW_OPTIONS[selected_view_label]
    calendar_options = {
        "initialView": view_config["view"],
        "initialDate": selected_date.isoformat(),
        "firstDay": 1,
        "selectable": True,
        "editable": False,
        "eventResizableFromStart": False,
        "height": view_config["height"],
        "contentHeight": view_config["content_height"],
        "expandRows": False,
        "handleWindowResize": True,
        "stickyHeaderDates": True,
        "headerToolbar": {
            "left": "prev,next today",
            "center": "title",
            "right": "",
        },
        "nowIndicator": True,
        "slotMinTime": "06:00:00",
        "slotMaxTime": "24:00:00",
        "slotDuration": "00:30:00",
        "slotLabelInterval": "01:00:00",
        "slotEventOverlap": False,
        "displayEventEnd": True,
        "eventDisplay": "block",
        "eventMinHeight": 26,
        "eventShortHeight": 24,
        "eventTimeFormat": {
            "hour": "2-digit",
            "minute": "2-digit",
            "hour12": False,
        },
    }
    custom_css = """
        html,
        body,
        #root {
            background: var(--hq-surface) !important;
            min-height: 0 !important;
        }
        .fc {
            --fc-page-bg-color: transparent;
            --fc-neutral-bg-color: var(--hq-muted-surface);
            --fc-border-color: var(--hq-border);
            --fc-today-bg-color: var(--hq-accent-soft);
            background: var(--hq-surface);
            color: var(--hq-text-primary);
            height: var(--hq-calendar-height) !important;
            min-height: 0 !important;
            overflow: hidden;
            width: 100%;
        }
        .fc .fc-view-harness {
            background: var(--hq-surface);
            height: var(--hq-calendar-content-height) !important;
            min-height: 0 !important;
        }
        .fc .fc-scroller,
        .fc .fc-scroller-liquid {
            background: var(--hq-surface);
            scrollbar-color: var(--hq-accent) var(--hq-muted-surface);
            scrollbar-width: thin;
        }
        .fc .fc-timegrid-body,
        .fc .fc-timegrid-body table,
        .fc .fc-timegrid-slots table {
            width: 100% !important;
        }
        .fc-theme-standard .fc-scrollgrid,
        .fc-theme-standard td,
        .fc-theme-standard th {
            border-color: var(--hq-border);
        }
        .fc-theme-standard .fc-scrollgrid {
            background: var(--hq-surface);
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 6px 18px rgba(15, 23, 42, 0.06);
        }
        .fc .fc-scrollgrid-section > td,
        .fc .fc-scrollgrid-section-liquid > td {
            background: var(--hq-surface);
        }
        .fc .fc-col-header-cell {
            background: var(--hq-surface-elevated);
        }
        .fc .fc-col-header-cell-cushion,
        .fc .fc-timegrid-axis-cushion,
        .fc .fc-timegrid-slot-label-cushion {
            color: var(--hq-text-secondary);
            font-size: 0.78rem;
            font-weight: 700;
            text-decoration: none;
        }
        .fc .fc-toolbar-title {
            color: var(--hq-text-primary);
            font-size: 1.15rem;
            font-weight: 740;
        }
        .fc .fc-toolbar {
            gap: 0.75rem;
            margin-bottom: 0.85rem;
        }
        .fc .fc-button-primary {
            background: var(--hq-surface);
            border-color: var(--hq-border);
            border-radius: 6px;
            box-shadow: none;
            color: var(--hq-text-primary);
            font-size: 0.82rem;
            font-weight: 750;
            padding: 0.42rem 0.62rem;
            transition: background-color 160ms ease, border-color 160ms ease, transform 160ms ease;
        }
        .fc .fc-button-primary:hover {
            background: var(--hq-surface-elevated);
            border-color: var(--hq-accent-border);
            transform: none;
        }
        .fc .fc-button-primary:not(:disabled).fc-button-active,
        .fc .fc-button-primary:not(:disabled):active {
            background: var(--hq-accent);
            border-color: var(--hq-accent-border);
            color: white;
        }
        .fc .fc-timegrid-slot {
            height: 2rem;
            background: var(--hq-surface);
        }
        .fc .fc-daygrid-day,
        .fc .fc-timegrid-col {
            background: var(--hq-surface);
        }
        .fc .fc-daygrid-day.fc-day-today,
        .fc .fc-timegrid-col.fc-day-today {
            background: var(--hq-accent-soft);
        }
        .fc .fc-timegrid-now-indicator-line {
            border-color: var(--hq-warning);
        }
        .fc .fc-timegrid-now-indicator-arrow {
            border-color: var(--hq-warning);
            border-bottom-color: transparent;
            border-top-color: transparent;
        }
        .fc .fc-event {
            border-radius: 6px;
            box-shadow: none;
            padding: 0.12rem 0.18rem;
        }
        .fc .fc-timegrid-event {
            min-height: 26px;
        }
        .fc .fc-event-main {
            color: white;
            overflow: hidden;
            padding: 0.12rem 0.2rem;
        }
        .fc .fc-event-time {
            color: rgba(255, 255, 255, 0.78);
            font-size: 0.72rem;
            font-weight: 700;
            line-height: 1.15;
            margin-bottom: 0.05rem;
            white-space: nowrap;
        }
        .fc .fc-event-title {
            color: white;
            font-size: 0.78rem;
            font-weight: 800;
            line-height: 1.18;
            overflow-wrap: anywhere;
        }
        .fc .fc-daygrid-event {
            padding: 0.14rem 0.3rem;
        }
        .fc .fc-daygrid-day-frame {
            min-height: 88px;
        }
        .fc .fc-list,
        .fc .fc-list-day-cushion {
            background: var(--hq-surface);
        }
        .fc .fc-list-empty {
            background: var(--hq-surface);
            color: var(--hq-text-secondary);
        }
        .fc .fc-list-event:hover td {
            background: var(--hq-surface-elevated);
        }
    """
    custom_css = (
        custom_css.replace("var(--hq-calendar-height)", f"{view_config['height']}px")
        .replace("var(--hq-calendar-content-height)", f"{view_config['content_height']}px")
        .replace("var(--hq-muted-surface)", tokens["muted_surface"])
        .replace("var(--hq-accent-soft)", tokens["accent_soft"])
        .replace("var(--hq-border)", tokens["border"])
        .replace("var(--hq-text-primary)", tokens["text_primary"])
        .replace("var(--hq-text-secondary)", tokens["text_secondary"])
        .replace("var(--hq-accent-border)", tokens["accent_border"])
        .replace("var(--hq-surface-elevated)", tokens["surface_elevated"])
        .replace("var(--hq-surface)", tokens["surface"])
        .replace("var(--hq-accent)", tokens["accent"])
        .replace("var(--hq-warning)", tokens["warning"])
    )

    try:
        calendar_state = calendar(
            events=calendar_events,
            options=calendar_options,
            custom_css=custom_css,
            key=(
                f"quest_calendar_{tokens['mode']}_{tokens['accent_name']}_"
                f"{selected_view_label}_{_calendar_events_signature(calendar_events)}"
            ),
        )
    except Exception as error:
        st.warning(f"Calendar component could not render. Use the selected date field below. Details: {error}")
        return

    clicked_date = _extract_calendar_date(calendar_state)
    if clicked_date and clicked_date != st.session_state["selected_date"]:
        st.session_state["selected_date"] = clicked_date
        st.rerun()


def render_schedule_list(quests: list, planned_date: date) -> None:
    if not quests:
        st.info("No quests planned for this day.")
        return

    for quest in quests:
        status = _display_status(quest)
        row_cols = st.columns([0.16, 0.44, 0.12, 0.28], vertical_alignment="center")
        with row_cols[0]:
            st.caption(_format_time_range(quest))
        with row_cols[1]:
            st.write(f"**{quest.title}**")
            st.caption(f"{_category_name(quest)} / {status}")
            if status == "Planned" and quest.recurring_habit_instance is None:
                if st.button("Edit", key=f"edit_day_quest_{quest.id}"):
                    st.session_state["editing_day_quest_id"] = quest.id
                    st.rerun()
        with row_cols[2]:
            st.caption(f"{int(quest.xp_reward or 0)} XP")
        with row_cols[3]:
            if status == "Planned":
                complete_col, skip_col, fail_col = st.columns(3)
                actions = (
                    (complete_col, "Complete", "Completed", "primary"),
                    (skip_col, "Skip", "Skipped", "secondary"),
                    (fail_col, "Fail", "Failed", "secondary"),
                )
            else:
                reset_col, _, _ = st.columns(3)
                actions = ((reset_col, "Reset", "Planned", "secondary"),)

            for action_col, label, next_status, button_type in actions:
                with action_col:
                    if st.button(
                        label,
                        type=button_type,
                        use_container_width=True,
                        key=f"day_status_{quest.id}_{planned_date.isoformat()}_{next_status}",
                    ):
                        try:
                            update_checkin_status(quest.id, planned_date, next_status)
                        except ValueError as error:
                            st.error(str(error))
                        else:
                            st.session_state["daily_status_message"] = (
                                f"{label} saved for {quest.title}."
                            )
                            st.rerun()
        st.divider()


def render_day_item_editor(quests: list, category_options: dict[str, int]) -> None:
    editing_quest_id = st.session_state.get("editing_day_quest_id")
    if editing_quest_id is None:
        return

    quest = next((item for item in quests if item.id == editing_quest_id), None)
    if quest is None:
        st.session_state.pop("editing_day_quest_id", None)
        return

    with st.expander("Edit planned item", expanded=True):
        if _display_status(quest) != "Planned":
            st.warning("Only unresolved planned items can be edited.")
            return

        is_goal_session = quest.goal_id is not None
        if is_goal_session:
            st.caption(f"Session title is generated from its project: {quest.title}")
            title = quest.title
        else:
            title = st.text_input("Title", value=quest.title, key=f"edit_quest_title_{quest.id}")

        category_names = list(category_options)
        current_category_index = next(
            (index for index, name in enumerate(category_names) if category_options[name] == quest.category_id),
            0,
        )
        category_name = st.selectbox(
            "Category",
            category_names,
            index=current_category_index,
            key=f"edit_quest_category_{quest.id}",
        )

        planned_date = st.date_input(
            "Date",
            value=quest.due_date or st.session_state["selected_date"],
            key=f"edit_quest_date_{quest.id}",
        )
        start_time = (quest.planned_start_at or datetime.combine(planned_date, time(9, 0))).time()
        duration_minutes = _quest_duration_minutes(quest) or 60
        time_col, duration_col = st.columns(2)
        with time_col:
            start_time = st.time_input(
                "Start time",
                value=start_time,
                step=300,
                key=f"edit_quest_start_time_{quest.id}",
            )
        with duration_col:
            duration_minutes = int(
                st.number_input(
                    "Duration (min)",
                    min_value=5,
                    max_value=720,
                    value=duration_minutes,
                    step=5,
                    key=f"edit_quest_duration_{quest.id}",
                )
            )

        end_at = datetime.combine(planned_date, start_time) + timedelta(minutes=duration_minutes)
        if end_at.date() != planned_date:
            st.error("The selected duration cannot cross midnight.")

        notes = st.text_area(
            "Notes",
            value=quest.description or "",
            height=64,
            key=f"edit_quest_notes_{quest.id}",
        )
        save_col, cancel_col = st.columns(2)
        with save_col:
            save_clicked = st.button(
                "Save changes",
                type="primary",
                use_container_width=True,
                key=f"save_quest_{quest.id}",
                disabled=end_at.date() != planned_date,
            )
        with cancel_col:
            cancel_clicked = st.button("Cancel", use_container_width=True, key=f"cancel_quest_{quest.id}")

        if cancel_clicked:
            st.session_state.pop("editing_day_quest_id", None)
            st.rerun()
        if not save_clicked:
            return

        try:
            update_one_time_quest_if_unresolved(
                quest.id,
                title=title,
                description=notes,
                category_id=category_options[category_name],
                planned_date=planned_date,
                start_time=start_time,
                end_time=end_at.time(),
                estimated_minutes=duration_minutes,
            )
        except ValueError as error:
            st.error(str(error))
        else:
            st.session_state.pop("editing_day_quest_id", None)
            st.session_state["pending_selected_date"] = planned_date
            st.session_state["daily_status_message"] = "Planned item updated."
            st.rerun()


def render_day_summary(quests: list) -> None:
    quest_count = len(quests)
    planned_minutes = sum(_quest_duration_minutes(quest) for quest in quests)
    planned_xp = sum(quest.xp_reward or 0 for quest in quests)
    completed_count = sum(1 for quest in quests if _display_status(quest).strip().lower() == "completed")
    quest_col, time_col, xp_col, complete_col = st.columns(4)
    quest_col.metric("Quests", f"{quest_count} {_pluralize('quest', quest_count)}")
    time_col.metric("Planned Time", _format_minutes(planned_minutes))
    xp_col.metric("Planned XP", f"{planned_xp} XP")
    complete_col.metric("Completed", completed_count)


def render_goal_progress_section(category_options: dict[str, int]) -> list:
    status_message = st.session_state.pop("goal_status_message", None)
    if status_message:
        if st.session_state.pop("goal_status_warning", False):
            st.warning(status_message)
        else:
            st.success(status_message)

    active_goals = list_active_goals()
    if not active_goals:
        render_empty_state(
            "No active goals yet",
            "Create a project from Add to plan, then link one-time sessions to track progress.",
        )
        return []

    category_names_by_id = {category_id: name for name, category_id in category_options.items()}
    for goal in active_goals:
        progress = get_goal_progress(goal.id)
        progress_percent = float(progress["progress_percent"])
        progress_label = _format_percent(progress_percent)
        progress_width = max(0, min(100, progress_percent))
        planned_label = (
            _format_minutes(progress["planned_total_minutes"])
            if int(progress["planned_total_minutes"]) > 0
            else "No time target"
        )
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
                        <div class="hq-progress-meta">
                            {escape(str(goal.status))} / {escape(str(category))} / Target: {escape(str(target))}
                        </div>
                    </div>
                    <div>
                        <div class="hq-progress-value">
                            {_format_minutes(progress['completed_minutes'])}
                            / {escape(planned_label)}
                        </div>
                        <div class="hq-progress-caption">{progress_label} complete</div>
                    </div>
                </div>
                <div class="hq-progress-track">
                    <div class="hq-progress-fill" style="width: {progress_width:.2f}%"></div>
                </div>
                <div class="hq-progress-footer">
                    <div class="hq-progress-caption">
                        {escape(xp_label)}
                    </div>
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
        if st.button("Open project", key=f"open_goal_{goal.id}"):
            st.session_state["selected_goal_detail_id"] = goal.id
            st.rerun()

    return active_goals


def render_goal_detail(active_goals: list) -> None:
    goals_by_id = {goal.id: goal for goal in active_goals}
    selected_goal_id = st.session_state.get("selected_goal_detail_id")
    if selected_goal_id not in goals_by_id:
        return

    goal = goals_by_id[selected_goal_id]
    st.divider()
    header_col, action_col = st.columns([0.76, 0.24], vertical_alignment="center")
    with header_col:
        render_section_title("Project Planning", f"Plan multiple sessions for {goal.title}.")
    with action_col:
        if st.button("Close project", use_container_width=True, key=f"close_goal_{goal.id}"):
            st.session_state.pop("selected_goal_detail_id", None)
            st.rerun()

    render_goal_session_planner(goal)


def render_goal_session_planner(goal) -> None:
    planner_key = f"goal_session_planner_{goal.id}"
    preview_key = f"{planner_key}_preview"
    config_key = f"{planner_key}_config"

    with st.expander("Plan Multiple Sessions", expanded=False):
        duration_hours = st.number_input(
            "Session Duration Hours",
            min_value=0,
            value=2,
            step=1,
            key=f"{planner_key}_hours",
        )
        duration_minutes = st.number_input(
            "Session Duration Minutes",
            min_value=0,
            max_value=59,
            value=0,
            step=5,
            key=f"{planner_key}_minutes",
        )
        session_duration_minutes = int(duration_hours) * 60 + int(duration_minutes)

        try:
            planning_summary = get_goal_session_planning_summary(
                goal.id,
                session_duration_minutes=session_duration_minutes if session_duration_minutes > 0 else None,
            )
        except ValueError as error:
            st.error(str(error))
            return

        metric_cols = st.columns(4)
        metric_cols[0].metric("Goal Effort", _format_minutes(planning_summary["planned_total_minutes"]))
        metric_cols[1].metric("Completed", _format_minutes(planning_summary["completed_minutes"]))
        metric_cols[2].metric("Already Planned", _format_minutes(planning_summary["currently_planned_minutes"]))
        metric_cols[3].metric("Still To Schedule", _format_minutes(planning_summary["effort_to_schedule_minutes"]))

        start_date = st.date_input(
            "Start Date",
            value=max(st.session_state.get("selected_date", date.today()), goal.start_date or date.min),
            key=f"{planner_key}_start_date",
        )
        selected_weekday_names = st.multiselect(
            "Selected Weekdays",
            list(WEEKDAY_OPTIONS.keys()),
            default=["Monday", "Wednesday", "Friday"],
            key=f"{planner_key}_weekdays",
        )
        selected_weekdays = [WEEKDAY_OPTIONS[name] for name in selected_weekday_names]
        planned_start_time = st.time_input(
            "Start Time",
            value=time(18, 0),
            step=300,
            key=f"{planner_key}_start_time",
        )
        use_planning_end_date = st.checkbox(
            "Use Planning End Date",
            value=goal.target_end_date is not None,
            key=f"{planner_key}_use_end_date",
        )
        planning_end_date = None
        if use_planning_end_date:
            end_date_kwargs = {}
            if goal.target_end_date is not None:
                end_date_kwargs["max_value"] = goal.target_end_date
            default_end_date = goal.target_end_date or start_date
            planning_end_date = st.date_input(
                "Planning End Date",
                value=default_end_date if default_end_date < start_date else max(start_date, default_end_date),
                key=f"{planner_key}_end_date",
                **end_date_kwargs,
            )
        allow_short_final_session = st.checkbox(
            "Allow shorter final session",
            value=True,
            key=f"{planner_key}_allow_short_final",
        )

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
        preview_config = st.session_state.get(config_key)
        if preview is not None and preview_config != current_config:
            preview = None
            st.session_state.pop(preview_key, None)
            st.session_state.pop(config_key, None)

        preview_disabled = (
            goal.category_id is None
            or session_duration_minutes <= 0
            or not selected_weekdays
            or planning_summary["effort_to_schedule_minutes"] <= 0
        )
        if goal.category_id is None:
            st.error("This goal needs a category before sessions can be planned.")
        if planning_summary["effort_to_schedule_minutes"] <= 0:
            st.info("This goal has no unscheduled effort right now.")

        if st.button(
            "Preview",
            use_container_width=True,
            key=f"{planner_key}_preview_button",
            disabled=preview_disabled,
        ):
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
            st.warning(
                f"{_format_minutes(preview['remaining_unallocated_minutes'])} will remain unallocated."
            )

        confirm_generate = st.checkbox(
            "Confirm bulk session generation",
            key=f"{planner_key}_confirm_generate",
            disabled=not preview["date_range_complete"] or preview["total_sessions"] == 0,
        )
        if st.button(
            "Generate Planned Sessions",
            type="primary",
            use_container_width=True,
            key=f"{planner_key}_generate_button",
            disabled=not confirm_generate or not preview["date_range_complete"] or preview["total_sessions"] == 0,
        ):
            try:
                generation_summary = plan_goal_sessions(**st.session_state[config_key])
            except ValueError as error:
                st.error(str(error))
            else:
                st.session_state.pop(preview_key, None)
                st.session_state.pop(config_key, None)
                st.session_state["goal_status_message"] = (
                    f"Generated {generation_summary['created_count']} planned goal sessions."
                )
                st.rerun()


def _render_goal_session_plan_preview(preview: dict) -> None:
    rows = [
        {
            "Session": f"Session {row['session_number']}",
            "Date": row["date"].strftime("%b %d"),
            "Time": f"{row['start_time']:%H:%M}-{row['end_time']:%H:%M}",
            "Duration": _format_minutes(row["duration_minutes"]),
            "Expected XP": f"{row['expected_quest_xp']} XP",
        }
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


def render_goal_management(category_options: dict[str, int]) -> None:
    goals = list_goals()

    category_names_by_id = {category_id: name for name, category_id in category_options.items()}
    with st.expander("Manage Projects", expanded=False):
        if not goals:
            st.markdown(
                """
                <div class="hq-empty-compact">
                    <strong>No projects to manage yet.</strong>
                    <span>Create a project from Add to plan first.</span>
                </div>
                """,
                unsafe_allow_html=True,
            )
            return

        goals_by_id = {goal.id: goal for goal in goals}
        selected_goal_id = st.selectbox(
            "Project",
            list(goals_by_id),
            format_func=lambda goal_id: f"{goals_by_id[goal_id].title} / {goals_by_id[goal_id].status}",
            key="managed_goal_id",
        )
        goal = goals_by_id[selected_goal_id]
        history = get_goal_history_summary(goal.id)
        category = category_names_by_id.get(goal.category_id, "Uncategorized")
        st.markdown(
            f"""
            <div class="hq-management-item">
                <div class="hq-management-title">{escape(str(goal.title))}</div>
                <div class="hq-management-meta">
                    {escape(str(goal.status))} / {escape(str(category))} /
                    {int(history['linked_quests_count'])} linked sessions /
                    {int(history['earned_xp'])} XP earned
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        action_cols = st.columns(3)
        with action_cols[0]:
            if goal.status in ("Active", "Completed"):
                if st.button("Archive", key=f"goal_archive_{goal.id}", use_container_width=True):
                    archive_goal(goal.id)
                    st.session_state["goal_status_message"] = "Project archived. Linked session history was preserved."
                    st.rerun()
            elif st.button("Reopen", key=f"goal_reopen_{goal.id}", use_container_width=True):
                reopen_goal(goal.id)
                st.session_state["goal_status_message"] = "Project reopened."
                st.rerun()

        with action_cols[1]:
            if goal.status == "Active":
                if st.button("Complete", key=f"goal_complete_{goal.id}", use_container_width=True):
                    complete_goal(goal.id)
                    st.session_state["goal_status_message"] = "Project marked as completed."
                    st.rerun()
            elif goal.status == "Completed":
                if st.button("Reopen", key=f"goal_reopen_completed_{goal.id}", use_container_width=True):
                    reopen_goal(goal.id)
                    st.session_state["goal_status_message"] = "Project reopened."
                    st.rerun()

        with action_cols[2]:
            can_delete = history["linked_quests_count"] == 0
            confirm_delete = st.checkbox(
                "Confirm delete",
                key=f"goal_confirm_delete_{goal.id}",
                disabled=not can_delete,
            )
            if st.button(
                "Delete",
                key=f"goal_delete_{goal.id}",
                use_container_width=True,
                disabled=not can_delete or not confirm_delete,
            ):
                delete_goal_if_unused(goal.id)
                st.session_state["goal_status_message"] = "Unused project deleted."
                st.rerun()

        if not can_delete:
            st.caption("Projects with linked sessions are preserved. Archive them instead of deleting them.")


def _ensure_checklist_period_state() -> None:
    selected_date = st.session_state.get("selected_date", date.today())
    if "checklist_month" not in st.session_state:
        st.session_state["checklist_month"] = selected_date.month
    if "checklist_year" not in st.session_state:
        st.session_state["checklist_year"] = selected_date.year

    selected_month_name = st.session_state.get("checklist_month_name")
    if selected_month_name in list(month_name)[1:]:
        st.session_state["checklist_month"] = list(month_name).index(selected_month_name)

    selected_year = st.session_state.get("checklist_year_input")
    if selected_year is not None:
        st.session_state["checklist_year"] = int(selected_year)


def render_recurring_habits(category_options: dict[str, int]) -> None:
    category_names_by_id = {category_id: name for name, category_id in category_options.items()}

    status_message = st.session_state.pop("recurring_habit_status_message", None)
    if status_message:
        st.success(status_message)

    st.caption("Create routines from Add to plan, then edit or manage their lifecycle here.")
    with st.container():
        habits = list_recurring_habits()
        if not habits:
            render_empty_state(
                "No routines yet.",
                "Create a repeating routine from Add to plan in the Plan tab.",
            )
        else:
            render_recurring_habit_template_list(habits, category_names_by_id)

            st.divider()
            selected_habit = st.selectbox(
                "Manage recurring habit",
                habits,
                format_func=lambda habit: f"{habit.title} | {_format_habit_pattern(habit)} | {_active_label(habit)}",
                key="recurring_habit_manage",
            )
            history_summary = get_recurring_habit_history_summary(selected_habit.id)
            st.markdown(
                f"""
                <div class="hq-meta-pills">
                    <span class="hq-meta-pill"><strong>{int(history_summary['generated_instances_count'])}</strong> generated</span>
                    <span class="hq-meta-pill"><strong>{int(history_summary['planned_count'])}</strong> planned</span>
                    <span class="hq-meta-pill"><strong>{int(history_summary['completed_count'])}</strong> completed</span>
                    <span class="hq-meta-pill"><strong>{int(history_summary['skipped_count'])}</strong> skipped</span>
                    <span class="hq-meta-pill"><strong>{int(history_summary['failed_count'])}</strong> failed</span>
                </div>
                """,
                unsafe_allow_html=True,
            )

            if st.button(
                "Edit template",
                use_container_width=True,
                key=f"edit_recurring_habit_{selected_habit.id}",
            ):
                st.session_state["editing_recurring_habit_id"] = selected_habit.id
                st.rerun()

            if st.session_state.get("editing_recurring_habit_id") == selected_habit.id:
                render_recurring_habit_editor(selected_habit, category_options)

            render_recurring_habit_lifecycle(selected_habit, history_summary)


def render_recurring_habit_editor(habit, category_options: dict[str, int]) -> None:
    """Render template-only routine editing without touching generated occurrences."""
    category_names = list(category_options)
    current_category_name = next(
        (name for name, category_id in category_options.items() if category_id == habit.category_id),
        category_names[0],
    )
    current_weekdays = deserialize_weekdays(habit.weekdays)
    if current_weekdays == [0, 1, 2, 3, 4, 5, 6]:
        current_recurrence = "Every day"
    elif current_weekdays == [0, 1, 2, 3, 4]:
        current_recurrence = "Weekdays"
    else:
        current_recurrence = "Custom days"
    key_prefix = f"recurring_habit_editor_{habit.id}"

    with st.expander("Edit routine template", expanded=True):
        st.caption("Changes apply only when routine days are generated next. Existing days and history stay unchanged.")
        title = st.text_input("Title", value=habit.title, key=f"{key_prefix}_title")
        category_name = st.selectbox(
            "Category",
            category_names,
            index=category_names.index(current_category_name),
            key=f"{key_prefix}_category",
        )
        start_date = st.date_input(
            "Starts on",
            value=habit.start_date,
            key=f"{key_prefix}_start_date",
        )
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

        set_time = st.checkbox(
            "Set a time",
            value=habit.planned_start_time is not None,
            key=f"{key_prefix}_set_time",
        )
        planned_start_time = None
        planned_end_time = None
        if set_time:
            planned_start_time = st.time_input(
                "Start time",
                value=habit.planned_start_time or time(9, 0),
                step=300,
                key=f"{key_prefix}_start_time",
            )
            end_at = datetime.combine(start_date, planned_start_time) + timedelta(minutes=estimated_minutes)
            planned_end_time = end_at.time()
            if end_at.date() != start_date:
                st.error("The selected duration cannot cross midnight.")

        recurrence = st.radio(
            "Repeat",
            ["Every day", "Weekdays", "Custom days"],
            index=["Every day", "Weekdays", "Custom days"].index(current_recurrence),
            horizontal=True,
            key=f"{key_prefix}_recurrence",
        )
        if recurrence == "Custom days":
            selected_weekday_names = st.multiselect(
                "Days",
                list(WEEKDAY_OPTIONS),
                default=[name for name, value in WEEKDAY_OPTIONS.items() if value in current_weekdays],
                key=f"{key_prefix}_weekdays",
            )
            weekdays = [WEEKDAY_OPTIONS[name] for name in selected_weekday_names]
        elif recurrence == "Every day":
            weekdays = [0, 1, 2, 3, 4, 5, 6]
        else:
            weekdays = [0, 1, 2, 3, 4]

        set_end_date = st.checkbox(
            "Set an end date",
            value=habit.end_date is not None,
            key=f"{key_prefix}_set_end_date",
        )
        end_date = (
            st.date_input("Ends on", value=habit.end_date or start_date, key=f"{key_prefix}_end_date")
            if set_end_date
            else None
        )
        notes = st.text_area(
            "Notes",
            value=habit.description or "",
            height=64,
            key=f"{key_prefix}_notes",
        )

        save_col, cancel_col = st.columns(2)
        with save_col:
            if st.button("Save template", type="primary", use_container_width=True, key=f"{key_prefix}_save"):
                if set_time and datetime.combine(start_date, planned_start_time) + timedelta(minutes=estimated_minutes) >= datetime.combine(start_date + timedelta(days=1), time.min):
                    st.error("The selected duration cannot cross midnight.")
                elif not weekdays:
                    st.error("Choose at least one day for the routine.")
                else:
                    try:
                        update_recurring_habit_template(
                            habit.id,
                            title=title,
                            category_id=category_options[category_name],
                            estimated_minutes=estimated_minutes,
                            recurrence_type="selected_weekdays",
                            weekdays=weekdays,
                            start_date=start_date,
                            end_date=end_date,
                            description=notes,
                            planned_start_time=planned_start_time,
                            planned_end_time=planned_end_time,
                        )
                    except ValueError as error:
                        st.error(str(error))
                    else:
                        st.session_state.pop("editing_recurring_habit_id", None)
                        st.session_state["recurring_habit_status_message"] = (
                            "Routine template updated. Existing generated days were not changed."
                        )
                        st.rerun()
        with cancel_col:
            if st.button("Cancel", use_container_width=True, key=f"{key_prefix}_cancel"):
                st.session_state.pop("editing_recurring_habit_id", None)
                st.rerun()


def render_recurring_habit_lifecycle(habit, history_summary: dict) -> None:
    """Keep routine deletion, stopping, cleanup, and resuming in one place."""
    key_prefix = f"recurring_habit_lifecycle_{habit.id}"
    with st.expander("Routine lifecycle", expanded=False):
        if history_summary["generated_instances_count"] == 0:
            st.caption("This template has no generated days and can be deleted.")
            confirmed = st.checkbox(
                "Confirm delete routine",
                key=f"{key_prefix}_confirm_delete",
            )
            if st.button(
                "Delete routine",
                use_container_width=True,
                disabled=not confirmed,
                key=f"{key_prefix}_delete",
            ):
                summary = delete_recurring_habit_if_unused(habit.id)
                if summary["deleted"]:
                    st.session_state["recurring_habit_status_message"] = "Routine deleted."
                else:
                    st.session_state["recurring_habit_status_message"] = (
                        "Routine was not deleted because generated history exists."
                    )
                st.rerun()
            return

        removable_count = int(history_summary["removable_future_planned_count"])
        if habit.is_active:
            st.caption("Stopping prevents new generation. Existing history is always preserved.")
            remove_future_planned = st.checkbox(
                f"Also remove {removable_count} future unresolved planned days",
                value=False,
                disabled=removable_count == 0,
                key=f"{key_prefix}_remove_future",
            )
            confirmed = st.checkbox(
                "Confirm stop routine",
                key=f"{key_prefix}_confirm_stop",
            )
            if st.button(
                "Stop routine",
                type="primary",
                use_container_width=True,
                disabled=not confirmed,
                key=f"{key_prefix}_stop",
            ):
                summary = stop_recurring_habit(
                    habit.id,
                    remove_future_planned=remove_future_planned,
                )
                removed_count = summary["removed_instances_count"]
                st.session_state["recurring_habit_status_message"] = (
                    f"Routine stopped and {removed_count} future planned days removed."
                    if remove_future_planned
                    else "Routine stopped. Existing generated days were kept."
                )
                st.rerun()
            return

        st.caption("This routine is stopped and will not generate new days.")
        if st.button(
            "Resume routine",
            type="primary",
            use_container_width=True,
            key=f"{key_prefix}_resume",
        ):
            set_recurring_habit_active(habit.id, True)
            st.session_state["recurring_habit_status_message"] = "Routine resumed."
            st.rerun()

        if removable_count:
            st.caption(f"{removable_count} future unresolved planned days remain.")
            confirmed = st.checkbox(
                "Confirm remove remaining future planned days",
                key=f"{key_prefix}_confirm_cleanup",
            )
            if st.button(
                "Remove future planned days",
                use_container_width=True,
                disabled=not confirmed,
                key=f"{key_prefix}_cleanup",
            ):
                summary = stop_recurring_habit(habit.id, remove_future_planned=True)
                st.session_state["recurring_habit_status_message"] = (
                    f"Removed {summary['removed_instances_count']} future planned days."
                )
                st.rerun()


def render_monthly_checklist() -> None:
    _ensure_checklist_period_state()

    control_col, year_col = st.columns([0.58, 0.42])
    with control_col:
        selected_month_name = st.selectbox(
            "Month",
            list(month_name)[1:],
            index=st.session_state["checklist_month"] - 1,
            key="checklist_month_name",
        )
        selected_month = list(month_name).index(selected_month_name)
        st.session_state["checklist_month"] = selected_month
    with year_col:
        selected_year = st.number_input(
            "Year",
            min_value=2000,
            max_value=2100,
            value=int(st.session_state["checklist_year"]),
            step=1,
            key="checklist_year_input",
        )
        st.session_state["checklist_year"] = int(selected_year)

    _render_routine_generation_action(int(selected_year), selected_month)
    checklist = get_month_checklist(int(selected_year), selected_month)
    _render_checklist_legend()

    status_message = st.session_state.pop("checklist_status_message", None)
    if status_message:
        st.success(status_message)

    if not checklist["rows"]:
        render_empty_state(
            "No planned quest days for this month yet.",
            "Add quests in the planner above to start tracking your checklist.",
        )
        return

    _render_checklist_table(checklist)

    st.divider()
    st.write("**Adjust Selected Day**")
    st.caption("Use this for a past day or a goal session. Today's work can be resolved directly in Plan.")

    row_lookup = {_checklist_row_id(row): row for row in checklist["rows"]}
    quest_labels = _build_checklist_quest_labels(checklist["rows"])
    editor_col, status_col = st.columns([0.68, 0.32], gap="large")

    if st.session_state.get("checklist_selected_row") not in row_lookup:
        st.session_state["checklist_selected_row"] = next(iter(row_lookup))

    with editor_col:
        quest_col, date_col = st.columns([0.62, 0.38])
        with quest_col:
            selected_row_id = st.selectbox(
                "Quest",
                list(row_lookup.keys()),
                format_func=lambda row_id: quest_labels[row_id],
                key="checklist_selected_row",
            )

        selected_row = row_lookup[selected_row_id]
        _sync_checklist_selected_date(selected_row, checklist["days"])

        with date_col:
            selected_checklist_date = st.selectbox(
                "Date",
                checklist["days"],
                format_func=lambda day: day.strftime("%b %d"),
                key="checklist_selected_date",
            )

    selected_cell = selected_row["cells"][selected_checklist_date]
    selected_entry = _select_checklist_cell_entry(selected_row, selected_cell, selected_checklist_date)
    display_cell = selected_entry or selected_cell
    cell_is_editable = selected_entry is not None or is_checklist_cell_editable(selected_row, selected_checklist_date)
    current_status = (
        CHECKLIST_STATUS_LABELS.get(display_cell["status"], "Unknown")
        if cell_is_editable
        else "Locked - Not scheduled"
    )

    with status_col:
        marker = CHECKLIST_STATUS_MARKERS.get(display_cell["status"], "")
        status_prefix = f"{marker} - " if marker and cell_is_editable else ""
        st.markdown(
            f"""
            <div class="hq-status-panel">
                <div class="hq-status-label">Current status</div>
                <div class="hq-status-value">{escape(status_prefix + current_status)}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if not cell_is_editable:
            st.warning("This quest is not scheduled for the selected date.")

    if not cell_is_editable:
        actions = ()
        action_cols = ()
    elif display_cell["status"] == "Planned":
        actions = (
            ("Complete", "Completed", "checklist_complete", "primary"),
            ("Skip", "Skipped", "checklist_skip", "secondary"),
            ("Fail", "Failed", "checklist_fail", "secondary"),
        )
        action_cols = st.columns(3)
    else:
        actions = (("Reset to Planned", "Planned", "checklist_reset", "secondary"),)
        action_cols = (st.columns([0.3, 0.7])[0],)

    for column, (label, status, key, button_type) in zip(action_cols, actions):
        with column:
            if st.button(label, type=button_type, use_container_width=True, key=key):
                try:
                    update_checklist_cell_status(
                        selected_row,
                        selected_checklist_date,
                        status,
                        quest_id=display_cell.get("quest_id"),
                        checkin_id=display_cell.get("checkin_id"),
                    )
                except ValueError as error:
                    st.warning(str(error))
                    continue
                st.session_state["pending_selected_date"] = selected_checklist_date
                st.session_state["checklist_status_message"] = (
                    f"{label} saved for {selected_checklist_date:%Y-%m-%d}."
                )
                st.rerun()

    _render_checklist_delete_action(selected_row, display_cell, selected_checklist_date, cell_is_editable)


def _render_routine_generation_action(selected_year: int, selected_month: int) -> None:
    generation_summary = st.session_state.pop("recurring_generation_summary", None)
    if generation_summary:
        st.success(
            "Generated "
            f"{generation_summary['total_generated']} planned days. "
            f"{generation_summary['total_skipped_existing']} already existed."
        )

    generate_col, copy_col = st.columns([0.35, 0.65], vertical_alignment="center")
    with generate_col:
        if st.button(
            f"Generate routines for {month_name[selected_month]} {selected_year}",
            use_container_width=True,
            key="generate_routines_for_review_month",
        ):
            try:
                summary = generate_all_recurring_habits_for_month(selected_year, selected_month)
            except ValueError as error:
                st.error(str(error))
            else:
                st.session_state["recurring_generation_summary"] = summary
                st.rerun()
    with copy_col:
        st.caption("Creates only missing planned days for active routines. Existing history is never overwritten.")


def _render_checklist_legend() -> None:
    legend_items = (
        ("-", "Not scheduled / locked"),
        ("P", "Planned"),
        ("C", "Completed"),
        ("S", "Skipped"),
        ("F", "Failed"),
    )
    legend_html = "".join(
        f'<span class="hq-legend-item"><span class="hq-legend-marker">{escape(marker)}</span>{escape(label)}</span>'
        for marker, label in legend_items
    )
    st.markdown(f'<div class="hq-legend-row">{legend_html}</div>', unsafe_allow_html=True)


def _render_checklist_table(checklist: dict) -> None:
    headers = ["Quest", "Category"] + [str(day.day) for day in checklist["days"]]
    header_html = "".join(
        f'<th class="{"hq-table-sticky" if index == 0 else "hq-table-day" if index >= 2 else ""}">'
        f"{escape(header)}</th>"
        for index, header in enumerate(headers)
    )
    row_html = "\n".join(_render_checklist_table_row(row, checklist["days"]) for row in checklist["rows"])
    st.markdown(
        f"""
        <div class="hq-table-scroll">
            <table class="hq-data-table">
                <thead><tr>{header_html}</tr></thead>
                <tbody>{row_html}</tbody>
            </table>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_checklist_table_row(row: dict, days: list[date]) -> str:
    day_cells = "".join(
        f'<td class="hq-table-day">{_checklist_cell_marker_html(row["cells"][day])}</td>'
        for day in days
    )
    return (
        "<tr>"
        f'<td class="hq-table-sticky">{escape(str(row["title"]))}</td>'
        f'<td>{escape(str(row["category"] or "Uncategorized"))}</td>'
        f"{day_cells}"
        "</tr>"
    )


def _checklist_cell_marker_html(cell: dict) -> str:
    entries = cell.get("entries") or []
    if not entries:
        return _status_marker_html(cell.get("status"))

    status_counts: dict[str, int] = {}
    for entry in entries:
        status = entry.get("status")
        if status:
            status_counts[status] = status_counts.get(status, 0) + 1
    if not status_counts:
        return ""

    if len(status_counts) == 1:
        status, count = next(iter(status_counts.items()))
        marker = CHECKLIST_STATUS_MARKERS.get(status, "")
        label = marker if count == 1 else f"{marker}{count}"
        return _status_marker_html(status, label=label)

    ordered_statuses = ("Completed", "Planned", "Skipped", "Failed")
    return " ".join(
        _status_marker_html(status, label=f"{CHECKLIST_STATUS_MARKERS[status]}{status_counts[status]}")
        for status in ordered_statuses
        if status in status_counts
    )


def _status_marker_html(status: str | None, label: str | None = None) -> str:
    marker = CHECKLIST_STATUS_MARKERS.get(status, "")
    if not marker:
        return ""
    label = label or marker
    status_class = {
        "Planned": "hq-status-planned",
        "Completed": "hq-status-completed",
        "Skipped": "hq-status-skipped",
        "Failed": "hq-status-failed",
    }.get(status, "hq-status-planned")
    return f'<span class="hq-status-marker {status_class}">{escape(label)}</span>'


def _select_checklist_cell_entry(row: dict, cell: dict, selected_date: date) -> dict | None:
    entries = cell.get("entries") or []
    if not entries:
        return cell if is_checklist_cell_editable(row, selected_date) else None
    if len(entries) == 1:
        return entries[0]

    option_lookup = {entry["checkin_id"]: entry for entry in entries}
    selected_checkin_id = st.selectbox(
        "Goal Session",
        list(option_lookup.keys()),
        format_func=lambda checkin_id: _format_checklist_session_option(option_lookup[checkin_id]),
        key=f"checklist_goal_session_{row.get('row_id')}_{selected_date.isoformat()}",
    )
    return option_lookup[selected_checkin_id]


def _format_checklist_session_option(entry: dict) -> str:
    session_number = entry.get("goal_session_number")
    session_label = f"Session {session_number}" if session_number else str(entry.get("title") or "Session")
    start = entry.get("planned_start_at")
    end = entry.get("planned_end_at")
    time_label = ""
    if start and end:
        time_label = f" {start:%H:%M}-{end:%H:%M}"
    status = CHECKLIST_STATUS_LABELS.get(entry.get("status"), "Unknown")
    return f"{session_label}{time_label} {status}"


def _render_checklist_delete_action(row: dict, cell: dict, selected_date: date, cell_is_editable: bool) -> None:
    st.divider()
    st.write("**Delete Planned Item**")
    if not cell_is_editable:
        st.caption("No scheduled quest day exists for this date, so there is nothing to delete.")
        return

    is_unresolved = _is_unresolved_planned_cell(cell)
    is_recurring = row.get("row_type") == "recurring_habit"
    if is_recurring:
        st.caption("Remove only this generated recurring day. Completed, skipped, failed, and XP-awarded days are blocked.")
        confirm_label = "Confirm remove this generated day"
        button_label = "Remove This Generated Day"
        blocked_message = "This generated habit day has history and cannot be deleted safely."
    else:
        st.caption("Delete this one-time planned quest only if it has no historical status or awarded XP.")
        confirm_label = "Confirm delete planned quest"
        button_label = "Delete Planned Quest"
        blocked_message = "This quest has historical status or awarded XP and cannot be deleted safely."

    if not is_unresolved:
        st.warning(blocked_message)

    confirm_delete = st.checkbox(
        confirm_label,
        key=f"checklist_confirm_delete_{row.get('row_id')}_{selected_date.isoformat()}_{cell.get('checkin_id')}",
        disabled=not is_unresolved,
    )
    if st.button(
        button_label,
        use_container_width=True,
        disabled=not is_unresolved or not confirm_delete,
        key=f"checklist_delete_{row.get('row_id')}_{cell.get('checkin_id')}",
    ):
        if is_recurring:
            summary = delete_recurring_generated_occurrence_if_unresolved(cell["quest_id"])
            if summary["deleted"]:
                st.session_state["checklist_status_message"] = "Removed this generated recurring planned day."
            else:
                st.warning(summary.get("reason") or blocked_message)
                return
        else:
            summary = delete_one_time_quest_if_unresolved(cell["quest_id"])
            if summary["deleted"]:
                st.session_state["checklist_status_message"] = "Deleted planned quest."
            else:
                st.warning(summary.get("reason") or blocked_message)
                return
        st.session_state["pending_selected_date"] = selected_date
        st.rerun()


def _is_unresolved_planned_cell(cell: dict) -> bool:
    return (
        cell.get("status") == "Planned"
        and cell.get("xp_awarded", 0) == 0
        and cell.get("completed_at") is None
        and cell.get("skipped_at") is None
        and cell.get("failed_at") is None
    )


def _checklist_row_id(row: dict) -> str:
    return row.get("row_id") or f"quest:{row['quest_id']}"


def _build_checklist_quest_labels(rows: list[dict]) -> dict[str, str]:
    base_labels = {
        _checklist_row_id(row): f"{row['title']} | {row['category'] or 'Uncategorized'}"
        for row in rows
    }
    label_counts: dict[str, int] = {}
    labels: dict[int, str] = {}
    for quest_id, label in base_labels.items():
        label_counts[label] = label_counts.get(label, 0) + 1
        labels[quest_id] = label if label_counts[label] == 1 else f"{label} ({label_counts[label]})"
    return labels


def _sync_checklist_selected_date(row: dict, days: list[date]) -> None:
    selected_row_id = _checklist_row_id(row)
    previous_row_id = st.session_state.get("checklist_last_row_id")
    current_date = st.session_state.get("checklist_selected_date")

    if current_date not in days or previous_row_id != selected_row_id:
        st.session_state["checklist_selected_date"] = _preferred_checklist_date(row, days)

    st.session_state["checklist_last_row_id"] = selected_row_id


def _preferred_checklist_date(row: dict, days: list[date]) -> date:
    current_page_date = st.session_state.get("selected_date")
    if current_page_date in days and is_checklist_cell_editable(row, current_page_date):
        return current_page_date

    for day in days:
        if is_checklist_cell_editable(row, day):
            return day

    return days[0]


def render_recurring_habit_template_list(habits: list, category_names_by_id: dict[int, str]) -> None:
    rows = []
    for habit in habits:
        category = category_names_by_id.get(habit.category_id, "Uncategorized")
        end_date = habit.end_date.isoformat() if habit.end_date else "No end"
        rows.append(
            (
                '<div class="hq-list-row">'
                f'<div class="hq-list-time">{escape(_active_label(habit))}</div>'
                "<div>"
                f'<div class="hq-list-title">{escape(str(habit.title))}</div>'
                f'<div class="hq-list-meta">{escape(category)} | {escape(_format_habit_pattern(habit))}</div>'
                f'<div class="hq-list-meta">{escape(_format_habit_time_window(habit))} | '
                f"{habit.start_date.isoformat()} to {end_date}</div>"
                "</div>"
                f'<div class="hq-list-value">{int(habit.estimated_minutes)} min</div>'
                "</div>"
            )
        )

    st.markdown(
        f'<div class="hq-list-panel">{"".join(rows)}</div>',
        unsafe_allow_html=True,
    )


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


def _calendar_events_signature(calendar_events: list[dict]) -> str:
    event_parts = [
        f"{event.get('id')}:{event.get('start')}:{event.get('end')}:{event.get('status')}:{event.get('color')}"
        for event in calendar_events
    ]
    raw_signature = "|".join(sorted(event_parts))
    return hashlib.md5(raw_signature.encode("utf-8")).hexdigest()[:12]


def _extract_calendar_date(calendar_state) -> date | None:
    if not isinstance(calendar_state, dict):
        return None

    for key in ("dateClick", "select", "eventClick"):
        value = calendar_state.get(key)
        if not isinstance(value, dict):
            continue
        date_value = value.get("dateStr") or value.get("startStr")
        if date_value is None and key == "eventClick":
            event = value.get("event") or {}
            date_value = event.get("start")
        parsed_date = _parse_calendar_date(date_value)
        if parsed_date:
            return parsed_date
    return None


def _parse_calendar_date(value) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return date.fromisoformat(str(value)[:10])
        except ValueError:
            return None


def _format_time_range(quest) -> str:
    if quest.planned_start_at and quest.planned_end_at:
        return f"{quest.planned_start_at:%H:%M} - {quest.planned_end_at:%H:%M}"
    return "All day"


def _category_name(quest) -> str:
    return quest.category.name if quest.category else "Uncategorized"


def _display_status(quest) -> str:
    return getattr(quest, "display_status", None) or quest.status or "Planned"


def _format_selected_date(value: date) -> str:
    return value.strftime("%A, %Y-%m-%d")


def _quest_duration_minutes(quest) -> int:
    if quest.planned_start_at and quest.planned_end_at:
        return max(int((quest.planned_end_at - quest.planned_start_at).total_seconds() // 60), 0)
    return int(quest.estimated_minutes or 0)


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
    if rounded.is_integer():
        return f"{int(rounded)}%"
    return f"{rounded}%"


def _pluralize(word: str, count: int) -> str:
    return word if count == 1 else f"{word}s"


def render_calendar_day_plan_tab(category_options: dict[str, int]) -> None:
    status_message = st.session_state.pop("plan_status_message", None)
    if status_message:
        st.success(status_message)
    daily_status_message = st.session_state.pop("daily_status_message", None)
    if daily_status_message:
        st.success(daily_status_message)

    st.caption("Plan tasks, repeating routines, and project sessions from one place.")
    calendar_events = get_quests_for_calendar()

    render_section_title("Quest Calendar", "Review planned quests and select a day to build its schedule.")
    with st.container():
        render_calendar(calendar_events, st.session_state["selected_date"])

    selected_day_quests = get_quests_for_day(st.session_state["selected_date"])

    render_section_title("Selected Day Board")
    with st.container():
        header_left, header_right = st.columns([0.68, 0.32], vertical_alignment="center")
        with header_left:
            st.subheader(_format_selected_date(st.session_state["selected_date"]))
            st.caption("Daily quest plan for the selected calendar date.")
        with header_right:
            st.date_input("Selected date", key="selected_date")

        render_day_summary(selected_day_quests)

        schedule_col, planner_col = st.columns([0.6, 0.4], gap="large")

    with schedule_col:
        st.write("**Day Schedule**")
        st.caption("Update today's work directly, or use Monthly Checklist for the full month.")
        render_schedule_list(selected_day_quests, st.session_state["selected_date"])
        render_day_item_editor(selected_day_quests, category_options)

    with planner_col:
        st.write("**Add to plan**")
        st.caption("Schedule one task, a repeating routine, or a session for an existing project.")
        active_goals = list_active_goals()
        form_result = render_plan_form(
            category_options=category_options,
            active_goals=active_goals,
            selected_date=st.session_state["selected_date"],
            goal_title_by_id={goal.id: goal.title for goal in active_goals},
        )
        if form_result is not None:
            try:
                if form_result.new_project is not None:
                    new_project = form_result.new_project
                    goal = create_goal(
                        title=new_project.title,
                        category_id=new_project.category_id,
                        planned_total_minutes=new_project.planned_total_minutes,
                        start_date=st.session_state["selected_date"],
                        target_end_date=new_project.target_end_date,
                    )
                    st.session_state["plan_goal"] = goal.id
                    st.session_state.pop("plan_creating_project", None)
                    st.session_state["plan_status_message"] = "Project created. Add its first session below."
                else:
                    draft = form_result.plan
                    if draft is None:
                        return
                    if draft.is_recurring:
                        habit = create_recurring_habit(
                            title=draft.title,
                            category_id=draft.category_id,
                            estimated_minutes=draft.estimated_minutes,
                            recurrence_type="selected_weekdays",
                            weekdays=draft.weekdays,
                            start_date=draft.planned_date,
                            end_date=draft.end_date,
                            description=draft.notes,
                            planned_start_time=draft.start_time,
                            planned_end_time=draft.end_time,
                        )
                        if draft.generate_initial_month:
                            generate_recurring_habit_for_month(
                                habit.id,
                                draft.planned_date.year,
                                draft.planned_date.month,
                            )
                        st.session_state["recurring_habit_status_message"] = "Routine created."
                    else:
                        create_scheduled_quest(
                            title=draft.title,
                            description=draft.notes,
                            category_id=draft.category_id,
                            planned_date=draft.planned_date,
                            start_time=draft.start_time,
                            end_time=draft.end_time,
                            estimated_minutes=draft.estimated_minutes,
                            goal_id=draft.goal_id,
                        )
                        st.session_state["plan_status_message"] = "Item added to the plan."
            except ValueError as error:
                st.error(str(error))
            else:
                st.rerun()


def render_manage_tab(category_options: dict[str, int]) -> None:
    st.caption("Manage long-running projects and repeating routines outside the daily planning flow.")
    render_section_title(
        "Projects",
        "Track active long-term goals through linked one-time quest sessions.",
    )
    active_goals = render_goal_progress_section(category_options)
    render_goal_detail(active_goals)
    render_goal_management(category_options)

    st.divider()
    render_section_title("Routines", "Create routines from Add to plan, then manage their planned days here.")
    render_recurring_habits(category_options)


def render_monthly_review_tab() -> None:
    st.caption("Review the selected month, generate routine days, and update history when needed.")
    render_section_title("Monthly Review", "Track scheduled quest completion for the selected month.")
    render_monthly_checklist()


apply_theme()
render_page_header(
    "Quest Planning",
    "Quest Planner",
    "Plan quests, schedule habits, and manage your daily quest flow.",
)

init_db()
ensure_default_categories()
categories = get_categories()
category_options = {category.name: category.id for category in categories}

if not category_options:
    st.warning("Run python -m src.database.seed to create default categories.")
    st.stop()

if "selected_date" not in st.session_state:
    st.session_state["selected_date"] = date.today()

pending_selected_date = st.session_state.pop("pending_selected_date", None)
if pending_selected_date is not None:
    st.session_state["selected_date"] = pending_selected_date

plan_tab, manage_tab, review_tab = st.tabs(
    [
        "Plan",
        "Manage",
        "Monthly Review",
    ]
)

with plan_tab:
    render_calendar_day_plan_tab(category_options)

with manage_tab:
    render_manage_tab(category_options)

with review_tab:
    render_monthly_review_tab()

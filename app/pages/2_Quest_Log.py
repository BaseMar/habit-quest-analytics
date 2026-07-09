from calendar import month_name
from datetime import date, datetime, time
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

from src.database.db import init_db
from src.database.seed import ensure_default_categories
from src.services.checklist_service import (
    get_month_checklist,
    is_checklist_cell_editable,
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
from src.services.quest_service import (
    create_scheduled_quest,
    delete_one_time_quest_if_unresolved,
    get_categories,
    get_quests_for_calendar,
    get_quests_for_day,
    preview_next_goal_session_title,
    validate_schedule_times,
)
from src.services.recurring_habit_service import (
    archive_recurring_habit,
    create_recurring_habit,
    delete_recurring_habit_if_unused,
    delete_recurring_generated_occurrence_if_unresolved,
    deserialize_weekdays,
    generate_all_recurring_habits_for_month,
    get_recurring_habit_history_summary,
    list_recurring_habits,
    remove_future_planned_recurring_instances,
    set_recurring_habit_active,
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
        "slotMaxTime": "22:00:00",
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


def render_schedule_list(quests: list) -> None:
    if not quests:
        st.info("No quests planned for this day.")
        return

    rows = "".join(
        (
            '<div class="hq-list-row">'
            f'<div class="hq-list-time">{escape(_format_time_range(quest))}</div>'
            "<div>"
            f'<div class="hq-list-title">{escape(str(quest.title))}</div>'
            f'<div class="hq-list-meta">{escape(_category_name(quest))} / {escape(_display_status(quest))}</div>'
            "</div>"
            f'<div class="hq-list-value">{int(quest.xp_reward or 0)} XP</div>'
            "</div>"
        )
        for quest in quests
    )
    st.markdown(f'<div class="hq-list-panel">{rows}</div>', unsafe_allow_html=True)


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


def render_goal_progress_section(category_options: dict[str, int]) -> None:
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
            "Create a long-term goal below, then link one-time quest sessions to track progress.",
        )
        return

    category_names_by_id = {category_id: name for name, category_id in category_options.items()}
    for goal in active_goals:
        progress = get_goal_progress(goal.id)
        progress_percent = float(progress["progress_percent"])
        progress_label = _format_percent(progress_percent)
        progress_width = max(0, min(100, progress_percent))
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
                            / {_format_minutes(progress['planned_total_minutes'])}
                        </div>
                        <div class="hq-progress-caption">{progress_label} complete</div>
                    </div>
                </div>
                <div class="hq-progress-track">
                    <div class="hq-progress-fill" style="width: {progress_width:.2f}%"></div>
                </div>
                <div class="hq-progress-footer">
                    <div class="hq-progress-caption">
                        {int(progress['earned_xp'])} / {int(progress['expected_total_xp'])} XP earned
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
        render_goal_session_form(goal)


def render_goal_session_form(goal) -> None:
    with st.expander("Add Session", expanded=False):
        try:
            session_title = preview_next_goal_session_title(goal.id)
        except ValueError:
            session_title = f"{goal.title} Session"
        st.caption(f"New session: {session_title}")
        session_date = st.date_input(
            "Planned Date",
            value=st.session_state.get("selected_date", date.today()),
            key=f"goal_session_date_{goal.id}",
        )

        start_col, end_col = st.columns(2)
        with start_col:
            session_start_time = st.time_input(
                "Start Time",
                value=time(9, 0),
                step=300,
                key=f"goal_session_start_{goal.id}",
            )
        with end_col:
            session_end_time = st.time_input(
                "End Time",
                value=time(10, 0),
                step=300,
                key=f"goal_session_end_{goal.id}",
            )

        session_notes = st.text_area(
            "Notes",
            height=64,
            placeholder="Optional notes",
            key=f"goal_session_notes_{goal.id}",
        )
        estimated_minutes = _calculate_duration_minutes_for_date(
            session_date,
            session_start_time,
            session_end_time,
        )
        if estimated_minutes is None:
            st.error("End time must be after start time.")
        if goal.category_id is None:
            st.error("This goal needs a category before sessions can be added.")

        if st.button(
            "Add Session",
            type="primary",
            use_container_width=True,
            key=f"goal_add_session_{goal.id}",
            disabled=goal.category_id is None,
        ):
            if estimated_minutes is None:
                st.error("End time must be after start time.")
            else:
                try:
                    create_scheduled_quest(
                        title=session_title,
                        description=session_notes,
                        category_id=goal.category_id,
                        goal_id=goal.id,
                        planned_date=session_date,
                        start_time=session_start_time,
                        end_time=session_end_time,
                        estimated_minutes=estimated_minutes,
                    )
                except ValueError as error:
                    st.error(str(error))
                else:
                    st.session_state["goal_status_message"] = "Goal session planned."
                    st.rerun()


def render_goal_creation_form(category_options: dict[str, int]) -> None:
    with st.expander("Create Goal / Project", expanded=False):
        st.markdown(
            """
            <div class="hq-compact-intro">
                <div class="hq-compact-title">New long-term goal</div>
                <div class="hq-compact-body">Create the project container first, then add one-time sessions to track progress.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        form_col, spacer_col = st.columns([0.68, 0.32], gap="large")
        with form_col:
            title = st.text_input("Goal Title", placeholder="Portfolio Project", key="new_goal_title")
            description = st.text_area(
                "Description / Notes",
                height=64,
                placeholder="Optional goal notes",
                key="new_goal_description",
            )

            hours_col, minutes_col = st.columns(2)
            with hours_col:
                planned_hours = st.number_input(
                    "Planned Hours",
                    min_value=0,
                    value=20,
                    step=1,
                    key="new_goal_planned_hours",
                )
            with minutes_col:
                planned_minutes_remainder = st.number_input(
                    "Planned Minutes",
                    min_value=0,
                    max_value=59,
                    value=0,
                    step=5,
                    key="new_goal_planned_minutes",
                )

            category_labels = list(category_options.keys())
            selected_category_label = st.selectbox(
                "Category",
                category_labels,
                key="new_goal_category",
            )
            selected_category_id = category_options[selected_category_label]

            date_col, target_col = st.columns(2)
            with date_col:
                use_start_date = st.checkbox("Set start date", value=True, key="new_goal_use_start")
                start_date = (
                    st.date_input("Start Date", value=date.today(), key="new_goal_start_date")
                    if use_start_date
                    else None
                )
            with target_col:
                use_target_date = st.checkbox("Set target date", value=False, key="new_goal_use_target")
                target_end_date = (
                    st.date_input("Target End Date", value=date.today(), key="new_goal_target_date")
                    if use_target_date
                    else None
                )

            if st.button("Create Goal", type="primary", use_container_width=True, key="create_goal_button"):
                planned_total_minutes = int(planned_hours) * 60 + int(planned_minutes_remainder)
                if not title.strip():
                    st.error("Goal title is required.")
                elif planned_total_minutes <= 0:
                    st.error("Planned total time must be greater than 0.")
                else:
                    try:
                        create_goal(
                            title=title,
                            description=description,
                            category_id=selected_category_id,
                            planned_total_minutes=planned_total_minutes,
                            start_date=start_date,
                            target_end_date=target_end_date,
                        )
                    except ValueError as error:
                        st.error(str(error))
                    else:
                        st.success("Goal created.")
                        st.rerun()
        with spacer_col:
            st.markdown(
                """
                <div class="hq-side-note">
                    <strong>Progress source</strong>
                    <span>Linked one-time quest sessions update this goal. XP is still awarded only by completed check-ins.</span>
                </div>
                """,
                unsafe_allow_html=True,
            )


def render_goal_management(category_options: dict[str, int]) -> None:
    goals = list_goals()

    category_names_by_id = {category_id: name for name, category_id in category_options.items()}
    with st.expander("Manage Goals", expanded=False):
        if not goals:
            st.markdown(
                """
                <div class="hq-empty-compact">
                    <strong>No goals to manage yet.</strong>
                    <span>Create a goal first, then lifecycle actions will appear here.</span>
                </div>
                """,
                unsafe_allow_html=True,
            )
            return

        for goal in goals:
            history = get_goal_history_summary(goal.id)
            category = category_names_by_id.get(goal.category_id, "Uncategorized")
            with st.container():
                detail_col, action_col = st.columns([0.58, 0.42], vertical_alignment="center")
                with detail_col:
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

                with action_col:
                    action_cols = st.columns(3)
                    with action_cols[0]:
                        if goal.status == "Active":
                            if st.button("Archive", key=f"goal_archive_{goal.id}", use_container_width=True):
                                archive_goal(goal.id)
                                st.session_state["goal_status_message"] = (
                                    "Goal archived. Existing linked quest history was preserved."
                                )
                                st.rerun()
                        elif goal.status == "Completed":
                            if st.button("Archive", key=f"goal_archive_{goal.id}", use_container_width=True):
                                archive_goal(goal.id)
                                st.session_state["goal_status_message"] = (
                                    "Goal archived. Existing linked quest history was preserved."
                                )
                                st.rerun()
                        else:
                            if st.button("Reopen", key=f"goal_reopen_{goal.id}", use_container_width=True):
                                reopen_goal(goal.id)
                                st.session_state["goal_status_message"] = "Goal reopened."
                                st.rerun()

                    with action_cols[1]:
                        if goal.status == "Active":
                            if st.button("Complete", key=f"goal_complete_{goal.id}", use_container_width=True):
                                complete_goal(goal.id)
                                st.session_state["goal_status_message"] = (
                                    "Goal marked as completed. Existing linked quest history was preserved."
                                )
                                st.rerun()
                        elif goal.status == "Completed":
                            if st.button("Reopen", key=f"goal_reopen_{goal.id}", use_container_width=True):
                                reopen_goal(goal.id)
                                st.session_state["goal_status_message"] = "Goal reopened."
                                st.rerun()

                    with action_cols[2]:
                        confirm_delete = st.checkbox(
                            "Confirm delete",
                            key=f"goal_confirm_delete_{goal.id}",
                        )
                        if st.button(
                            "Delete",
                            key=f"goal_delete_{goal.id}",
                            use_container_width=True,
                            disabled=not confirm_delete,
                        ):
                            delete_summary = delete_goal_if_unused(goal.id)
                            if delete_summary["deleted"]:
                                st.session_state["goal_status_message"] = "Unused goal deleted."
                            else:
                                st.session_state["goal_status_message"] = (
                                    "This goal has linked quest sessions and cannot be deleted safely. "
                                    "Archive it instead."
                                )
                                st.session_state["goal_status_warning"] = True
                            st.rerun()


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
    _ensure_checklist_period_state()
    selected_month = int(st.session_state["checklist_month"])
    selected_year = int(st.session_state["checklist_year"])
    category_names_by_id = {category_id: name for name, category_id in category_options.items()}

    status_message = st.session_state.pop("recurring_habit_status_message", None)
    if status_message:
        st.success(status_message)

    form_col, list_col = st.columns([0.4, 0.6], gap="medium")

    with form_col:
        st.write("**Create Recurring Habit**")
        st.caption("Define a template, then generate planned days for the selected month.")
        with st.container():
            habit_title = st.text_input(
                "Title",
                placeholder="Reading",
                key="recurring_habit_title",
            )
            habit_category_name = st.selectbox(
                "Category",
                list(category_options.keys()),
                key="recurring_habit_category",
            )

            minutes_col, active_col = st.columns([0.58, 0.42])
            with minutes_col:
                estimated_minutes = st.number_input(
                    "Estimated minutes",
                    min_value=1,
                    max_value=1440,
                    value=30,
                    step=5,
                    key="recurring_habit_estimated_minutes",
                )
            with active_col:
                is_active = st.checkbox("Active", value=True, key="recurring_habit_is_active")

            recurrence_preset = st.radio(
                "Recurrence",
                ["Every day", "Weekdays", "Custom selected weekdays"],
                horizontal=False,
                key="recurring_habit_preset",
            )
            if recurrence_preset == "Custom selected weekdays":
                selected_weekday_names = st.multiselect(
                    "Weekdays",
                    list(WEEKDAY_OPTIONS.keys()),
                    default=["Monday", "Wednesday", "Friday"],
                    key="recurring_habit_weekdays",
                )
                weekdays = [WEEKDAY_OPTIONS[name] for name in selected_weekday_names]
            else:
                weekdays = RECURRENCE_PRESETS[recurrence_preset]

            date_col, end_col = st.columns(2)
            with date_col:
                start_date = st.date_input(
                    "Start date",
                    value=st.session_state.get("selected_date", date.today()),
                    key="recurring_habit_start_date",
                )
            with end_col:
                has_end_date = st.checkbox("End date", value=False, key="recurring_habit_has_end_date")
                end_date = (
                    st.date_input(
                        "Final date",
                        value=start_date,
                        key="recurring_habit_end_date",
                    )
                    if has_end_date
                    else None
                )

            has_time_window = st.checkbox("Time window", value=False, key="recurring_habit_has_time_window")
            if has_time_window:
                start_time_col, end_time_col = st.columns(2)
                with start_time_col:
                    planned_start_time = st.time_input(
                        "Start Time",
                        value=time(9, 0),
                        step=300,
                        key="recurring_habit_start_time",
                    )
                with end_time_col:
                    planned_end_time = st.time_input(
                        "End Time",
                        value=time(10, 0),
                        step=300,
                        key="recurring_habit_end_time",
                    )
            else:
                planned_start_time = None
                planned_end_time = None

            description = st.text_area(
                "Notes",
                height=64,
                placeholder="Optional notes",
                key="recurring_habit_description",
            )

            if st.button("Create Recurring Habit", type="primary", use_container_width=True):
                try:
                    create_recurring_habit(
                        title=habit_title,
                        category_id=category_options[habit_category_name],
                        estimated_minutes=int(estimated_minutes),
                        recurrence_type="selected_weekdays",
                        weekdays=weekdays,
                        start_date=start_date,
                        end_date=end_date,
                        description=description,
                        is_active=is_active,
                        planned_start_time=planned_start_time,
                        planned_end_time=planned_end_time,
                    )
                except ValueError as error:
                    st.error(str(error))
                else:
                    st.session_state["recurring_habit_status_message"] = "Recurring habit created."
                    st.rerun()

    with list_col:
        st.write("**Recurring Habit Templates**")
        st.caption(
            f"Generate planned days for {month_name[selected_month]} {selected_year}. "
            "Change the month in Monthly Checklist."
        )
        st.caption("Deactivate stops future generation. Existing generated days remain for history.")

        habits = list_recurring_habits()
        if not habits:
            render_empty_state(
                "No recurring habits yet.",
                "Create one to generate planned quest days for the selected month.",
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

            if history_summary["generated_instances_count"] == 0:
                st.caption("No generated history exists, so this template can be deleted safely.")
                confirm_delete = st.checkbox(
                    "Confirm delete unused recurring habit",
                    key=f"recurring_habit_confirm_delete_{selected_habit.id}",
                )
                if st.button(
                    "Delete Template",
                    use_container_width=True,
                    disabled=not confirm_delete,
                    key="recurring_habit_delete",
                ):
                    delete_summary = delete_recurring_habit_if_unused(selected_habit.id)
                    if delete_summary["deleted"]:
                        st.session_state["recurring_habit_status_message"] = (
                            "Recurring habit deleted because it had no generated history."
                        )
                    else:
                        st.session_state["recurring_habit_status_message"] = (
                            "Recurring habit was not deleted because generated history exists."
                        )
                    st.rerun()
            else:
                st.info("This habit has generated history, so it will be archived/deactivated instead of deleted.")
                action_cols = st.columns(2)
                with action_cols[0]:
                    if st.button(
                        "Activate",
                        use_container_width=True,
                        disabled=selected_habit.is_active,
                        key="recurring_habit_activate",
                    ):
                        set_recurring_habit_active(selected_habit.id, True)
                        st.session_state["recurring_habit_status_message"] = "Recurring habit activated."
                        st.rerun()
                with action_cols[1]:
                    if st.button(
                        "Archive / Deactivate",
                        use_container_width=True,
                        disabled=not selected_habit.is_active,
                        key="recurring_habit_archive",
                    ):
                        archive_recurring_habit(selected_habit.id)
                        st.session_state["recurring_habit_status_message"] = (
                            "Recurring habit archived. Existing history was preserved."
                        )
                        st.rerun()

                if history_summary["removable_future_planned_count"] > 0:
                    st.caption(
                        "Remove only future unresolved Planned generated days. "
                        "Completed, skipped, and failed history will be preserved."
                    )
                    confirm_remove = st.checkbox(
                        "Confirm remove future planned days",
                        key=f"recurring_habit_confirm_remove_future_{selected_habit.id}",
                    )
                    if st.button(
                        "Remove Future Planned Days",
                        use_container_width=True,
                        disabled=not confirm_remove,
                        key="recurring_habit_remove_future",
                    ):
                        removal_summary = remove_future_planned_recurring_instances(selected_habit.id)
                        removed_count = removal_summary["removed_instances_count"]
                        if removed_count:
                            st.session_state["recurring_habit_status_message"] = (
                                f"Removed {removed_count} future planned days. "
                                "Completed, skipped, and failed history was preserved."
                            )
                        else:
                            st.session_state["recurring_habit_status_message"] = (
                                "No removable future planned days found."
                            )
                        st.rerun()
                else:
                    st.caption("No removable future planned days found.")

        st.divider()
        generation_summary = st.session_state.pop("recurring_generation_summary", None)
        if generation_summary:
            st.success(
                "Generated "
                f"{generation_summary['total_generated']} planned days. "
                f"{generation_summary['total_skipped_existing']} already existed. "
                f"{generation_summary['total_eligible']} eligible days checked."
            )

        if st.button("Generate Planned Days for Selected Month", use_container_width=True):
            try:
                summary = generate_all_recurring_habits_for_month(selected_year, selected_month)
            except ValueError as error:
                st.error(str(error))
            else:
                st.session_state["recurring_generation_summary"] = summary
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
    st.write("**Update Daily Status**")
    st.caption("Choose a quest and day, then apply a checklist status.")

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

    action_cols = st.columns(4)
    actions = (
        ("Complete", "Completed", "checklist_complete"),
        ("Skip", "Skipped", "checklist_skip"),
        ("Fail", "Failed", "checklist_fail"),
        ("Reset", "Planned", "checklist_reset"),
    )
    for column, (label, status, key) in zip(action_cols, actions):
        with column:
            if st.button(label, use_container_width=True, disabled=not cell_is_editable, key=key):
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


def _calculate_duration_minutes(start_time: time, end_time: time) -> int | None:
    try:
        planned_start_at, planned_end_at = validate_schedule_times(
            st.session_state["selected_date"],
            start_time,
            end_time,
        )
    except ValueError:
        return None
    return int((planned_end_at - planned_start_at).total_seconds() // 60)


def _calculate_duration_minutes_for_date(planned_date: date, start_time: time, end_time: time) -> int | None:
    try:
        planned_start_at, planned_end_at = validate_schedule_times(
            planned_date,
            start_time,
            end_time,
        )
    except ValueError:
        return None
    return int((planned_end_at - planned_start_at).total_seconds() // 60)


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
    st.caption("Plan one-time quests, review the selected day, and link sessions to active goals.")
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
        st.caption("Planned quests ordered by start time.")
        render_schedule_list(selected_day_quests)

    with planner_col:
        st.write("**New Quest**")
        st.caption("Add a scheduled quest to the selected day.")
        selected_date = st.session_state["selected_date"]
        default_start = time(9, 0)
        default_end = time(10, 0)

        with st.container():
            active_goals = list_active_goals()
            selected_goal_id = None
            selected_goal = None
            if active_goals:
                goal_options = [None] + [goal.id for goal in active_goals]
                goal_labels = {None: "None"} | {goal.id: goal.title for goal in active_goals}
                selected_goal_id = st.selectbox(
                    "Link to Goal / Project",
                    goal_options,
                    format_func=lambda goal_id: goal_labels[goal_id],
                )
                selected_goal = next((goal for goal in active_goals if goal.id == selected_goal_id), None)

            if selected_goal is None:
                title = st.text_input("Title", placeholder="Quest title")
            else:
                try:
                    title = preview_next_goal_session_title(selected_goal.id)
                except ValueError:
                    title = f"{selected_goal.title} Session"
                st.caption(f"New goal session: {title}")

            category_name = st.selectbox("Category", list(category_options.keys()))

            start_col, end_col = st.columns(2)
            with start_col:
                start_time = st.time_input("Start Time", value=default_start, step=300)
            with end_col:
                end_time = st.time_input("End Time", value=default_end, step=300)

            estimated_minutes = _calculate_duration_minutes(start_time, end_time)
            notes = st.text_area("Notes", height=64, placeholder="Optional notes")

            if estimated_minutes is None:
                st.error("End time must be after start time.")

            submitted = st.button("Add Quest", type="primary", use_container_width=True)
            if submitted:
                if selected_goal_id is None and not title.strip():
                    st.error("Every quest needs a title.")
                elif estimated_minutes is None:
                    st.error("End time must be after start time.")
                else:
                    try:
                        create_scheduled_quest(
                            title=title,
                            description=notes,
                            category_id=category_options[category_name],
                            planned_date=selected_date,
                            start_time=start_time,
                            end_time=end_time,
                            estimated_minutes=estimated_minutes,
                            goal_id=selected_goal_id,
                        )
                    except ValueError as error:
                        st.error(str(error))
                    else:
                        st.success("Quest scheduled.")
                        st.rerun()


def render_goals_projects_tab(category_options: dict[str, int]) -> None:
    st.caption("Create long-term goals, add planned sessions, and monitor linked quest progress.")
    render_section_title(
        "Goal Progress",
        "Track active long-term goals through linked one-time quest sessions.",
    )
    render_goal_progress_section(category_options)
    render_goal_creation_form(category_options)
    render_goal_management(category_options)


def render_recurring_habits_tab(category_options: dict[str, int]) -> None:
    st.caption("Manage recurring templates and generate planned quest days for the selected checklist month.")
    render_section_title("Recurring Habits", "Create templates and generate planned days for the selected month.")
    render_recurring_habits(category_options)


def render_monthly_checklist_tab() -> None:
    st.caption("Resolve scheduled quest days while preserving check-in XP idempotency.")
    render_section_title("Monthly Checklist", "Track daily quest completion for the selected month.")
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

calendar_tab, goals_tab, recurring_tab, checklist_tab = st.tabs(
    [
        "Calendar & Day Plan",
        "Goals / Projects",
        "Recurring Habits",
        "Monthly Checklist",
    ]
)

with calendar_tab:
    render_calendar_day_plan_tab(category_options)

with goals_tab:
    render_goals_projects_tab(category_options)

with recurring_tab:
    render_recurring_habits_tab(category_options)

with checklist_tab:
    render_monthly_checklist_tab()

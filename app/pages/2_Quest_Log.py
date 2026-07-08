from calendar import month_name
from datetime import date, datetime, time
import hashlib
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

try:
    from streamlit_calendar import calendar
except ImportError:
    calendar = None

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.constants import QUEST_DIFFICULTIES
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
from src.ui import apply_theme, render_empty_state, render_page_header, render_section_title


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


def render_calendar(calendar_events: list[dict], selected_date: date) -> None:
    if calendar is None:
        st.info("Calendar component unavailable. Use the selected date field below to plan quests.")
        return

    calendar_options = {
        "initialView": "timeGridWeek",
        "initialDate": selected_date.isoformat(),
        "selectable": True,
        "editable": False,
        "eventResizableFromStart": False,
        "height": "auto",
        "contentHeight": "auto",
        "expandRows": True,
        "stickyHeaderDates": True,
        "headerToolbar": {
            "left": "prev,next today",
            "center": "title",
            "right": "dayGridMonth,timeGridWeek,timeGridDay,listWeek",
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
        .fc {
            --fc-page-bg-color: rgba(15, 23, 42, 0);
            --fc-neutral-bg-color: rgba(15, 23, 42, 0.78);
            --fc-border-color: rgba(148, 163, 184, 0.18);
            --fc-today-bg-color: rgba(56, 189, 248, 0.08);
            color: #e5e7eb;
            min-height: 760px;
            width: 100%;
        }
        .fc .fc-view-harness {
            min-height: 660px;
        }
        .fc .fc-scroller,
        .fc .fc-scroller-liquid {
            scrollbar-color: rgba(139, 92, 246, 0.55) rgba(15, 23, 42, 0.42);
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
            border-color: rgba(148, 163, 184, 0.18);
        }
        .fc-theme-standard .fc-scrollgrid {
            border-radius: 8px;
            overflow: hidden;
            box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.03);
        }
        .fc .fc-col-header-cell {
            background: rgba(15, 23, 42, 0.9);
        }
        .fc .fc-col-header-cell-cushion,
        .fc .fc-timegrid-axis-cushion,
        .fc .fc-timegrid-slot-label-cushion {
            color: #cbd5e1;
            font-size: 0.78rem;
            font-weight: 700;
            text-decoration: none;
        }
        .fc .fc-toolbar-title {
            color: #f8fafc;
            font-size: 1.28rem;
            font-weight: 850;
        }
        .fc .fc-toolbar {
            gap: 0.75rem;
            margin-bottom: 0.85rem;
        }
        .fc .fc-button-primary {
            background: rgba(56, 189, 248, 0.18);
            border-color: rgba(56, 189, 248, 0.38);
            border-radius: 5px;
            box-shadow: none;
            color: #f8fafc;
            font-size: 0.82rem;
            font-weight: 750;
            padding: 0.42rem 0.62rem;
            transition: background-color 160ms ease, border-color 160ms ease, transform 160ms ease;
        }
        .fc .fc-button-primary:hover {
            background: rgba(56, 189, 248, 0.28);
            border-color: rgba(125, 211, 252, 0.58);
            transform: translateY(-1px);
        }
        .fc .fc-button-primary:not(:disabled).fc-button-active,
        .fc .fc-button-primary:not(:disabled):active {
            background: rgba(139, 92, 246, 0.48);
            border-color: rgba(196, 181, 253, 0.62);
        }
        .fc .fc-timegrid-slot {
            height: 2.15rem;
        }
        .fc .fc-daygrid-day.fc-day-today,
        .fc .fc-timegrid-col.fc-day-today {
            background: rgba(56, 189, 248, 0.08);
        }
        .fc .fc-timegrid-now-indicator-line {
            border-color: #f59e0b;
        }
        .fc .fc-timegrid-now-indicator-arrow {
            border-color: #f59e0b;
            border-bottom-color: transparent;
            border-top-color: transparent;
        }
        .fc .fc-event {
            border-radius: 5px;
            box-shadow: 0 8px 18px rgba(2, 6, 23, 0.24);
            padding: 0.12rem 0.18rem;
        }
        .fc .fc-timegrid-event {
            min-height: 26px;
        }
        .fc .fc-event-main {
            color: #f8fafc;
            overflow: hidden;
            padding: 0.12rem 0.2rem;
        }
        .fc .fc-event-time {
            color: rgba(248, 250, 252, 0.78);
            font-size: 0.72rem;
            font-weight: 700;
            line-height: 1.15;
            margin-bottom: 0.05rem;
            white-space: nowrap;
        }
        .fc .fc-event-title {
            color: #ffffff;
            font-size: 0.78rem;
            font-weight: 800;
            line-height: 1.18;
            overflow-wrap: anywhere;
        }
        .fc .fc-daygrid-event {
            padding: 0.14rem 0.3rem;
        }
        .fc .fc-daygrid-day-frame {
            min-height: 112px;
        }
        .fc .fc-list,
        .fc .fc-list-day-cushion {
            background: rgba(15, 23, 42, 0.72);
        }
        .fc .fc-list-event:hover td {
            background: rgba(30, 41, 59, 0.92);
        }
    """

    try:
        calendar_state = calendar(
            events=calendar_events,
            options=calendar_options,
            custom_css=custom_css,
            key=f"quest_calendar_{_calendar_events_signature(calendar_events)}",
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

    for quest in quests:
        with st.container(border=True):
            time_col, detail_col, xp_col = st.columns([0.26, 0.56, 0.18], vertical_alignment="center")
            with time_col:
                st.write(f"**{_format_time_range(quest)}**")
            with detail_col:
                st.write(f"**{quest.title}**")
                st.caption(f"{_category_name(quest)} | {quest.difficulty} | {_display_status(quest)}")
            with xp_col:
                st.write(f"**{quest.xp_reward or 0} XP**")


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
        category = category_names_by_id.get(goal.category_id, "Uncategorized")
        target = goal.target_end_date.isoformat() if goal.target_end_date else "No target date"
        skipped_failed = progress["skipped_sessions_count"] + progress["failed_sessions_count"]

        with st.container(border=True):
            header_col, progress_col, xp_col = st.columns([0.48, 0.3, 0.22], vertical_alignment="center")
            with header_col:
                st.write(f"**{goal.title}**")
                st.caption(f"{goal.status} | {category} | Target: {target}")
            with progress_col:
                st.write(
                    f"**{_format_minutes(progress['completed_minutes'])} / "
                    f"{_format_minutes(progress['planned_total_minutes'])}**"
                )
                st.caption(f"{progress_label} complete")
            with xp_col:
                st.write(f"**{progress['earned_xp']} / {progress['expected_total_xp']} XP**")
                st.caption("earned")

            st.progress(min(max(progress_percent / 100, 0), 1))
            st.caption(
                "Sessions: "
                f"{progress['completed_sessions_count']} completed | "
                f"{progress['planned_sessions_count']} planned | "
                f"{skipped_failed} skipped/failed"
            )
            render_goal_session_form(goal)


def render_goal_session_form(goal) -> None:
    with st.expander("Add Session", expanded=False):
        session_title = st.text_input(
            "Session Title",
            value=f"{goal.title} Session",
            key=f"goal_session_title_{goal.id}",
        )
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

        if st.button("Add Session", type="primary", use_container_width=True, key=f"goal_add_session_{goal.id}"):
            if not session_title.strip():
                st.error("Session title is required.")
            elif estimated_minutes is None:
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
        title = st.text_input("Goal Title", placeholder="Portfolio Project", key="new_goal_title")
        description = st.text_area(
            "Description / Notes",
            height=72,
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

        category_labels = ["No category"] + list(category_options.keys())
        selected_category_label = st.selectbox(
            "Category",
            category_labels,
            key="new_goal_category",
        )
        selected_category_id = (
            None
            if selected_category_label == "No category"
            else category_options[selected_category_label]
        )

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


def render_goal_management(category_options: dict[str, int]) -> None:
    goals = list_goals()
    if not goals:
        return

    category_names_by_id = {category_id: name for name, category_id in category_options.items()}
    with st.expander("Manage Goals", expanded=False):
        for goal in goals:
            history = get_goal_history_summary(goal.id)
            category = category_names_by_id.get(goal.category_id, "Uncategorized")
            with st.container(border=True):
                detail_col, action_col = st.columns([0.58, 0.42], vertical_alignment="center")
                with detail_col:
                    st.write(f"**{goal.title}**")
                    st.caption(
                        f"{goal.status} | {category} | "
                        f"{history['linked_quests_count']} linked sessions | "
                        f"{history['earned_xp']} XP earned"
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

    form_col, list_col = st.columns([0.42, 0.58], gap="large")

    with form_col:
        st.write("**Create Recurring Habit**")
        st.caption("Define a template, then generate planned days for the selected month.")
        with st.container(border=True):
            habit_title = st.text_input(
                "Title",
                placeholder="Reading",
                key="recurring_habit_title",
            )
            category_col, difficulty_col = st.columns([1.15, 0.85])
            with category_col:
                habit_category_name = st.selectbox(
                    "Category",
                    list(category_options.keys()),
                    key="recurring_habit_category",
                )
            with difficulty_col:
                habit_difficulty = st.selectbox(
                    "Difficulty",
                    list(QUEST_DIFFICULTIES),
                    key="recurring_habit_difficulty",
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
                        difficulty=habit_difficulty,
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
            st.dataframe(
                _build_recurring_habits_dataframe(habits, category_names_by_id),
                width="stretch",
                hide_index=True,
                height=min(360, 92 + (len(habits) * 35)),
            )

            st.divider()
            selected_habit = st.selectbox(
                "Manage recurring habit",
                habits,
                format_func=lambda habit: f"{habit.title} | {_format_habit_pattern(habit)} | {_active_label(habit)}",
                key="recurring_habit_manage",
            )
            history_summary = get_recurring_habit_history_summary(selected_habit.id)
            st.caption(
                f"{history_summary['generated_instances_count']} generated days | "
                f"{history_summary['planned_count']} planned | "
                f"{history_summary['completed_count']} completed | "
                f"{history_summary['skipped_count']} skipped | "
                f"{history_summary['failed_count']} failed"
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

    checklist_df = _build_checklist_dataframe(checklist)
    st.dataframe(
        checklist_df,
        width="stretch",
        hide_index=True,
        height=min(420, 92 + (len(checklist_df) * 35)),
    )

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
    cell_is_editable = is_checklist_cell_editable(selected_row, selected_checklist_date)
    current_status = (
        CHECKLIST_STATUS_LABELS.get(selected_cell["status"], "Unknown")
        if cell_is_editable
        else "Locked - Not scheduled"
    )

    with status_col:
        marker = CHECKLIST_STATUS_MARKERS.get(selected_cell["status"], "")
        status_prefix = f"{marker} - " if marker and cell_is_editable else ""
        st.info(f"Current: {status_prefix}{current_status}")
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
                    update_checklist_cell_status(selected_row, selected_checklist_date, status)
                except ValueError as error:
                    st.warning(str(error))
                    continue
                st.session_state["pending_selected_date"] = selected_checklist_date
                st.session_state["checklist_status_message"] = (
                    f"{label} saved for {selected_checklist_date:%Y-%m-%d}."
                )
                st.rerun()

    _render_checklist_delete_action(selected_row, selected_cell, selected_checklist_date, cell_is_editable)


def _render_checklist_legend() -> None:
    legend_items = (
        ("blank", "Not scheduled / locked"),
        ("P", "Planned"),
        ("C", "Completed"),
        ("S", "Skipped"),
        ("F", "Failed"),
    )
    legend_cols = st.columns(len(legend_items))
    for column, (marker, label) in zip(legend_cols, legend_items):
        column.caption(f"{marker} = {label}")


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
        key=f"checklist_confirm_delete_{row.get('row_id')}_{selected_date.isoformat()}",
        disabled=not is_unresolved,
    )
    if st.button(
        button_label,
        use_container_width=True,
        disabled=not is_unresolved or not confirm_delete,
        key=f"checklist_delete_{row.get('row_id')}",
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


def _build_checklist_dataframe(checklist: dict) -> pd.DataFrame:
    rows = []
    for row in checklist["rows"]:
        table_row = {
            "Quest": row["title"],
            "Category": row["category"] or "Uncategorized",
            "Difficulty": row["difficulty"],
        }
        for day in checklist["days"]:
            table_row[str(day.day)] = CHECKLIST_STATUS_MARKERS.get(row["cells"][day]["status"], "")
        rows.append(table_row)
    return pd.DataFrame(rows)


def _checklist_row_id(row: dict) -> str:
    return row.get("row_id") or f"quest:{row['quest_id']}"


def _build_checklist_quest_labels(rows: list[dict]) -> dict[str, str]:
    base_labels = {
        _checklist_row_id(row): f"{row['title']} | {row['category'] or 'Uncategorized'} | {row['difficulty']}"
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
    if current_page_date in days and row["cells"][current_page_date]["status"] is not None:
        return current_page_date

    for day in days:
        if row["cells"][day]["status"] is not None:
            return day

    return days[0]


def _build_recurring_habits_dataframe(habits: list, category_names_by_id: dict[int, str]) -> pd.DataFrame:
    rows = [
        {
            "Habit": habit.title,
            "Category": category_names_by_id.get(habit.category_id, "Uncategorized"),
            "Difficulty": habit.difficulty,
            "Pattern": _format_habit_pattern(habit),
            "Minutes": habit.estimated_minutes,
            "Time": _format_habit_time_window(habit),
            "Start": habit.start_date.isoformat(),
            "End": habit.end_date.isoformat() if habit.end_date else "",
            "Active": _active_label(habit),
        }
        for habit in habits
    ]
    return pd.DataFrame(rows)


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
    with st.container(border=True):
        render_calendar(calendar_events, st.session_state["selected_date"])

    selected_day_quests = get_quests_for_day(st.session_state["selected_date"])

    render_section_title("Selected Day Board")
    with st.container(border=True):
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

        with st.container(border=True):
            title = st.text_input("Title", placeholder="Quest title")

            category_col, difficulty_col = st.columns([1.15, 0.85])
            with category_col:
                category_name = st.selectbox("Category", list(category_options.keys()))
            with difficulty_col:
                difficulty = st.selectbox("Difficulty", list(QUEST_DIFFICULTIES))

            start_col, end_col = st.columns(2)
            with start_col:
                start_time = st.time_input("Start Time", value=default_start, step=300)
            with end_col:
                end_time = st.time_input("End Time", value=default_end, step=300)

            estimated_minutes = _calculate_duration_minutes(start_time, end_time)
            notes = st.text_area("Notes", height=64, placeholder="Optional notes")
            active_goals = list_active_goals()
            selected_goal_id = None
            if active_goals:
                goal_options = [None] + [goal.id for goal in active_goals]
                goal_labels = {None: "None"} | {goal.id: goal.title for goal in active_goals}
                selected_goal_id = st.selectbox(
                    "Link to Goal / Project",
                    goal_options,
                    format_func=lambda goal_id: goal_labels[goal_id],
                )

            if estimated_minutes is None:
                st.error("End time must be after start time.")

            submitted = st.button("Add Quest", type="primary", use_container_width=True)
            if submitted:
                if not title.strip():
                    st.error("Every quest needs a title.")
                elif estimated_minutes is None:
                    st.error("End time must be after start time.")
                else:
                    try:
                        create_scheduled_quest(
                            title=title,
                            description=notes,
                            category_id=category_options[category_name],
                            difficulty=difficulty,
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
    with st.container(border=True):
        render_goal_progress_section(category_options)
        render_goal_creation_form(category_options)
        render_goal_management(category_options)


def render_recurring_habits_tab(category_options: dict[str, int]) -> None:
    st.caption("Manage recurring templates and generate planned quest days for the selected checklist month.")
    render_section_title("Recurring Habits", "Create templates and generate planned days for the selected month.")
    with st.container(border=True):
        render_recurring_habits(category_options)


def render_monthly_checklist_tab() -> None:
    st.caption("Resolve scheduled quest days while preserving check-in XP idempotency.")
    render_section_title("Monthly Checklist", "Track daily quest completion for the selected month.")
    with st.container(border=True):
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

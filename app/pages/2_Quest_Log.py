from datetime import date, datetime, time
import hashlib
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

from app.components.plan_form import render_plan_form
from app.components.planner_month_review import render_month_checklist, render_month_review_controls
from src.database.db import init_db
from src.database.seed import ensure_default_categories
from src.services.goal_service import list_active_goals
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
    delete_recurring_generated_occurrence_if_unresolved,
    generate_recurring_habit_for_month,
)
from src.ui import get_theme_tokens, render_empty_state, render_page_header, render_section_title


def render_calendar(calendar_events: list[dict], selected_date: date) -> None:
    if calendar is None:
        st.info("Calendar component unavailable.")
        return

    tokens = get_theme_tokens()
    calendar_height = 650
    calendar_content_height = 590
    calendar_options = {
        "initialView": "dayGridMonth",
        "initialDate": selected_date.isoformat(),
        "firstDay": 1,
        "selectable": True,
        "editable": False,
        "eventResizableFromStart": False,
        "height": calendar_height,
        "contentHeight": calendar_content_height,
        "expandRows": False,
        "handleWindowResize": True,
        "stickyHeaderDates": True,
        "headerToolbar": {
            "left": "",
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
            box-shadow: none;
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
        @media (max-width: 520px) {
            .fc .fc-toolbar {
                flex-wrap: wrap;
                gap: 0.5rem;
            }
            .fc .fc-header-toolbar .fc-toolbar-chunk:empty {
                display: none;
            }
            .fc .fc-col-header-cell-cushion {
                padding-inline: 2px;
            }
            .fc .fc-daygrid-more-link,
            .fc .fc-daygrid-event {
                font-size: 0.72rem;
            }
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
            color: var(--hq-accent-foreground);
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
        @media (max-width: 520px) {
            .fc .fc-daygrid-event .fc-event-main {
                min-width: 0;
                padding-inline: 0.05rem;
            }
            .fc .fc-daygrid-event .fc-event-title {
                overflow: hidden;
                text-overflow: ellipsis;
                white-space: nowrap;
            }
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
        custom_css.replace("var(--hq-calendar-height)", f"{calendar_height}px")
        .replace("var(--hq-calendar-content-height)", f"{calendar_content_height}px")
        .replace("var(--hq-muted-surface)", tokens["muted_surface"])
        .replace("var(--hq-accent-soft)", tokens["accent_soft"])
        .replace("var(--hq-border)", tokens["border"])
        .replace("var(--hq-text-primary)", tokens["text_primary"])
        .replace("var(--hq-text-secondary)", tokens["text_secondary"])
        .replace("var(--hq-accent-border)", tokens["accent_border"])
        .replace("var(--hq-surface-elevated)", tokens["surface_elevated"])
        .replace("var(--hq-surface)", tokens["surface"])
        .replace("var(--hq-accent)", tokens["accent"])
        .replace("var(--hq-accent-foreground)", tokens["accent_foreground"])
        .replace("var(--hq-warning)", tokens["warning"])
    )

    try:
        calendar_revision = st.session_state.get("planner_calendar_revision", 0)
        calendar_state = calendar(
            events=calendar_events,
            options=calendar_options,
            custom_css=custom_css,
            callbacks=["dateClick", "select", "eventClick"],
            key=(
                f"quest_calendar_{tokens['mode']}_"
                f"{selected_date.isoformat()}_{calendar_revision}_"
                f"{_calendar_events_signature(calendar_events)}"
            ),
        )
    except Exception as error:
        st.warning(f"Calendar component could not render. Use the selected date field below. Details: {error}")
        return

    clicked_date = _extract_calendar_date(calendar_state)
    if clicked_date and clicked_date != st.session_state["selected_date"]:
        st.session_state["selected_date"] = clicked_date
        st.session_state["planner_manage_date"] = clicked_date


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


def _save_plan_result(draft) -> None:
    try:
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
            generate_recurring_habit_for_month(
                habit.id,
                draft.planned_date.year,
                draft.planned_date.month,
            )
            st.session_state["plan_status_message"] = "Routine created and added to this month's plan."
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


@st.dialog("Add item", width="medium", on_dismiss="rerun")
def _add_item_dialog(category_options: dict[str, int]) -> None:
    active_goals = list_active_goals()
    form_result = render_plan_form(
        category_options=category_options,
        active_goals=active_goals,
        selected_date=st.session_state["selected_date"],
        goal_title_by_id={goal.id: goal.title for goal in active_goals},
    )
    if form_result is not None:
        _save_plan_result(form_result)


def _display_status(quest) -> str:
    return getattr(quest, "display_status", None) or quest.status or "Planned"


def _format_time_range(quest) -> str:
    if quest.planned_start_at and quest.planned_end_at:
        return f"{quest.planned_start_at:%H:%M} - {quest.planned_end_at:%H:%M}"
    return "All day"


def _category_name(quest) -> str:
    return quest.category.name if quest.category else "Uncategorized"


def _render_planned_item_list(quests: list, category_options: dict[str, int]) -> None:
    if not quests:
        render_empty_state("No items for this day.", "Choose another date or add a new item.")
        return

    for quest in quests:
        status = _display_status(quest)
        is_recurring = quest.recurring_habit_instance is not None
        with st.container(border=True):
            details_col, actions_col = st.columns([0.68, 0.32], vertical_alignment="center")
            with details_col:
                st.caption(_format_time_range(quest))
                st.write(f"**{quest.title}**")
                st.caption(f"{_category_name(quest)} / {status} / {int(quest.xp_reward or 0)} XP")
            with actions_col:
                if status != "Planned":
                    st.caption("Status in Command Center")
                    continue
                if is_recurring:
                    st.caption("Edit the routine in Projects & Routines")
                elif st.button("Edit", key=f"edit_planned_quest_{quest.id}", width="stretch"):
                    _edit_planned_item_dialog(quest, category_options)
                if st.button("Remove", key=f"remove_planned_quest_{quest.id}", width="stretch"):
                    _remove_planned_item_dialog(quest)


@st.dialog("Edit planned item", width="medium", on_dismiss="rerun")
def _edit_planned_item_dialog(quest, category_options: dict[str, int]) -> None:
    key_prefix = f"edit_planned_quest_{quest.id}"
    is_goal_session = quest.goal_id is not None
    if is_goal_session:
        st.text_input("Title", value=quest.title, disabled=True, key=f"{key_prefix}_title")
        title = quest.title
    else:
        title = st.text_input("Title", value=quest.title, key=f"{key_prefix}_title")

    category_names = list(category_options)
    current_category_name = next(
        (name for name, category_id in category_options.items() if category_id == quest.category_id),
        category_names[0],
    )
    category_name = st.selectbox(
        "Category",
        category_names,
        index=category_names.index(current_category_name),
        disabled=is_goal_session,
        key=f"{key_prefix}_category",
    )
    planned_date = st.date_input(
        "Date",
        value=quest.due_date or st.session_state["planner_manage_date"],
        key=f"{key_prefix}_date",
    )
    default_start_time = (quest.planned_start_at or datetime.combine(planned_date, time(9, 0))).time()
    default_end_time = (quest.planned_end_at or datetime.combine(planned_date, time(10, 0))).time()
    start_col, end_col = st.columns(2)
    with start_col:
        start_time = st.time_input("Start time", value=default_start_time, step=300, key=f"{key_prefix}_start")
    with end_col:
        end_time = st.time_input("End time", value=default_end_time, step=300, key=f"{key_prefix}_end")

    estimated_minutes = int(
        (datetime.combine(planned_date, end_time) - datetime.combine(planned_date, start_time)).total_seconds() // 60
    )
    has_valid_time_range = estimated_minutes > 0
    if not has_valid_time_range:
        st.error("End time must be after start time.")
    notes = st.text_area("Notes (optional)", value=quest.description or "", height=72, key=f"{key_prefix}_notes")
    save_col, cancel_col = st.columns(2)
    with save_col:
        save_clicked = st.button(
            "Save changes",
            type="primary",
            use_container_width=True,
            disabled=not has_valid_time_range,
            key=f"{key_prefix}_save",
        )
    with cancel_col:
        cancel_clicked = st.button("Cancel", use_container_width=True, key=f"{key_prefix}_cancel")

    if cancel_clicked:
        st.rerun()
    if not save_clicked:
        return
    if not title.strip():
        st.error("A title is required.")
        return

    try:
        update_one_time_quest_if_unresolved(
            quest.id,
            title=title,
            description=notes,
            category_id=category_options[category_name],
            planned_date=planned_date,
            start_time=start_time,
            end_time=end_time,
            estimated_minutes=estimated_minutes,
        )
    except ValueError as error:
        st.error(str(error))
        return

    st.session_state["pending_planner_manage_date"] = planned_date
    _set_planner_day(planned_date)
    st.session_state["planner_overview_status_message"] = "Planned item updated."
    st.rerun()


@st.dialog("Remove planned item", on_dismiss="rerun")
def _remove_planned_item_dialog(quest) -> None:
    st.write(quest.title)
    is_recurring = quest.recurring_habit_instance is not None
    item_label = "this routine day" if is_recurring else "this planned task"
    st.warning(f"Remove {item_label}? This cannot be undone.")
    st.caption("Completed, skipped, failed, and XP-awarded items are always preserved.")
    confirmed = st.checkbox(f"Confirm removal of {item_label}", key=f"confirm_remove_planned_quest_{quest.id}")
    remove_col, cancel_col = st.columns(2)
    with remove_col:
        remove_clicked = st.button(
            "Remove planned item",
            type="primary",
            use_container_width=True,
            disabled=not confirmed,
            key=f"confirm_remove_planned_quest_button_{quest.id}",
        )
    with cancel_col:
        cancel_clicked = st.button("Cancel", use_container_width=True, key=f"cancel_remove_planned_quest_{quest.id}")

    if cancel_clicked:
        st.rerun()
    if not remove_clicked:
        return

    try:
        summary = (
            delete_recurring_generated_occurrence_if_unresolved(quest.id)
            if is_recurring
            else delete_one_time_quest_if_unresolved(quest.id)
        )
    except ValueError as error:
        st.error(str(error))
        return
    if not summary["deleted"]:
        st.warning(summary.get("reason") or "This planned item could not be removed.")
        return

    st.session_state["planner_overview_status_message"] = "Planned item removed."
    st.rerun()


def _set_planner_day(selected_day: date) -> None:
    """Reset the calendar's previous event when the day changes outside the calendar."""
    st.session_state["selected_date"] = selected_day
    st.session_state["planner_calendar_revision"] = st.session_state.get("planner_calendar_revision", 0) + 1


def _render_day_management_panel(category_options: dict[str, int]) -> None:
    pending_date = st.session_state.pop("pending_planner_manage_date", None)
    if pending_date is not None:
        st.session_state["planner_manage_date"] = pending_date
    if "planner_manage_date" not in st.session_state:
        st.session_state["planner_manage_date"] = st.session_state["selected_date"]
    selected_day = st.date_input(
        "Selected day",
        key="planner_manage_date",
        on_change=lambda: _set_planner_day(st.session_state["planner_manage_date"]),
    )
    _render_planned_item_list(get_quests_for_day(selected_day), category_options)


render_page_header("Planner", "Schedule tasks, routines, and project sessions.")

init_db()
ensure_default_categories()
categories = get_categories()
category_options = {category.name: category.id for category in categories}

if not category_options:
    st.warning("Run python -m src.database.seed to create default categories.")
    st.stop()

if "selected_date" not in st.session_state:
    st.session_state["selected_date"] = date.today()

month_col, action_col = st.container(key="hq_planner_toolbar").columns(
    [0.68, 0.32], gap="large", vertical_alignment="bottom"
)
with month_col:
    selected_year, selected_month = render_month_review_controls(st.session_state["selected_date"])
with action_col:
    if st.button("Add item", type="primary", icon=":material/add:", width="stretch"):
        _add_item_dialog(category_options)

for message_key in ("plan_status_message", "planner_overview_status_message"):
    if message := st.session_state.pop(message_key, None):
        st.success(message)

calendar_tab, checklist_tab = st.tabs(
    ["Calendar", "Monthly checklist"], key="planner_tab", on_change="rerun"
)

if calendar_tab.open:
    with calendar_tab:
        calendar_col, day_col = st.container(key="hq_calendar").columns([0.68, 0.32], gap="large")
        with calendar_col:
            render_calendar(get_quests_for_calendar(), date(selected_year, selected_month, 1))
        with day_col:
            _render_day_management_panel(category_options)

if checklist_tab.open:
    with checklist_tab:
        render_month_checklist(selected_year, selected_month)

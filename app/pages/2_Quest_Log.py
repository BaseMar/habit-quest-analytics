from calendar import month_name
from datetime import date, datetime
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

from app.components.plan_form import render_plan_form
from src.database.db import init_db
from src.database.seed import ensure_default_categories
from src.services.checklist_service import get_month_checklist
from src.services.goal_service import create_goal, list_active_goals
from src.services.quest_service import (
    create_scheduled_quest,
    get_categories,
    get_quests_for_calendar,
)
from src.services.recurring_habit_service import (
    create_recurring_habit,
    generate_recurring_habit_for_month,
)
from src.ui import apply_theme, get_theme_tokens, render_empty_state, render_page_header, render_section_title


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


def render_calendar(
    calendar_events: list[dict],
    selected_date: date,
    fixed_view_label: str | None = None,
) -> None:
    if calendar is None:
        st.info("Calendar component unavailable.")
        return

    tokens = get_theme_tokens()
    if fixed_view_label is None:
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
    else:
        selected_view_label = fixed_view_label
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
            "left": "" if fixed_view_label is not None else "prev,next today",
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


def _render_month_review_controls() -> tuple[int, int]:
    month_col, year_col = st.columns([0.64, 0.36], vertical_alignment="bottom")
    with month_col:
        selected_month_name = st.selectbox(
            "Month",
            list(month_name)[1:],
            index=st.session_state["checklist_month"] - 1,
            key="checklist_month_name",
        )
        selected_month = list(month_name).index(selected_month_name)
        st.session_state["checklist_month"] = selected_month
    with year_col:
        selected_year = int(
            st.number_input(
                "Year",
                min_value=2000,
                max_value=2100,
                value=int(st.session_state["checklist_year"]),
                step=1,
                key="checklist_year_input",
            )
        )
        st.session_state["checklist_year"] = selected_year
    return selected_year, selected_month


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
    headers = ["Item", "Category"] + [str(day.day) for day in checklist["days"]]
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


def _save_plan_result(form_result) -> None:
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


def render_add_item_tab(category_options: dict[str, int]) -> None:
    status_message = st.session_state.pop("plan_status_message", None)
    if status_message:
        st.success(status_message)
    _, form_col, _ = st.columns([0.2, 0.6, 0.2])
    with form_col:
        with st.container(border=True):
            active_goals = list_active_goals()
            form_result = render_plan_form(
                category_options=category_options,
                active_goals=active_goals,
                selected_date=st.session_state["selected_date"],
                goal_title_by_id={goal.id: goal.title for goal in active_goals},
            )
            if form_result is not None:
                _save_plan_result(form_result)


def render_month_overview_tab() -> None:
    _ensure_checklist_period_state()
    selected_year, selected_month = _render_month_review_controls()
    selected_month_date = date(selected_year, selected_month, 1)
    render_calendar(get_quests_for_calendar(), selected_month_date, fixed_view_label="Month")

    checklist = get_month_checklist(selected_year, selected_month)
    _render_checklist_legend()
    if not checklist["rows"]:
        render_empty_state(
            "No planned items for this month yet.",
            "Add tasks in the Add item tab to start tracking this month.",
        )
        return
    _render_checklist_table(checklist)


apply_theme()
render_page_header(
    "Plan your day",
    "Quest Planner",
    "Schedule one-time tasks, routines, and project sessions in one place.",
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

add_item_tab, month_overview_tab = st.tabs(
    [
        "Add item",
        "Month overview",
    ]
)

with add_item_tab:
    render_add_item_tab(category_options)

with month_overview_tab:
    render_month_overview_tab()

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

from app.components.plan_form import render_plan_form
from app.components.scheduling import duration_crosses_midnight, end_at_for_duration
from src.database.db import init_db
from src.database.seed import ensure_default_categories
from src.services.checklist_service import get_month_checklist
from src.services.goal_service import create_goal, list_active_goals
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


def render_calendar(calendar_events: list[dict], selected_date: date) -> None:
    if calendar is None:
        st.info("Calendar component unavailable. Use the selected date field below to plan tasks.")
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


def render_schedule_list(quests: list) -> None:
    if not quests:
        st.info("No tasks planned for this day.")
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
                    st.session_state.pop("deleting_day_quest_id", None)
                    st.session_state["editing_day_quest_id"] = quest.id
                    st.rerun()
        with row_cols[2]:
            st.caption(f"{int(quest.xp_reward or 0)} XP")
        with row_cols[3]:
            if status == "Planned":
                if st.button("Remove", key=f"remove_day_quest_{quest.id}"):
                    st.session_state.pop("editing_day_quest_id", None)
                    st.session_state["deleting_day_quest_id"] = quest.id
                    st.rerun()
            else:
                st.caption("Manage status in Command Center.")
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

        end_at = end_at_for_duration(planned_date, start_time, duration_minutes)
        if duration_crosses_midnight(planned_date, start_time, duration_minutes):
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
                disabled=duration_crosses_midnight(planned_date, start_time, duration_minutes),
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
            st.session_state["plan_status_message"] = "Planned item updated."
            st.rerun()


def render_day_item_delete_action(quests: list) -> None:
    deleting_quest_id = st.session_state.get("deleting_day_quest_id")
    if deleting_quest_id is None:
        return

    quest = next((item for item in quests if item.id == deleting_quest_id), None)
    if quest is None:
        st.session_state.pop("deleting_day_quest_id", None)
        return

    with st.expander("Remove planned item", expanded=True):
        if _display_status(quest) != "Planned":
            st.warning("Only unresolved planned items can be removed.")
            return

        is_recurring = quest.recurring_habit_instance is not None
        item_label = "this routine day" if is_recurring else "this planned task"
        st.warning(f"Remove {item_label}? This cannot be undone.")
        st.caption("Completed, skipped, failed, and XP-awarded items are always preserved.")
        confirm_delete = st.checkbox(
            f"Confirm removal of {item_label}",
            key=f"confirm_remove_day_quest_{quest.id}",
        )
        remove_col, cancel_col = st.columns(2)
        with remove_col:
            remove_clicked = st.button(
                "Remove planned item",
                type="primary",
                use_container_width=True,
                disabled=not confirm_delete,
                key=f"confirm_remove_day_quest_button_{quest.id}",
            )
        with cancel_col:
            cancel_clicked = st.button(
                "Cancel",
                use_container_width=True,
                key=f"cancel_remove_day_quest_{quest.id}",
            )

        if cancel_clicked:
            st.session_state.pop("deleting_day_quest_id", None)
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

        st.session_state.pop("deleting_day_quest_id", None)
        st.session_state["plan_status_message"] = "Planned item removed."
        st.rerun()


def render_day_summary(quests: list) -> None:
    quest_count = len(quests)
    planned_minutes = sum(_quest_duration_minutes(quest) for quest in quests)
    planned_xp = sum(quest.xp_reward or 0 for quest in quests)
    completed_count = sum(1 for quest in quests if _display_status(quest).strip().lower() == "completed")
    quest_col, time_col, xp_col, complete_col = st.columns(4)
    quest_col.metric("Tasks", f"{quest_count} {_pluralize('task', quest_count)}")
    time_col.metric("Planned Time", _format_minutes(planned_minutes))
    xp_col.metric("Planned XP", f"{planned_xp} XP")
    complete_col.metric("Completed", completed_count)


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


def render_monthly_checklist() -> None:
    _ensure_checklist_period_state()
    selected_year, selected_month = _render_month_review_controls()
    checklist = get_month_checklist(selected_year, selected_month)
    _render_checklist_legend()

    if not checklist["rows"]:
        render_empty_state(
            "No planned items for this month yet.",
            "Add tasks in Plan to start tracking this month.",
        )
        return

    _render_checklist_table(checklist)


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
    st.caption("Plan tasks, repeating routines, and project sessions from one place.")
    calendar_events = get_quests_for_calendar()

    render_section_title("Calendar", "Review planned items and select a day to build its schedule.")
    with st.container():
        render_calendar(calendar_events, st.session_state["selected_date"])

    selected_day_quests = get_quests_for_day(st.session_state["selected_date"])

    render_section_title("Selected Day Board")
    with st.container():
        header_left, header_right = st.columns([0.68, 0.32], vertical_alignment="center")
        with header_left:
            st.subheader(_format_selected_date(st.session_state["selected_date"]))
            st.caption("Daily plan for the selected calendar date.")
        with header_right:
            st.date_input("Selected date", key="selected_date")

        render_day_summary(selected_day_quests)

        schedule_col, planner_col = st.columns([0.6, 0.4], gap="large")

    with schedule_col:
        st.write("**Planned work**")
        render_schedule_list(selected_day_quests)
        render_day_item_editor(selected_day_quests, category_options)
        render_day_item_delete_action(selected_day_quests)

    with planner_col:
        st.write("**Add to plan**")
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


def render_monthly_review_tab() -> None:
    st.caption("Review the selected month. Generate missing routine days in Projects & Routines.")
    render_section_title("Monthly Review", "View the planned and completed work for the selected month.")
    render_monthly_checklist()


apply_theme()
render_page_header(
    "Daily Planning",
    "Quest Planner",
    "Build the calendar for one-time tasks, routines, and project sessions.",
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

plan_tab, review_tab = st.tabs(
    [
        "Plan",
        "Monthly Review",
    ]
)

with plan_tab:
    render_calendar_day_plan_tab(category_options)

with review_tab:
    render_monthly_review_tab()

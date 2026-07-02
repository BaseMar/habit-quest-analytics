from calendar import month_name
from datetime import date, datetime, time
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
    complete_checkin,
    fail_checkin,
    get_month_checklist,
    reset_checkin,
    skip_checkin,
)
from src.services.quest_service import (
    create_scheduled_quest,
    get_categories,
    get_quests_for_calendar,
    get_quests_for_day,
    validate_schedule_times,
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
            key="quest_calendar",
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
                st.caption(f"{_category_name(quest)} | {quest.difficulty} | {quest.status}")
            with xp_col:
                st.write(f"**{quest.xp_reward or 0} XP**")


def render_day_summary(quests: list) -> None:
    quest_count = len(quests)
    planned_minutes = sum(_quest_duration_minutes(quest) for quest in quests)
    planned_xp = sum(quest.xp_reward or 0 for quest in quests)
    completed_count = sum(1 for quest in quests if (quest.status or "").strip().lower() == "completed")
    quest_col, time_col, xp_col, complete_col = st.columns(4)
    quest_col.metric("Quests", f"{quest_count} {_pluralize('quest', quest_count)}")
    time_col.metric("Planned Time", _format_minutes(planned_minutes))
    xp_col.metric("Planned XP", f"{planned_xp} XP")
    complete_col.metric("Completed", completed_count)


def render_monthly_checklist() -> None:
    today = date.today()
    selected_date = st.session_state.get("selected_date", today)

    if "checklist_month" not in st.session_state:
        st.session_state["checklist_month"] = selected_date.month
    if "checklist_year" not in st.session_state:
        st.session_state["checklist_year"] = selected_date.year

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

    row_lookup = {row["quest_id"]: row for row in checklist["rows"]}
    quest_labels = _build_checklist_quest_labels(checklist["rows"])
    editor_col, status_col = st.columns([0.68, 0.32], gap="large")

    if st.session_state.get("checklist_selected_quest") not in row_lookup:
        st.session_state["checklist_selected_quest"] = next(iter(row_lookup))
    if st.session_state.get("checklist_selected_date") not in checklist["days"]:
        st.session_state["checklist_selected_date"] = checklist["days"][0]

    with editor_col:
        quest_col, date_col = st.columns([0.62, 0.38])
        with quest_col:
            selected_quest_id = st.selectbox(
                "Quest",
                list(row_lookup.keys()),
                format_func=lambda quest_id: quest_labels[quest_id],
                key="checklist_selected_quest",
            )
        with date_col:
            selected_checklist_date = st.selectbox(
                "Date",
                checklist["days"],
                format_func=lambda day: day.strftime("%b %d"),
                key="checklist_selected_date",
            )

    selected_row = row_lookup[selected_quest_id]
    selected_cell = selected_row["cells"][selected_checklist_date]
    current_status = CHECKLIST_STATUS_LABELS.get(selected_cell["status"], "Unknown")

    with status_col:
        marker = CHECKLIST_STATUS_MARKERS.get(selected_cell["status"], "")
        status_prefix = f"{marker} - " if marker else ""
        st.info(f"Current: {status_prefix}{current_status}")

    action_cols = st.columns(4)
    actions = (
        ("Complete", complete_checkin, "checklist_complete"),
        ("Skip", skip_checkin, "checklist_skip"),
        ("Fail", fail_checkin, "checklist_fail"),
        ("Reset", reset_checkin, "checklist_reset"),
    )
    for column, (label, action, key) in zip(action_cols, actions):
        with column:
            if st.button(label, use_container_width=True, key=key):
                action(selected_quest_id, selected_checklist_date)
                st.session_state["checklist_status_message"] = (
                    f"{label} saved for {selected_checklist_date:%Y-%m-%d}."
                )
                st.rerun()


def _render_checklist_legend() -> None:
    legend_items = (
        ("blank", "Empty / not scheduled"),
        ("P", "Planned"),
        ("C", "Completed"),
        ("S", "Skipped"),
        ("F", "Failed"),
    )
    legend_cols = st.columns(len(legend_items))
    for column, (marker, label) in zip(legend_cols, legend_items):
        column.caption(f"{marker} = {label}")


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


def _build_checklist_quest_labels(rows: list[dict]) -> dict[int, str]:
    base_labels = {
        row["quest_id"]: f"{row['title']} | {row['category'] or 'Uncategorized'} | {row['difficulty']}"
        for row in rows
    }
    label_counts: dict[str, int] = {}
    labels: dict[int, str] = {}
    for quest_id, label in base_labels.items():
        label_counts[label] = label_counts.get(label, 0) + 1
        labels[quest_id] = label if label_counts[label] == 1 else f"{label} ({label_counts[label]})"
    return labels


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


def _format_time_range(quest) -> str:
    if quest.planned_start_at and quest.planned_end_at:
        return f"{quest.planned_start_at:%H:%M} - {quest.planned_end_at:%H:%M}"
    return "All day"


def _category_name(quest) -> str:
    return quest.category.name if quest.category else "Uncategorized"


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


def _pluralize(word: str, count: int) -> str:
    return word if count == 1 else f"{word}s"


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
                    )
                except ValueError as error:
                    st.error(str(error))
                else:
                    st.success("Quest scheduled.")
                    st.rerun()

render_section_title("Monthly Checklist", "Track daily quest completion for the selected month.")
with st.container(border=True):
    render_monthly_checklist()

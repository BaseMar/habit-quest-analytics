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
from src.services.quest_service import (
    VALID_QUEST_STATUSES,
    create_scheduled_quest,
    get_all_quests,
    get_categories,
    get_quest_xp_reward,
    get_quests_for_calendar,
    get_quests_for_day,
    update_quest_status,
    validate_schedule_times,
)
from src.ui import apply_theme, render_empty_state, render_page_header, render_section_title


st.set_page_config(page_title="Quest Log", page_icon="HQ", layout="wide")


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
        "headerToolbar": {
            "left": "prev,next today",
            "center": "title",
            "right": "dayGridMonth,timeGridWeek,timeGridDay,listWeek",
        },
        "height": 560,
        "nowIndicator": True,
        "slotMinTime": "06:00:00",
        "slotMaxTime": "22:00:00",
        "eventTimeFormat": {
            "hour": "2-digit",
            "minute": "2-digit",
            "hour12": False,
        },
    }
    custom_css = """
        .fc-theme-standard .fc-scrollgrid,
        .fc-theme-standard td,
        .fc-theme-standard th {
            border-color: rgba(148, 163, 184, 0.18);
        }
        .fc .fc-toolbar-title {
            color: #f8fafc;
            font-size: 1.2rem;
        }
        .fc .fc-button-primary {
            background: rgba(56, 189, 248, 0.18);
            border-color: rgba(56, 189, 248, 0.38);
            color: #f8fafc;
        }
        .fc .fc-button-primary:not(:disabled).fc-button-active,
        .fc .fc-button-primary:not(:disabled):active {
            background: rgba(139, 92, 246, 0.48);
            border-color: rgba(196, 181, 253, 0.62);
        }
        .fc .fc-daygrid-day.fc-day-today,
        .fc .fc-timegrid-col.fc-day-today {
            background: rgba(56, 189, 248, 0.08);
        }
        .fc .fc-list,
        .fc .fc-list-day-cushion {
            background: rgba(15, 23, 42, 0.72);
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


def _format_date(value) -> str:
    return value.strftime("%Y-%m-%d") if value else ""


def _format_datetime(value) -> str:
    return value.strftime("%Y-%m-%d %H:%M") if value else ""


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
    "Quest Log",
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
        title = st.text_input("Title")

        category_col, difficulty_col, xp_col = st.columns([1.2, 1, 0.8])
        with category_col:
            category_name = st.selectbox("Category", list(category_options.keys()))
        with difficulty_col:
            difficulty = st.selectbox("Difficulty", list(QUEST_DIFFICULTIES))
        with xp_col:
            xp_reward = get_quest_xp_reward(difficulty)
            st.text_input("XP Reward", value=f"{xp_reward} XP", disabled=True)

        start_col, end_col, estimate_col = st.columns(3)
        with start_col:
            start_time = st.time_input("Start Time", value=default_start, step=300)
        with end_col:
            end_time = st.time_input("End Time", value=default_end, step=300)
        with estimate_col:
            estimated_minutes = _calculate_duration_minutes(start_time, end_time)
            estimate_label = f"{estimated_minutes} min" if estimated_minutes is not None else "Invalid range"
            st.text_input("Duration", value=estimate_label, disabled=True)

        notes = st.text_area("Notes", height=72, placeholder="Optional notes")

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

quests = get_all_quests()

if not quests:
    render_empty_state("No quests yet", "Plan your first quest above to start building your adventure log.")
else:
    quest_rows = [
        {
            "ID": quest.id,
            "Title": quest.title,
            "Category": _category_name(quest),
            "Difficulty": quest.difficulty,
            "Status": quest.status,
            "Planned Date": _format_date(quest.due_date),
            "Start": _format_datetime(quest.planned_start_at),
            "End": _format_datetime(quest.planned_end_at),
            "Estimated Minutes": quest.estimated_minutes or "",
            "XP Reward": quest.xp_reward,
            "Completed At": _format_datetime(quest.completed_at),
        }
        for quest in quests
    ]
    render_section_title("Maintenance", "Secondary controls for reviewing and maintaining quest records.")
    with st.container(border=True):
        with st.expander("Quest Ledger", expanded=False):
            st.caption("Review persisted quest history without taking focus from the planner.")
            st.dataframe(pd.DataFrame(quest_rows), width="stretch", hide_index=True)

        # Temporary v1 status control. Replace later with a monthly habit checklist for per-day completion.
        with st.expander("Temporary Status Controls", expanded=False):
            st.caption("Temporary workflow. This will later be replaced by a monthly habit checklist.")
            quest_labels = {f"#{quest.id} - {quest.title}": quest.id for quest in quests}
            with st.form("update_quest_status_form"):
                selected_quest = st.selectbox("Quest", list(quest_labels.keys()))
                selected_status = st.selectbox("Status", list(VALID_QUEST_STATUSES))
                status_submitted = st.form_submit_button("Update Status")

                if status_submitted:
                    update_quest_status(quest_labels[selected_quest], selected_status)
                    st.success("Quest status updated.")
                    st.rerun()

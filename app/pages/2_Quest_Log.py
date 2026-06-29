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


def apply_quest_log_styles() -> None:
    st.markdown(
        """
        <style>
            .fc {
                color: #e5e7eb;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


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
        "height": 620,
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

    schedule_rows = [
        {
            "Time": _format_time_range(quest),
            "Quest": quest.title,
            "Category": _category_name(quest),
            "Difficulty": quest.difficulty,
            "Status": quest.status,
            "XP": f"{quest.xp_reward or 0} XP",
        }
        for quest in quests
    ]
    st.dataframe(pd.DataFrame(schedule_rows), width="stretch", hide_index=True)


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


def _calculate_duration_minutes(start_time: time, end_time: time) -> int:
    try:
        planned_start_at, planned_end_at = validate_schedule_times(
            st.session_state["selected_date"],
            start_time,
            end_time,
        )
    except ValueError:
        return 30
    return int((planned_end_at - planned_start_at).total_seconds() // 60)


def _format_time_range(quest) -> str:
    if quest.planned_start_at and quest.planned_end_at:
        return f"{quest.planned_start_at:%H:%M} - {quest.planned_end_at:%H:%M}"
    return "All day"


def _category_name(quest) -> str:
    return quest.category.name if quest.category else "Uncategorized"


apply_theme()
apply_quest_log_styles()
render_page_header(
    "Quest Planning",
    "Quest Log",
    "Plan quests, schedule habits, and update quest progress.",
)

init_db()
categories = get_categories()
category_options = {category.name: category.id for category in categories}

if not category_options:
    st.warning("Run python -m src.database.seed to create default categories.")
    st.stop()

if "selected_date" not in st.session_state:
    st.session_state["selected_date"] = date.today()

calendar_events = get_quests_for_calendar()

render_section_title("Quest Calendar", "Review planned quests and select a day to build its schedule.")
render_calendar(calendar_events, st.session_state["selected_date"])

planner_col, schedule_col = st.columns([0.52, 0.48], gap="large")

with planner_col:
    render_section_title("Plan Quest", "Add a scheduled quest to the selected day.")
    selected_date = st.date_input("Selected date", key="selected_date")
    default_start = time(9, 0)
    default_end = time(10, 0)

    with st.container(border=True):
        with st.form("plan_quest_form", clear_on_submit=True):
            title = st.text_input("Title")
            description = st.text_area("Description")

            col1, col2 = st.columns(2)
            with col1:
                category_name = st.selectbox("Category", list(category_options.keys()))
                difficulty = st.selectbox("Difficulty", list(QUEST_DIFFICULTIES))
                start_time = st.time_input("Start time", value=default_start, step=300)
            with col2:
                xp_reward = get_quest_xp_reward(difficulty)
                st.text_input("XP reward", value=f"{xp_reward} XP", disabled=True)
                end_time = st.time_input("End time", value=default_end, step=300)
                estimated_minutes = st.number_input(
                    "Estimated minutes",
                    min_value=0,
                    max_value=1440,
                    value=_calculate_duration_minutes(start_time, end_time),
                    step=5,
                )

            submitted = st.form_submit_button("Add Quest")
            if submitted:
                if not title.strip():
                    st.error("Every quest needs a title.")
                else:
                    try:
                        create_scheduled_quest(
                            title=title,
                            description=description,
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

with schedule_col:
    render_section_title("Selected Day Schedule", f"Planned quests for {st.session_state['selected_date']:%Y-%m-%d}.")
    selected_day_quests = get_quests_for_day(st.session_state["selected_date"])
    with st.container(border=True):
        render_schedule_list(selected_day_quests)

render_section_title("Existing Quests", "Review persisted quests and update their current status.")
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
            "Planned Date": quest.due_date,
            "Start": quest.planned_start_at,
            "End": quest.planned_end_at,
            "Estimated Minutes": quest.estimated_minutes,
            "XP Reward": quest.xp_reward,
            "Completed At": quest.completed_at,
        }
        for quest in quests
    ]
    st.dataframe(pd.DataFrame(quest_rows), width="stretch", hide_index=True)

    render_section_title("Update Quest Status", "Move a quest through the existing status flow.")
    quest_labels = {f"#{quest.id} - {quest.title}": quest.id for quest in quests}

    with st.container(border=True):
        with st.form("update_quest_status_form"):
            selected_quest = st.selectbox("Quest", list(quest_labels.keys()))
            selected_status = st.selectbox("Status", list(VALID_QUEST_STATUSES))
            status_submitted = st.form_submit_button("Update Status")

            if status_submitted:
                update_quest_status(quest_labels[selected_quest], selected_status)
                st.success("Quest status updated.")
                st.rerun()

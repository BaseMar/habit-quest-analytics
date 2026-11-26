from calendar import Calendar, day_abbr
from datetime import date, datetime, time
from html import escape
from pathlib import Path

import streamlit as st

from app.components.checkin_actions import get_checkin_status_actions
from app.components.plan_form import render_plan_form
from app.components.planner_month_review import render_month_checklist
from src.services.checklist_service import update_checkin_status
from src.services.goal_service import list_active_goals
from src.services.quest_service import (
    create_scheduled_quest,
    delete_one_time_quest_if_unresolved,
    get_categories,
    get_planner_schedule,
    get_quest_status_for_date,
    update_planned_quest,
)
from src.services.recurring_habit_service import (
    create_recurring_habit,
    delete_recurring_generated_occurrence_if_unresolved,
    generate_recurring_habit_for_month,
)
from src.ui import render_empty_state, render_page_header


PLANNER_STYLES = Path(__file__).resolve().parents[1] / "components" / "planner.css"
FIRST_DAY = date(1900, 1, 1)
LAST_DAY = date(2200, 12, 31)


def select_day(day: date) -> None:
    st.session_state["selected_date"] = day
    st.session_state.pop("planner_editing_item", None)


def move_month(day: date, step: int) -> None:
    year, month = divmod(day.year * 12 + day.month - 1 + step, 12)
    select_day(date(year, month + 1, 1))


def render_month_navigation(selected_day: date, today: date) -> None:
    with st.container(key="hq_month_heading", horizontal=True, horizontal_alignment="distribute", vertical_alignment="center"):
        st.html(f'<h2 class="hq-month-title">{selected_day:%B %Y}</h2>')
        with st.container(horizontal=True, gap="xxsmall", width="content"):
            st.button(
                "‹", key="planner_previous_month", help="Previous month", on_click=move_month,
                args=(selected_day, -1), disabled=selected_day.replace(day=1) == FIRST_DAY,
            )
            st.button("Today", key="planner_today", on_click=select_day, args=(today,))
            st.button(
                "›", key="planner_next_month", help="Next month", on_click=move_month,
                args=(selected_day, 1), disabled=selected_day.replace(day=1) == LAST_DAY.replace(day=1),
            )


def render_calendar(weeks: list[list[date]], schedule: dict, selected_day: date, today: date) -> None:
    with st.container(key="hq_calendar_grid", gap=None):
        st.html('<div class="hq-weekday-labels">' + "".join(f"<span>{day}</span>" for day in day_abbr) + "</div>")
        for week in weeks:
            for column, day in zip(st.columns(7, gap=None, wrap=False), week):
                items = schedule.get(day, [])
                count = len(items)
                variant = "selected" if day == selected_day else "today" if day == today else "regular"
                if day == selected_day == today:
                    variant = "selected_today"
                if day.month != selected_day.month:
                    variant += "_adjacent"
                with column.container(key=f"hq_day_{variant}_{day.isoformat()}", gap=None):
                    day_label = f"{day:%A, %B} {day.day}, {day.year}"
                    item_label = "item" if count == 1 else "items"
                    st.button(
                        str(day.day), key=f"planner_day_{day.isoformat()}", width="stretch",
                        help=f"{day_label} · {count} {item_label}", on_click=select_day,
                        args=(day,), disabled=not FIRST_DAY <= day <= LAST_DAY,
                    )
                    if items:
                        entries = "".join(
                            f'<div class="hq-cal-event hq-state-{get_quest_status_for_date(item, day).lower()}">'
                            f'<span>{escape(item.title)}</span></div>'
                            for item in items[:2]
                        )
                        more = f'<span class="hq-cal-more">+{count - 2} more</span>' if count > 2 else ""
                        st.html(f'<div class="hq-cal-events" aria-hidden="true">{entries}{more}</div>')


@st.dialog("Add item", width="medium", on_dismiss="rerun")
def add_item_dialog(category_options: dict[str, int], selected_day: date) -> None:
    active_goals = list_active_goals()
    draft = render_plan_form(
        category_options=category_options,
        active_goals=active_goals,
        selected_date=selected_day,
        goal_title_by_id={goal.id: goal.title for goal in active_goals},
    )
    if draft is None:
        return
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
            generate_recurring_habit_for_month(habit.id, draft.planned_date.year, draft.planned_date.month)
            message = "Routine added to this month's plan."
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
            message = "Item added to the plan."
    except ValueError as error:
        st.error(str(error))
    else:
        select_day(draft.planned_date)
        st.session_state["planner_message"] = message
        st.rerun()


def render_item_editor(quest, category_options: dict[str, int], selected_day: date) -> None:
    prefix = f"planner_edit_{quest.id}"
    is_routine_day = quest.recurring_habit_instance is not None
    is_project_session = quest.goal_id is not None
    if is_routine_day:
        st.caption("Changes apply to this routine day only.")
    with st.form(prefix):
        title = st.text_input("Title", value=quest.title, disabled=is_project_session)
        category_names = {category_id: name for name, category_id in category_options.items()}
        categories = [None, *category_names]
        category = st.selectbox(
            "Category", categories, index=categories.index(quest.category_id) if quest.category_id in categories else 0,
            format_func=lambda category_id: category_names.get(category_id, "Uncategorized"),
            disabled=is_project_session,
        )
        planned_day = st.date_input(
            "Date", value=quest.recurring_habit_instance.scheduled_date if is_routine_day else quest.due_date or selected_day,
            disabled=is_routine_day, min_value=FIRST_DAY, max_value=LAST_DAY,
        )
        all_day = st.checkbox("All day", value=quest.planned_start_at is None)
        start_col, end_col = st.columns(2)
        with start_col:
            start = st.time_input("Start", value=quest.planned_start_at.time() if quest.planned_start_at else time(9))
        with end_col:
            end = st.time_input("End", value=quest.planned_end_at.time() if quest.planned_end_at else time(10))
        notes = st.text_area("Notes", value=quest.description or "", height=80)
        with st.container(horizontal=True, gap="xsmall"):
            save = st.form_submit_button("Save changes", type="primary")
            cancel = st.form_submit_button("Cancel")
    if cancel:
        st.session_state.pop("planner_editing_item", None)
        st.rerun()
    if save:
        try:
            update_planned_quest(
                quest.id, title, notes, category, planned_day, None if all_day else start, None if all_day else end,
                estimated_minutes=quest.estimated_minutes if all_day else None,
            )
        except ValueError as error:
            st.error(str(error))
        else:
            select_day(planned_day)
            st.session_state["planner_message"] = "Item updated."
            st.rerun()


@st.dialog("Remove planned item", on_dismiss="rerun")
def remove_item_dialog(quest) -> None:
    st.text(quest.title)
    confirmed = st.checkbox("Confirm removal")
    with st.container(horizontal=True, gap="xsmall"):
        remove = st.button("Remove", type="primary", disabled=not confirmed)
        cancel = st.button("Cancel")
    if cancel:
        st.rerun()
    if remove:
        delete = (
            delete_recurring_generated_occurrence_if_unresolved
            if quest.recurring_habit_instance is not None
            else delete_one_time_quest_if_unresolved
        )
        try:
            result = delete(quest.id)
        except ValueError as error:
            st.error(str(error))
        else:
            if result["deleted"]:
                st.session_state["planner_message"] = "Item removed."
                st.rerun()
            st.warning(result.get("reason") or "This item could not be removed.")


def save_status(quest_id: int, day: date, status: str, next_status: str) -> None:
    try:
        update_checkin_status(quest_id, day, next_status, expected_status=status)
    except ValueError as error:
        st.error(str(error))
    else:
        st.session_state["planner_message"] = f"Status updated to {next_status.lower()}."
        st.rerun()


def render_date_jump(selected_day: date, width: int | str = "stretch") -> None:
    if st.session_state.get("planner_manage_date") != selected_day:
        st.session_state["planner_manage_date"] = selected_day

    def select_input_day() -> None:
        select_day(st.session_state["planner_manage_date"])

    st.date_input(
        "Jump to date", key="planner_manage_date", min_value=FIRST_DAY, max_value=LAST_DAY,
        on_change=select_input_day, width=width,
    )


def render_agenda(items: list, selected_day: date, today: date, category_options: dict[str, int]) -> None:
    completed = sum(get_quest_status_for_date(item, selected_day) == "Completed" for item in items)
    day_label = "Today" if selected_day == today else selected_day.strftime("%A")
    st.html(
        f'<header class="hq-agenda-header"><p>{day_label}</p>'
        f'<h2>{selected_day:%B} {selected_day.day}</h2>'
        f'<div class="hq-agenda-count">{len(items)} {"item" if len(items) == 1 else "items"}'
        f' <span>·</span> {completed} completed</div></header>'
    )
    render_date_jump(selected_day)
    if not items:
        render_empty_state("Nothing planned", "Pick another date or add an item to this day.")
    for quest in items:
        status = get_quest_status_for_date(quest, selected_day)
        time_label = "All day"
        if quest.planned_start_at and quest.planned_end_at and quest.planned_start_at.date() == selected_day:
            time_label = f"{quest.planned_start_at:%H:%M}–{quest.planned_end_at:%H:%M}"
        category = quest.category.name if quest.category else "Uncategorized"
        prefix = f"agenda_{quest.id}_{selected_day.isoformat()}"
        with st.container(key=prefix, border=True, gap="xsmall"):
            st.html(
                f'<div class="hq-agenda-card hq-state-{status.lower()}">'
                f'<div class="hq-agenda-card-meta"><time>{time_label}</time><span>{status}</span></div>'
                f'<h3>{escape(quest.title)}</h3><p>{escape(category)} · {quest.xp_reward or 0} XP</p></div>'
            )
            if st.session_state.get("planner_editing_item") == quest.id and status == "Planned":
                render_item_editor(quest, category_options, selected_day)
                continue

            actions = get_checkin_status_actions(status) if selected_day <= today else ()
            with st.container(key=f"{prefix}_actions", horizontal=True, gap="xsmall", vertical_alignment="center"):
                if status == "Planned":
                    if actions and st.button("Complete", key=f"{prefix}_complete", icon=":material/check:"):
                        save_status(quest.id, selected_day, status, "Completed")
                    if st.button("Edit", key=f"{prefix}_edit"):
                        st.session_state["planner_editing_item"] = quest.id
                        st.rerun()
                    with st.popover("More", key=f"{prefix}_more"):
                        for label, next_status, _ in actions[1:]:
                            if st.button(label, key=f"{prefix}_{next_status}", width="stretch"):
                                save_status(quest.id, selected_day, status, next_status)
                        if st.button("Remove item", key=f"{prefix}_remove", width="stretch"):
                            remove_item_dialog(quest)
                else:
                    for label, next_status, _ in actions:
                        if st.button(label, key=f"{prefix}_{next_status}"):
                            save_status(quest.id, selected_day, status, next_status)


st.html(PLANNER_STYLES)
today = date.today()
selected_day = st.session_state.setdefault("selected_date", today)
category_options = {category.name: category.id for category in get_categories()}
with st.container(key="hq_planner_heading", horizontal=True, horizontal_alignment="distribute", vertical_alignment="bottom"):
    render_page_header("Planner", "Schedule tasks, routines, and project sessions.")
    if st.button("Add item", type="primary", icon=":material/add:", disabled=not category_options):
        add_item_dialog(category_options, selected_day)

if message := st.session_state.pop("planner_message", None):
    st.success(message)

calendar_tab, checklist_tab = st.tabs(["Calendar", "Monthly checklist"], key="planner_tab", on_change="rerun")
if calendar_tab.open:
    weeks = Calendar().monthdatescalendar(selected_day.year, selected_day.month)
    schedule = get_planner_schedule(weeks[0][0], weeks[-1][-1])
    with calendar_tab:
        calendar_col, agenda_col = st.container(key="hq_planner_split").columns([2.2, 1], gap="medium", wrap=False)
        with calendar_col.container(key="hq_month_card", gap="small"):
            render_month_navigation(selected_day, today)
            render_calendar(weeks, schedule, selected_day, today)
        with agenda_col.container(key="hq_agenda", gap="small"):
            render_agenda(schedule.get(selected_day, []), selected_day, today, category_options)
if checklist_tab.open:
    with checklist_tab:
        render_month_navigation(selected_day, today)
        render_date_jump(selected_day, width=220)
        render_month_checklist(selected_day.year, selected_day.month)

import sys
from datetime import date
from html import escape
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.database.db import init_db
from app.components.checkin_actions import render_checkin_status_actions
from src.services.analytics_service import get_command_center_data, get_command_center_items_for_date
from src.services.checklist_service import update_checkin_status
from src.ui import apply_theme, render_empty_state, render_page_header, render_section_title


def render_mission_brief(command_center: dict) -> None:
    today_count = len(command_center["today_quests"])
    attention_count = command_center["overdue_quests"]

    if today_count == 0:
        message = "No work is scheduled for today. Add an item in Planner when you are ready."
    else:
        item_word = "item" if today_count == 1 else "items"
        message = f"You have {today_count} planned {item_word} for today."

    overdue_note = ""
    if command_center["overdue_quests"] > 0:
        overdue_note = (
            f"<div class=\"command-brief-note\">"
            f"{command_center['overdue_quests']} overdue items need review."
            f"</div>"
        )

    st.markdown(
        f"""
        <div class="command-brief">
            <div class="command-brief-label">Today</div>
            <div class="command-brief-message">{escape(message)}</div>
            {overdue_note}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_work_items(items: list[dict], empty_title: str, empty_message: str, key_prefix: str) -> None:
    if not items:
        render_empty_state(
            empty_title,
            empty_message,
        )
        return

    for item in items:
        with st.container(border=True):
            is_planned = item["status"] == "Planned"
            column_widths = [0.72, 0.28] if is_planned else [0.78, 0.22]
            details_col, effort_col = st.columns(column_widths, vertical_alignment="center")
            actual_minutes = None
            with details_col:
                time_label = item["time"] if item["time"] != "Not scheduled" else "Any time"
                st.write(f"**{item['title']}**")
                st.caption(f"{item['checkin_date']:%a, %b %d} / {time_label} / {item['category']} / {item['status']}")
            with effort_col:
                st.caption(f"{item['xp']} XP")
                if is_planned:
                    actual_minutes = int(
                        st.number_input(
                            "Actual minutes",
                            min_value=0,
                            value=0,
                            step=5,
                            key=f"actual_minutes_{key_prefix}_{item['quest_id']}_{item['checkin_date'].isoformat()}",
                            help="Optional. Saved only when you complete this item.",
                        )
                    )

            action = render_checkin_status_actions(
                item["status"],
                key_prefix=f"{key_prefix}_{item['quest_id']}_{item['checkin_date'].isoformat()}",
            )
            if action is not None:
                label, next_status = action
                try:
                    update_checkin_status(
                        item["quest_id"],
                        item["checkin_date"],
                        next_status,
                        actual_minutes=actual_minutes or None,
                    )
                except ValueError as error:
                    st.error(str(error))
                else:
                    st.session_state["command_status_message"] = f"{label} saved for {item['title']}."
                    st.rerun()


def render_status_kpis(command_center: dict) -> None:
    status_items = (
        ("Planned today", command_center["planned_quests"], "info"),
        ("Completed today", command_center["completed_today"], "success"),
        ("Needs review", command_center["overdue_quests"] + command_center["failed_quests"], "warning"),
    )
    cards = "\n".join(
        f"""
        <div class="command-status-card {tone}">
            <span class="command-status-label">{label}</span>
            <span class="command-status-value">{value}</span>
        </div>
        """
        for label, value, tone in status_items
    )

    st.markdown(
        f"""
        <style>
            .command-status-row {{
                display: grid;
                grid-template-columns: repeat(3, minmax(0, 1fr));
                gap: 0.75rem;
                margin: 0 0 1rem;
            }}

            .command-status-card {{
                position: relative;
                display: flex;
                align-items: center;
                justify-content: space-between;
                gap: 0.75rem;
                min-height: 58px;
                padding: 0.75rem 0.9rem 0.75rem 1rem;
                border: 1px solid var(--hq-border);
                border-radius: 8px;
                background: var(--hq-surface);
                box-shadow: none;
            }}

            .command-status-card::before {{
                content: "";
                position: absolute;
                left: 0.72rem;
                top: 0.86rem;
                width: 0.45rem;
                height: 0.45rem;
                border-radius: 999px;
                background: var(--hq-accent);
            }}

            .command-status-card.warning::before {{
                background: var(--hq-warning);
            }}

            .command-status-card.danger::before {{
                background: var(--hq-danger);
            }}

            .command-status-card.info::before {{
                background: var(--hq-info);
            }}

            .command-status-card.success::before {{
                background: var(--hq-success);
            }}

            .command-status-label {{
                color: var(--hq-text-secondary);
                font-size: 0.82rem;
                line-height: 1.15;
                padding-left: 0.72rem;
            }}

            .command-status-value {{
                color: var(--hq-text-primary);
                font-size: 1.38rem;
                font-weight: 760;
                line-height: 1;
            }}

            .command-brief {{
                background: var(--hq-surface);
                border: 1px solid var(--hq-border);
                border-radius: 8px;
                box-shadow: none;
                margin: 0.15rem 0 1rem;
                padding: 0.85rem 0.95rem;
            }}

            .command-brief-label {{
                color: var(--hq-text-secondary);
                font-size: 0.74rem;
                font-weight: 740;
                letter-spacing: 0.05em;
                margin-bottom: 0.25rem;
                text-transform: uppercase;
            }}

            .command-brief-message {{
                color: var(--hq-text-primary);
                font-size: 1rem;
                font-weight: 700;
                line-height: 1.35;
            }}

            .command-brief-note {{
                color: var(--hq-warning);
                font-size: 0.86rem;
                margin-top: 0.35rem;
            }}

            @media (max-width: 900px) {{
                .command-status-row {{
                grid-template-columns: repeat(2, minmax(0, 1fr));
                }}
            }}

            @media (max-width: 520px) {{
                .command-status-row {{
                    grid-template-columns: 1fr;
                }}

            }}
        </style>
        <div class="command-status-row">
            {cards}
        </div>
        """,
        unsafe_allow_html=True,
    )


apply_theme()
render_page_header(
    "Today",
    "Command Center",
    "Keep today's work visible and resolve anything that needs review.",
)

init_db()
command_center = get_command_center_data()

if not command_center["has_quests"]:
    render_empty_state(
        "No quest data yet",
        "Create a quest in Quest Planner to start today's mission.",
    )
else:
    status_message = st.session_state.pop("command_status_message", None)
    if status_message:
        st.success(status_message)

    render_status_kpis(command_center)
    render_mission_brief(command_center)

    render_section_title("Today's work", "Complete, skip, fail, or reset planned work without leaving this page.")
    render_work_items(
        command_center["today_work_items"],
        "No work planned for today",
        "Schedule tasks in Quest Planner to build today's focus.",
        "command_today",
    )

    render_section_title("Needs review", "Resolve overdue planned work before it disappears from your daily flow.")
    render_work_items(
        command_center["attention_items"],
        "No overdue planned work",
        "Your previous planned work has been resolved.",
        "command_attention",
    )

    render_section_title("Review another day")
    review_date = st.date_input(
        "Review date",
        value=date.today(),
        max_value=date.today(),
        key="command_review_date",
    )
    if review_date != date.today():
        render_work_items(
            get_command_center_items_for_date(review_date),
            "No work recorded for this day",
            "Choose another date or create future work in Planner.",
            f"command_review_{review_date.isoformat()}",
        )

st.caption("Data source: local SQLite quest check-in records.")

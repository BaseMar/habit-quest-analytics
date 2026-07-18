import sys
from html import escape
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.database.db import init_db
from app.components.checkin_actions import render_checkin_status_actions
from src.services.analytics_service import get_command_center_data
from src.services.checklist_service import update_checkin_status
from src.ui import apply_theme, render_empty_state, render_page_header, render_section_title


def render_mission_brief(command_center: dict) -> None:
    today_count = len(command_center["today_quests"])
    attention_count = command_center["overdue_quests"]

    if today_count == 0:
        message = "No quest check-ins planned for today. Schedule quests in Quest Planner to start today's mission."
    else:
        quest_word = "check-in" if today_count == 1 else "check-ins"
        attention_word = "item needs" if attention_count == 1 else "items need"
        message = f"Today's mission: {today_count} {quest_word} planned. {attention_count} {attention_word} attention."

    overdue_note = ""
    if command_center["overdue_quests"] > 0:
        overdue_note = (
            f"<div class=\"command-brief-note\">"
            f"{command_center['overdue_quests']} overdue check-ins need review below."
            f"</div>"
        )

    st.markdown(
        f"""
        <div class="command-brief">
            <div class="command-brief-label">Mission brief</div>
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
        details_col, xp_col, action_col = st.columns([0.62, 0.1, 0.28], vertical_alignment="center")
        with details_col:
            time_label = item["time"] if item["time"] != "Not scheduled" else "Any time"
            st.write(f"**{item['title']}**")
            st.caption(f"{item['checkin_date']:%a, %b %d} / {time_label} / {item['category']} / {item['status']}")
        with xp_col:
            st.caption(f"{item['xp']} XP")
        with action_col:
            action = render_checkin_status_actions(
                item["status"],
                key_prefix=f"{key_prefix}_{item['quest_id']}_{item['checkin_date'].isoformat()}",
            )
            if action is not None:
                label, next_status = action
                try:
                    update_checkin_status(item["quest_id"], item["checkin_date"], next_status)
                except ValueError as error:
                    st.error(str(error))
                else:
                    st.session_state["command_status_message"] = f"{label} saved for {item['title']}."
                    st.rerun()
        st.divider()


def render_status_kpis(command_center: dict) -> None:
    status_items = (
        ("Overdue", command_center["overdue_quests"], "warning"),
        ("Failed", command_center["failed_quests"], "danger"),
        ("Planned Today", command_center["planned_quests"], "info"),
        ("Completed Today", command_center["completed_today"], "success"),
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
                grid-template-columns: repeat(4, minmax(0, 1fr));
                gap: 0.75rem;
                margin: 0.15rem 0 1rem;
            }}

            .command-status-card {{
                position: relative;
                display: flex;
                align-items: center;
                justify-content: space-between;
                gap: 0.75rem;
                min-height: 54px;
                padding: 0.72rem 0.85rem 0.72rem 1rem;
                border: 1px solid var(--hq-border);
                border-radius: 8px;
                background: var(--hq-surface);
                box-shadow: var(--hq-shadow);
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
                font-size: 1.24rem;
                font-weight: 760;
                line-height: 1;
            }}

            .command-brief {{
                background: var(--hq-surface);
                border: 1px solid var(--hq-border);
                border-radius: 8px;
                box-shadow: var(--hq-shadow);
                margin: 0.2rem 0 1.15rem;
                padding: 0.9rem 1rem;
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
    "Command Overview",
    "Command Center",
    "Focus on today's quests and review what needs attention.",
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

    render_section_title("Today's Focus", "Complete, skip, fail, or reset today's planned work here.")
    render_work_items(
        command_center["today_work_items"],
        "No work planned for today",
        "Schedule tasks in Quest Planner to build today's focus.",
        "command_today",
    )

    render_section_title("Needs Attention", "Resolve overdue planned work before it becomes invisible in the day-to-day flow.")
    render_work_items(
        command_center["attention_items"],
        "No overdue planned work",
        "Your previous planned work has been resolved.",
        "command_attention",
    )

st.caption("Data source: local SQLite quest check-in records.")

import sys
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.database.db import init_db
from src.services.analytics_service import get_command_center_data
from src.ui import apply_theme, render_empty_state, render_page_header, render_section_title


def render_mission_brief(command_center: dict) -> None:
    today_count = len(command_center["today_quests"])
    attention_count = command_center["overdue_quests"] + command_center["failed_quests"]

    if today_count == 0:
        message = "No quest check-ins planned for today. Schedule quests in Quest Planner to start today's mission."
    else:
        quest_word = "check-in" if today_count == 1 else "check-ins"
        attention_word = "item needs" if attention_count == 1 else "items need"
        message = f"Today's mission: {today_count} {quest_word} planned. {attention_count} {attention_word} attention."

    with st.container(border=True):
        st.write(f"**{message}**")
        if command_center["overdue_quests"] > 0:
            st.caption(f"{command_center['overdue_quests']} overdue check-ins need review in Quest Planner.")


def render_todays_focus(today_quests: list[dict]) -> None:
    if not today_quests:
        render_empty_state(
            "No quest check-ins planned for today",
            "Schedule quests in Quest Planner to build today's focus.",
        )
        return

    for quest in today_quests:
        with st.container(border=True):
            time_col, detail_col, xp_col = st.columns([0.24, 0.58, 0.18], vertical_alignment="center")
            with time_col:
                st.write(f"**{quest['Time']}**")
            with detail_col:
                st.write(f"**{quest['Title']}**")
                st.caption(f"{quest['Category']} | {quest['Difficulty']} | {quest['Status']}")
            with xp_col:
                st.write(f"**{quest['XP']}**")


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
                display: flex;
                align-items: center;
                justify-content: space-between;
                gap: 0.75rem;
                min-height: 54px;
                padding: 0.65rem 0.85rem;
                border: 1px solid var(--hq-border);
                border-left-width: 4px;
                border-radius: 8px;
                background:
                    linear-gradient(135deg, var(--hq-accent-soft), transparent 86%),
                    var(--hq-surface);
                box-shadow: var(--hq-shadow);
            }}

            .command-status-card.warning {{
                border-left-color: var(--hq-warning);
            }}

            .command-status-card.danger {{
                border-left-color: var(--hq-danger);
            }}

            .command-status-card.info {{
                border-left-color: var(--hq-info);
            }}

            .command-status-card.success {{
                border-left-color: var(--hq-success);
            }}

            .command-status-label {{
                color: var(--hq-text-secondary);
                font-size: 0.82rem;
                line-height: 1.15;
            }}

            .command-status-value {{
                color: var(--hq-text-primary);
                font-size: 1.18rem;
                font-weight: 800;
                line-height: 1;
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
    render_status_kpis(command_center)
    render_mission_brief(command_center)

    render_section_title("Today's Focus", "Today's planned quest check-ins. Manage status updates in Quest Planner.")
    render_todays_focus(command_center["today_quests"])

st.caption("Data source: local SQLite quest check-in records.")

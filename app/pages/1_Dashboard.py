import sys
from pathlib import Path

import pandas as pd
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.database.db import init_db
from src.services.analytics_service import get_command_center_data
from src.ui import apply_theme, render_empty_state, render_page_header, render_section_title


st.set_page_config(page_title="Command Center", page_icon="HQ", layout="wide")


def render_mission_brief(command_center: dict) -> None:
    today_count = len(command_center["today_quests"])
    attention_count = command_center["overdue_quests"] + command_center["failed_quests"]

    if today_count == 0:
        message = "No quests planned for today. Create a quest in Quest Log to start today's mission."
    else:
        quest_word = "quest" if today_count == 1 else "quests"
        attention_word = "item needs" if attention_count == 1 else "items need"
        message = f"Today's mission: {today_count} {quest_word} planned. {attention_count} {attention_word} attention."

    with st.container(border=True):
        st.subheader("Mission Brief")
        st.write(f"**{message}**")
        if command_center["overdue_quests"] > 0:
            st.caption(f"{command_center['overdue_quests']} overdue quests need review in Quest Log.")


def render_todays_focus(today_quests: list[dict]) -> None:
    if not today_quests:
        render_empty_state(
            "No quests planned for today",
            "Create a quest in Quest Log to start today's mission.",
        )
        return

    st.dataframe(
        pd.DataFrame(today_quests),
        hide_index=True,
        width="stretch",
    )


def render_needs_attention(command_center: dict) -> None:
    attention_items = (
        ("Overdue", command_center["overdue_quests"], "warning"),
        ("Failed", command_center["failed_quests"], "danger"),
        ("Planned", command_center["planned_quests"], "info"),
        ("Completed Today", command_center["completed_today"], "success"),
    )
    chips = "\n".join(
        f"""
        <div class="attention-chip {tone}">
            <span class="attention-label">{label}</span>
            <span class="attention-value">{value}</span>
        </div>
        """
        for label, value, tone in attention_items
    )

    st.markdown(
        f"""
        <style>
            .attention-strip {{
                display: flex;
                flex-wrap: wrap;
                gap: 0.55rem;
                align-items: center;
                margin: 0.15rem 0 0.35rem;
            }}

            .attention-chip {{
                display: inline-flex;
                align-items: center;
                gap: 0.45rem;
                min-height: 30px;
                padding: 0.28rem 0.62rem;
                border: 1px solid rgba(148, 163, 184, 0.22);
                border-left-width: 3px;
                border-radius: 999px;
                background: rgba(15, 23, 42, 0.58);
                box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.03);
            }}

            .attention-chip.warning {{
                border-left-color: #f59e0b;
            }}

            .attention-chip.danger {{
                border-left-color: #ef4444;
            }}

            .attention-chip.info {{
                border-left-color: #38bdf8;
            }}

            .attention-chip.success {{
                border-left-color: #22c55e;
            }}

            .attention-label {{
                color: rgba(226, 232, 240, 0.68);
                font-size: 0.78rem;
                line-height: 1;
            }}

            .attention-value {{
                color: #f8fafc;
                font-size: 0.9rem;
                font-weight: 700;
                line-height: 1;
            }}
        </style>
        <div class="attention-strip">
            {chips}
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
        "Create a quest in Quest Log to start today's mission.",
    )
else:
    render_mission_brief(command_center)

    render_section_title("Today's Focus", "Quests planned for today. Updates still happen in Quest Log.")
    render_todays_focus(command_center["today_quests"])

    render_section_title("Needs Attention", "Operational items worth reviewing before planning more work.")
    render_needs_attention(command_center)

st.caption("Data source: local SQLite quest records.")

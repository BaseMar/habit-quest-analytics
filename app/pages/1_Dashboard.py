import sys
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.database.db import init_db
from src.services.analytics_service import get_dashboard_kpis
from src.ui import apply_theme, render_empty_state, render_metric_card, render_page_header, render_section_title


st.set_page_config(page_title="Command Center", page_icon="HQ", layout="wide")
apply_theme()
render_page_header(
    "Command Overview",
    "Command Center",
    "Review your quest ledger at a glance: completion, XP, weekly progress, and level growth.",
)

init_db()
kpis = get_dashboard_kpis()

render_section_title("Quest Overview", "A compact snapshot of your current quest ledger.")

quest_col1, quest_col2, quest_col3 = st.columns(3)
with quest_col1:
    render_metric_card("Total Quests", kpis["total_quests"], "All persisted quest records")
with quest_col2:
    render_metric_card("Completed Quests", kpis["completed_quests"], "Quests that awarded XP")
with quest_col3:
    render_metric_card("Completion Rate", f"{kpis['completion_rate']}%", "Completed / total quests")

render_section_title("XP Progress", "Level progress is based only on completed quests.")

xp_col1, xp_col2, xp_col3, xp_col4 = st.columns(4)
with xp_col1:
    render_metric_card("Total XP", kpis["total_xp"], "Lifetime completed quest XP")
with xp_col2:
    render_metric_card("Weekly XP", kpis["weekly_xp"], "Completed this week")
with xp_col3:
    render_metric_card("Current Level", kpis["current_level"], "Character progression tier")
with xp_col4:
    render_metric_card("XP to Next Level", kpis["xp_to_next_level"], "Remaining before level up")

progress = (kpis["total_xp"] % 500) / 500
st.progress(progress)
st.caption(f"{int(progress * 100)}% progress toward the next level")

if kpis["total_quests"] == 0:
    render_empty_state(
        "No quest records yet",
        "Create your first quest in Quest Log to activate this command center.",
    )
elif kpis["completed_quests"] == 0:
    render_empty_state(
        "No completed quests yet",
        "Your quests are planned, but none are completed. Mark a quest as Completed to start earning XP.",
    )

st.caption("KPI values are calculated from quests stored in the local SQLite database.")

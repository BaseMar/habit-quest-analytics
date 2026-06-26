import sys
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.database.db import init_db
from src.services.analytics_service import get_dashboard_kpis


st.title("Dashboard")

init_db()
kpis = get_dashboard_kpis()

st.header("Quest Overview")

quest_col1, quest_col2, quest_col3 = st.columns(3)
quest_col1.metric("Total Quests", kpis["total_quests"])
quest_col2.metric("Completed Quests", kpis["completed_quests"])
quest_col3.metric("Completion Rate", f"{kpis['completion_rate']}%")

st.header("XP Progress")

xp_col1, xp_col2, xp_col3, xp_col4 = st.columns(4)
xp_col1.metric("Total XP", kpis["total_xp"])
xp_col2.metric("Weekly XP", kpis["weekly_xp"])
xp_col3.metric("Current Level", kpis["current_level"])
xp_col4.metric("XP to Next Level", kpis["xp_to_next_level"])

st.caption("KPI values are calculated from quests stored in the local SQLite database.")

import sys
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.ui import apply_theme, render_page_header
from src.database.db import init_db
from src.database.seed import ensure_default_categories


st.set_page_config(
    page_title="Habit Quest Analytics",
    page_icon="HQ",
    layout="wide",
)
apply_theme()
init_db()
ensure_default_categories()

render_page_header(
    "Habit Quest Analytics",
    "Habit Quest Analytics",
    "Turn daily tasks into quests, earn XP for completed work, and review progress through dashboard KPIs, habit charts, and character stats.",
)

st.info("Start in Quest Log to create your first quest, then return to Dashboard and Habit Analytics to inspect progress.")

st.header("Current Sections")
st.markdown(
    """
    <div class="hq-card-grid">
        <div class="hq-card">
            <div class="hq-card-title">Dashboard</div>
            <div class="hq-card-body">Summary KPIs from persisted quests.</div>
        </div>
        <div class="hq-card">
            <div class="hq-card-title">Quest Log</div>
            <div class="hq-card-body">Create quests and update quest status.</div>
        </div>
        <div class="hq-card">
            <div class="hq-card-title">Habit Analytics</div>
            <div class="hq-card-body">Charts for XP, categories, status, and consistency.</div>
        </div>
        <div class="hq-card">
            <div class="hq-card-title">Character Profile</div>
            <div class="hq-card-body">RPG level, XP progress, and stat growth.</div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

import sys
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.ui import apply_theme, render_appearance_controls


st.set_page_config(
    page_title="Habit Quest Analytics",
    page_icon="HQ",
    layout="wide",
)


def render_sidebar_brand() -> None:
    st.sidebar.markdown(
        """
        <div class="hq-sidebar-brand">
            <div class="hq-sidebar-brand-title">Habit Quest Analytics</div>
            <div class="hq-sidebar-brand-caption">RPG habit planner</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


apply_theme()
render_sidebar_brand()
render_appearance_controls()

pages = [
    st.Page(
        "pages/1_Dashboard.py",
        title="Command Center",
        icon=":material/dashboard:",
        url_path="Dashboard",
        default=True,
    ),
    st.Page(
        "pages/2_Quest_Log.py",
        title="Planner",
        icon=":material/event:",
        url_path="Quest_Log",
    ),
    st.Page(
        "pages/5_Projects_and_Routines.py",
        title="Projects & Routines",
        icon=":material/assignment:",
        url_path="Projects_and_Routines",
    ),
    st.Page(
        "pages/3_Habit_Analytics.py",
        title="Habit Analytics",
        icon=":material/analytics:",
        url_path="Habit_Analytics",
    ),
    st.Page(
        "pages/4_Character_Profile.py",
        title="Character Profile",
        icon=":material/person:",
        url_path="Character_Profile",
    ),
]

current_page = st.navigation(pages, position="sidebar", expanded=True)
current_page.run()

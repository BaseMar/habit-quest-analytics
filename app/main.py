import logging
import sys
from inspect import signature
from pathlib import Path

import streamlit as st
from sqlalchemy.exc import SQLAlchemyError

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.auth import bind_account, current_user_id, google_identity, google_login_configured, log_out
from src.database import db
from src.services.account_service import register_google_account
from src.ui import apply_theme, render_appearance_controls


st.set_page_config(
    page_title="Habit Quest Analytics",
    page_icon="HQ",
    layout="wide",
)

if "on_change" not in signature(st.tabs).parameters:
    st.error(f"The app needs Streamlit 1.66.1 or newer. This process is using {st.__version__}.")
    st.markdown("From the project directory, start the app with its local virtual environment.")
    st.code("python run_streamlit.py", language="bash")
    st.stop()

if db.engine is None:
    st.error("Set DATABASE_URL in Streamlit secrets or the environment to connect to PostgreSQL.")
    st.stop()


identity = google_identity()
if identity is None:
    apply_theme()
    st.title("Habit Quest Analytics")
    if st.user.get("is_logged_in"):
        st.error("Sign in with a Google account that has a verified email address.")
        st.button("Log out", on_click=log_out)
    elif google_login_configured():
        st.button("Log in with Google", type="primary", on_click=st.login)
    else:
        st.info("Configure Google sign-in in the Streamlit secrets.")
    st.stop()

try:
    current_user_id()
except PermissionError:
    subject, email = identity
    try:
        bind_account(subject, register_google_account(subject, email))
    except SQLAlchemyError as error:
        logging.getLogger(__name__).error(
            "Account database operation failed (%s, SQLSTATE %s).",
            type(error).__name__,
            getattr(getattr(error, "orig", None), "sqlstate", None),
        )
        st.error("Unable to load your account. Check the database connection and apply the latest migrations.")
        st.stop()


def render_sidebar_brand() -> None:
    st.sidebar.markdown(
        """
        <div class="hq-sidebar-brand">
            <div class="hq-sidebar-brand-title">Habit Quest Analytics</div>
            <div class="hq-sidebar-brand-caption">Personal planner</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar_navigation(pages: list, current_page) -> None:
    """Render navigation below the fixed sidebar branding."""
    for page in pages:
        target = st.sidebar.container(key="hq_active_page") if page is current_page else st.sidebar
        target.page_link(page)


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

current_page = st.navigation(pages, position="hidden")
render_sidebar_brand()
render_sidebar_navigation(pages, current_page)
render_appearance_controls()
st.sidebar.text(identity[1])
st.sidebar.button("Log out", on_click=log_out, width="stretch")
apply_theme()
current_page.run()

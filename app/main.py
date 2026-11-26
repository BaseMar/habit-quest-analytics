import logging
import sys
from html import escape
from inspect import signature
from pathlib import Path

import streamlit as st
from sqlalchemy.exc import SQLAlchemyError

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.components.loading_screen import loading_screen
from app.components.sign_in import render_sign_in
from src.auth import DEMO_STATE, bind_account, current_user_id, end_demo, google_identity, log_out, reset_demo
from src.database import db
from src.services.account_service import register_google_account
from src.services.demo_service import DEMO_NAME
from src.ui import apply_theme, render_appearance_controls


st.set_page_config(
    page_title="Habit Quest Analytics",
    page_icon="HQ",
    layout="wide",
    initial_sidebar_state="auto",
)

if "on_change" not in signature(st.tabs).parameters:
    st.error(f"The app needs Streamlit 1.66.1 or newer. This process is using {st.__version__}.")
    st.markdown("From the project directory, start the app with its local virtual environment.")
    st.code("python run_streamlit.py", language="bash")
    st.stop()

identity = google_identity()
is_demo = DEMO_STATE in st.session_state
if not is_demo and (identity is None or db.engine is None):
    render_sign_in(database_configured=db.engine is not None)
    st.stop()

def ensure_account(identity: tuple[str, str]) -> None:
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
            render_sign_in(error="Unable to load your account. Check the database connection and apply the latest migrations.")
            st.stop()


def render_sidebar_brand() -> None:
    st.sidebar.markdown(
        """
        <div class="hq-sidebar-brand">
            <div class="hq-sidebar-mark" aria-hidden="true">HQ</div>
            <div class="hq-sidebar-brand-title">Habit Quest<br>Analytics</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar_navigation(pages: list, current_page) -> None:
    """Render navigation below the fixed sidebar branding."""
    for page in pages:
        target = st.sidebar.container(key="hq_active_page") if page is current_page else st.sidebar
        target.page_link(page)


def render_sidebar_account(is_demo: bool, identity: tuple[str, str] | None) -> None:
    account_name = DEMO_NAME if is_demo else st.user.get("name") or identity[1]
    account_name = str(account_name)
    account_detail = "Demo session" if is_demo else identity[1] if account_name != identity[1] else "Google account"
    initials = "".join(part[0] for part in account_name.split()[:2]).upper() or "HQ"
    st.sidebar.html(
        f'<div class="hq-sidebar-account"><div class="hq-account-initials" aria-hidden="true">{escape(initials)}</div>'
        f'<div class="hq-account-label"><strong>{escape(account_name)}</strong>'
        f'<small>{escape(account_detail)}</small></div></div>'
    )
    if is_demo:
        st.sidebar.caption("Changes last for this session.")
        st.sidebar.button(
            "Reset demo", key="reset_demo", icon=":material/restart_alt:", width="stretch",
            help="Restore sample data and discard your demo changes.", on_click=reset_demo,
        )
        st.sidebar.button("Exit demo", on_click=end_demo, width="stretch")
    else:
        st.sidebar.button("Log out", on_click=log_out, width="stretch")


pages = [
    st.Page(
        "pages/2_Quest_Log.py",
        title="Planner",
        icon=":material/calendar_month:",
        url_path="Planner",
        default=True,
    ),
    st.Page(
        "pages/1_Dashboard.py",
        title="Summary",
        icon=":material/space_dashboard:",
        url_path="Dashboard",
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

legacy_planner = st.Page("pages/2_Quest_Log.py", title="Planner", url_path="Quest_Log", visibility="hidden")
current_page = st.navigation([*pages, legacy_planner], position="hidden")
open_demo_planner = st.session_state.pop("_hq_demo_open_planner", False)
if current_page is legacy_planner or (open_demo_planner and current_page is not pages[0]):
    st.switch_page(pages[0])
route = current_page.url_path
route_changed = st.session_state.get("_hq_loaded_route") != route
if route_changed:
    st.session_state.pop("_hq_loaded_route", None)

with loading_screen(f"Loading {current_page.title}", enabled=route_changed):
    if not is_demo:
        ensure_account(identity)
    render_sidebar_brand()
    render_sidebar_navigation(pages, current_page)
    render_appearance_controls()
    render_sidebar_account(is_demo, identity)
    apply_theme()
    # Replace the previous page as soon as the next route starts rendering.
    page = st.empty()
    with page.container(key=f"hq_page_{route}"):
        current_page.run()
    st.session_state["_hq_loaded_route"] = route

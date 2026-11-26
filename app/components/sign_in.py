from pathlib import Path

import streamlit as st

from src.auth import google_login_configured, log_out, start_demo
from src.ui import apply_theme


SIGN_IN_STYLES = Path(__file__).with_suffix(".css")


def render_sign_in(*, database_configured: bool = True, error: str | None = None) -> None:
    """Show a standalone sign-in screen before rendering app navigation."""
    apply_theme()
    st.html(SIGN_IN_STYLES)
    signed_in = st.user.get("is_logged_in")

    with st.container(key="hq_sign_in"):
        st.html(
            """
            <div class="hq-sign-in-intro">
                <div class="hq-sidebar-mark" aria-hidden="true">HQ</div>
                <h1>Habit Quest Analytics</h1>
                <p>Plan your days, build routines, and see your progress over time.</p>
            </div>
            """
        )
        st.button("Try live demo", type="primary", icon=":material/arrow_forward:", width="stretch", on_click=start_demo)
        st.caption("Explore with sample data. No account required.")

        if error:
            st.error(error)
        elif signed_in and not database_configured:
            st.error("Set DATABASE_URL in the deployment environment to connect to PostgreSQL.")
        elif signed_in:
            st.error("Sign in with a Google account that has a verified email address.")
        elif database_configured and google_login_configured():
            st.button("Log in with Google", width="stretch", on_click=st.login)

        if signed_in:
            st.button("Log out", width="stretch", on_click=log_out)

from pathlib import Path

import streamlit as st

from src.auth import google_login_configured, log_out


SIGN_IN_STYLES = Path(__file__).with_suffix(".css")


def render_sign_in(error: str | None = None) -> None:
    """Show a standalone sign-in screen before rendering app navigation."""
    st.html(SIGN_IN_STYLES)
    signed_in = st.user.get("is_logged_in")

    with st.container(key="hq_sign_in"):
        st.html(
            """
            <div class="hq-sign-in-intro">
                <div class="hq-sign-in-mark" aria-hidden="true">HQ</div>
                <h1>Habit Quest Analytics</h1>
                <p>Sign in to access your personal planner and habit progress.</p>
            </div>
            """
        )
        if error:
            st.error(error)
        elif signed_in:
            st.error("Sign in with a Google account that has a verified email address.")
        elif google_login_configured():
            st.button("Log in with Google", type="primary", width="stretch", on_click=st.login)
        else:
            st.info("Configure Google sign-in in the Streamlit secrets.")

        if signed_in:
            st.button("Log out", width="stretch", on_click=log_out)

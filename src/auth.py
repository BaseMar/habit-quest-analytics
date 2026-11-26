"""Manage verified Streamlit identities and per-session guest workspaces."""

import logging

import streamlit as st
from sqlalchemy.engine import Engine


_ACCOUNT_STATE = "_hq_authenticated_account"
DEMO_STATE = "_hq_demo_database"
_DEMO_SUBJECT = "_hq_demo_subject"
_GOOGLE_ISSUERS = {"https://accounts.google.com", "accounts.google.com"}
_AUTH_KEYS = ("redirect_uri", "cookie_secret", "client_id", "client_secret", "server_metadata_url")


def google_login_configured() -> bool:
    try:
        return all(st.secrets.get("auth", {}).get(key) for key in _AUTH_KEYS)
    except FileNotFoundError:
        return False


def google_identity() -> tuple[str, str] | None:
    if st.user.get("is_logged_in") is not True:
        return None
    issuer, subject, email = (st.user.get(key) for key in ("iss", "sub", "email"))
    if (
        issuer in _GOOGLE_ISSUERS
        and st.user.get("email_verified") is True
        and isinstance(subject, str) and 0 < len(subject) <= 255
        and isinstance(email, str) and 0 < len(email) <= 320
    ):
        return subject, email
    return None


def bind_account(subject: str, user_id: int) -> None:
    st.session_state[_ACCOUNT_STATE] = (subject, user_id)


def current_user_id() -> int:
    identity = google_identity()
    account = st.session_state.get(_ACCOUNT_STATE)
    if identity is None or account is None or identity[0] != account[0]:
        raise PermissionError("Sign in to use this account.")
    return account[1]


def _subject(identity: tuple[str, str] | None) -> str | None:
    return identity[0] if identity is not None else None


def active_demo_engine() -> Engine | None:
    engine = st.session_state.get(DEMO_STATE)
    if engine is not None and st.session_state.get(_DEMO_SUBJECT) == _subject(google_identity()):
        return engine
    return None


def clear_stale_workspace(identity: tuple[str, str] | None) -> None:
    subject = _subject(identity)
    account = st.session_state.get(_ACCOUNT_STATE)
    if (
        (DEMO_STATE in st.session_state and st.session_state.get(_DEMO_SUBJECT) != subject)
        or (account is not None and account[0] != subject)
    ):
        end_demo()


def _build_demo() -> Engine | None:
    from src.services.demo_service import create_demo_database

    try:
        return create_demo_database()
    except Exception:
        logging.getLogger(__name__).exception("Failed to initialize the guest demo.")
        st.error("Unable to load the demo scenario. Try again.")
        return None


def _replace_workspace(state: dict) -> None:
    previous_demo = st.session_state.get(DEMO_STATE)
    st.session_state.clear()
    st.session_state.update(state)
    if previous_demo is not None:
        previous_demo.dispose()


def start_demo() -> None:
    if active_demo_engine() is not None:
        return
    if (database := _build_demo()) is not None:
        # Allow an explicit demo in the sign-in fallback for this identity.
        _replace_workspace({
            DEMO_STATE: database,
            _DEMO_SUBJECT: _subject(google_identity()),
            "_hq_demo_open_planner": True,
        })


def reset_demo() -> None:
    from src.ui import THEME_MODE_KEY

    if active_demo_engine() is None:
        return
    if (database := _build_demo()) is not None:
        _replace_workspace({
            DEMO_STATE: database,
            _DEMO_SUBJECT: st.session_state.get(_DEMO_SUBJECT),
            THEME_MODE_KEY: st.session_state.get(THEME_MODE_KEY, "Light"),
        })


def end_demo() -> None:
    _replace_workspace({})


def log_out() -> None:
    end_demo()
    st.logout()

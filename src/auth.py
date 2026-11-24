"""Read the Google identity verified by Streamlit for the current session."""

import streamlit as st


_ACCOUNT_STATE = "_hq_authenticated_account"
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


def log_out() -> None:
    st.session_state.clear()
    st.logout()

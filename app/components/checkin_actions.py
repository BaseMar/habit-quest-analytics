from __future__ import annotations

import streamlit as st


CheckinAction = tuple[str, str, str]


def get_checkin_status_actions(current_status: str | None) -> tuple[CheckinAction, ...]:
    """Return the allowed UI actions for a persisted check-in status."""
    if current_status == "Planned":
        return (
            ("Complete", "Completed", "primary"),
            ("Skip", "Skipped", "secondary"),
            ("Fail", "Failed", "secondary"),
        )
    if current_status in ("Completed", "Skipped", "Failed"):
        return (("Reset", "Planned", "secondary"),)
    return ()


def render_checkin_status_actions(
    current_status: str | None,
    key_prefix: str,
) -> tuple[str, str] | None:
    """Render consistent status buttons and return the selected label/status pair."""
    actions = get_checkin_status_actions(current_status)
    if not actions:
        return None

    if len(actions) == 1:
        label, next_status, button_type = actions[0]
        if st.button(
            label,
            type=button_type,
            use_container_width=True,
            key=f"{key_prefix}_{next_status}",
        ):
            return label, next_status
        return None

    action_columns = st.columns(3)
    for action_column, (label, next_status, button_type) in zip(action_columns, actions):
        with action_column:
            if st.button(
                label,
                type=button_type,
                use_container_width=True,
                key=f"{key_prefix}_{next_status}",
            ):
                return label, next_status
    return None

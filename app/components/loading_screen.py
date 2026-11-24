from contextlib import contextmanager
from html import escape
from pathlib import Path

import streamlit as st

from src.ui import theme_css_declarations


LOADING_STYLES = Path(__file__).with_suffix(".css").read_text(encoding="utf-8")


@contextmanager
def loading_screen(title: str, *, enabled: bool):
    """Show the navigation overlay until the current page finishes rendering."""
    # Reserve the same position on ordinary reruns so the page slot stays stable.
    placeholder = st.empty()
    if not enabled:
        yield
        return

    placeholder.html(
        f"<style>.hq-loading-screen {{ {theme_css_declarations()} }}\n{LOADING_STYLES}</style>"
        '<div class="hq-loading-screen" role="status" aria-live="polite" aria-atomic="true">'
        '<div class="hq-loading-card">'
        '<div class="hq-loading-mark" aria-hidden="true">'
        '<div class="hq-loading-journal">'
        '<div class="hq-loading-journal-page hq-loading-journal-notes"></div>'
        '<div class="hq-loading-journal-page hq-loading-journal-check"></div>'
        '</div></div>'
        '<div class="hq-loading-brand">Habit Quest Analytics</div>'
        f'<div class="hq-loading-title">{escape(title)}</div>'
        '<div class="hq-loading-detail">Preparing your view</div>'
        '<div class="hq-loading-track" aria-hidden="true">'
        '<div class="hq-loading-bar"></div></div>'
        '</div></div>'
    )
    try:
        yield
    finally:
        placeholder.empty()

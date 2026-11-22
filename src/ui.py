from __future__ import annotations

from html import escape
from pathlib import Path
from typing import TypedDict

import streamlit as st


class ThemeTokens(TypedDict):
    mode: str
    background: str
    background_alt: str
    surface: str
    surface_elevated: str
    border: str
    border_strong: str
    text_primary: str
    text_secondary: str
    accent: str
    accent_bright: str
    accent_foreground: str
    accent_glow: str
    accent_text: str
    accent_soft: str
    accent_border: str
    success: str
    warning: str
    danger: str
    info: str
    shadow: str
    input_background: str
    muted_surface: str
    chart_grid: str


THEME_MODE_KEY = "hq_theme_mode"
DARK_MODE_SWITCH_KEY = "hq_dark_mode"
STYLES = Path(__file__).with_name("styles.css").read_text(encoding="utf-8")

THEMES = {
    "Dark": ThemeTokens(
        mode="Dark",
        background="#222831",
        background_alt="#282F39",
        surface="#393E46",
        surface_elevated="#414852",
        border="#555D68",
        border_strong="#89929E",
        text_primary="#EEEEEE",
        text_secondary="#B8C1CB",
        accent="#00ADB5",
        accent_bright="#25C5CD",
        accent_foreground="#122B30",
        accent_glow="rgba(0, 173, 181, 0.20)",
        accent_text="#58D8DE",
        accent_soft="rgba(0, 173, 181, 0.14)",
        accent_border="#00ADB5",
        success="#86E6AA",
        warning="#FFC947",
        danger="#FF8585",
        info="#7DD3FC",
        shadow="0 2px 6px rgba(0, 0, 0, 0.22)",
        input_background="#222831",
        muted_surface="rgba(238, 238, 238, 0.08)",
        chart_grid="#555D68",
    ),
    "Light": ThemeTokens(
        mode="Light",
        background="#F2F5F6",
        background_alt="#EAF0F1",
        surface="#FFFFFF",
        surface_elevated="#F3F7F7",
        border="#CDD8DB",
        border_strong="#7E9095",
        text_primary="#222831",
        text_secondary="#4D5B64",
        accent="#00777D",
        accent_bright="#087279",
        accent_foreground="#FFFFFF",
        accent_glow="rgba(0, 119, 125, 0.16)",
        accent_text="#00666C",
        accent_soft="rgba(0, 119, 125, 0.10)",
        accent_border="#00777D",
        success="#15803D",
        warning="#9A4E00",
        danger="#B91C1C",
        info="#075985",
        shadow="0 2px 6px rgba(34, 40, 49, 0.08)",
        input_background="#F5F8F8",
        muted_surface="rgba(34, 40, 49, 0.06)",
        chart_grid="#D4DEE0",
    ),
}

# Backward-compatible color constants used by older page code and tests.
TEXT_MUTED = "#9CA3AF"
SURFACE = "#111827"
SURFACE_LIGHT = "#1F2937"
PRIMARY = "#2563EB"
SUCCESS = "#22C55E"
WARNING = "#F59E0B"
DANGER = "#EF4444"
INFO = "#38BDF8"


def get_theme_tokens() -> ThemeTokens:
    return THEMES.get(st.session_state.get(THEME_MODE_KEY), THEMES["Light"])


def render_appearance_controls() -> None:
    """Keep the selected theme in session state across page changes."""
    st.sidebar.markdown('<div class="hq-sidebar-section-title">Appearance</div>', unsafe_allow_html=True)
    st.session_state.setdefault(DARK_MODE_SWITCH_KEY, get_theme_tokens()["mode"] == "Dark")
    dark_mode = st.sidebar.toggle("Dark mode", key=DARK_MODE_SWITCH_KEY)
    st.session_state[THEME_MODE_KEY] = "Dark" if dark_mode else "Light"


def apply_global_styles() -> None:
    """Apply the current session's palette and the shared stylesheet."""
    tokens = get_theme_tokens()
    palette = "\n".join(
        f"--hq-{name.replace('_', '-')}: {value};"
        for name, value in tokens.items()
        if name != "mode"
    )
    st.html(f'<style>:root {{ color-scheme: {tokens["mode"].lower()}; {palette} }}\n{STYLES}</style>')


def apply_theme() -> None:
    """Backward-compatible alias for existing pages."""
    apply_global_styles()


def render_page_header(title: str, subtitle: str) -> None:
    st.html(
        f"""
        <header class="hq-page-header">
            <h1 class="hq-page-title">{escape(title)}</h1>
            <p class="hq-page-subtitle">{escape(subtitle)}</p>
        </header>
        """,
    )


def render_section_title(title: str, description: str | None = None) -> None:
    description_html = f'<p class="hq-section-description">{escape(description)}</p>' if description else ""
    st.html(f'<h2 class="hq-section-title">{escape(title)}</h2>{description_html}')


def render_empty_state(title: str, message: str) -> None:
    st.markdown(
        f"""
        <div class="hq-empty-state">
            <div class="hq-empty-title">{escape(title)}</div>
            <div class="hq-empty-body">{escape(message)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_metric_card(label: str, value: str | int | float, caption: str | None = None) -> None:
    caption_html = f'<div class="hq-metric-caption">{escape(caption)}</div>' if caption else ""
    st.markdown(
        f"""
        <div class="hq-metric-card">
            <div class="hq-metric-label">{escape(label)}</div>
            <div class="hq-metric-value">{escape(str(value))}</div>
            {caption_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def style_chart(fig, height: int = 320):
    tokens = get_theme_tokens()
    fig.update_layout(
        height=height,
        paper_bgcolor="rgba(0, 0, 0, 0)",
        plot_bgcolor="rgba(0, 0, 0, 0)",
        font={"color": tokens["text_primary"]},
        title={"font": {"color": tokens["text_primary"], "size": 16}},
        xaxis={
            "gridcolor": tokens["chart_grid"],
            "linecolor": tokens["border"],
            "tickfont": {"color": tokens["text_secondary"]},
            "title": {"font": {"color": tokens["text_secondary"]}},
        },
        yaxis={
            "gridcolor": tokens["chart_grid"],
            "linecolor": tokens["border"],
            "tickfont": {"color": tokens["text_secondary"]},
            "title": {"font": {"color": tokens["text_secondary"]}},
        },
        margin={"l": 24, "r": 18, "t": 48, "b": 42},
    )
    return fig

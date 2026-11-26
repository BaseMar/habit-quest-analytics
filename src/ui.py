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
    marker: str
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
        background="#191422",
        background_alt="#241B30",
        surface="#231B2E",
        surface_elevated="#2E243B",
        border="#473A53",
        border_strong="#83718E",
        text_primary="#F6EFF9",
        text_secondary="#C7B9D1",
        accent="#DDC0FF",
        accent_bright="#E8D3FF",
        accent_foreground="#281737",
        accent_glow="rgb(221 192 255 / 17%)",
        accent_text="#E4CDFF",
        accent_soft="rgb(221 192 255 / 13%)",
        accent_border="#C69DEF",
        marker="#FFAA80",
        success="#A6DBAB",
        warning="#F8CC82",
        danger="#FFAAB4",
        info="#AFC8FF",
        shadow="0 1px 2px rgb(0 0 0 / 18%)",
        input_background="#191422",
        muted_surface="rgb(246 239 249 / 7%)",
        chart_grid="#473A53",
    ),
    "Light": ThemeTokens(
        mode="Light",
        background="#F6F1EB",
        background_alt="#EFE7DF",
        surface="#FFFCF8",
        surface_elevated="#F2EAE5",
        border="#DFD3DA",
        border_strong="#927E9B",
        text_primary="#30243A",
        text_secondary="#62546A",
        accent="#593777",
        accent_bright="#704B8D",
        accent_foreground="#FFFFFF",
        accent_glow="rgb(89 55 119 / 14%)",
        accent_text="#593777",
        accent_soft="rgb(116 75 149 / 11%)",
        accent_border="#8E68AB",
        marker="#A8462C",
        success="#326741",
        warning="#8F550B",
        danger="#A83A4B",
        info="#395E95",
        shadow="0 1px 2px rgb(48 36 58 / 9%)",
        input_background="#FFFCF8",
        muted_surface="rgb(48 36 58 / 6%)",
        chart_grid="#DFD3DA",
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


def theme_css_declarations() -> str:
    """Return the current session's theme as CSS declarations."""
    tokens = get_theme_tokens()
    palette = "\n".join(
        f"--hq-{name.replace('_', '-')}: {value};"
        for name, value in tokens.items()
        if name != "mode"
    )
    return f'color-scheme: {tokens["mode"].lower()};\n{palette}'


def apply_global_styles() -> None:
    """Apply the current session's palette and the shared stylesheet."""
    st.html(f'<style>:root {{ {theme_css_declarations()} }}\n{STYLES}</style>')


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

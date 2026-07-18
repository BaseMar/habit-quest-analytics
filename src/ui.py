from __future__ import annotations

from html import escape
from typing import TypedDict

import streamlit as st
from streamlit import config as streamlit_config


class ThemeTokens(TypedDict):
    mode: str
    accent_name: str
    background: str
    background_alt: str
    surface: str
    surface_elevated: str
    border: str
    text_primary: str
    text_secondary: str
    accent: str
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
ACCENT_PRESET_KEY = "hq_accent_preset"

THEME_MODES = ("Light", "Dark")
ACCENT_PRESETS = {
    "Blue": {
        "accent": "#2563EB",
        "accent_soft_dark": "rgba(96, 165, 250, 0.16)",
        "accent_soft_light": "#EFF6FF",
        "accent_border_dark": "rgba(96, 165, 250, 0.36)",
        "accent_border_light": "#BFDBFE",
    },
}

BASE_TOKENS = {
    "Dark": {
        "background": "#111827",
        "background_alt": "#111827",
        "surface": "#182234",
        "surface_elevated": "#223047",
        "border": "rgba(148, 163, 184, 0.2)",
        "text_primary": "#F3F6FA",
        "text_secondary": "#AEB9C9",
        "success": "#22C55E",
        "warning": "#F59E0B",
        "danger": "#EF4444",
        "info": "#38BDF8",
        "shadow": "0 1px 2px rgba(2, 6, 23, 0.24)",
        "input_background": "#182234",
        "muted_surface": "rgba(148, 163, 184, 0.1)",
        "chart_grid": "rgba(148, 163, 184, 0.16)",
    },
    "Light": {
        "background": "#F6F7F9",
        "background_alt": "#F6F7F9",
        "surface": "#FFFFFF",
        "surface_elevated": "#F8FAFC",
        "border": "#E2E8F0",
        "text_primary": "#18212F",
        "text_secondary": "#64748B",
        "success": "#15803D",
        "warning": "#B45309",
        "danger": "#DC2626",
        "info": "#0369A1",
        "shadow": "0 1px 2px rgba(15, 23, 42, 0.04)",
        "input_background": "#FFFFFF",
        "muted_surface": "rgba(15, 23, 42, 0.035)",
        "chart_grid": "rgba(100, 116, 139, 0.16)",
    },
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


def _safe_theme_mode(value: str | None) -> str:
    return value if value in THEME_MODES else "Light"


def _safe_accent_preset(value: str | None) -> str:
    return value if value in ACCENT_PRESETS else "Blue"


def get_theme_tokens() -> ThemeTokens:
    mode = _safe_theme_mode(st.session_state.get(THEME_MODE_KEY))
    accent_name = _safe_accent_preset(st.session_state.get(ACCENT_PRESET_KEY))
    base = BASE_TOKENS[mode]
    accent = ACCENT_PRESETS[accent_name]
    soft_key = "accent_soft_dark" if mode == "Dark" else "accent_soft_light"
    border_key = "accent_border_dark" if mode == "Dark" else "accent_border_light"

    return ThemeTokens(
        mode=mode,
        accent_name=accent_name,
        background=base["background"],
        background_alt=base["background_alt"],
        surface=base["surface"],
        surface_elevated=base["surface_elevated"],
        border=base["border"],
        text_primary=base["text_primary"],
        text_secondary=base["text_secondary"],
        accent=accent["accent"],
        accent_soft=accent[soft_key],
        accent_border=accent[border_key],
        success=base["success"],
        warning=base["warning"],
        danger=base["danger"],
        info=base["info"],
        shadow=base["shadow"],
        input_background=base["input_background"],
        muted_surface=base["muted_surface"],
        chart_grid=base["chart_grid"],
    )


def render_appearance_controls() -> None:
    """Render app-wide appearance controls in the sidebar."""
    st.sidebar.markdown('<div class="hq-sidebar-section-title">Appearance</div>', unsafe_allow_html=True)
    st.sidebar.radio(
        "Theme",
        options=list(THEME_MODES),
        key=THEME_MODE_KEY,
        horizontal=True,
        label_visibility="visible",
    )


def _sync_streamlit_theme_config(tokens: ThemeTokens) -> None:
    """Keep native Streamlit/BaseWeb widgets aligned with the selected app theme."""
    theme_options = {
        "theme.primaryColor": tokens["accent"],
        "theme.backgroundColor": tokens["background"],
        "theme.secondaryBackgroundColor": tokens["surface"],
        "theme.textColor": tokens["text_primary"],
    }
    for option_name, option_value in theme_options.items():
        try:
            if streamlit_config.get_option(option_name) != option_value:
                streamlit_config.set_option(option_name, option_value)
        except Exception:
            # CSS tokens still provide the fallback if Streamlit disallows a runtime theme update.
            continue


def apply_global_styles() -> None:
    """Apply token-based app-wide styles."""
    tokens = get_theme_tokens()
    _sync_streamlit_theme_config(tokens)
    accent_rgb = ", ".join(
        str(int(tokens["accent"].lstrip("#")[index : index + 2], 16))
        for index in (0, 2, 4)
    )
    is_dark = tokens["mode"] == "Dark"
    sidebar_background = tokens["surface"]

    st.markdown(
        f"""
        <style>
        :root {{
            --hq-background: {tokens["background"]};
            --hq-background-alt: {tokens["background_alt"]};
            --hq-surface: {tokens["surface"]};
            --hq-surface-elevated: {tokens["surface_elevated"]};
            --hq-border: {tokens["border"]};
            --hq-text-primary: {tokens["text_primary"]};
            --hq-text-secondary: {tokens["text_secondary"]};
            --hq-accent: {tokens["accent"]};
            --hq-accent-soft: {tokens["accent_soft"]};
            --hq-accent-border: {tokens["accent_border"]};
            --hq-success: {tokens["success"]};
            --hq-warning: {tokens["warning"]};
            --hq-danger: {tokens["danger"]};
            --hq-info: {tokens["info"]};
            --hq-shadow: {tokens["shadow"]};
            --hq-input-background: {tokens["input_background"]};
            --hq-muted-surface: {tokens["muted_surface"]};
            --hq-chart-grid: {tokens["chart_grid"]};
            --hq-radius: 8px;
            --primary-color: var(--hq-accent);
            --primary-color-rgb: {accent_rgb};
            --background-color: var(--hq-background);
            --secondary-background-color: var(--hq-surface);
            --text-color: var(--hq-text-primary);
            --border-color: var(--hq-border);
            --input-background-color: var(--hq-input-background);
            --button-secondary-background-color: var(--hq-surface-elevated);
            --button-secondary-text-color: var(--hq-text-primary);
            --button-secondary-border-color: var(--hq-border);
            color-scheme: {"dark" if is_dark else "light"};
        }}

        .stApp {{
            --primary-color: var(--hq-accent);
            --primary-color-rgb: {accent_rgb};
            --background-color: var(--hq-background);
            --secondary-background-color: var(--hq-surface);
            --text-color: var(--hq-text-primary);
            --border-color: var(--hq-border);
            --input-background-color: var(--hq-input-background);
            background: var(--hq-background);
            color: var(--hq-text-primary);
        }}

        .stApp > header,
        .stApp [data-testid="stAppViewContainer"],
        .stApp section[data-testid="stSidebar"] {{
            position: relative;
            z-index: 1;
        }}

        .block-container {{
            max-width: 1360px;
            padding: 1.5rem 2rem 3rem;
        }}

        @media (max-width: 768px) {{
            .block-container {{
                padding-top: 1.1rem;
                padding-left: 1rem;
                padding-right: 1rem;
            }}
        }}

        .stApp,
        .stMarkdown,
        .stMarkdown p,
        .stMarkdown li,
        label,
        p,
        li,
        span {{
            color: var(--hq-text-primary);
        }}

        .stCaptionContainer,
        .stCaptionContainer p,
        div[data-testid="stCaptionContainer"] p,
        small {{
            color: var(--hq-text-secondary) !important;
        }}

        hr {{
            border-color: var(--hq-border) !important;
            margin: 1rem 0 !important;
        }}

        section[data-testid="stSidebar"] {{
            background: {sidebar_background} !important;
            border-right: 1px solid var(--hq-border);
        }}

        section[data-testid="stSidebar"] > div {{
            padding-top: 0.9rem;
        }}

        .hq-sidebar-brand {{
            background: transparent;
            border: 0;
            border-bottom: 1px solid var(--hq-border);
            border-radius: 0;
            box-shadow: none;
            margin: 0.15rem 0 0.8rem;
            padding: 0.35rem 0.15rem 0.75rem;
        }}

        .hq-sidebar-brand-title {{
            color: var(--hq-text-primary);
            font-size: 1.08rem;
            font-weight: 820;
            line-height: 1.12;
        }}

        .hq-sidebar-section-title {{
            color: var(--hq-accent);
            font-size: 0.74rem;
            font-weight: 760;
            letter-spacing: 0.06em;
            margin-top: 0.14rem;
            text-transform: uppercase;
        }}

        .hq-sidebar-section-title {{
            margin: 1.1rem 0 0.35rem;
        }}

        .hq-sidebar-brand-caption {{
            color: var(--hq-text-secondary);
            font-size: 0.78rem;
            line-height: 1.35;
            margin-top: 0.42rem;
        }}

        section[data-testid="stSidebar"] nav ul {{
            gap: 0.35rem;
        }}

        section[data-testid="stSidebar"] nav a,
        section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a,
        section[data-testid="stSidebar"] [data-testid="stPageLink"] a,
        section[data-testid="stSidebar"] a[href^="/"] {{
            align-items: center;
            background: transparent;
            border: 0;
            border-left: 3px solid transparent;
            border-radius: 6px !important;
            color: var(--hq-text-secondary) !important;
            min-height: 40px;
            padding: 0.58rem 0.72rem !important;
            text-decoration: none;
            transition:
                background-color 160ms ease,
                border-color 160ms ease,
                box-shadow 160ms ease,
                color 160ms ease,
                transform 160ms ease;
        }}

        section[data-testid="stSidebar"] nav a:hover,
        section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a:hover,
        section[data-testid="stSidebar"] [data-testid="stPageLink"] a:hover,
        section[data-testid="stSidebar"] a[href^="/"]:hover {{
            background: var(--hq-muted-surface);
            border-left-color: var(--hq-accent);
            box-shadow: none;
            color: var(--hq-text-primary) !important;
            transform: none;
        }}

        section[data-testid="stSidebar"] nav a[aria-current="page"],
        section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a[aria-current="page"],
        section[data-testid="stSidebar"] [data-testid="stPageLink"] a[aria-current="page"],
        section[data-testid="stSidebar"] a[aria-current="page"],
        section[data-testid="stSidebar"] a[data-active="true"] {{
            background: var(--hq-accent-soft);
            border-left-color: var(--hq-accent);
            box-shadow: none;
            color: var(--hq-text-primary) !important;
            font-weight: 750;
        }}

        section[data-testid="stSidebar"] nav a span,
        section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a span,
        section[data-testid="stSidebar"] [data-testid="stPageLink"] a span {{
            color: inherit !important;
            font-size: 0.94rem;
            font-weight: inherit;
        }}

        .hq-page-header {{
            margin-bottom: 1.1rem;
            padding-top: 0.35rem;
        }}

        h1,
        .hq-page-title {{
            color: var(--hq-text-primary) !important;
            font-size: 1.8rem !important;
            font-weight: 740 !important;
            line-height: 1.2 !important;
            margin-bottom: 0.35rem !important;
            letter-spacing: 0;
        }}

        h2 {{
            color: var(--hq-text-primary) !important;
            font-size: 1.25rem !important;
            margin-top: 1.65rem !important;
            padding-top: 0.2rem !important;
        }}

        h3 {{
            color: var(--hq-text-primary) !important;
            font-size: 1.02rem !important;
        }}

        .hq-page-kicker {{
            color: var(--hq-accent);
            font-size: 0.76rem;
            font-weight: 760;
            letter-spacing: 0.06em;
            line-height: 1.35;
            margin-bottom: 0.3rem;
            text-transform: uppercase;
        }}

        .hq-page-subtitle {{
            color: var(--hq-text-secondary);
            font-size: 1rem;
            line-height: 1.5;
            margin-bottom: 0;
            max-width: 920px;
        }}

        .hq-section-title {{
            color: var(--hq-text-primary);
            font-size: 1.05rem;
            font-weight: 740;
            margin-top: 1.4rem;
            margin-bottom: 0.25rem;
        }}

        .hq-section-description {{
            color: var(--hq-text-secondary);
            font-size: 0.9rem;
            line-height: 1.45;
            margin-bottom: 0.85rem;
        }}

        div[data-testid="stMetric"] {{
            background: var(--hq-surface);
            border: 1px solid var(--hq-border);
            border-radius: var(--hq-radius);
            box-shadow: none;
            padding: 0.85rem 0.95rem;
        }}

        div[data-testid="stMetricLabel"] p {{
            color: var(--hq-text-secondary) !important;
            font-size: 0.78rem !important;
            letter-spacing: 0.03em;
            text-transform: uppercase;
        }}

        div[data-testid="stMetricValue"] {{
            color: var(--hq-text-primary) !important;
        }}

        div[data-testid="stMetricDelta"] svg,
        div[data-testid="stMetricDelta"] p {{
            color: var(--hq-accent) !important;
            fill: var(--hq-accent) !important;
        }}

        div[data-testid="stAlert"] {{
            background: var(--hq-surface);
            border: 1px solid var(--hq-border);
            border-radius: var(--hq-radius);
            box-shadow: none;
            color: var(--hq-text-primary);
        }}

        div[data-testid="stDataFrame"] {{
            border: 1px solid var(--hq-border);
            border-radius: var(--hq-radius);
            overflow: hidden;
            box-shadow: none;
            background: var(--hq-surface);
        }}

        div[data-testid="stDataFrame"] div[role="grid"] {{
            border-color: var(--hq-border) !important;
        }}

        .hq-table-scroll {{
            background: var(--hq-surface);
            border: 1px solid var(--hq-border);
            border-radius: var(--hq-radius);
            box-shadow: none;
            margin: 0.35rem 0 1rem;
            max-height: 430px;
            overflow: auto;
            width: 100%;
        }}

        .hq-data-table {{
            border-collapse: separate;
            border-spacing: 0;
            color: var(--hq-text-primary);
            font-size: 0.82rem;
            min-width: 100%;
            width: max-content;
        }}

        .hq-data-table th {{
            background: var(--hq-surface-elevated);
            border-bottom: 1px solid var(--hq-border);
            color: var(--hq-text-secondary);
            font-size: 0.74rem;
            font-weight: 760;
            letter-spacing: 0.03em;
            padding: 0.55rem 0.65rem;
            position: sticky;
            text-align: left;
            text-transform: uppercase;
            top: 0;
            z-index: 2;
        }}

        .hq-data-table td {{
            background: var(--hq-surface);
            border-bottom: 1px solid var(--hq-border);
            color: var(--hq-text-primary);
            padding: 0.5rem 0.65rem;
            vertical-align: middle;
        }}

        .hq-data-table tr:last-child td {{
            border-bottom: 0;
        }}

        .hq-data-table .hq-table-sticky {{
            left: 0;
            position: sticky;
            z-index: 3;
        }}

        .hq-data-table td.hq-table-sticky {{
            background: var(--hq-surface);
            font-weight: 700;
        }}

        .hq-data-table th.hq-table-sticky {{
            background: var(--hq-surface-elevated);
        }}

        .hq-data-table .hq-table-day {{
            min-width: 2.4rem;
            text-align: center;
        }}

        .hq-status-marker {{
            align-items: center;
            border-radius: 999px;
            display: inline-flex;
            font-size: 0.74rem;
            font-weight: 760;
            height: 1.45rem;
            justify-content: center;
            min-width: 1.45rem;
            padding: 0 0.32rem;
        }}

        .hq-status-planned {{
            background: var(--hq-muted-surface);
            color: var(--hq-text-secondary);
        }}

        .hq-status-completed {{
            background: rgba(34, 197, 94, 0.14);
            color: var(--hq-success);
        }}

        .hq-status-skipped {{
            background: rgba(245, 158, 11, 0.14);
            color: var(--hq-warning);
        }}

        .hq-status-failed {{
            background: rgba(239, 68, 68, 0.13);
            color: var(--hq-danger);
        }}

        div[data-testid="stForm"],
        div[data-testid="stVerticalBlockBorderWrapper"] {{
            background: var(--hq-surface);
            border-color: var(--hq-border) !important;
            border-radius: var(--hq-radius);
            box-shadow: none;
        }}

        div[data-testid="stVerticalBlockBorderWrapper"] {{
            box-shadow: none;
        }}

        div[data-testid="stVerticalBlockBorderWrapper"] > div {{
            border-radius: var(--hq-radius);
        }}

        div[data-testid="stVerticalBlockBorderWrapper"] [data-testid="stVerticalBlock"] {{
            gap: 0.65rem;
        }}

        div[data-testid="stSegmentedControl"] {{
            margin: 0.15rem 0 0.75rem;
        }}

        div[data-testid="stSegmentedControl"] > div,
        div[data-testid="stSegmentedControl"] [role="radiogroup"],
        div[data-testid="stSegmentedControl"] [role="tablist"] {{
            background: var(--hq-surface-elevated) !important;
            border: 1px solid var(--hq-border) !important;
            border-radius: 8px !important;
            overflow: hidden;
        }}

        input[type="checkbox"],
        input[type="radio"] {{
            accent-color: var(--hq-accent) !important;
        }}

        div[data-testid="stSegmentedControl"] label,
        div[data-testid="stSegmentedControl"] p {{
            color: var(--hq-text-secondary) !important;
        }}

        div[data-testid="stSegmentedControl"] label {{
            background: transparent !important;
            border: 0 !important;
            color: var(--hq-text-primary) !important;
        }}

        div[data-testid="stSegmentedControl"] label > div,
        div[data-testid="stSegmentedControl"] button > div,
        div[data-testid="stSegmentedControl"] [role="radio"],
        div[data-testid="stSegmentedControl"] [role="tab"] {{
            background: transparent !important;
            color: var(--hq-text-primary) !important;
        }}

        div[data-testid="stSegmentedControl"] label:has(input:checked),
        div[data-testid="stSegmentedControl"] label:has(input[checked]),
        div[data-testid="stSegmentedControl"] label:has([aria-checked="true"]) {{
            background: var(--hq-accent) !important;
            border-color: var(--hq-accent-border) !important;
            color: white !important;
        }}

        div[data-testid="stSegmentedControl"] label:has(input:checked) > div,
        div[data-testid="stSegmentedControl"] label:has(input[checked]) > div,
        div[data-testid="stSegmentedControl"] label:has([aria-checked="true"]) > div {{
            background: var(--hq-accent) !important;
            color: white !important;
        }}

        div[data-testid="stSegmentedControl"] label:has(input:checked) *,
        div[data-testid="stSegmentedControl"] label:has(input[checked]) *,
        div[data-testid="stSegmentedControl"] label:has([aria-checked="true"]) * {{
            color: white !important;
        }}

        div[data-testid="stSegmentedControl"] button {{
            background: var(--hq-surface-elevated) !important;
            border: 1px solid var(--hq-border) !important;
            border-radius: 7px !important;
            color: var(--hq-text-primary) !important;
            font-weight: 720 !important;
        }}

        div[data-testid="stSegmentedControl"] button:hover {{
            background: var(--hq-muted-surface) !important;
            border-color: var(--hq-accent-border) !important;
            color: var(--hq-text-primary) !important;
        }}

        div[data-testid="stSegmentedControl"] button[aria-pressed="true"],
        div[data-testid="stSegmentedControl"] button[aria-selected="true"],
        div[data-testid="stSegmentedControl"] button[data-selected="true"],
        div[data-testid="stSegmentedControl"] [role="radio"][aria-checked="true"],
        div[data-testid="stSegmentedControl"] [role="tab"][aria-selected="true"] {{
            background: var(--hq-accent) !important;
            border-color: var(--hq-accent-border) !important;
            color: white !important;
            box-shadow: 0 0 0 1px var(--hq-accent-border) inset !important;
        }}

        div[data-testid="stSegmentedControl"] button[aria-pressed="true"] *,
        div[data-testid="stSegmentedControl"] button[aria-selected="true"] *,
        div[data-testid="stSegmentedControl"] button[data-selected="true"] *,
        div[data-testid="stSegmentedControl"] [role="radio"][aria-checked="true"] *,
        div[data-testid="stSegmentedControl"] [role="tab"][aria-selected="true"] * {{
            color: white !important;
        }}

        div[data-testid="stExpander"] details {{
            background: var(--hq-surface);
            border: 1px solid var(--hq-border);
            border-radius: var(--hq-radius);
            box-shadow: none;
            margin-bottom: 0.75rem;
        }}

        div[data-testid="stExpander"] summary {{
            background: var(--hq-surface) !important;
            color: var(--hq-text-primary);
            font-weight: 720;
            min-height: 40px;
            padding-bottom: 0.42rem !important;
            padding-top: 0.42rem !important;
        }}

        div[data-testid="stExpander"] summary:hover {{
            background: var(--hq-surface-elevated) !important;
        }}

        div[data-testid="stExpander"] summary *,
        div[data-testid="stExpander"] summary svg {{
            color: var(--hq-text-primary) !important;
            fill: var(--hq-text-primary) !important;
            stroke: var(--hq-text-primary) !important;
        }}

        div[data-testid="stExpander"] details > div {{
            background: var(--hq-surface) !important;
            border-top-color: var(--hq-border) !important;
        }}

        .stTabs [data-baseweb="tab-list"] {{
            gap: 0.25rem;
            background: transparent;
            border: 0;
            border-bottom: 1px solid var(--hq-border);
            border-radius: 0;
            margin-bottom: 0.85rem;
            padding: 0 0.15rem;
        }}

        .stTabs [data-baseweb="tab"] {{
            background: transparent;
            border: 0;
            border-radius: 0;
            color: var(--hq-text-secondary);
            font-weight: 750;
            min-height: 44px;
            padding: 0.55rem 1rem 0.82rem;
            position: relative;
            transition:
                color 160ms ease,
                background-color 160ms ease;
        }}

        .stTabs [data-baseweb="tab"]::after {{
            background: transparent;
            border-radius: 999px 999px 0 0;
            bottom: 0;
            content: "";
            height: 3px;
            left: 0.8rem;
            position: absolute;
            right: 0.8rem;
            transition:
                background-color 160ms ease,
                box-shadow 160ms ease;
        }}

        .stTabs [data-baseweb="tab"]:hover {{
            color: var(--hq-text-primary);
        }}

        .stTabs [data-baseweb="tab"]:hover::after {{
            background: var(--hq-accent-soft);
        }}

        .stTabs [aria-selected="true"] {{
            background: transparent;
            color: var(--hq-text-primary) !important;
            box-shadow: none;
        }}

        .stTabs [aria-selected="true"]::after {{
            background: var(--hq-accent);
            box-shadow: none;
        }}

        .stTabs [data-baseweb="tab-highlight"] {{
            background-color: transparent;
            height: 0;
            box-shadow: none;
        }}

        button[kind="primary"],
        div[data-testid="stFormSubmitButton"] button,
        div[data-testid="stButton"] button[kind="primary"],
        button[data-testid="stBaseButton-primary"],
        button[data-testid="baseButton-primary"] {{
            background: var(--hq-accent) !important;
            border: 1px solid var(--hq-accent-border) !important;
            border-radius: 7px !important;
            box-shadow: none;
            color: white !important;
            font-weight: 750 !important;
        }}

        button[kind="secondary"],
        div[data-testid="stButton"] button,
        button[data-testid="stBaseButton-secondary"],
        button[data-testid="baseButton-secondary"] {{
            background: var(--hq-surface-elevated) !important;
            border: 1px solid var(--hq-border) !important;
            border-radius: 7px !important;
            color: var(--hq-text-primary) !important;
            font-weight: 720 !important;
        }}

        button[kind="primary"]:hover,
        button[kind="secondary"]:hover,
        div[data-testid="stButton"] button:hover,
        div[data-testid="stFormSubmitButton"] button:hover {{
            background: var(--hq-muted-surface) !important;
            border-color: var(--hq-accent-border) !important;
            transform: none;
        }}

        button[kind="primary"]:hover,
        div[data-testid="stFormSubmitButton"] button:hover,
        div[data-testid="stButton"] button[kind="primary"]:hover,
        button[data-testid="stBaseButton-primary"]:hover,
        button[data-testid="baseButton-primary"]:hover {{
            background: var(--hq-accent) !important;
            color: white !important;
        }}

        button:disabled,
        button[disabled],
        div[data-testid="stButton"] button:disabled,
        div[data-testid="stFormSubmitButton"] button:disabled {{
            background: var(--hq-muted-surface) !important;
            border-color: var(--hq-border) !important;
            color: var(--hq-text-secondary) !important;
            opacity: 0.62 !important;
        }}

        button *,
        div[data-testid="stButton"] button *,
        div[data-testid="stFormSubmitButton"] button * {{
            color: inherit !important;
        }}

        div[data-baseweb="select"] > div,
        div[data-baseweb="input"] > div,
        div[data-baseweb="textarea"] > div,
        div[data-testid="stNumberInput"] > div,
        div[data-testid="stNumberInput"] input,
        div[data-testid="stDateInput"] > div,
        div[data-testid="stDateInput"] input,
        div[data-testid="stTimeInput"] > div,
        div[data-testid="stTimeInput"] input,
        input,
        textarea {{
            background-color: var(--hq-input-background) !important;
            border-color: var(--hq-border) !important;
            color: var(--hq-text-primary) !important;
        }}

        div[data-baseweb="select"] > div:hover,
        div[data-baseweb="input"] > div:hover,
        div[data-baseweb="textarea"] > div:hover,
        div[data-testid="stDateInput"] input:hover,
        div[data-testid="stTimeInput"] input:hover {{
            border-color: var(--hq-accent-border) !important;
        }}

        div[data-baseweb="select"] > div:hover {{
            background: var(--hq-input-background) !important;
        }}

        div[data-baseweb="select"] > div:focus-within,
        div[data-baseweb="input"] > div:focus-within,
        div[data-baseweb="textarea"] > div:focus-within,
        div[data-testid="stDateInput"] div:focus-within,
        div[data-testid="stTimeInput"] div:focus-within {{
            border-color: var(--hq-accent-border) !important;
            box-shadow: 0 0 0 1px var(--hq-accent-border) !important;
            outline-color: var(--hq-accent-border) !important;
        }}

        div[data-baseweb="select"] > div:focus-within {{
            background: var(--hq-input-background) !important;
            border-color: var(--hq-accent) !important;
            box-shadow: none !important;
        }}

        div[data-baseweb="input"] > div:focus-within,
        div[data-testid="stNumberInput"] > div:focus-within,
        div[data-testid="stDateInput"] > div:focus-within,
        div[data-testid="stTimeInput"] > div:focus-within {{
            border-color: var(--hq-accent-border) !important;
            box-shadow: 0 0 0 1px var(--hq-accent-border) !important;
        }}

        div[data-testid="stDateInput"] > div:focus-within,
        div[data-testid="stDateInput"] input:focus {{
            border-color: var(--hq-border) !important;
            box-shadow: none !important;
            outline: none !important;
        }}

        input:focus,
        textarea:focus {{
            border-color: var(--hq-accent-border) !important;
            box-shadow: none !important;
            outline-color: var(--hq-accent-border) !important;
        }}

        div[data-baseweb="input"] > div,
        div[data-testid="stNumberInput"] > div,
        div[data-testid="stDateInput"] > div,
        div[data-testid="stTimeInput"] > div {{
            box-shadow: none !important;
        }}

        div[data-baseweb="select"] svg,
        div[data-baseweb="input"] svg,
        div[data-testid="stDateInput"] svg,
        div[data-testid="stTimeInput"] svg {{
            color: var(--hq-text-secondary) !important;
            fill: var(--hq-text-secondary) !important;
        }}

        div[data-testid="stMultiSelect"] [data-baseweb="tag"],
        div[data-baseweb="select"] [data-baseweb="tag"],
        span[data-baseweb="tag"] {{
            background: var(--hq-accent) !important;
            border-color: var(--hq-accent-border) !important;
            color: white !important;
        }}

        div[data-testid="stMultiSelect"] [data-baseweb="tag"] *,
        div[data-baseweb="select"] [data-baseweb="tag"] *,
        span[data-baseweb="tag"] * {{
            color: white !important;
            fill: white !important;
            stroke: white !important;
        }}

        div[data-testid="stNumberInput"] button,
        div[data-testid="stNumberInput"] button[kind],
        div[data-testid="stDateInput"] button,
        div[data-testid="stTimeInput"] button {{
            background: var(--hq-surface-elevated) !important;
            border-color: var(--hq-border) !important;
            color: var(--hq-text-primary) !important;
        }}

        div[data-testid="stNumberInput"] button:hover,
        div[data-testid="stDateInput"] button:hover,
        div[data-testid="stTimeInput"] button:hover {{
            background: var(--hq-accent-soft) !important;
            border-color: var(--hq-accent-border) !important;
            color: var(--hq-text-primary) !important;
        }}

        div[data-testid="stNumberInput"] button svg,
        div[data-testid="stDateInput"] button svg,
        div[data-testid="stTimeInput"] button svg {{
            color: var(--hq-text-primary) !important;
            fill: var(--hq-text-primary) !important;
            stroke: var(--hq-text-primary) !important;
        }}

        div[role="radiogroup"] label,
        div[data-testid="stRadio"] label,
        div[data-baseweb="radio"] label {{
            color: var(--hq-text-primary) !important;
        }}

        div[data-testid="stRadio"] label,
        div[data-testid="stCheckbox"] label {{
            color: var(--hq-text-primary) !important;
        }}

        div[data-testid="stRadio"] label p,
        div[data-testid="stCheckbox"] label p {{
            color: var(--hq-text-primary) !important;
        }}

        div[data-testid="stCheckbox"] [role="checkbox"],
        div[data-testid="stCheckbox"] label > div:first-child,
        div[data-baseweb="checkbox"] [role="checkbox"] {{
            background: var(--hq-input-background) !important;
            border-color: var(--hq-border) !important;
        }}

        div[data-testid="stCheckbox"] [role="checkbox"][aria-checked="true"],
        div[data-testid="stCheckbox"] label:has(input:checked) > div:first-child,
        div[data-baseweb="checkbox"] [role="checkbox"][aria-checked="true"] {{
            background: var(--hq-accent) !important;
            border-color: var(--hq-accent) !important;
            color: white !important;
        }}

        div[data-testid="stCheckbox"] [role="checkbox"][aria-checked="true"] *,
        div[data-testid="stCheckbox"] label:has(input:checked) > div:first-child *,
        div[data-baseweb="checkbox"] [role="checkbox"][aria-checked="true"] * {{
            color: white !important;
            fill: white !important;
            stroke: white !important;
        }}

        div[role="radiogroup"] label > div:first-child,
        div[data-testid="stRadio"] label > div:first-child,
        div[data-baseweb="radio"] div:first-child {{
            background: var(--hq-input-background) !important;
            border-color: var(--hq-border) !important;
        }}

        div[role="radiogroup"] [aria-checked="true"],
        div[data-testid="stRadio"] [aria-checked="true"],
        div[data-testid="stRadio"] label:has(input:checked) > div:first-child,
        div[data-baseweb="radio"] [aria-checked="true"] {{
            background: var(--hq-accent) !important;
            border-color: var(--hq-accent) !important;
            color: var(--hq-accent) !important;
        }}

        div[role="radiogroup"] [aria-checked="true"] *,
        div[data-testid="stRadio"] [aria-checked="true"] *,
        div[data-testid="stRadio"] label:has(input:checked) > div:first-child *,
        div[data-baseweb="radio"] [aria-checked="true"] * {{
            color: var(--hq-accent) !important;
            fill: var(--hq-accent) !important;
            border-color: var(--hq-accent) !important;
        }}

        div[data-baseweb="popover"],
        div[data-baseweb="menu"],
        div[data-baseweb="popover"] > div {{
            background: {tokens["surface"]} !important;
            border: 1px solid var(--hq-border) !important;
            color: {tokens["text_primary"]} !important;
        }}

        div[data-baseweb="popover"] ul,
        div[data-baseweb="menu"] ul,
        ul[role="listbox"] {{
            background: {tokens["surface"]} !important;
            color: {tokens["text_primary"]} !important;
        }}

        div[data-baseweb="menu"] li,
        div[role="listbox"] li,
        div[role="option"] {{
            background: {tokens["surface"]} !important;
            background-image: none !important;
            border-left: 3px solid transparent !important;
            color: {tokens["text_primary"]} !important;
            transition:
                background-color 140ms ease,
                border-color 140ms ease,
                color 140ms ease;
        }}

        div[data-baseweb="menu"] li > div,
        div[role="listbox"] li > div,
        div[role="option"] > div {{
            background: transparent !important;
            background-image: none !important;
            color: {tokens["text_primary"]} !important;
        }}

        div[data-baseweb="menu"] li:hover,
        div[data-baseweb="menu"] li[data-highlighted="true"],
        div[data-baseweb="menu"] li[aria-current="true"],
        div[data-baseweb="menu"] li[aria-selected="true"],
        div[role="listbox"] li:hover,
        div[role="listbox"] li[data-highlighted="true"],
        div[role="listbox"] li[aria-current="true"],
        div[role="listbox"] li[aria-selected="true"],
        div[role="option"]:hover,
        div[role="option"][data-highlighted="true"],
        div[role="option"][aria-current="true"],
        div[role="option"][aria-selected="true"] {{
            background-color: rgba(var(--primary-color-rgb), 0.16) !important;
            background-image: none !important;
            border-left-color: var(--hq-accent) !important;
            box-shadow: inset 3px 0 0 var(--hq-accent) !important;
            color: {tokens["text_primary"]} !important;
        }}

        div[data-baseweb="menu"] li:hover > div,
        div[data-baseweb="menu"] li[data-highlighted="true"] > div,
        div[data-baseweb="menu"] li[aria-current="true"] > div,
        div[data-baseweb="menu"] li[aria-selected="true"] > div,
        div[role="listbox"] li:hover > div,
        div[role="listbox"] li[data-highlighted="true"] > div,
        div[role="listbox"] li[aria-current="true"] > div,
        div[role="listbox"] li[aria-selected="true"] > div,
        div[role="option"]:hover > div,
        div[role="option"][data-highlighted="true"] > div,
        div[role="option"][aria-current="true"] > div,
        div[role="option"][aria-selected="true"] > div {{
            background-color: transparent !important;
            background-image: none !important;
            color: {tokens["text_primary"]} !important;
        }}

        div[data-baseweb="menu"] li[aria-selected="true"],
        div[role="listbox"] li[aria-selected="true"],
        div[role="option"][aria-selected="true"] {{
            background-color: rgba(var(--primary-color-rgb), 0.2) !important;
            background-image: none !important;
            border-left-color: var(--hq-accent) !important;
            box-shadow: inset 3px 0 0 var(--hq-accent) !important;
            color: {tokens["text_primary"]} !important;
            font-weight: 740 !important;
        }}

        .stProgress > div > div > div > div {{
            background-color: var(--hq-accent);
        }}

        .stProgress > div > div > div {{
            background-color: var(--hq-muted-surface);
        }}

        .hq-card-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 0.85rem;
            margin-top: 0.75rem;
        }}

        .hq-card,
        .hq-empty-state,
        .hq-metric-card {{
            background: var(--hq-surface);
            border: 1px solid var(--hq-border);
            border-radius: var(--hq-radius);
            box-shadow: none;
        }}

        .hq-card {{
            padding: 1rem;
        }}

        .hq-card-title {{
            color: var(--hq-text-primary);
            font-size: 0.96rem;
            font-weight: 780;
            margin-bottom: 0.28rem;
        }}

        .hq-card-body {{
            color: var(--hq-text-secondary);
            font-size: 0.9rem;
            line-height: 1.45;
        }}

        .hq-empty-state {{
            padding: 1rem 1.1rem;
            margin: 0.65rem 0 0.9rem;
            border-left: 3px solid var(--hq-accent);
        }}

        .hq-empty-state .hq-empty-body {{
            max-width: 58ch;
        }}

        .hq-empty-compact {{
            background: var(--hq-muted-surface);
            border: 1px solid var(--hq-border);
            border-radius: var(--hq-radius);
            color: var(--hq-text-secondary);
            display: grid;
            gap: 0.18rem;
            margin: 0.45rem 0 0.25rem;
            padding: 0.72rem 0.85rem;
        }}

        .hq-empty-compact strong {{
            color: var(--hq-text-primary);
            font-size: 0.9rem;
        }}

        .hq-empty-compact span {{
            font-size: 0.84rem;
            line-height: 1.35;
        }}

        .hq-empty-title {{
            color: var(--hq-text-primary);
            font-weight: 780;
            margin-bottom: 0.25rem;
        }}

        .hq-empty-body {{
            color: var(--hq-text-secondary);
            line-height: 1.45;
        }}

        div[data-testid="stButton"] button,
        div[data-testid="stFormSubmitButton"] button {{
            min-height: 38px;
        }}

        .hq-metric-card {{
            padding: 1rem;
        }}

        .hq-metric-label {{
            color: var(--hq-text-secondary);
            font-size: 0.76rem;
            font-weight: 750;
            letter-spacing: 0.05em;
            text-transform: uppercase;
        }}

        .hq-metric-value {{
            color: var(--hq-text-primary);
            font-size: 1.7rem;
            font-weight: 850;
            line-height: 1.2;
            margin-top: 0.25rem;
        }}

        .hq-metric-card::before {{
            background: var(--hq-accent);
            border-radius: 999px;
            content: "";
            display: block;
            height: 0.2rem;
            margin-bottom: 0.65rem;
            width: 2rem;
        }}

        .hq-metric-caption {{
            color: var(--hq-text-secondary);
            font-size: 0.82rem;
            margin-top: 0.25rem;
        }}

        .hq-list-panel {{
            background: var(--hq-surface);
            border: 1px solid var(--hq-border);
            border-radius: var(--hq-radius);
            box-shadow: none;
            overflow: hidden;
        }}

        .hq-chart-panel {{
            background: var(--hq-surface);
            border: 1px solid var(--hq-border);
            border-radius: var(--hq-radius);
            box-shadow: none;
            margin-bottom: 0.9rem;
            padding: 0.65rem 0.75rem 0.35rem;
        }}

        .hq-progress-card {{
            background: var(--hq-surface);
            border: 1px solid var(--hq-border);
            border-radius: var(--hq-radius);
            box-shadow: none;
            margin: 0.65rem 0;
            padding: 0.9rem 1rem;
        }}

        .hq-progress-card-header {{
            align-items: start;
            display: grid;
            gap: 1rem;
            grid-template-columns: minmax(0, 1fr) minmax(150px, 0.26fr);
        }}

        .hq-progress-title {{
            color: var(--hq-text-primary);
            font-size: 1rem;
            font-weight: 740;
            line-height: 1.25;
            margin-bottom: 0.22rem;
        }}

        .hq-progress-meta,
        .hq-progress-caption {{
            color: var(--hq-text-secondary);
            font-size: 0.84rem;
            line-height: 1.35;
        }}

        .hq-progress-value {{
            color: var(--hq-text-primary);
            font-size: 0.96rem;
            font-weight: 740;
            line-height: 1.25;
            text-align: right;
        }}

        .hq-progress-track {{
            background: var(--hq-muted-surface);
            border-radius: 999px;
            height: 0.55rem;
            margin: 0.85rem 0 0.48rem;
            overflow: hidden;
            width: 100%;
        }}

        .hq-progress-fill {{
            background: var(--hq-accent);
            border-radius: inherit;
            height: 100%;
            min-width: 0;
        }}

        .hq-progress-footer {{
            align-items: center;
            display: flex;
            flex-wrap: wrap;
            gap: 0.5rem 0.9rem;
            justify-content: space-between;
        }}

        .hq-progress-pill {{
            background: var(--hq-muted-surface);
            border-radius: 999px;
            color: var(--hq-text-secondary);
            display: inline-flex;
            font-size: 0.78rem;
            font-weight: 680;
            line-height: 1;
            padding: 0.35rem 0.55rem;
        }}

        .hq-management-item {{
            background: var(--hq-surface);
            border: 1px solid var(--hq-border);
            border-radius: var(--hq-radius);
            box-shadow: none;
            margin: 0.45rem 0;
            padding: 0.72rem 0.82rem;
        }}

        .hq-management-title {{
            color: var(--hq-text-primary);
            font-size: 0.96rem;
            font-weight: 720;
            line-height: 1.25;
            margin-bottom: 0.18rem;
        }}

        .hq-management-meta {{
            color: var(--hq-text-secondary);
            font-size: 0.83rem;
            line-height: 1.35;
        }}

        .hq-compact-intro {{
            background: var(--hq-muted-surface);
            border: 1px solid var(--hq-border);
            border-radius: var(--hq-radius);
            margin: 0 0 0.75rem;
            padding: 0.7rem 0.82rem;
        }}

        .hq-compact-title {{
            color: var(--hq-text-primary);
            font-size: 0.98rem;
            font-weight: 780;
            line-height: 1.25;
        }}

        .hq-compact-body {{
            color: var(--hq-text-secondary);
            font-size: 0.84rem;
            line-height: 1.35;
            margin-top: 0.18rem;
        }}

        .hq-side-note {{
            background: var(--hq-accent-soft);
            border: 1px solid var(--hq-border);
            border-radius: var(--hq-radius);
            color: var(--hq-text-secondary);
            display: grid;
            gap: 0.25rem;
            margin-top: 0;
            padding: 0.82rem 0.9rem;
        }}

        .hq-side-note strong {{
            color: var(--hq-text-primary);
            font-size: 0.9rem;
            line-height: 1.25;
        }}

        .hq-side-note span {{
            font-size: 0.83rem;
            line-height: 1.4;
        }}

        .hq-meta-pills {{
            display: flex;
            flex-wrap: wrap;
            gap: 0.45rem;
            margin: 0.6rem 0 0.75rem;
        }}

        .hq-meta-pill {{
            background: var(--hq-muted-surface);
            border: 1px solid var(--hq-border);
            border-radius: 999px;
            color: var(--hq-text-secondary);
            display: inline-flex;
            font-size: 0.78rem;
            font-weight: 680;
            line-height: 1;
            padding: 0.4rem 0.58rem;
        }}

        .hq-meta-pill strong {{
            color: var(--hq-text-primary);
            font-weight: 740;
            margin-right: 0.25rem;
        }}

        .hq-status-panel {{
            background: var(--hq-surface);
            border: 1px solid var(--hq-border);
            border-radius: var(--hq-radius);
            box-shadow: none;
            margin: 0.45rem 0 0.9rem;
            padding: 0.85rem 0.95rem;
        }}

        .hq-status-label {{
            color: var(--hq-text-secondary);
            font-size: 0.74rem;
            font-weight: 720;
            letter-spacing: 0.05em;
            margin-bottom: 0.25rem;
            text-transform: uppercase;
        }}

        .hq-status-value {{
            color: var(--hq-text-primary);
            font-size: 1rem;
            font-weight: 740;
            line-height: 1.35;
        }}

        .planner-day-summary {{
            display: grid;
            gap: 0.5rem;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            margin: 0.7rem 0 0.9rem;
        }}

        .planner-day-stat {{
            background: var(--hq-surface-elevated);
            border: 1px solid var(--hq-border);
            border-radius: 6px;
            display: grid;
            gap: 0.12rem;
            padding: 0.55rem 0.62rem;
        }}

        .planner-day-stat span {{
            color: var(--hq-text-secondary);
            font-size: 0.72rem;
            font-weight: 720;
            line-height: 1.2;
            text-transform: uppercase;
        }}

        .planner-day-stat strong {{
            color: var(--hq-text-primary);
            font-size: 0.92rem;
            line-height: 1.25;
        }}

        .hq-legend-row {{
            align-items: center;
            display: flex;
            flex-wrap: wrap;
            gap: 0.45rem;
            margin: 0.45rem 0 0.75rem;
        }}

        .hq-legend-item {{
            align-items: center;
            background: var(--hq-muted-surface);
            border-radius: 999px;
            color: var(--hq-text-secondary);
            display: inline-flex;
            font-size: 0.78rem;
            gap: 0.34rem;
            line-height: 1;
            padding: 0.36rem 0.54rem;
        }}

        .hq-legend-marker {{
            color: var(--hq-text-primary);
            font-weight: 760;
            min-width: 1rem;
            text-align: center;
        }}

        @media (max-width: 720px) {{
            .hq-progress-card-header {{
                grid-template-columns: 1fr;
            }}

            .hq-progress-value {{
                text-align: left;
            }}
        }}

        .hq-list-row {{
            align-items: center;
            display: grid;
            gap: 0.85rem;
            grid-template-columns: minmax(92px, 0.22fr) minmax(0, 1fr) minmax(72px, 0.16fr);
            min-height: 62px;
            padding: 0.72rem 0.9rem;
        }}

        .hq-list-row + .hq-list-row {{
            border-top: 1px solid var(--hq-border);
        }}

        .hq-list-time,
        .hq-list-meta {{
            color: var(--hq-text-secondary);
            font-size: 0.84rem;
            line-height: 1.25;
        }}

        .hq-list-time,
        .hq-list-value {{
            font-weight: 720;
        }}

        .hq-list-title {{
            color: var(--hq-text-primary);
            font-size: 0.94rem;
            font-weight: 720;
            line-height: 1.25;
        }}

        .hq-list-meta {{
            margin-top: 0.15rem;
        }}

        .hq-list-value {{
            color: var(--hq-text-primary);
            font-size: 0.9rem;
            text-align: right;
            white-space: nowrap;
        }}

        @media (max-width: 720px) {{
            .hq-list-row {{
                grid-template-columns: 1fr;
            }}

            .hq-list-value {{
                text-align: left;
            }}
        }}

        [data-testid="stPlotlyChart"] {{
            background: transparent;
            border: 0;
            border-radius: 0;
            box-shadow: none;
            padding: 0;
        }}

        @media (max-width: 768px) {{
            h1,
            .hq-page-title {{
                font-size: 1.55rem !important;
            }}

            .hq-page-subtitle {{
                font-size: 0.92rem;
            }}

            .hq-section-title {{
                margin-top: 1.2rem;
            }}

            .hq-empty-state {{
                padding: 0.85rem 0.9rem;
            }}

            .stTabs [data-baseweb="tab"] {{
                min-height: 40px;
                padding-left: 0.72rem;
                padding-right: 0.72rem;
            }}
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def apply_theme() -> None:
    """Backward-compatible alias for existing pages."""
    apply_global_styles()


def render_page_header(kicker: str, title: str, subtitle: str) -> None:
    st.markdown(
        f"""
        <div class="hq-page-header">
            <div class="hq-page-kicker">{escape(kicker)}</div>
            <h1 class="hq-page-title">{escape(title)}</h1>
            <div class="hq-page-subtitle">{escape(subtitle)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_section_title(title: str, description: str | None = None) -> None:
    st.markdown(f'<div class="hq-section-title">{escape(title)}</div>', unsafe_allow_html=True)
    if description:
        st.markdown(
            f'<div class="hq-section-description">{escape(description)}</div>',
            unsafe_allow_html=True,
        )


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

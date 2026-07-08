from __future__ import annotations

from html import escape
from typing import TypedDict

import streamlit as st


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

THEME_MODES = ("Dark", "Light")
ACCENT_PRESETS = {
    "Violet": {
        "accent": "#8B5CF6",
        "accent_soft_dark": "rgba(139, 92, 246, 0.18)",
        "accent_soft_light": "rgba(139, 92, 246, 0.12)",
        "accent_border_dark": "rgba(167, 139, 250, 0.42)",
        "accent_border_light": "rgba(124, 58, 237, 0.28)",
    },
    "Cyan": {
        "accent": "#0891B2",
        "accent_soft_dark": "rgba(8, 145, 178, 0.2)",
        "accent_soft_light": "rgba(8, 145, 178, 0.12)",
        "accent_border_dark": "rgba(34, 211, 238, 0.42)",
        "accent_border_light": "rgba(8, 145, 178, 0.28)",
    },
    "Emerald": {
        "accent": "#10B981",
        "accent_soft_dark": "rgba(16, 185, 129, 0.18)",
        "accent_soft_light": "rgba(16, 185, 129, 0.12)",
        "accent_border_dark": "rgba(52, 211, 153, 0.4)",
        "accent_border_light": "rgba(5, 150, 105, 0.28)",
    },
    "Rose": {
        "accent": "#E11D48",
        "accent_soft_dark": "rgba(225, 29, 72, 0.18)",
        "accent_soft_light": "rgba(225, 29, 72, 0.11)",
        "accent_border_dark": "rgba(251, 113, 133, 0.4)",
        "accent_border_light": "rgba(225, 29, 72, 0.28)",
    },
}

BASE_TOKENS = {
    "Dark": {
        "background": "#0F172A",
        "background_alt": "#111827",
        "surface": "#172033",
        "surface_elevated": "#1F2937",
        "border": "rgba(148, 163, 184, 0.22)",
        "text_primary": "#F8FAFC",
        "text_secondary": "#A7B0BF",
        "success": "#22C55E",
        "warning": "#F59E0B",
        "danger": "#EF4444",
        "info": "#38BDF8",
        "shadow": "0 18px 44px rgba(2, 6, 23, 0.32)",
        "input_background": "rgba(15, 23, 42, 0.72)",
        "muted_surface": "rgba(15, 23, 42, 0.62)",
        "chart_grid": "rgba(148, 163, 184, 0.18)",
    },
    "Light": {
        "background": "#F4F7FB",
        "background_alt": "#E9EEF6",
        "surface": "#FFFFFF",
        "surface_elevated": "#F8FAFC",
        "border": "rgba(100, 116, 139, 0.22)",
        "text_primary": "#111827",
        "text_secondary": "#5B6472",
        "success": "#15803D",
        "warning": "#B45309",
        "danger": "#DC2626",
        "info": "#0369A1",
        "shadow": "0 16px 38px rgba(15, 23, 42, 0.1)",
        "input_background": "rgba(255, 255, 255, 0.88)",
        "muted_surface": "rgba(241, 245, 249, 0.88)",
        "chart_grid": "rgba(100, 116, 139, 0.2)",
    },
}

# Backward-compatible color constants used by older page code and tests.
TEXT_MUTED = "#9CA3AF"
SURFACE = "#111827"
SURFACE_LIGHT = "#1F2937"
PRIMARY = "#8B5CF6"
SUCCESS = "#22C55E"
WARNING = "#F59E0B"
DANGER = "#EF4444"
INFO = "#38BDF8"


def _safe_theme_mode(value: str | None) -> str:
    return value if value in THEME_MODES else "Dark"


def _safe_accent_preset(value: str | None) -> str:
    return value if value in ACCENT_PRESETS else "Violet"


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
        "Theme Mode",
        options=list(THEME_MODES),
        key=THEME_MODE_KEY,
        horizontal=True,
        label_visibility="visible",
    )
    st.sidebar.selectbox(
        "Accent Preset",
        options=list(ACCENT_PRESETS),
        key=ACCENT_PRESET_KEY,
        label_visibility="visible",
    )


def apply_global_styles() -> None:
    """Apply token-based app-wide styles."""
    tokens = get_theme_tokens()
    is_dark = tokens["mode"] == "Dark"
    if is_dark:
        app_background = (
            f"radial-gradient(circle at 8% 0%, {tokens['accent_soft']}, transparent 30rem), "
            "radial-gradient(circle at 92% 12%, rgba(56, 189, 248, 0.11), transparent 28rem), "
            "radial-gradient(circle at 72% 88%, rgba(34, 197, 94, 0.08), transparent 30rem), "
            "linear-gradient(135deg, rgba(255, 255, 255, 0.035) 0 1px, transparent 1px), "
            f"linear-gradient(180deg, {tokens['background']} 0%, {tokens['background_alt']} 48%, #0B1120 100%)"
        )
    else:
        app_background = (
            f"radial-gradient(circle at 7% 0%, {tokens['accent_soft']}, transparent 30rem), "
            "radial-gradient(circle at 92% 10%, rgba(14, 165, 233, 0.13), transparent 27rem), "
            "radial-gradient(circle at 72% 88%, rgba(16, 185, 129, 0.1), transparent 31rem), "
            "linear-gradient(135deg, rgba(15, 23, 42, 0.045) 0 1px, transparent 1px), "
            f"linear-gradient(180deg, {tokens['background']} 0%, #EEF4FB 50%, {tokens['background_alt']} 100%)"
        )
    app_background_size = (
        "auto, auto, auto, 38px 38px, auto"
    )
    sidebar_background = (
        f"linear-gradient(180deg, {tokens['background']} 0%, {tokens['background_alt']} 100%)"
        if is_dark
        else "linear-gradient(180deg, #FFFFFF 0%, #F1F5F9 100%)"
    )

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
        }}

        .stApp {{
            background: {app_background};
            background-attachment: fixed;
            background-size: {app_background_size};
            color: var(--hq-text-primary);
        }}

        .stApp::before {{
            content: "";
            inset: 0;
            pointer-events: none;
            position: fixed;
            z-index: 0;
            background:
                linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.04), transparent),
                radial-gradient(circle at 50% 0%, rgba(255, 255, 255, 0.05), transparent 34rem);
            opacity: {"0.55" if is_dark else "0.72"};
        }}

        .stApp > header,
        .stApp [data-testid="stAppViewContainer"],
        .stApp section[data-testid="stSidebar"] {{
            position: relative;
            z-index: 1;
        }}

        .block-container {{
            max-width: 1480px;
            padding: 2.35rem 2rem 3rem;
        }}

        @media (max-width: 768px) {{
            .block-container {{
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

        section[data-testid="stSidebar"] {{
            background: {sidebar_background} !important;
            border-right: 1px solid var(--hq-border);
        }}

        section[data-testid="stSidebar"] > div {{
            padding-top: 1.1rem;
        }}

        .hq-sidebar-brand {{
            background:
                linear-gradient(135deg, var(--hq-accent-soft), transparent 78%),
                var(--hq-surface);
            border: 1px solid var(--hq-border);
            border-left: 4px solid var(--hq-accent);
            border-radius: 3px;
            box-shadow: var(--hq-shadow);
            margin: 0.2rem 0 1rem;
            padding: 0.85rem 0.9rem;
        }}

        .hq-sidebar-brand-title {{
            color: var(--hq-text-primary);
            font-size: 1rem;
            font-weight: 850;
            line-height: 1.12;
        }}

        .hq-sidebar-brand-subtitle,
        .hq-sidebar-section-title {{
            color: var(--hq-accent);
            font-size: 0.74rem;
            font-weight: 800;
            letter-spacing: 0.08em;
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
            background: var(--hq-muted-surface);
            border: 1px solid var(--hq-border);
            border-left: 4px solid var(--hq-border);
            border-radius: 3px !important;
            color: var(--hq-text-secondary) !important;
            min-height: 46px;
            padding: 0.78rem 0.85rem !important;
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
            background: var(--hq-surface-elevated);
            border-color: var(--hq-accent-border);
            border-left-color: var(--hq-accent);
            box-shadow: var(--hq-shadow);
            color: var(--hq-text-primary) !important;
            transform: translateX(3px);
        }}

        section[data-testid="stSidebar"] nav a[aria-current="page"],
        section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a[aria-current="page"],
        section[data-testid="stSidebar"] [data-testid="stPageLink"] a[aria-current="page"],
        section[data-testid="stSidebar"] a[aria-current="page"],
        section[data-testid="stSidebar"] a[data-active="true"] {{
            background:
                linear-gradient(135deg, var(--hq-accent-soft), transparent 78%),
                var(--hq-surface-elevated);
            border-color: var(--hq-accent-border);
            border-left-color: var(--hq-accent);
            box-shadow: var(--hq-shadow);
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
            margin-bottom: 1.35rem;
            padding-top: 0.85rem;
        }}

        h1,
        .hq-page-title {{
            color: var(--hq-text-primary) !important;
            font-size: 2.18rem !important;
            font-weight: 850 !important;
            line-height: 1.15 !important;
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
            font-weight: 800;
            letter-spacing: 0.08em;
            line-height: 1.35;
            margin-bottom: 0.3rem;
            text-transform: uppercase;
        }}

        .hq-page-subtitle {{
            color: var(--hq-text-secondary);
            font-size: 1rem;
            line-height: 1.6;
            margin-bottom: 0;
            max-width: 920px;
        }}

        .hq-section-title {{
            color: var(--hq-text-primary);
            font-size: 1.12rem;
            font-weight: 780;
            margin-top: 1.6rem;
            margin-bottom: 0.25rem;
        }}

        .hq-section-description {{
            color: var(--hq-text-secondary);
            font-size: 0.9rem;
            line-height: 1.45;
            margin-bottom: 0.85rem;
        }}

        div[data-testid="stMetric"] {{
            background:
                linear-gradient(135deg, var(--hq-accent-soft), transparent 76%),
                linear-gradient(180deg, var(--hq-surface), var(--hq-surface-elevated));
            border: 1px solid var(--hq-border);
            border-left: 4px solid var(--hq-accent);
            border-radius: var(--hq-radius);
            box-shadow: var(--hq-shadow);
            padding: 1rem 1.05rem;
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
            border-left: 4px solid var(--hq-accent);
            border-radius: var(--hq-radius);
            box-shadow: 0 10px 24px rgba(15, 23, 42, 0.08);
            color: var(--hq-text-primary);
        }}

        div[data-testid="stDataFrame"] {{
            border: 1px solid var(--hq-border);
            border-radius: var(--hq-radius);
            overflow: hidden;
            box-shadow: 0 10px 24px rgba(15, 23, 42, 0.08);
        }}

        div[data-testid="stForm"],
        div[data-testid="stVerticalBlockBorderWrapper"] {{
            background:
                linear-gradient(135deg, var(--hq-accent-soft), transparent 84%),
                var(--hq-surface);
            border-color: var(--hq-border) !important;
            border-radius: var(--hq-radius);
            box-shadow: var(--hq-shadow);
        }}

        div[data-testid="stExpander"] details {{
            background: var(--hq-surface);
            border: 1px solid var(--hq-border);
            border-radius: var(--hq-radius);
            box-shadow: 0 10px 24px rgba(15, 23, 42, 0.08);
        }}

        div[data-testid="stExpander"] summary {{
            color: var(--hq-text-primary);
            font-weight: 750;
        }}

        .stTabs [data-baseweb="tab-list"] {{
            gap: 0.45rem;
            background: var(--hq-muted-surface);
            border: 1px solid var(--hq-border);
            border-radius: var(--hq-radius);
            padding: 0.35rem;
        }}

        .stTabs [data-baseweb="tab"] {{
            border-radius: 6px;
            color: var(--hq-text-secondary);
            font-weight: 750;
            min-height: 42px;
            padding: 0.5rem 0.85rem;
        }}

        .stTabs [aria-selected="true"] {{
            background:
                linear-gradient(135deg, var(--hq-accent-soft), transparent 75%),
                var(--hq-surface-elevated);
            border: 1px solid var(--hq-accent-border);
            color: var(--hq-text-primary) !important;
            box-shadow: 0 8px 20px rgba(15, 23, 42, 0.12);
        }}

        .stTabs [data-baseweb="tab-highlight"] {{
            background-color: var(--hq-accent);
        }}

        button[kind="primary"],
        div[data-testid="stFormSubmitButton"] button {{
            background: var(--hq-accent) !important;
            border: 1px solid var(--hq-accent-border) !important;
            border-radius: 7px !important;
            box-shadow: 0 10px 22px rgba(15, 23, 42, 0.16);
            color: white !important;
            font-weight: 750 !important;
        }}

        button[kind="secondary"] {{
            background: var(--hq-surface-elevated) !important;
            border: 1px solid var(--hq-border) !important;
            border-radius: 7px !important;
            color: var(--hq-text-primary) !important;
            font-weight: 720 !important;
        }}

        button[kind="primary"]:hover,
        button[kind="secondary"]:hover,
        div[data-testid="stFormSubmitButton"] button:hover {{
            border-color: var(--hq-accent-border) !important;
            transform: translateY(-1px);
        }}

        div[data-baseweb="select"] > div,
        div[data-baseweb="input"] > div,
        div[data-baseweb="textarea"] > div,
        div[data-testid="stDateInput"] input,
        div[data-testid="stTimeInput"] input,
        input,
        textarea {{
            background-color: var(--hq-input-background) !important;
            border-color: var(--hq-border) !important;
            color: var(--hq-text-primary) !important;
        }}

        div[data-baseweb="popover"],
        div[data-baseweb="menu"] {{
            background: var(--hq-surface) !important;
            border: 1px solid var(--hq-border) !important;
            color: var(--hq-text-primary) !important;
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
            background:
                linear-gradient(135deg, var(--hq-accent-soft), transparent 82%),
                linear-gradient(180deg, var(--hq-surface), var(--hq-surface-elevated));
            border: 1px solid var(--hq-border);
            border-radius: var(--hq-radius);
            box-shadow: var(--hq-shadow);
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

        .hq-metric-card {{
            border-left: 4px solid var(--hq-accent);
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

        .hq-metric-caption {{
            color: var(--hq-text-secondary);
            font-size: 0.82rem;
            margin-top: 0.25rem;
        }}

        [data-testid="stPlotlyChart"] {{
            background: var(--hq-surface);
            border: 1px solid var(--hq-border);
            border-radius: var(--hq-radius);
            box-shadow: 0 10px 24px rgba(15, 23, 42, 0.08);
            padding: 0.25rem;
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

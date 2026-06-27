from html import escape

import streamlit as st


TEXT_MUTED = "#9CA3AF"
SURFACE = "#111827"
SURFACE_LIGHT = "#1F2937"
PRIMARY = "#8B5CF6"
SUCCESS = "#22C55E"
WARNING = "#F59E0B"
DANGER = "#EF4444"
INFO = "#38BDF8"


def apply_global_styles() -> None:
    """Apply lightweight app-wide dark dashboard styles."""
    st.markdown(
        """
        <style>
        .stApp {
            background:
                radial-gradient(circle at top left, rgba(139, 92, 246, 0.16), transparent 34rem),
                linear-gradient(180deg, #0f172a 0%, #111827 100%);
        }

        .block-container {
            max-width: 1480px;
            padding: 2.4rem 2rem 3rem;
        }

        @media (max-width: 768px) {
            .block-container {
                padding-left: 1rem;
                padding-right: 1rem;
            }
        }

        .hq-page-header {
            margin-bottom: 1.35rem;
            padding-top: 0.85rem;
        }

        h1 {
            color: #f9fafb !important;
            font-size: 2.15rem !important;
            line-height: 1.15 !important;
            margin-bottom: 0.35rem !important;
        }

        .hq-page-title {
            color: #f9fafb;
            font-size: 2.15rem;
            font-weight: 800;
            line-height: 1.22;
            margin: 0.15rem 0 0.55rem;
        }

        h2 {
            color: #f9fafb !important;
            font-size: 1.25rem !important;
            margin-top: 1.65rem !important;
            padding-top: 0.2rem !important;
        }

        h3 {
            color: #f9fafb !important;
            font-size: 1.02rem !important;
        }

        p, li, label, span {
            color: inherit;
        }

        div[data-testid="stMetric"] {
            background: linear-gradient(180deg, rgba(31, 41, 55, 0.98), rgba(17, 24, 39, 0.98));
            border: 1px solid rgba(148, 163, 184, 0.2);
            border-radius: 8px;
            padding: 1rem 1.05rem;
            box-shadow: 0 12px 26px rgba(2, 6, 23, 0.22);
        }

        div[data-testid="stMetricLabel"] p {
            color: #9ca3af !important;
            font-size: 0.78rem !important;
            letter-spacing: 0.03em;
            text-transform: uppercase;
        }

        div[data-testid="stMetricValue"] {
            color: #f9fafb !important;
        }

        div[data-testid="stAlert"] {
            background: rgba(31, 41, 55, 0.86);
            border: 1px solid rgba(148, 163, 184, 0.22);
            border-radius: 8px;
            color: #f9fafb;
        }

        div[data-testid="stDataFrame"] {
            border: 1px solid rgba(148, 163, 184, 0.22);
            border-radius: 8px;
            overflow: hidden;
        }

        div[data-testid="stForm"], div[data-testid="stVerticalBlockBorderWrapper"] {
            border-color: rgba(148, 163, 184, 0.22) !important;
            background: rgba(17, 24, 39, 0.72);
            border-radius: 8px;
        }

        button[kind="primary"], button[kind="secondary"] {
            border-radius: 7px !important;
        }

        .stProgress > div > div > div > div {
            background-color: #8b5cf6;
        }

        .hq-page-kicker {
            color: #a78bfa;
            font-size: 0.76rem;
            font-weight: 800;
            letter-spacing: 0.08em;
            line-height: 1.35;
            margin-bottom: 0.3rem;
            text-transform: uppercase;
        }

        .hq-page-subtitle {
            color: #9ca3af;
            font-size: 1rem;
            line-height: 1.6;
            margin-bottom: 0;
            max-width: 920px;
        }

        .hq-section-title {
            color: #f9fafb;
            font-size: 1.12rem;
            font-weight: 750;
            margin-top: 1.6rem;
            margin-bottom: 0.25rem;
        }

        .hq-section-description {
            color: #9ca3af;
            font-size: 0.9rem;
            line-height: 1.45;
            margin-bottom: 0.85rem;
        }

        .hq-card-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 0.85rem;
            margin-top: 0.75rem;
        }

        .hq-card, .hq-empty-state, .hq-metric-card {
            background: linear-gradient(180deg, rgba(31, 41, 55, 0.96), rgba(17, 24, 39, 0.96));
            border: 1px solid rgba(148, 163, 184, 0.2);
            border-radius: 8px;
            box-shadow: 0 14px 30px rgba(2, 6, 23, 0.24);
        }

        .hq-card {
            padding: 1rem;
        }

        .hq-card-title {
            color: #f9fafb;
            font-size: 0.96rem;
            font-weight: 750;
            margin-bottom: 0.28rem;
        }

        .hq-card-body {
            color: #9ca3af;
            font-size: 0.9rem;
            line-height: 1.45;
        }

        .hq-empty-state {
            padding: 1rem 1.1rem;
            margin: 0.65rem 0 0.9rem;
        }

        .hq-empty-title {
            color: #f9fafb;
            font-weight: 750;
            margin-bottom: 0.25rem;
        }

        .hq-empty-body {
            color: #9ca3af;
            line-height: 1.45;
        }

        .hq-metric-card {
            padding: 1rem;
        }

        .hq-metric-label {
            color: #9ca3af;
            font-size: 0.76rem;
            font-weight: 750;
            letter-spacing: 0.05em;
            text-transform: uppercase;
        }

        .hq-metric-value {
            color: #f9fafb;
            font-size: 1.7rem;
            font-weight: 800;
            line-height: 1.2;
            margin-top: 0.25rem;
        }

        .hq-metric-caption {
            color: #9ca3af;
            font-size: 0.82rem;
            margin-top: 0.25rem;
        }
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
    fig.update_layout(
        height=height,
        paper_bgcolor="rgba(17, 24, 39, 0)",
        plot_bgcolor="rgba(17, 24, 39, 0)",
        font={"color": "#F9FAFB"},
        title={"font": {"color": "#F9FAFB", "size": 16}},
        xaxis={
            "gridcolor": "rgba(148, 163, 184, 0.16)",
            "linecolor": "rgba(148, 163, 184, 0.3)",
            "tickfont": {"color": "#D1D5DB"},
            "title": {"font": {"color": "#9CA3AF"}},
        },
        yaxis={
            "gridcolor": "rgba(148, 163, 184, 0.16)",
            "linecolor": "rgba(148, 163, 184, 0.3)",
            "tickfont": {"color": "#D1D5DB"},
            "title": {"font": {"color": "#9CA3AF"}},
        },
        margin={"l": 24, "r": 18, "t": 48, "b": 42},
    )
    return fig

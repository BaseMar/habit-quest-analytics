import sys
from html import escape
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.database.db import init_db
from src.services.analytics_service import get_character_profile_data
from src.services.profile_service import remove_avatar, resolve_avatar_path, save_avatar
from src.ui import apply_theme, get_theme_tokens, render_page_header, render_section_title


def apply_character_profile_styles() -> None:
    st.markdown(
        """
        <style>
        .block-container {
            padding-top: 1.7rem;
        }

        .hq-page-header {
            margin-bottom: 0.85rem;
            padding-top: 0.3rem;
        }

        .hq-section-title {
            margin-top: 1.05rem;
            margin-bottom: 0.18rem;
        }

        .hq-section-description {
            margin-bottom: 0.55rem;
        }

        .hq-hero-avatar-placeholder {
            align-items: center;
            aspect-ratio: 1;
            background:
                linear-gradient(135deg, var(--hq-surface), var(--hq-surface-elevated)),
                radial-gradient(circle at center, var(--hq-accent-soft), transparent 60%);
            border: 1px dashed var(--hq-accent-border);
            border-radius: 8px;
            color: var(--hq-text-secondary);
            display: flex;
            flex-direction: column;
            font-size: 0.8rem;
            justify-content: center;
            line-height: 1.3;
            min-height: 104px;
            padding: 0.65rem;
            text-align: center;
        }

        .hq-hero-avatar-icon {
            color: var(--hq-accent);
            font-size: 1.8rem;
            line-height: 1;
            margin-bottom: 0.32rem;
        }

        .hq-hero-avatar-title {
            color: var(--hq-text-primary);
            font-weight: 760;
        }

        .hq-hero-identity {
            padding: 0.05rem 0 0;
        }

        .hq-character-name {
            color: var(--hq-text-primary);
            font-size: 1.58rem;
            font-weight: 850;
            line-height: 1.12;
            margin: 0 0 0.12rem;
        }

        .hq-character-title {
            color: var(--hq-accent);
            font-size: 0.92rem;
            font-weight: 750;
            line-height: 1.25;
            margin-bottom: 0.45rem;
        }

        .hq-level-badge {
            align-items: center;
            background: var(--hq-accent-soft);
            border: 1px solid var(--hq-accent-border);
            border-radius: 6px;
            box-shadow: none;
            color: #ffffff;
            display: inline-flex;
            font-size: 0.78rem;
            font-weight: 850;
            letter-spacing: 0.07em;
            margin: 0 0 0.4rem;
            padding: 0.36rem 0.64rem;
            text-transform: uppercase;
        }

        .hq-empty-compact {
            background: var(--hq-surface);
            border: 1px solid var(--hq-border);
            border-radius: 8px;
            color: var(--hq-text-secondary);
            font-size: 0.9rem;
            line-height: 1.35;
            margin-top: 0.7rem;
            padding: 0.62rem 0.78rem;
        }

        .hq-empty-compact strong {
            color: var(--hq-text-primary);
        }

        .hq-radar-caption {
            color: var(--hq-text-secondary);
            font-size: 0.78rem;
            line-height: 1.25;
            margin-top: -0.45rem;
            text-align: center;
        }

        .hq-explainer {
            background: linear-gradient(180deg, var(--hq-surface), var(--hq-surface-elevated));
            border: 1px solid var(--hq-border);
            border-radius: 8px;
            color: var(--hq-text-secondary);
            line-height: 1.5;
            padding: 0.82rem 0.95rem;
        }

        .hq-xp-metric {
            background: var(--hq-muted-surface);
            border: 1px solid var(--hq-border);
            border-radius: 7px;
            box-sizing: border-box;
        }

        .hq-xp-label {
            color: var(--hq-text-secondary);
            font-size: 0.64rem;
            font-weight: 760;
            letter-spacing: 0.05em;
            line-height: 1.18;
            overflow: hidden;
            text-overflow: ellipsis;
            text-transform: uppercase;
            white-space: nowrap;
        }

        .hq-xp-value {
            color: var(--hq-text-primary);
            font-weight: 800;
            line-height: 1.18;
            margin-top: 0.18rem;
            overflow-wrap: anywhere;
        }

        .hq-xp-panel {
            background: var(--hq-muted-surface);
            border: 1px solid var(--hq-border);
            border-radius: 8px;
            box-sizing: border-box;
            min-height: 134px;
            padding: 0.85rem 1rem 0.8rem;
            width: 100%;
        }

        .hq-xp-row {
            display: grid;
            gap: 0.65rem;
            grid-template-columns: repeat(2, minmax(0, 1fr));
        }

        .hq-xp-metric {
            min-height: 52px;
            padding: 0.5rem 0.56rem;
        }

        .hq-xp-value {
            font-size: 1.1rem;
        }

        .hq-xp-track {
            background: var(--hq-muted-surface);
            border: 1px solid var(--hq-border);
            border-radius: 999px;
            height: 0.62rem;
            margin-top: 0.72rem;
            overflow: hidden;
            width: 100%;
        }

        .hq-xp-fill {
            background: var(--hq-accent);
            border-radius: inherit;
            height: 100%;
        }

        .hq-xp-caption {
            color: var(--hq-text-secondary);
            font-size: 0.72rem;
            line-height: 1.2;
            margin-top: 0.38rem;
        }

        div[data-testid="stFileUploader"] button {
            display: none;
        }

        div[data-testid="stFileUploader"] section {
            min-height: 74px;
            padding: 0.55rem;
        }

        @media (max-width: 820px) {
            .hq-xp-row {
                grid-template-columns: 1fr;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_avatar(profile: dict) -> None:
    avatar_path = resolve_avatar_path(profile.get("avatar_path"))
    if avatar_path:
        st.image(str(avatar_path), width=116)
    else:
        st.markdown(
            """
            <div class="hq-hero-avatar-placeholder">
                <div class="hq-hero-avatar-icon">[+]</div>
                <div class="hq-hero-avatar-title">No avatar</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_avatar_controls(profile: dict) -> None:
    with st.popover("Change avatar", use_container_width=True):
        uploaded_avatar = st.file_uploader(
            "Drag and drop an avatar image",
            type=["png", "jpg", "jpeg"],
            accept_multiple_files=False,
        )
        if uploaded_avatar is not None:
            try:
                save_avatar(uploaded_avatar.name, uploaded_avatar.getvalue())
                st.success("Avatar uploaded.")
                st.rerun()
            except ValueError as error:
                st.error(str(error))

        if profile.get("avatar_path") and st.button("Remove Avatar", use_container_width=True):
            remove_avatar()
            st.rerun()


def render_character_hero(profile: dict) -> None:
    progress_percent = int(profile["level_progress"] * 100)

    with st.container():
        avatar_col, identity_col, xp_col = st.columns([0.16, 0.51, 0.33], gap="medium")
        with avatar_col:
            render_avatar(profile)
            render_avatar_controls(profile)

        with identity_col:
            st.markdown(
                f"""
                <div class="hq-hero-identity">
                    <div class="hq-character-name">{escape(str(profile["character_name"]))}</div>
                    <div class="hq-character-title">{escape(str(profile["character_title"]))}</div>
                    <div class="hq-level-badge">Level {int(profile["current_level"])}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        with xp_col:
            progress_width = max(0, min(100, progress_percent))
            st.markdown(
                f"""
                <div class="hq-xp-panel">
                    <div class="hq-xp-row">
                        <div class="hq-xp-metric">
                            <div class="hq-xp-label">Total XP</div>
                            <div class="hq-xp-value">{int(profile["total_xp"])}</div>
                        </div>
                        <div class="hq-xp-metric">
                            <div class="hq-xp-label">Next Level</div>
                            <div class="hq-xp-value">{int(profile["xp_to_next_level"])}</div>
                        </div>
                    </div>
                    <div class="hq-xp-track">
                        <div class="hq-xp-fill" style="width: {progress_width}%"></div>
                    </div>
                    <div class="hq-xp-caption">{progress_percent}% progress toward the next level</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    if not profile["has_completed_quests"]:
        st.markdown(
            """
            <div class="hq-empty-compact">
                <strong>No completed quest days yet.</strong>
                Complete planned work in Command Center to earn XP and grow RPG stats.
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_rpg_stats_section(profile: dict) -> None:
    tokens = get_theme_tokens()
    render_section_title("RPG Stats", "Stat levels from completed quest-day XP by category.")
    rows = "".join(_render_stat_row(row) for row in profile["stat_profile"])
    radar_html = _build_radar_figure(profile, height=260).to_html(
        full_html=False,
        include_plotlyjs=True,
        config={"displayModeBar": False, "responsive": True},
    )
    components.html(
        f"""
        <style>
            body {{
                background: transparent;
                margin: 0;
                overflow: hidden;
            }}

            .rpg-stats-grid {{
                box-sizing: border-box;
                display: grid;
                gap: 14px;
                grid-template-columns: minmax(0, 1.45fr) minmax(0, 0.95fr);
                height: 334px;
                width: 100%;
            }}

            .rpg-card {{
                background: {tokens["surface"]};
                border: 1px solid {tokens["border"]};
                border-radius: 8px;
                box-sizing: border-box;
                display: flex;
                flex-direction: column;
                height: 100%;
                padding: 12px;
                width: 100%;
            }}

            .rpg-card-title {{
                color: {tokens["text_primary"]};
                font: 800 15px/1.2 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
                margin: 0 0 8px;
            }}

            .stat-panel {{
                box-sizing: border-box;
                display: flex;
                flex: 1;
                flex-direction: column;
                justify-content: space-between;
                min-height: 0;
                width: 100%;
            }}

            .stat-row {{
                align-items: center;
                background: {tokens["muted_surface"]};
                border: 1px solid {tokens["border"]};
                border-radius: 7px;
                box-sizing: border-box;
                display: grid;
                gap: 8px;
                grid-template-columns: minmax(96px, 0.86fr) minmax(150px, 1.55fr) 50px;
                min-height: 43px;
                padding: 6px 8px;
                width: 100%;
            }}

            .stat-name {{
                color: {tokens["text_primary"]};
                font: 800 13px/1.12 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
                overflow-wrap: anywhere;
            }}

            .stat-category {{
                color: {tokens["text_secondary"]};
                font: 650 10.5px/1.15 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
                margin-top: 1px;
            }}

            .stat-track {{
                background: {tokens["muted_surface"]};
                border: 1px solid {tokens["border"]};
                border-radius: 999px;
                box-shadow: inset 0 1px 4px rgba(0, 0, 0, 0.38);
                height: 10px;
                overflow: hidden;
                width: 100%;
            }}

            .stat-fill {{
                background: {tokens["accent"]};
                border-radius: inherit;
                box-shadow: none;
                height: 100%;
                min-width: 3px;
            }}

            .stat-fill.empty {{
                min-width: 0;
            }}

            .stat-help {{
                color: {tokens["text_secondary"]};
                font: 600 10.5px/1.15 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
                margin-top: 3px;
                white-space: nowrap;
            }}

            .stat-level {{
                color: {tokens["accent"]};
                font: 850 13px/1 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
                text-align: right;
                white-space: nowrap;
            }}

            .radar-card {{
                align-items: stretch;
            }}

            .radar-wrap {{
                align-items: center;
                display: flex;
                flex: 1;
                justify-content: center;
                min-height: 0;
                width: 100%;
            }}

            .radar-caption {{
                color: {tokens["text_secondary"]};
                font: 650 11px/1.25 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
                margin-top: 2px;
                text-align: center;
            }}

            @media (max-width: 900px) {{
                .rpg-stats-grid {{
                    grid-template-columns: 1fr;
                    height: 672px;
                }}
            }}
        </style>
        <div class="rpg-stats-grid">
            <section class="rpg-card">
                <div class="rpg-card-title">RPG Stat Progress</div>
                <div class="stat-panel">{rows}</div>
            </section>
            <section class="rpg-card radar-card">
                <div class="rpg-card-title">Stat Level Radar</div>
                <div class="radar-wrap">{radar_html}</div>
                <div class="radar-caption">Current stat levels, not raw XP.</div>
            </section>
        </div>
        """,
        height=348,
    )


def _build_radar_figure(profile: dict, height: int) -> go.Figure:
    tokens = get_theme_tokens()
    stat_profile = profile["stat_profile"]
    stats = [row["stat"] for row in stat_profile]
    values = [int(row["level"]) for row in stat_profile]
    max_value = max(5, max(values + [1]) + 1)

    fig = go.Figure(
        data=[
            go.Scatterpolar(
                r=values + values[:1],
                theta=stats + stats[:1],
                fill="toself",
                fillcolor=tokens["accent_soft"],
                line={"color": tokens["accent"], "width": 3},
                marker={"color": tokens["info"], "size": 7},
                name="Stat Levels",
            )
        ]
    )
    fig.update_layout(
        title={"text": ""},
        autosize=True,
        height=height,
        paper_bgcolor="rgba(0, 0, 0, 0)",
        plot_bgcolor="rgba(0, 0, 0, 0)",
        font={"color": tokens["text_primary"]},
        margin={"l": 24, "r": 24, "t": 0, "b": 8},
        polar={
            "bgcolor": "rgba(0, 0, 0, 0)",
            "domain": {"x": [0.08, 0.92], "y": [0.07, 0.95]},
            "radialaxis": {
                "gridcolor": tokens["chart_grid"],
                "range": [0, max_value],
                "tickfont": {"color": tokens["text_secondary"], "size": 9},
                "showline": False,
                "dtick": 1,
            },
            "angularaxis": {
                "gridcolor": tokens["chart_grid"],
                "tickfont": {"color": tokens["text_primary"], "size": 10},
            },
        },
        showlegend=False,
    )
    return fig


def _render_stat_row(row: dict) -> str:
    progress_percent = max(0, min(100, float(row["progress_percent"])))
    fill_class = "stat-fill empty" if progress_percent <= 0 else "stat-fill"
    return f"""
    <div class="stat-row">
        <div>
            <div class="stat-name">{escape(str(row["stat"]))}</div>
            <div class="stat-category">{escape(str(row["category"]))}</div>
        </div>
        <div>
            <div class="stat-track">
                <div class="{fill_class}" style="width: {progress_percent:.2f}%"></div>
            </div>
            <div class="stat-help">
                {int(row["xp_into_current_level"])} / {int(row["xp_needed_for_next_level"])} XP to next level
            </div>
        </div>
        <div class="stat-level">Lv. {int(row["level"])}</div>
    </div>
    """


def render_how_stats_are_calculated() -> None:
    with st.expander("How Stats Are Calculated"):
        st.markdown(
            """
            <div class="hq-explainer">
                Completed quest days grant stored check-in XP. That XP contributes to one RPG stat through the quest category
                mapping: Learning to Knowledge, Health to Strength, Work to Discipline, Social to Creativity, and Home to
                Recovery. Character and stat levels use nonlinear XP thresholds.
            </div>
            """,
            unsafe_allow_html=True,
        )


apply_theme()
apply_character_profile_styles()
render_page_header(
    "Character Profile",
    "Character Profile",
    "A compact RPG character sheet for XP, level progression, and stat growth.",
)

init_db()
profile = get_character_profile_data()

render_character_hero(profile)
render_rpg_stats_section(profile)
render_how_stats_are_calculated()

import sys
from html import escape
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.database.db import init_db
from src.services.analytics_service import get_character_profile_data
from src.services.profile_service import remove_avatar, resolve_avatar_path, save_avatar
from src.ui import get_theme_tokens, render_page_header, render_section_title


def apply_character_profile_styles() -> None:
    st.markdown(
        """
        <style>
        .hq-hero-avatar-placeholder {
            align-items: center;
            aspect-ratio: 1;
            background: var(--hq-surface-elevated);
            border: 1px dashed var(--hq-accent-border);
            border-radius: 8px;
            color: var(--hq-text-secondary);
            display: flex;
            flex-direction: column;
            font-size: 0.8rem;
            justify-content: center;
            line-height: 1.3;
            min-height: 104px;
            max-width: 116px;
            padding: 0.65rem;
            text-align: center;
        }

        .hq-hero-avatar-icon {
            color: var(--hq-accent-text);
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
            overflow-wrap: anywhere;
        }

        .hq-character-title {
            color: var(--hq-accent-text);
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
            color: var(--hq-accent-text);
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
            background: var(--hq-surface);
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
            overflow-wrap: anywhere;
            text-transform: uppercase;
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

        div[data-testid="stFileUploader"] section {
            min-height: 74px;
            padding: 0.55rem;
        }

        .hq-stat-panel {
            display: grid;
            gap: 0.4rem;
        }

        .hq-stat-panel .stat-row {
            align-items: center;
            background: var(--hq-muted-surface);
            border: 1px solid var(--hq-border);
            border-radius: 7px;
            display: grid;
            gap: 0.5rem;
            grid-template-columns: minmax(0, 1fr) minmax(0, 1.5fr) auto;
            padding: 0.5rem;
            overflow-wrap: anywhere;
        }

        .hq-stat-panel .stat-name,
        .hq-stat-panel .stat-level {
            font-size: 0.86rem;
            font-weight: 800;
        }

        .hq-stat-panel .stat-level {
            color: var(--hq-accent-text);
            text-align: right;
        }

        .hq-stat-panel .stat-category,
        .hq-stat-panel .stat-help {
            color: var(--hq-text-secondary);
            font-size: 0.72rem;
            line-height: 1.3;
        }

        .hq-stat-panel .stat-track {
            background: var(--hq-surface);
            border: 1px solid var(--hq-border);
            border-radius: 999px;
            height: 0.6rem;
            margin-bottom: 0.18rem;
            overflow: hidden;
        }

        .hq-stat-panel .stat-fill {
            background: var(--hq-accent);
            border-radius: inherit;
            height: 100%;
        }

        @container hq-main (min-width: 100rem) {
            .st-key-hq_character_hero,
            .st-key-hq_character_stats {
                max-width: 100rem;
            }

            .st-key-hq_character_hero [data-testid="stHorizontalBlock"] {
                display: grid;
                grid-template-columns: 10rem minmax(0, 1fr) minmax(0, 32rem);
            }

            .st-key-hq_character_hero [data-testid="stColumn"] {
                min-width: 0;
                width: 100%;
            }
        }

        @container hq-main (max-width: 44rem) {
            .st-key-hq_character_hero [data-testid="stHorizontalBlock"] {
                display: grid;
                grid-template-columns: 7.25rem minmax(0, 1fr);
            }

            .st-key-hq_character_hero [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {
                min-width: 0;
                width: 100%;
            }

            .st-key-hq_character_hero [data-testid="stHorizontalBlock"] > :last-child {
                grid-column: 1 / -1;
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


@st.dialog("Change avatar", on_dismiss="rerun")
def _change_avatar_dialog(has_avatar: bool) -> None:
    uploaded_avatar = st.file_uploader("Avatar image", type=["png", "jpg", "jpeg"])
    if st.button("Save avatar", type="primary", width="stretch", disabled=uploaded_avatar is None):
        try:
            save_avatar(uploaded_avatar.name, uploaded_avatar.getvalue())
        except ValueError as error:
            st.error(str(error))
        else:
            st.session_state["avatar_status_message"] = "Avatar updated."
            st.rerun()

    if has_avatar and st.button("Remove avatar", width="stretch"):
        remove_avatar()
        st.session_state["avatar_status_message"] = "Avatar removed."
        st.rerun()


def render_character_hero(profile: dict) -> None:
    progress_percent = int(profile["level_progress"] * 100)

    with st.container(key="hq_character_hero"):
        avatar_col, identity_col, xp_col = st.columns([0.16, 0.51, 0.33], gap="medium")
        with avatar_col:
            render_avatar(profile)
            if st.button("Change avatar", width="stretch"):
                _change_avatar_dialog(bool(profile.get("avatar_path")))

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
    render_section_title("RPG stats", "Stat levels from completed quest-day XP by category.")
    stats_col, radar_col = st.container(key="hq_character_stats").columns([1.45, 1], gap="medium")

    with stats_col:
        rows = "".join(_render_stat_row(row) for row in profile["stat_profile"])
        st.html(f'<div class="hq-stat-panel">{rows}</div>')

    with radar_col:
        render_section_title("Stat level radar")
        st.plotly_chart(
            _build_radar_figure(profile, height=260),
            width="stretch",
            theme=None,
            config={"displayModeBar": False},
        )
        st.caption("Current stat levels, not raw XP.")


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
    return f"""
    <div class="stat-row">
        <div>
            <div class="stat-name">{escape(str(row["stat"]))}</div>
            <div class="stat-category">{escape(str(row["category"]))}</div>
        </div>
        <div>
            <div class="stat-track">
                <div class="stat-fill" style="width: {progress_percent:.2f}%"></div>
            </div>
            <div class="stat-help">
                {int(row["xp_into_current_level"])} / {int(row["xp_needed_for_next_level"])} XP to next level
            </div>
        </div>
        <div class="stat-level">Lv. {int(row["level"])}</div>
    </div>
    """


def render_how_stats_are_calculated() -> None:
    with st.expander("How stats are calculated"):
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


apply_character_profile_styles()
render_page_header(
    "Character Profile",
    "See your level, XP, and RPG stats.",
)

init_db()
profile = get_character_profile_data()

if message := st.session_state.pop("avatar_status_message", None):
    st.success(message)
render_character_hero(profile)
render_rpg_stats_section(profile)
render_how_stats_are_calculated()

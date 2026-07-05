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
from src.ui import apply_theme, render_empty_state, render_page_header, render_section_title


def apply_character_profile_styles() -> None:
    st.markdown(
        """
        <style>
        .hq-character-identity {
            padding: 0 0 0.25rem;
        }

        .hq-character-name {
            color: #f9fafb;
            font-size: 1.55rem;
            font-weight: 850;
            line-height: 1.15;
            margin: 0.1rem 0 0.12rem;
        }

        .hq-character-title {
            color: #c4b5fd;
            font-size: 0.94rem;
            font-weight: 700;
            margin-bottom: 0.42rem;
        }

        .hq-level-badge {
            align-items: center;
            background: linear-gradient(135deg, rgba(139, 92, 246, 0.95), rgba(56, 189, 248, 0.75));
            border: 1px solid rgba(221, 214, 254, 0.34);
            border-radius: 8px;
            box-shadow: 0 12px 28px rgba(2, 6, 23, 0.28);
            color: #ffffff;
            display: inline-flex;
            font-size: 0.82rem;
            font-weight: 850;
            letter-spacing: 0.04em;
            margin: 0.05rem 0 0.35rem;
            padding: 0.38rem 0.66rem;
            text-transform: uppercase;
        }

        .hq-xp-line {
            color: #d1d5db;
            display: flex;
            flex-wrap: wrap;
            gap: 0.85rem;
            margin: 0.25rem 0 0.45rem;
        }

        .hq-xp-line strong {
            color: #f9fafb;
        }

        .hq-avatar-placeholder {
            align-items: center;
            aspect-ratio: 1;
            background:
                linear-gradient(135deg, rgba(31, 41, 55, 0.96), rgba(15, 23, 42, 0.96)),
                radial-gradient(circle at center, rgba(139, 92, 246, 0.22), transparent 60%);
            border: 1px dashed rgba(196, 181, 253, 0.42);
            border-radius: 8px;
            color: #d1d5db;
            display: flex;
            flex-direction: column;
            font-size: 0.9rem;
            justify-content: center;
            line-height: 1.35;
            min-height: 118px;
            padding: 0.75rem;
            text-align: center;
        }

        .hq-avatar-icon {
            color: #c4b5fd;
            font-size: 2.1rem;
            line-height: 1;
            margin-bottom: 0.4rem;
        }

        .hq-avatar-title {
            color: #f9fafb;
            font-weight: 760;
        }

        .hq-avatar-subtitle {
            color: #9ca3af;
            font-size: 0.78rem;
            margin-top: 0.15rem;
        }

        div[data-testid="stFileUploader"] button {
            display: none;
        }

        div[data-testid="stFileUploader"] section {
            min-height: 74px;
            padding: 0.55rem;
        }

        .hq-explainer {
            background: linear-gradient(180deg, rgba(31, 41, 55, 0.92), rgba(17, 24, 39, 0.92));
            border: 1px solid rgba(148, 163, 184, 0.2);
            border-radius: 8px;
            color: #d1d5db;
            line-height: 1.55;
            padding: 1rem 1.1rem;
        }

        .hq-radar-caption {
            color: #9ca3af;
            font-size: 0.82rem;
            line-height: 1.25;
            margin-top: -0.35rem;
            text-align: center;
        }

        </style>
        """,
        unsafe_allow_html=True,
    )


def render_avatar(profile: dict) -> None:
    avatar_path = resolve_avatar_path(profile.get("avatar_path"))
    if avatar_path:
        st.image(str(avatar_path), width=145)
    else:
        st.markdown(
            """
            <div class="hq-avatar-placeholder">
                <div class="hq-avatar-icon">[+]</div>
                <div class="hq-avatar-title">No avatar yet</div>
                <div class="hq-avatar-subtitle">Upload your portrait below</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_identity(profile: dict) -> None:
    progress_percent = int(profile["level_progress"] * 100)
    st.markdown(
        f"""
        <div class="hq-character-identity">
            <div class="hq-character-name">{escape(profile["character_name"])}</div>
            <div class="hq-character-title">{escape(profile["character_title"])}</div>
            <div class="hq-level-badge">Level {profile["current_level"]}</div>
            <div class="hq-xp-line">
                <span><strong>{profile["total_xp"]}</strong> total XP</span>
                <span><strong>{profile["xp_to_next_level"]}</strong> XP to next level</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.progress(profile["level_progress"])
    st.caption(f"{progress_percent}% progress toward the next level")


def render_radar_chart(profile: dict) -> None:
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
                fillcolor="rgba(139, 92, 246, 0.28)",
                line={"color": "#A78BFA", "width": 3},
                marker={"color": "#38BDF8", "size": 7},
                name="Stat Levels",
            )
        ]
    )
    fig.update_layout(
        title={"text": ""},
        height=322,
        paper_bgcolor="rgba(17, 24, 39, 0)",
        plot_bgcolor="rgba(17, 24, 39, 0)",
        font={"color": "#F9FAFB"},
        margin={"l": 34, "r": 34, "t": 18, "b": 28},
        polar={
            "bgcolor": "rgba(17, 24, 39, 0)",
            "domain": {"x": [0.08, 0.92], "y": [0.08, 0.92]},
            "radialaxis": {
                "gridcolor": "rgba(148, 163, 184, 0.22)",
                "range": [0, max_value],
                "tickfont": {"color": "#9CA3AF", "size": 10},
                "showline": False,
                "dtick": 1,
            },
            "angularaxis": {
                "gridcolor": "rgba(148, 163, 184, 0.18)",
                "tickfont": {"color": "#F9FAFB", "size": 10},
            },
        },
        showlegend=False,
    )
    st.markdown("**Stat Level Radar**")
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    st.markdown(
        '<div class="hq-radar-caption">Displays current stat levels, derived from completed quest-day XP.</div>',
        unsafe_allow_html=True,
    )


def render_stat_panel(profile: dict) -> None:
    rows = "".join(_render_stat_row(row) for row in profile["stat_profile"])
    components.html(
        f"""
        <style>
            body {{
                background: transparent;
                margin: 0;
                overflow: hidden;
            }}

            .stat-panel {{
                box-sizing: border-box;
                display: grid;
                gap: 7px;
                padding: 2px 1px;
                width: 100%;
            }}

            .stat-row {{
                align-items: center;
                background: rgba(15, 23, 42, 0.46);
                border: 1px solid rgba(148, 163, 184, 0.14);
                border-radius: 7px;
                box-sizing: border-box;
                display: grid;
                gap: 10px;
                grid-template-columns: minmax(92px, 0.85fr) minmax(132px, 1.55fr) 48px;
                min-height: 44px;
                padding: 6px 9px;
                width: 100%;
            }}

            .stat-name {{
                color: #f9fafb;
                font: 800 14px/1.15 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
                overflow-wrap: anywhere;
            }}

            .stat-category {{
                color: #9ca3af;
                font: 650 11px/1.15 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
                margin-top: 2px;
            }}

            .stat-track {{
                background: rgba(2, 6, 23, 0.76);
                border: 1px solid rgba(148, 163, 184, 0.24);
                border-radius: 999px;
                box-shadow: inset 0 1px 4px rgba(0, 0, 0, 0.38);
                height: 11px;
                overflow: hidden;
                width: 100%;
            }}

            .stat-fill {{
                background: linear-gradient(90deg, #38bdf8 0%, #a78bfa 72%, #c4b5fd 100%);
                border-radius: inherit;
                box-shadow: 0 0 12px rgba(56, 189, 248, 0.28);
                height: 100%;
                min-width: 3px;
            }}

            .stat-fill.empty {{
                min-width: 0;
            }}

            .stat-help {{
                color: #9ca3af;
                font: 600 11px/1.2 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
                margin-top: 3px;
                white-space: nowrap;
            }}

            .stat-level {{
                color: #c4b5fd;
                font: 850 14px/1 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
                text-align: right;
                white-space: nowrap;
            }}

            @media (max-width: 520px) {{
                .stat-row {{
                    gap: 8px;
                    grid-template-columns: minmax(78px, 0.82fr) minmax(104px, 1.35fr) 44px;
                    padding: 6px 7px;
                }}
            }}
        </style>
        <div class="stat-panel">{rows}</div>
        """,
        height=268,
    )


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


def render_basic_stats(profile: dict) -> None:
    stats = profile["activity_stats"]
    midpoint = (len(stats) + 1) // 2
    left_stats = _format_basic_stats(stats[:midpoint])
    right_stats = _format_basic_stats(stats[midpoint:])

    components.html(
        f"""
        <style>
            body {{
                background: transparent;
                margin: 0;
                overflow: visible;
            }}

            .rpg-basic-stats-card {{
                background: linear-gradient(180deg, rgba(31, 41, 55, 0.96), rgba(17, 24, 39, 0.96));
                border: 1px solid rgba(148, 163, 184, 0.22);
                border-radius: 8px;
                box-sizing: border-box;
                padding: 10px 10px 12px;
                overflow: visible;
                width: 100%;
            }}

            .rpg-stat-columns {{
                display: grid;
                gap: 10px;
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }}

            .rpg-stat-panel {{
                display: grid;
                gap: 5px;
            }}

            .rpg-stat-row {{
                align-items: center;
                background: rgba(15, 23, 42, 0.58);
                border: 1px solid rgba(148, 163, 184, 0.16);
                border-radius: 6px;
                display: grid;
                grid-template-columns: minmax(0, 1fr) auto;
                min-height: 38px;
                padding: 5px 8px;
            }}

            .rpg-stat-label {{
                color: #9ca3af;
                font: 700 11px/1.2 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
                letter-spacing: 0.04em;
                overflow: hidden;
                padding-right: 10px;
                text-overflow: ellipsis;
                text-transform: uppercase;
                white-space: nowrap;
            }}

            .rpg-stat-value {{
                color: #f9fafb;
                font: 800 14px/1.2 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
                min-width: 42px;
                text-align: right;
                white-space: nowrap;
            }}

            .rpg-stat-value.accent {{
                color: #c4b5fd;
            }}
        </style>
        <div class="rpg-basic-stats-card">
            <div class="rpg-stat-columns">
                <div class="rpg-stat-panel">{_render_basic_stat_rows(left_stats)}</div>
                <div class="rpg-stat-panel">{_render_basic_stat_rows(right_stats, accent_values=True)}</div>
            </div>
        </div>
        """,
        height=244,
    )


def _format_basic_stats(stats: list[dict]) -> list[dict]:
    label_overrides = {
        "Boss Quests Completed": "Boss Quests",
        "Completed Quest Days": "Quest Days",
        "Boss Quest Days": "Boss Days",
        "Average XP / Quest Day": "Avg XP / Day",
        "Average XP / Completed Quest": "Avg XP / Quest",
        "Strongest RPG Stat": "Strongest Stat",
        "Most Productive Weekday": "Best Weekday",
    }
    return [
        {
            "label": label_overrides.get(str(stat["label"]), str(stat["label"])),
            "value": str(stat["value"]),
        }
        for stat in stats
    ]


def _render_basic_stat_rows(stats: list[dict], accent_values: bool = False) -> str:
    value_class = "rpg-stat-value accent" if accent_values else "rpg-stat-value"
    return "".join(
        f"""
        <div class="rpg-stat-row">
            <div class="rpg-stat-label">{escape(stat["label"])}</div>
            <div class="{value_class}">{escape(stat["value"])}</div>
        </div>
        """
        for stat in stats
    )


def render_avatar_controls(profile: dict) -> None:
    with st.expander("Change avatar"):
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


apply_theme()
apply_character_profile_styles()
render_page_header(
    "Character Profile",
    "Character Profile",
    "Your RPG-style progression based on completed quests and habit data.",
)

init_db()
profile = get_character_profile_data()

render_section_title("Character Summary", "A character-sheet view of your current quest progression.")
with st.container(border=True):
    avatar_col, identity_col = st.columns([0.24, 0.76], gap="medium")
    with avatar_col:
        render_avatar(profile)
    with identity_col:
        render_identity(profile)
    render_avatar_controls(profile)

if not profile["has_completed_quests"]:
    render_empty_state(
        "No completed quest days yet",
        "Complete quest days in Quest Planner to earn XP, level up, and grow your RPG stats.",
    )

render_section_title("RPG Stats", "Stat levels from completed quest-day XP by category.")
stat_col, radar_col = st.columns([0.5, 0.5], gap="medium")
with stat_col:
    with st.container(border=True):
        render_stat_panel(profile)

with radar_col:
    with st.container(border=True):
        render_radar_chart(profile)

render_section_title("Basic Stats", "Compact activity stats that complement the character sheet.")
render_basic_stats(profile)

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

render_section_title("Achievements - planned")
st.caption("Achievement unlocks will be added in a future update.")

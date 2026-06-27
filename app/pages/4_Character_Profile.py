import sys
from pathlib import Path

import plotly.express as px
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.database.db import init_db
from src.services.analytics_service import get_character_profile_data
from src.ui import apply_theme, render_empty_state, render_metric_card, render_page_header, render_section_title, style_chart


st.set_page_config(page_title="Character Profile", page_icon="HQ", layout="wide")
apply_theme()
render_page_header(
    "Character Sheet",
    "Character Profile",
    "Track how completed quests shape your RPG character progression.",
)

init_db()
profile = get_character_profile_data()

render_section_title("Character Summary", "Progression is calculated from completed quests only.")

with st.container(border=True):
    st.subheader(profile["character_name"])
    st.caption(profile["character_title"])

    col1, col2, col3 = st.columns(3)
    with col1:
        render_metric_card("Current Level", profile["current_level"])
    with col2:
        render_metric_card("Total XP", profile["total_xp"])
    with col3:
        render_metric_card("XP to Next Level", profile["xp_to_next_level"])

    st.progress(profile["level_progress"])
    st.caption(f"{int(profile['level_progress'] * 100)}% progress toward the next level")

if not profile["has_completed_quests"]:
    render_empty_state(
        "No completed quests yet",
        "Complete quests in Quest Log to earn XP and grow your RPG stats.",
    )
else:
    render_section_title(
        "RPG Stats",
        "Each completed quest contributes XP to the stat mapped from its category.",
    )
    rpg_stats = profile["rpg_stats"]

    stat_cols = st.columns(len(rpg_stats))
    for index, row in rpg_stats.iterrows():
        with stat_cols[index]:
            st.metric(row["Stat"], int(row["XP"]))
            st.progress(float(row["Progress"]))

    st.dataframe(rpg_stats[["Stat", "XP"]], hide_index=True, width="stretch")

    fig = px.bar(rpg_stats, x="Stat", y="XP", title="XP by RPG Stat", color_discrete_sequence=["#8B5CF6"])
    fig.update_layout(xaxis_title="RPG Stat", yaxis_title="XP Earned", showlegend=False, height=360)
    st.plotly_chart(style_chart(fig, height=340), width="stretch")

render_section_title("Achievements")
render_empty_state(
    "Achievements are quiet for now",
    "Achievement rules have not been added yet, so this section is intentionally inactive.",
)

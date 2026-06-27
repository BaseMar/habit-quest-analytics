import sys
from pathlib import Path

import plotly.express as px
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.database.db import init_db
from src.services.analytics_service import get_character_profile_data


st.title("Character Profile")
st.write("Track how completed quests shape your RPG character progression.")

init_db()
profile = get_character_profile_data()

st.header("Character Summary")

st.subheader(profile["character_name"])
st.caption(profile["character_title"])

col1, col2, col3 = st.columns(3)
col1.metric("Current Level", profile["current_level"])
col2.metric("Total XP", profile["total_xp"])
col3.metric("XP to Next Level", profile["xp_to_next_level"])

st.progress(profile["level_progress"])
st.caption(f"{int(profile['level_progress'] * 100)}% progress toward the next level")

if not profile["has_completed_quests"]:
    st.info("No completed quests yet. Complete quests in Quest Log to earn XP and grow your RPG stats.")
else:
    st.header("RPG Stats")
    rpg_stats = profile["rpg_stats"]

    stat_cols = st.columns(len(rpg_stats))
    for index, row in rpg_stats.iterrows():
        with stat_cols[index]:
            st.metric(row["Stat"], int(row["XP"]))
            st.progress(float(row["Progress"]))

    st.dataframe(rpg_stats[["Stat", "XP"]], hide_index=True, width="stretch")

    fig = px.bar(rpg_stats, x="Stat", y="XP", title="XP by RPG Stat")
    fig.update_layout(xaxis_title="RPG Stat", yaxis_title="XP Earned", showlegend=False, height=360)
    st.plotly_chart(fig, width="stretch")

st.header("Achievements")
st.info("Achievements are not unlocked yet. This section will remain quiet until achievement rules are added.")

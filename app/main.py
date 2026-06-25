import streamlit as st


st.set_page_config(
    page_title="Habit Quest Analytics",
    page_icon="HQ",
    layout="wide",
)

st.title("Habit Quest Analytics")
st.subheader("RPG-style habit and to-do dashboard")

st.write(
    "Track quests, earn XP, level up your character, and review habit consistency. "
    "This scaffold contains the initial app shell, database models, services, and tests."
)

col1, col2, col3 = st.columns(3)

with col1:
    st.metric("Active Quests", "0")

with col2:
    st.metric("Total XP", "0")

with col3:
    st.metric("Current Level", "1")

st.divider()

st.header("Today")
st.info("Quest cards and daily habit check-ins will appear here in the MVP.")

st.header("Progress")
st.info("XP charts, streaks, and completion trends will be added in later iterations.")

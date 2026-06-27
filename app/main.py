import streamlit as st


st.set_page_config(
    page_title="Habit Quest Analytics",
    page_icon="HQ",
    layout="wide",
)

st.title("Habit Quest Analytics")
st.subheader("RPG-style habit and productivity dashboard")

st.write(
    "Turn daily tasks into quests, earn XP for completed work, and review your progress "
    "through dashboard KPIs, habit charts, and character stats."
)

st.info("Start in Quest Log to create your first quest, then return to Dashboard and Habit Analytics to inspect your progress.")

st.header("Current Sections")
st.markdown(
    """
    - **Dashboard**: summary KPIs from persisted quests.
    - **Quest Log**: create quests and update quest status.
    - **Habit Analytics**: charts for XP, categories, status, and consistency.
    - **Character Profile**: RPG level, XP progress, and stat growth.
    """
)

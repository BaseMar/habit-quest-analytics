import sys
from pathlib import Path

import pandas as pd
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.database.db import init_db
from src.database.seed import seed_default_categories
from src.services.quest_service import (
    VALID_QUEST_STATUSES,
    create_quest,
    get_all_quests,
    get_categories,
    update_quest_status,
)


st.title("Quest Log")

init_db()
categories = get_categories()
if not categories:
    seed_default_categories()
    categories = get_categories()

category_options = {category.name: category.id for category in categories}

st.header("Create Quest")

with st.form("create_quest_form", clear_on_submit=True):
    title = st.text_input("Title")
    description = st.text_area("Description")

    col1, col2 = st.columns(2)
    with col1:
        category_name = st.selectbox("Category", list(category_options.keys()))
        difficulty = st.selectbox("Difficulty", ["Easy", "Medium", "Hard", "Boss"])
    with col2:
        planned_date = st.date_input("Planned date")
        estimated_minutes = st.number_input(
            "Estimated minutes",
            min_value=0,
            max_value=1440,
            value=30,
            step=5,
        )

    submitted = st.form_submit_button("Create Quest")
    if submitted:
        if not title.strip():
            st.error("Quest title is required.")
        else:
            create_quest(
                title=title,
                description=description,
                category_id=category_options[category_name],
                difficulty=difficulty,
                planned_date=planned_date,
                estimated_minutes=estimated_minutes,
            )
            st.success("Quest created.")
            st.rerun()

st.header("Existing Quests")

quests = get_all_quests()

if not quests:
    st.info("No quests yet. Create your first quest above.")
else:
    quest_rows = [
        {
            "ID": quest.id,
            "Title": quest.title,
            "Category": quest.category.name if quest.category else "",
            "Difficulty": quest.difficulty,
            "Status": quest.status,
            "Planned Date": quest.due_date,
            "Estimated Minutes": quest.estimated_minutes,
            "XP Reward": quest.xp_reward,
            "Completed At": quest.completed_at,
        }
        for quest in quests
    ]
    st.dataframe(pd.DataFrame(quest_rows), use_container_width=True, hide_index=True)

    st.subheader("Update Quest Status")
    quest_labels = {f"#{quest.id} - {quest.title}": quest.id for quest in quests}

    with st.form("update_quest_status_form"):
        selected_quest = st.selectbox("Quest", list(quest_labels.keys()))
        selected_status = st.selectbox("Status", list(VALID_QUEST_STATUSES))
        status_submitted = st.form_submit_button("Update Status")

        if status_submitted:
            update_quest_status(quest_labels[selected_quest], selected_status)
            st.success("Quest status updated.")
            st.rerun()

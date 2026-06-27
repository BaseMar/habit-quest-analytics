import sys
from pathlib import Path

import pandas as pd
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.constants import QUEST_DIFFICULTIES
from src.database.db import init_db
from src.database.seed import seed_default_categories
from src.services.quest_service import (
    VALID_QUEST_STATUSES,
    create_quest,
    get_all_quests,
    get_categories,
    update_quest_status,
)
from src.ui import apply_theme, render_empty_state, render_page_header, render_section_title


st.set_page_config(page_title="Quest Log", page_icon="HQ", layout="wide")
apply_theme()
render_page_header(
    "Quest Management",
    "Quest Log",
    "Create quests, assign difficulty, and keep your quest ledger up to date.",
)

init_db()
categories = get_categories()
if not categories:
    seed_default_categories()
    categories = get_categories()

category_options = {category.name: category.id for category in categories}

if not category_options:
    st.warning("No categories are available yet. Run the seed script to prepare the quest categories.")
    st.stop()

render_section_title("Create a Quest", "Define the quest, planned effort, and reward difficulty.")

form_col, guide_col = st.columns([2, 1], gap="large")

with form_col:
    with st.container(border=True):
        with st.form("create_quest_form", clear_on_submit=True):
            title = st.text_input("Quest title")
            description = st.text_area("Quest notes")

            col1, col2 = st.columns(2)
            with col1:
                category_name = st.selectbox("Category", list(category_options.keys()))
                difficulty = st.selectbox("Difficulty", list(QUEST_DIFFICULTIES))
            with col2:
                planned_date = st.date_input("Planned date")
                estimated_minutes = st.number_input(
                    "Estimated minutes",
                    min_value=0,
                    max_value=1440,
                    value=30,
                    step=5,
                )

            submitted = st.form_submit_button("Add Quest")
            if submitted:
                if not title.strip():
                    st.error("Every quest needs a title.")
                else:
                    create_quest(
                        title=title,
                        description=description,
                        category_id=category_options[category_name],
                        difficulty=difficulty,
                        planned_date=planned_date,
                        estimated_minutes=estimated_minutes,
                    )
                    st.success("Quest added to your log.")
                    st.rerun()

with guide_col:
    st.markdown(
        """
        <div class="hq-card">
            <div class="hq-card-title">XP Reward Guide</div>
            <div class="hq-card-body">
                Easy: 10 XP<br>
                Medium: 30 XP<br>
                Hard: 75 XP<br>
                Boss: 150 XP
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

render_section_title("Existing Quests", "Review persisted quests and update their current status.")

quests = get_all_quests()

if not quests:
    render_empty_state("No quests yet", "Add your first quest above to start building your adventure log.")
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
    st.dataframe(pd.DataFrame(quest_rows), width="stretch", hide_index=True)

    render_section_title("Update Quest Status", "Move a quest through the existing status flow.")
    quest_labels = {f"#{quest.id} - {quest.title}": quest.id for quest in quests}

    with st.container(border=True):
        with st.form("update_quest_status_form"):
            selected_quest = st.selectbox("Quest", list(quest_labels.keys()))
            selected_status = st.selectbox("Status", list(VALID_QUEST_STATUSES))
            status_submitted = st.form_submit_button("Update Status")

            if status_submitted:
                update_quest_status(quest_labels[selected_quest], selected_status)
                st.success("Quest status updated.")
                st.rerun()

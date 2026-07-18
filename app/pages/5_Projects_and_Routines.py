import sys
from datetime import date
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.components.project_routine_workspace import render_project_routine_workspace
from src.database.db import init_db
from src.database.seed import ensure_default_categories
from src.services.quest_service import get_categories
from src.ui import apply_theme, render_page_header


apply_theme()
render_page_header(
    "Manage your system",
    "Projects & Routines",
    "Review projects, maintain routines, and generate the future schedule when you need it.",
)

init_db()
ensure_default_categories()
categories = get_categories()
category_options = {category.name: category.id for category in categories}

if not category_options:
    st.warning("Run python -m src.database.seed to create default categories.")
    st.stop()

render_project_routine_workspace(
    category_options,
    st.session_state.get("selected_date", date.today()),
)

import sys
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.ui import apply_theme, render_appearance_controls, render_page_header, render_section_title
from src.database.db import init_db
from src.database.seed import ensure_default_categories


st.set_page_config(
    page_title="Habit Quest Analytics",
    page_icon="HQ",
    layout="wide",
)


def apply_home_base_styles() -> None:
    st.markdown(
        """
        <style>
        .home-hero {
            background: var(--hq-surface);
            border: 1px solid var(--hq-border);
            border-radius: 8px;
            box-shadow: var(--hq-shadow);
            margin: 0.25rem 0 1.1rem;
            padding: 1.1rem 1.2rem;
        }

        .home-hero-label {
            color: var(--hq-accent);
            font-size: 0.74rem;
            font-weight: 760;
            letter-spacing: 0.06em;
            margin-bottom: 0.35rem;
            text-transform: uppercase;
        }

        .home-hero-title {
            color: var(--hq-text-primary);
            font-size: 1.32rem;
            font-weight: 760;
            line-height: 1.2;
            margin-bottom: 0.4rem;
        }

        .home-hero-copy {
            color: var(--hq-text-secondary);
            font-size: 0.98rem;
            line-height: 1.55;
            max-width: 880px;
        }

        .home-step-grid {
            display: grid;
            gap: 0.85rem;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            margin-top: 0.75rem;
        }

        .home-step-card {
            background: var(--hq-surface);
            border: 1px solid var(--hq-border);
            border-radius: 8px;
            box-shadow: var(--hq-shadow);
            min-height: 132px;
            padding: 0.95rem;
        }

        .home-step-number {
            align-items: center;
            background: var(--hq-accent-soft);
            border: 0;
            border-radius: 999px;
            color: var(--hq-accent);
            display: inline-flex;
            font-size: 0.78rem;
            font-weight: 800;
            height: 1.75rem;
            justify-content: center;
            margin-bottom: 0.75rem;
            width: 1.75rem;
        }

        .home-step-title {
            color: var(--hq-text-primary);
            font-size: 0.96rem;
            font-weight: 720;
            line-height: 1.25;
            margin-bottom: 0.35rem;
        }

        .home-step-body {
            color: var(--hq-text-secondary);
            font-size: 0.88rem;
            line-height: 1.45;
        }

        .home-loop {
            align-items: stretch;
            display: grid;
            gap: 0.6rem;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            margin: 0.7rem 0 0.35rem;
        }

        .home-loop-item {
            background: var(--hq-muted-surface);
            border: 1px solid var(--hq-border);
            border-radius: 8px;
            color: var(--hq-text-primary);
            font-size: 0.9rem;
            font-weight: 750;
            padding: 0.75rem 0.85rem;
            text-align: center;
        }

        .home-note {
            background: var(--hq-muted-surface);
            border: 1px solid var(--hq-border);
            border-radius: 8px;
            color: var(--hq-text-secondary);
            font-size: 0.82rem;
            line-height: 1.45;
            margin-top: 1.5rem;
            padding: 0.85rem 0.95rem;
        }

        @media (max-width: 960px) {
            .home-step-grid, .home-loop {
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }
        }

        @media (max-width: 560px) {
            .home-step-grid, .home-loop {
                grid-template-columns: 1fr;
            }

            .home-step-card {
                min-height: auto;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar_brand() -> None:
    st.sidebar.markdown(
        """
        <div class="hq-sidebar-brand">
            <div class="hq-sidebar-brand-title">Habit Quest Analytics</div>
            <div class="hq-sidebar-brand-caption">RPG habit planner</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_home_base() -> None:
    init_db()
    ensure_default_categories()
    apply_home_base_styles()

    render_page_header(
        "Home Base",
        "Home Base",
        "A focused workspace for planning tasks, reviewing progress, and keeping daily work visible.",
    )

    st.markdown(
        """
        <div class="home-hero">
            <div class="home-hero-label">Workspace overview</div>
            <div class="home-hero-title">Plan the day, complete scheduled work, and review progress from one local app.</div>
            <div class="home-hero-copy">
                Habit Quest Analytics combines calendar planning, recurring habits, checklist status, XP, analytics,
                and character progress without changing the underlying local-first workflow.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    render_section_title(
        "Mission Briefing",
        "The core workflow stays intentionally small and repeatable.",
    )
    st.markdown(
        """
        <div class="home-step-grid">
            <div class="home-step-card">
                <div class="home-step-number">1</div>
                <div class="home-step-title">Plan</div>
                <div class="home-step-body">Schedule tasks, routines, and project sessions.</div>
            </div>
            <div class="home-step-card">
                <div class="home-step-number">2</div>
                <div class="home-step-title">Focus</div>
                <div class="home-step-body">Use Command Center to see today's work and attention items.</div>
            </div>
            <div class="home-step-card">
                <div class="home-step-number">3</div>
                <div class="home-step-title">Review</div>
                <div class="home-step-body">Use Analytics to inspect XP, completion, categories, and consistency.</div>
            </div>
            <div class="home-step-card">
                <div class="home-step-number">4</div>
                <div class="home-step-title">Progress</div>
                <div class="home-step-body">Use Character Profile to view XP, level, avatar, and RPG stats.</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    render_section_title(
        "App Map",
        "Use these sections as the main paths through the current MVP.",
    )
    st.markdown(
        """
        <div class="hq-card-grid">
            <div class="hq-card">
                <div class="hq-card-title">Command Center</div>
                <div class="hq-card-body">Today's focus and task status.</div>
            </div>
            <div class="hq-card">
                <div class="hq-card-title">Quest Planner</div>
                <div class="hq-card-body">Calendar planner for scheduled tasks and routines.</div>
            </div>
            <div class="hq-card">
                <div class="hq-card-title">Habit Analytics</div>
                <div class="hq-card-body">Trends, weekly pulse, categories, status breakdowns, and consistency.</div>
            </div>
            <div class="hq-card">
                <div class="hq-card-title">Character Profile</div>
                <div class="hq-card-body">RPG level, XP progress, avatar, and stat growth.</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    render_section_title(
        "How It Works",
        "The app keeps the loop practical: plan the day, complete tasks, and review what the data shows.",
    )
    st.markdown(
        """
        <div class="home-loop">
            <div class="home-loop-item">Tasks</div>
            <div class="home-loop-item">XP</div>
            <div class="home-loop-item">Character Growth</div>
            <div class="home-loop-item">Analytics</div>
        </div>
        <div class="hq-card">
            <div class="hq-card-body">
                Scheduled tasks create a daily plan. Completed tasks award XP. Categories contribute to RPG stats.
                Analytics reveal patterns over time.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <div class="home-note">
            This is a local-first MVP. SQLite is used for local/demo persistence, and Streamlit Cloud is used as a
            portfolio demo. Local uploaded files and local database data may not behave like production-grade
            persistent storage.
        </div>
        """,
        unsafe_allow_html=True,
    )


apply_theme()
render_sidebar_brand()
render_appearance_controls()

pages = [
    st.Page(render_home_base, title="Home Base", icon=":material/home:", default=True),
    st.Page(
        "pages/1_Dashboard.py",
        title="Command Center",
        icon=":material/dashboard:",
        url_path="Dashboard",
    ),
    st.Page(
        "pages/2_Quest_Log.py",
        title="Quest Planner",
        icon=":material/event:",
        url_path="Quest_Log",
    ),
    st.Page(
        "pages/3_Habit_Analytics.py",
        title="Habit Analytics",
        icon=":material/analytics:",
        url_path="Habit_Analytics",
    ),
    st.Page(
        "pages/4_Character_Profile.py",
        title="Character Profile",
        icon=":material/person:",
        url_path="Character_Profile",
    ),
]

current_page = st.navigation(pages, position="sidebar", expanded=True)
current_page.run()

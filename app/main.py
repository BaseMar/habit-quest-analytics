import sys
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.ui import apply_theme, render_page_header, render_section_title
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
            background:
                linear-gradient(135deg, rgba(139, 92, 246, 0.24), rgba(56, 189, 248, 0.08)),
                linear-gradient(180deg, rgba(31, 41, 55, 0.96), rgba(17, 24, 39, 0.96));
            border: 1px solid rgba(167, 139, 250, 0.28);
            border-radius: 8px;
            box-shadow: 0 18px 38px rgba(2, 6, 23, 0.3);
            margin: 0.25rem 0 1.1rem;
            padding: 1.25rem 1.35rem;
        }

        .home-hero-label {
            color: #a78bfa;
            font-size: 0.74rem;
            font-weight: 800;
            letter-spacing: 0.08em;
            margin-bottom: 0.35rem;
            text-transform: uppercase;
        }

        .home-hero-title {
            color: #f9fafb;
            font-size: 1.65rem;
            font-weight: 850;
            line-height: 1.2;
            margin-bottom: 0.4rem;
        }

        .home-hero-copy {
            color: #d1d5db;
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
            background: linear-gradient(180deg, rgba(31, 41, 55, 0.92), rgba(17, 24, 39, 0.96));
            border: 1px solid rgba(148, 163, 184, 0.2);
            border-radius: 8px;
            box-shadow: 0 14px 30px rgba(2, 6, 23, 0.22);
            min-height: 156px;
            padding: 0.95rem;
        }

        .home-step-number {
            align-items: center;
            background: rgba(139, 92, 246, 0.18);
            border: 1px solid rgba(167, 139, 250, 0.28);
            border-radius: 999px;
            color: #ddd6fe;
            display: inline-flex;
            font-size: 0.78rem;
            font-weight: 800;
            height: 1.75rem;
            justify-content: center;
            margin-bottom: 0.75rem;
            width: 1.75rem;
        }

        .home-step-title {
            color: #f9fafb;
            font-size: 0.96rem;
            font-weight: 750;
            line-height: 1.25;
            margin-bottom: 0.35rem;
        }

        .home-step-body {
            color: #9ca3af;
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
            background: rgba(15, 23, 42, 0.68);
            border: 1px solid rgba(148, 163, 184, 0.2);
            border-radius: 8px;
            color: #f9fafb;
            font-size: 0.9rem;
            font-weight: 750;
            padding: 0.75rem 0.85rem;
            text-align: center;
        }

        .home-note {
            background: rgba(15, 23, 42, 0.52);
            border: 1px solid rgba(148, 163, 184, 0.16);
            border-radius: 8px;
            color: #9ca3af;
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


def apply_sidebar_styles() -> None:
    st.markdown(
        """
        <style>
        section[data-testid="stSidebar"] {
            background:
                linear-gradient(180deg, rgba(15, 23, 42, 1), rgba(17, 24, 39, 0.98)) !important;
            border-right: 1px solid rgba(148, 163, 184, 0.16);
        }

        section[data-testid="stSidebar"] > div {
            padding-top: 1.15rem;
        }

        .hq-sidebar-brand {
            border: 1px solid rgba(148, 163, 184, 0.2);
            border-left: 4px solid #8b5cf6;
            border-radius: 3px;
            background: linear-gradient(135deg, rgba(139, 92, 246, 0.18), rgba(56, 189, 248, 0.08));
            box-shadow: 0 12px 26px rgba(2, 6, 23, 0.22);
            margin: 0.2rem 0 1rem;
            padding: 0.85rem 0.9rem;
        }

        .hq-sidebar-brand-title {
            color: #f9fafb;
            font-size: 1rem;
            font-weight: 850;
            line-height: 1.12;
        }

        .hq-sidebar-brand-subtitle {
            color: #a78bfa;
            font-size: 0.74rem;
            font-weight: 800;
            letter-spacing: 0.08em;
            margin-top: 0.14rem;
            text-transform: uppercase;
        }

        .hq-sidebar-brand-caption {
            color: #9ca3af;
            font-size: 0.78rem;
            line-height: 1.35;
            margin-top: 0.42rem;
        }

        section[data-testid="stSidebar"] nav ul {
            gap: 0.35rem;
        }

        section[data-testid="stSidebar"] nav a,
        section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a,
        section[data-testid="stSidebar"] [data-testid="stPageLink"] a,
        section[data-testid="stSidebar"] a[href^="/"] {
            align-items: center;
            background: rgba(15, 23, 42, 0.55);
            border: 1px solid rgba(148, 163, 184, 0.14);
            border-left: 4px solid rgba(148, 163, 184, 0.24);
            border-radius: 2px !important;
            color: #cbd5e1 !important;
            min-height: 46px;
            padding: 0.78rem 0.85rem !important;
            text-decoration: none;
            transition:
                background-color 160ms ease,
                border-color 160ms ease,
                box-shadow 160ms ease,
                color 160ms ease,
                transform 160ms ease;
        }

        section[data-testid="stSidebar"] nav a:hover,
        section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a:hover,
        section[data-testid="stSidebar"] [data-testid="stPageLink"] a:hover,
        section[data-testid="stSidebar"] a[href^="/"]:hover {
            background: rgba(30, 41, 59, 0.95);
            border-color: rgba(56, 189, 248, 0.38);
            border-left-color: #38bdf8;
            box-shadow: 0 10px 24px rgba(2, 6, 23, 0.26);
            color: #f8fafc !important;
            transform: translateX(3px);
        }

        section[data-testid="stSidebar"] nav a:focus-visible,
        section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a:focus-visible,
        section[data-testid="stSidebar"] [data-testid="stPageLink"] a:focus-visible,
        section[data-testid="stSidebar"] a[href^="/"]:focus-visible {
            outline: 2px solid rgba(56, 189, 248, 0.75);
            outline-offset: 2px;
        }

        section[data-testid="stSidebar"] nav a:active,
        section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a:active,
        section[data-testid="stSidebar"] [data-testid="stPageLink"] a:active,
        section[data-testid="stSidebar"] a[href^="/"]:active {
            background: rgba(139, 92, 246, 0.24);
            border-left-color: #8b5cf6;
            transform: translateX(1px);
        }

        section[data-testid="stSidebar"] nav a[aria-current="page"],
        section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a[aria-current="page"],
        section[data-testid="stSidebar"] [data-testid="stPageLink"] a[aria-current="page"],
        section[data-testid="stSidebar"] a[aria-current="page"],
        section[data-testid="stSidebar"] a[data-active="true"] {
            background: linear-gradient(135deg, rgba(139, 92, 246, 0.32), rgba(56, 189, 248, 0.14));
            border-color: rgba(167, 139, 250, 0.42);
            border-left-color: #8b5cf6;
            box-shadow:
                inset 0 1px 0 rgba(255, 255, 255, 0.05),
                0 12px 26px rgba(2, 6, 23, 0.24);
            color: #ffffff !important;
            font-weight: 750;
        }

        section[data-testid="stSidebar"] nav a span,
        section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a span,
        section[data-testid="stSidebar"] [data-testid="stPageLink"] a span {
            color: inherit !important;
            font-size: 0.94rem;
            font-weight: inherit;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar_brand() -> None:
    st.sidebar.markdown(
        """
        <div class="hq-sidebar-brand">
            <div class="hq-sidebar-brand-title">Habit Quest</div>
            <div class="hq-sidebar-brand-subtitle">Analytics</div>
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
        "Plan quests, build habits, earn XP, and review your progress.",
    )

    st.markdown(
        """
        <div class="home-hero">
            <div class="home-hero-label">Habit Quest Analytics</div>
            <div class="home-hero-title">Habit Quest Analytics</div>
            <div class="home-hero-copy">
                An RPG-inspired habit planner that turns daily tasks into quests and tracks progress through XP,
                analytics, and character growth.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    render_section_title(
        "Mission Briefing",
        "A simple app loop for planning work, reviewing today's mission, and understanding progress over time.",
    )
    st.markdown(
        """
        <div class="home-step-grid">
            <div class="home-step-card">
                <div class="home-step-number">1</div>
                <div class="home-step-title">Plan your quests</div>
                <div class="home-step-body">Use Quest Planner to schedule tasks and habits on the calendar.</div>
            </div>
            <div class="home-step-card">
                <div class="home-step-number">2</div>
                <div class="home-step-title">Review todays mission</div>
                <div class="home-step-body">Use Command Center to see todays focus and attention items.</div>
            </div>
            <div class="home-step-card">
                <div class="home-step-number">3</div>
                <div class="home-step-title">Analyze your patterns</div>
                <div class="home-step-body">Use Habit Analytics to review trends, categories, and consistency.</div>
            </div>
            <div class="home-step-card">
                <div class="home-step-number">4</div>
                <div class="home-step-title">Track your character</div>
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
                <div class="hq-card-body">Todays focus and operational quest status.</div>
            </div>
            <div class="hq-card">
                <div class="hq-card-title">Quest Planner</div>
                <div class="hq-card-body">Calendar planner for scheduled quests and habits.</div>
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
        "The app keeps the loop practical: plan the day, complete quests, and review what the data shows.",
    )
    st.markdown(
        """
        <div class="home-loop">
            <div class="home-loop-item">Quests</div>
            <div class="home-loop-item">XP</div>
            <div class="home-loop-item">Character Growth</div>
            <div class="home-loop-item">Analytics</div>
        </div>
        <div class="hq-card">
            <div class="hq-card-body">
                Scheduled quests create a daily plan. Completed quests award XP. Categories contribute to RPG stats.
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
apply_sidebar_styles()
render_sidebar_brand()

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

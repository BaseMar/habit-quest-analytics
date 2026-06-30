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
    page_title="Home Base",
    page_icon="HQ",
    layout="wide",
)
apply_theme()
init_db()
ensure_default_categories()

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
            <div class="home-step-body">Use Quest Log to schedule tasks and habits on the calendar.</div>
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
            <div class="hq-card-title">Quest Log</div>
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

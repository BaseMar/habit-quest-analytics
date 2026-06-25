# Habit Quest Analytics

A Streamlit analytics dashboard for tracking habits and to-do items as RPG-style quests. The app is structured around a small testable service and metrics layer so the UI can render prepared data instead of owning business rules.

## Features

- quest tracking for habits and tasks,
- XP rewards based on quest difficulty,
- player level calculation from total XP,
- basic habit consistency metrics,
- SQLite database models with SQLAlchemy,
- placeholder Streamlit pages for the MVP workflow.

## Architecture

The project is split into clear layers:

```text
app/
  main.py                  # Streamlit entrypoint
  pages/                   # Streamlit page skeletons
src/
  database/                # SQLAlchemy setup, models, and seed data
  services/                # quest, XP, and analytics services
  analysis/                # pure metric calculation logic
tests/                     # pytest coverage for pure logic
docs/                      # project planning and data documentation
```

Core rule: Streamlit pages should display data and call services. XP rules, level rules, and metrics should stay in plain Python functions with tests.

## Data Model

The local SQLite database uses these SQLAlchemy models:

- `Quest`
- `Category`
- `PlayerProfile`
- `Achievement`
- `UnlockedAchievement`

Default quest categories can be seeded with:

```bash
python -m src.database.seed
```

## Requirements

- Python 3.12 or newer
- dependencies from `requirements.txt`
- local SQLite database stored in `data/habit_quest.db` by default

## Installation

```bash
git clone https://github.com/BaseMar/habit-quest-analytics.git
cd habit-quest-analytics
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Running The App

Initialize the database and seed default categories:

```bash
python -m src.database.seed
```

Run Streamlit:

```bash
streamlit run app/main.py
```

The initial skeleton exposes these pages:

- Dashboard
- Quest Log
- Habit Analytics
- Character Profile

## Tests

The test suite uses `pytest` and currently covers XP rewards, level calculation, and basic metric functions.

```bash
python -m pytest
```

## MVP Scope

- Create and complete quests.
- Assign categories and difficulty levels.
- Award XP for completed quests.
- Calculate character level from total XP.
- Show basic habit completion and consistency analytics.
- Display achievements once achievement rules are added.

## Planned Future Features

- quest creation and editing forms,
- calendar-based habit tracking,
- XP progress charts with Plotly,
- streak and consistency views,
- achievement unlock rules,
- richer character profile stats,
- import and export for local data backups.

## Design Principles

- keep Streamlit pages simple,
- keep business logic in services and analysis modules,
- use SQLite for local-first development,
- test pure logic before expanding UI behavior,
- avoid authentication, machine learning, and external APIs until the MVP is stable.

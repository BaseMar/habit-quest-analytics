# Habit Quest Analytics

An RPG-inspired habit tracker and productivity analytics dashboard built with Streamlit.

Daily tasks are represented as quests. Users earn XP for completed quests, level up a character profile, and analyze habit consistency over time. The current repository is an MVP implementation with calendar-based Quest Log planning, Dashboard KPIs, Habit Analytics charts, an RPG-style Character Profile with local avatar upload, and a polished dark RPG dashboard UI backed by the local SQLite database.

![Python](https://img.shields.io/badge/Python-3.11%2B-blue)
![Streamlit](https://img.shields.io/badge/Streamlit-Dashboard-red)
![SQLite](https://img.shields.io/badge/SQLite-Local%20Database-lightgrey)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-ORM-brown)
![Pandas](https://img.shields.io/badge/Pandas-Data%20Analysis-purple)
![Plotly](https://img.shields.io/badge/Plotly-Charts-green)
![Pytest](https://img.shields.io/badge/Tests-Pytest-yellow)
![Status](https://img.shields.io/badge/Status-MVP%20%2F%20In%20Development-orange)

## Table of Contents

- [Project Goal](#project-goal)
- [My Role](#my-role)
- [Project Status](#project-status)
- [Preview](#preview)
- [Tech Stack](#tech-stack)
- [What It Does](#what-it-does)
- [Example Insights](#example-insights)
- [Features](#features)
- [App Sections](#app-sections)
- [Key Technical Decisions](#key-technical-decisions)
- [Data Flow](#data-flow)
- [Architecture](#architecture)
- [Data Model](#data-model)
- [Metrics](#metrics)
- [Requirements](#requirements)
- [Installation](#installation)
- [Running The App](#running-the-app)
- [Database Setup / Seeding](#database-setup--seeding)
- [Local Storage Notes](#local-storage-notes)
- [Tests](#tests)
- [Design Principles](#design-principles)
- [Limitations & Future Work](#limitations--future-work)
- [Screenshots](#screenshots)

## Project Goal

Habit and to-do tools often track completion, but they rarely make progress feel tangible or show whether daily effort is becoming consistent over time.

Habit Quest Analytics turns tasks into quests and combines habit tracking with lightweight analytics. The goal is to help a user answer:

- what did I complete,
- how much XP did that work generate,
- which habits are becoming consistent,
- which categories are being neglected,
- how my character progression reflects real activity.

## My Role

I designed and built the MVP foundation, including:

- Streamlit multi-page app shell,
- SQLite and SQLAlchemy data model,
- default category seeding script,
- XP and level calculation services,
- basic metric functions,
- a consistent dark Streamlit UI layer,
- documentation for the planned MVP,
- pytest coverage for XP, level, and metric behavior.

The next implementation step is refining the quest lifecycle and daily workflow on top of this foundation.

## Project Status

This repository is currently an MVP in development.

Implemented:

- project scaffold and folder structure,
- Streamlit multi-page app with polished dark RPG dashboard styling,
- SQLAlchemy models and SQLite setup,
- default category seed script,
- calendar-based Quest Log planning, list, and status update workflow,
- Dashboard KPI cards backed by persisted quest data,
- Habit Analytics charts for XP, status, category, weekday completion, and estimated minutes,
- RPG-style Character Profile with level progress, RPG stat XP, compact stat rows, radar chart, achievements placeholder, and local avatar upload,
- XP reward calculation by difficulty,
- level calculation from total XP,
- basic completion and consistency metric functions,
- pytest tests for XP, level, metrics, and quest service behavior.

Planned next:

- quest editing and delete/archive behavior,
- advanced habit analytics filters and trends,
- achievement unlock logic.

## Preview

Screenshots will be added after the current UI is captured from a representative local dataset.

Current UI state: the Command Center page shows real KPI cards from SQLite, the Quest Log page has calendar-based planning with selected-day schedules, Habit Analytics shows Plotly charts, and Character Profile shows an RPG-style character sheet with stat balance and avatar upload. Achievement unlocking remains planned.

## Tech Stack

- Python
- Streamlit
- SQLite
- SQLAlchemy
- Pandas
- Plotly
- streamlit-calendar
- Pytest

## What It Does

Habit Quest Analytics treats ordinary productivity tracking as a small RPG loop:

- quests replace regular tasks,
- difficulty controls XP rewards,
- completed quests increase total XP,
- total XP determines character level,
- character stats reflect accumulated activity,
- habit and productivity analytics show patterns over time.

The current MVP implements calendar-based quest planning, core formulas, KPI cards, analytics charts, and RPG character summary needed for this loop.

## Example Insights

The finished dashboard should answer questions such as:

- Which days of the week are most productive?
- Which quest categories are completed most often?
- How much XP is gained each week?
- Are planned tasks actually completed?
- Which categories are neglected?
- Is estimated time close to actual time?
- Which habits are consistent and which ones are slipping?
- How close is the character to the next level?

## Features

### Implemented

- Streamlit entrypoint and implemented multi-page app sections.
- Reusable dark UI styling helpers for page headers, cards, metrics, charts, and empty states.
- SQLAlchemy models for quests, categories, profiles, achievements, and unlocked achievements.
- SQLite database initialization.
- Seed script for default categories.
- Calendar-based Quest Log planner with scheduled quest creation.
- Selected-day schedule list showing planned quest times, category, difficulty, status, and XP.
- Quest table showing persisted records from SQLite.
- Quest status updates for `Planned`, `Completed`, `Failed`, and `Skipped`.
- Dashboard KPI cards for total quests, completed quests, completion rate, total XP, weekly XP, current level, and XP to next level.
- Habit Analytics charts for XP by day, quests by status, quests by category, completion rate by weekday, and estimated minutes by category.
- Character Profile sheet with avatar upload, character title, level progress, total XP, XP to next level, RPG stats, radar chart, compact stat rows, and achievements placeholder.
- XP calculation for `Easy`, `Medium`, `Hard`, and `Boss` quests.
- Level calculation from total XP.
- Basic completion rate and consistency score functions.
- Pytest coverage for core formulas.

### Planned MVP Features

- Edit and archive quests.
- Add habit flags to the Quest Log form.
- Update player XP after quest completion.
- Add dashboard and analytics filters.
- Track basic streaks.
- Add achievement unlocking.

### Future Ideas

- Calendar-based habit tracking beyond one-time scheduled quests.
- Richer achievement rules.
- Quest templates and recurring quests.
- Planned vs actual time analysis.
- Import and export for local backups.
- Optional ML prediction for quest completion probability.

## App Sections

- `Dashboard` - implemented KPI cards for total quests, completed quests, completion rate, total XP, weekly XP, current level, and XP to next level.
- `Quest Log` - implemented calendar-based quest planning, persisted quest listing, selected-day schedules, and status updates; editing and archive behavior are planned.
- `Habit Analytics` - implemented first Plotly charts for XP by day, status counts, category counts, weekday completion rate, and estimated minutes by category.
- `Character Profile` - implemented character name, title, avatar upload, total XP, level, XP to next level, progress bar, RPG stat XP, radar chart, compact stat rows, and achievements placeholder; achievement unlock logic is still planned.

## Key Technical Decisions

- Keep business rules outside Streamlit pages so they can be tested directly.
- Use SQLite for simple local development and review.
- Use SQLAlchemy models as the persistence boundary.
- Keep metrics as small pure functions before adding chart-specific logic.
- Introduce Pandas and Plotly when real quest records are available for analysis.
- Avoid authentication, external APIs, and ML until the MVP is stable.

## Data Flow

```text
Streamlit UI
  -> Services
  -> SQLAlchemy Models
  -> SQLite Database
  -> Analytics / Metrics
  -> Dashboard Views
```

The intended flow is to keep Streamlit responsible for presentation, services responsible for workflows, SQLAlchemy responsible for persistence, and metrics responsible for calculations.

## Architecture

The project is split into clear layers:

```text
habit-quest-analytics/
  app/
    main.py                  # Streamlit entrypoint
    pages/                   # Streamlit page views
  src/
    database/                # SQLAlchemy setup, models, and seed script
    services/                # quest, XP, and analytics service functions
    analysis/                # pure metric calculation functions
  data/
    sample/                  # placeholder for future sample data
  docs/                      # project overview, MVP, data model, and metrics docs
  tests/                     # pytest coverage for core logic
```

Layer purpose:

- `app/` contains the main Streamlit shell.
- `app/pages/` contains the multi-page navigation targets.
- `src/database/` contains the SQLite connection, SQLAlchemy models, and seed script.
- `src/services/` contains application workflow functions.
- `src/analysis/` contains metric formulas that should not depend on Streamlit.
- `docs/` contains project planning and technical documentation.
- `tests/` contains focused pytest coverage for behavior.

## Data Model

The current SQLAlchemy model set includes:

- `Quest` - a task or habit represented as an RPG quest.
- `Category` - a grouping such as Health, Work, Learning, Home, or Social.
- `PlayerProfile` - the user character profile with total XP and optional local avatar path.
- `Achievement` - an unlockable milestone definition.
- `UnlockedAchievement` - a join record linking a profile to an unlocked achievement.

Current relationships:

- one `Category` can have many `Quest` records,
- one `PlayerProfile` can have many `UnlockedAchievement` records,
- one `Achievement` can be unlocked by many profiles through `UnlockedAchievement`.

## Metrics

Implemented:

- `total XP` - calculated from completed quest XP.
- `level` - calculated with `total_xp // 500 + 1`.
- `XP to next level` - remaining XP before the next 500 XP threshold.
- `completion rate` - calculated as completed quests divided by total quests.
- `weekly XP` - XP earned in the current week from completed quests.

Planned:

- `current streak` - consecutive days with completed habit activity.
- `planned vs actual time` - comparison between estimated quest duration and actual time spent.

XP rewards by difficulty:

- `Easy`: 10 XP
- `Medium`: 30 XP
- `Hard`: 75 XP
- `Boss`: 150 XP

## Requirements

- Python 3.11 or newer
- dependencies from `requirements.txt`
- local SQLite database stored at `data/habit_quest.db` by default

## Installation

```bash
git clone https://github.com/BaseMar/habit-quest-analytics.git
cd habit-quest-analytics
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Running The App

```bash
streamlit run app/main.py
```

The current app opens a polished Streamlit dashboard shell with KPI, quest management, analytics, and character profile pages.

## Database Setup / Seeding

Create the SQLite database tables and seed default categories:

```bash
python -m src.database.seed
```

By default, the database is created at:

```text
data/habit_quest.db
```

## Local Storage Notes

Avatar uploads are stored locally under `data/uploads/`, and the SQLite database is stored locally under `data/` by default. This is suitable for the current local-first MVP and demo workflow.

On Streamlit Community Cloud, local file storage is not guaranteed to persist after an app reboot, redeploy, or instance reset. Production-grade persistence for avatars or durable user data would require external storage or a production database later.

## Tests

The test suite uses `pytest` and currently covers XP reward rules, level calculation, completion rate, and consistency score.

```bash
python -m pytest
python -m compileall -q app src tests
```

## Design Principles

- Keep business logic outside Streamlit views.
- Keep metrics testable as plain Python functions.
- Keep database access separated from calculation logic.
- Keep UI styling consistent, practical, and readable for portfolio review.
- Avoid over-engineering while the MVP is still small.
- Build the MVP step by step, with tests around rules before expanding UI behavior.
- Keep unfinished features clearly labeled as planned or in progress.

## Limitations & Future Work

- Quest calendar planning, list, and status update are implemented; edit and delete/archive are not implemented yet.
- Persistent quest management is limited to scheduled one-time quests; recurring quests and external calendar sync are not implemented.
- Dashboard KPI cards, first Habit Analytics charts, and the RPG-style Character Profile are implemented; advanced filters and charts are still planned.
- Character profile achievements are planned.
- Achievements need unlock rules and UI.
- Planned vs actual time requires an actual-time field; estimated minutes are already stored on quests.
- Optional future ML prediction for quest completion probability may be explored later, but is intentionally out of scope for the MVP.

## Screenshots

Screenshots are not included yet. Capture them after seeding representative quest data so the dashboard, charts, and character profile show meaningful values.

Planned screenshot sections:

- Dashboard overview
- Quest Log
- Habit Analytics
- Character Profile

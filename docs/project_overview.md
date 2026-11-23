# Project Overview

Habit Quest Analytics is an RPG-inspired habit planner and productivity analytics dashboard. It turns scheduled tasks into quests, tracks each planned quest day with check-ins, rewards completed work with XP, and uses analytics to show consistency and progression over time.

## Problem

Most task trackers record whether a task was done, but they do not always connect daily planning, completion, long-term progress, and performance analysis. Users can complete many small actions without seeing which categories are improving, which routines are slipping, or how repeated completion affects long-term growth.

## Purpose

The project combines:

- a practical planner for scheduled quests,
- a checklist-based daily completion workflow,
- an RPG progression layer for motivation,
- an analytics dashboard for reflection.

The MVP should help one user plan quests, resolve daily quest check-ins, earn XP, grow RPG stats, and review trends without adding unnecessary product complexity.

## Target User

The target user is a single person who wants a local-first productivity dashboard for personal habits, focused work, and routine planning. The app is designed for people who like structured self-tracking and prefer an engaging RPG-style interface over a plain checklist.

## Current State

The MVP is deployed on Streamlit Community Cloud with PostgreSQL on Supabase.

Implemented:

- Custom Streamlit navigation with Command Center as the default page.
- Command Center for today's and overdue `QuestCheckin` status actions.
- Planner with calendar scheduling, selected-day editing, unified task/routine/
  project-session form, and read-only Monthly Review.
- Projects & Routines workspace for project creation, editing, lifecycle,
  comparison, bulk session planning, routine templates, future-month generation,
  and safe cleanup.
- Recurring Habits v1 with selected-weekday templates, creation-month
  generation, archive/delete controls, safe single generated-day deletion, and
  safe future planned-day cleanup.
- `QuestCheckin` model for per-day completion status.
- Checklist service for planned, completed, skipped, failed, and reset
  transitions, with scheduled-date validation.
- XP idempotency through `QuestCheckin.xp_awarded`.
- Scheduled quest creation that creates a planned check-in for the scheduled date.
- Safe deletion for unused recurring templates and unresolved one-time planned
  quests while preserving historical and XP-awarded records.
- Time-based XP for new scheduled quests and recurring habit templates.
- Habit Analytics using check-ins for date-filtered plan-versus-completion
  trends, category and routine performance, and insights.
- Character Profile using check-in XP for total XP, nonlinear level, RPG stat
  levels, and stat-level radar chart.
- PostgreSQL through SQLAlchemy, with Alembic schema
  upgrades and a SQLite importer for PostgreSQL.
- Default category seeding.
- Pytest coverage for model, service, metric, profile, and analytics behavior.

Compatibility:

- `Quest.status` still exists on the `quests` table.
- New operational, analytics, and profile behavior should use `QuestCheckin` as the main source of truth when check-ins exist.
- Legacy quest status remains only as compatibility/fallback during the migration.

## Non-Goals For The MVP

- Authentication.
- Multi-user accounts.
- External APIs.
- Machine learning.
- Cloud sync.
- Production-grade hosted persistence.

## Future Roadmap

1. Authentication and user-specific data isolation.
2. Google Calendar sync for scheduled quests.
3. AI planning assistant for natural-language scheduling.
4. Voice quest capture / microphone input.
5. Streak system / bonus XP.
6. Optional automatic stale planned failure workflow.
7. Legacy `Quest.status` cleanup after the check-in migration is stable.

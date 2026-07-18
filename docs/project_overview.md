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

The MVP is functional and deployed as a public Streamlit Cloud portfolio demo.

Implemented:

- Custom Streamlit navigation with Command Center as the default page.
- Command Center for today's and overdue `QuestCheckin` status actions.
- Planner with calendar scheduling, selected-day editing, unified task/routine/
  project-session form, and read-only Monthly Review.
- Projects & Routines workspace for project lifecycle, bulk session planning,
  routine templates, future-month generation, and safe cleanup.
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
- Habit Analytics using check-ins for weekly pulse, XP trends, status/category breakdowns, consistency, planned minutes, and insights.
- Character Profile using check-in XP for total XP, nonlinear level, RPG stat
  levels, and stat-level radar chart.
- SQLite/SQLAlchemy persistence and startup schema helpers.
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

These ideas are not currently implemented.

1. True N-times-per-week routine scheduling.
2. PostgreSQL / production persistence.
3. Authentication and user-specific data isolation.
4. Google Calendar sync for scheduled quests.
5. AI planning assistant for natural-language scheduling.
6. Voice quest capture / microphone input.
7. Streak system / bonus XP.
8. Optional automatic stale planned failure workflow.
9. Legacy `Quest.status` cleanup after the check-in migration is stable.

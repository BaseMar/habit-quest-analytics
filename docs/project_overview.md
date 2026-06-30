# Project Overview

Habit Quest Analytics is an RPG-inspired habit tracker and productivity analytics dashboard. It turns daily habits and to-do items into quests, rewards completed work with XP, and uses simple analytics to show whether effort is becoming consistent over time.

## Problem

Most task trackers record whether a task was done, but they do not make progress feel cumulative or easy to analyze. Users can complete many small actions without seeing which categories they are improving, which routines are slipping, or how daily activity adds up over weeks.

## Purpose

The project combines two ideas:

- a lightweight RPG progression loop for motivation,
- a dashboard-style analytics layer for reflection.

The MVP should help a user manage quests, earn XP, level up a character profile, and review habit consistency without adding unnecessary product complexity.

## Target User

The target user is a single person who wants a local-first productivity dashboard for personal habits, recurring routines, and focused work tasks. The project is designed for people who like structured self-tracking but want a more engaging interface than a plain checklist.

## Current State

The repository currently contains the initial scaffold:

- placeholder Streamlit pages plus an interactive Quest Log page,
- SQLite and SQLAlchemy setup,
- models for quests, categories, player profiles, and achievements,
- seed data for default categories,
- quest create, list, and status update behavior,
- dashboard KPI cards powered by persisted quests,
- first Habit Analytics charts powered by persisted quests,
- RPG-style Character Profile with level progress, RPG stat XP, radar chart, compact stat rows, achievements placeholder, and local avatar upload,
- XP, level, completion, and consistency calculations,
- pytest coverage for core formulas.

Quest editing, delete/archive behavior, analytics filters, and achievement unlocking are planned next.

## Non-Goals For The MVP

- Authentication.
- Multi-user accounts.
- External APIs.
- Machine learning.
- Cloud sync.

## Advanced Future Extensions

These ideas are intentionally outside the current local-first MVP and should not be treated as implemented features.

- Google Calendar integration - sync scheduled quests with Google Calendar so planned habits and tasks can appear alongside real calendar events.
- User authentication - add login support so each user has separate quests, calendar, character profile, and analytics. This would likely require a production database and a user-specific data model.
- AI planning assistant - add an LLM-powered assistant that understands natural language planning requests, such as "Schedule gym tomorrow from 9 to 11", and creates scheduled quests.
- Voice quest capture - add microphone input so users can speak tasks or habit plans. This depends on the future AI planning assistant and should come after the core planner is stable.

Suggested implementation order:

1. Monthly habit checklist
2. Recurring habits
3. PostgreSQL / production persistence
4. Authentication
5. Google Calendar sync
6. AI planning assistant
7. Voice input

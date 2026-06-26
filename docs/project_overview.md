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
- XP, level, completion, and consistency calculations,
- pytest coverage for core formulas.

Quest editing, delete/archive behavior, advanced analytics charts, player XP updates, and achievement unlocking are planned next.

## Non-Goals For The MVP

- Authentication.
- Multi-user accounts.
- External APIs.
- Machine learning.
- Cloud sync.

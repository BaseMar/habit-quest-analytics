# Long-term Goals / Projects Design

This design record explains the project and session decisions currently used
by Habit Quest Analytics. See the [metrics reference](metrics.md#goal-analytics)
for current formulas and the [roadmap](roadmap.md) for future work.

Current implementation status:

- `Goal` model and service-layer foundation are implemented.
- One-time scheduled quests can link to active goals through `Quest.goal_id`.
- Goal-linked quest sessions receive stable per-goal session numbers through
  `Quest.goal_session_number`.
- Goal progress is derived from linked quest sessions and their check-ins.
- Projects & Routines owns project creation, editing, progress, lifecycle, and
  comparison.
- Planner can link one-time sessions to an existing active project.
- The selected-project workspace includes a Goal Session Planner for previewing
  and bulk creating multiple planned one-time sessions.
- Goal session titles are generated automatically as
  `{Goal Title} Session {N}`.
- The same project workspace includes lifecycle actions to archive, complete,
  reopen, and delete goals.
- Recurring habits are not linked to goals.
- The Portfolio tab compares active and completed projects. The Projects tab
  includes a deterministic completion forecast for the selected project.

## Problem

Some habits and quests are not single isolated tasks. They are sessions inside a
larger goal or project.

Example:

A Portfolio Project planned for 20 hours can be split into 10 sessions of 2
hours.

Project reporting tracks the following measures.

- total planned effort,
- completed effort,
- remaining effort,
- progress percentage,
- XP earned through completed sessions,
- linked quest/session history.

## Core Concept

The project entity is `Goal`. Its core fields are listed below. The
[data model](data_model.md#goals) documents account ownership and constraints.

- `id`
- `title`
- `description`
- `category_id`
- `planned_total_minutes`
- `start_date`
- `target_end_date`
- `status`: `Active`, `Completed`, or `Archived`
- `created_at`
- `updated_at`

A goal/project does not award XP directly. XP is earned through completed linked
quest sessions.

`planned_total_minutes` can be `0` when the user does not know the total effort
up front. In that case the app still tracks completed session effort and XP, but
does not show a time-target percentage until a target is set.

## Quest / Session Relationship

A quest can optionally belong to a goal/project.

Implemented field:

- `Quest.goal_id`, nullable foreign key
- `Quest.goal_session_number`, nullable integer

Rules:

- One-time scheduled quests can be linked to an active goal.
- Linked goal sessions are numbered per goal using the current maximum session
  number plus one.
- Existing linked sessions without a number are backfilled deterministically by
  planned start/due date, creation time, then id.
- Deleting a session does not renumber remaining sessions.
- User-supplied titles do not override goal session titles.
- Routines and their generated occurrences remain separate from projects.
- A goal can have many quest sessions.
- Each linked quest session has its own `QuestCheckin`.
- `QuestCheckin.xp_awarded` remains the XP source of truth.

Example:

```text
Goal: Portfolio Project
planned_total_minutes = 1200

Sessions:
- Session 1: 120 minutes, Completed, 40 XP
- Session 2: 120 minutes, Completed, 40 XP
- Session 3: 120 minutes, Planned, 0 XP

Progress:
- completed_minutes = 240
- total_minutes = 1200
- progress = 20%
- earned_xp = 80
```

## XP Behavior

Goals should not double-award XP.

Rules:

- Linked quest sessions award XP normally using time-based XP.
- Goal earned XP is the sum of `QuestCheckin.xp_awarded` for linked sessions.
- Expected project XP applies the time-based formula to positive target effort.
- Project completion itself awards no additional XP.

Current XP formula remains unchanged:

```text
XP = max(5, round(planned_minutes / 60 * 20))
```

## Progress Calculation

The goal service returns the following progress metrics.

- `planned_total_minutes`
- `completed_minutes` from completed linked quest check-ins
- `remaining_minutes`
- `progress_percent`
- `completed_sessions_count`
- `planned_sessions_count`
- `failed_sessions_count`
- `skipped_sessions_count`
- `earned_xp`
- `expected_total_xp`

Rules:

- Completed sessions contribute to `completed_minutes`.
- Planned sessions do not contribute to `completed_minutes`.
- Skipped and failed sessions do not contribute to `completed_minutes`.
- Reset sessions remove completed contribution because `xp_awarded` returns to
  `0` and status is reset.
- When `planned_total_minutes > 0`, `progress_percent = completed_minutes /
  planned_total_minutes * 100`, capped at 100% for display.
- When `planned_total_minutes = 0`, progress percent remains `0` and completed
  effort is still tracked from linked sessions.

## UI Design

### Planner And Projects Workspace

- Create projects from Projects & Routines with a title, required category,
  and optional effort target, dates, and notes.
- A one-time scheduled quest can optionally be linked to an active goal/project
  at creation time.
- Users select one project workspace in Projects & Routines; it shows
  completed/planned effort, progress percentage,
  earned/expected XP, session counts, category, status, and target date.
- The Add to plan form can select an existing active project. It creates a normal
  one-time scheduled quest session with a planned `QuestCheckin` and awards no
  XP until completed.
- Project-linked sessions use generated session titles instead of asking the
  user to name each session manually.
- Goal/project creation and linked goal sessions reject missing categories.
- Project lifecycle actions appear in the selected project workspace alongside
  progress and session-planning controls.
- Project deletion requires confirmation and leaves linked sessions in Planner
  as one-time tasks, with check-ins and XP preserved.
- Recurring habit template creation does not show or set a goal link.
- Linked quest sessions continue to create normal planned `QuestCheckin` rows.
- Bulk-planned sessions also create separate normal `Quest` and
  `QuestCheckin` records. They do not award XP until completed.

Goal Session Planner behavior:

- The planner is opened explicitly from the selected project workspace.
- It does not generate sessions on page load.
- The user enters one session duration in minutes, start date, selected weekdays, start time,
  optional planning end date, and whether a shorter final session is allowed.
- The UI shows goal effort, completed effort, already planned effort, and the
  still-unscheduled effort before preview.
- Preview is read-only and shows proposed session number, generated title, date,
  time, duration, and expected quest XP.
- Bulk creation requires explicit confirmation after preview.
- Generation recalculates scheduling effort immediately before writing rows, so
  reruns or stale previews do not over-allocate already planned effort.
- Each generated session uses time-based `Quest.xp_reward`, but
  `QuestCheckin.xp_awarded` remains `0` until completion.
- Existing sessions are not renamed or renumbered.

Planning effort formula:

```text
effort_to_schedule_minutes =
    max(planned_total_minutes - completed_minutes - currently_planned_minutes, 0)
```

Rules:

- Completed check-ins reduce effort still requiring scheduling.
- Planned check-ins reduce effort still requiring scheduling.
- Failed and skipped check-ins are counted separately but do not reduce
  scheduling effort, so replacement work can be planned.
- Reset check-ins count according to their current `Planned` status.
- Archived and completed goals cannot generate sessions.

Example flow:

1. Create Goal: Portfolio Project, 20h total.
2. Open the project and select **Plan sessions**.
3. Preview 2h sessions on Monday, Wednesday, and Friday.
4. Confirm generation of 10 separate planned quest sessions.
5. Complete sessions in Planner or Summary.
6. Goal progress updates automatically.

### Projects & Routines

The implemented Projects & Routines page provides project creation, editing,
the selected-project workspace, lifecycle actions, compact comparison, and bulk
session planning.

### Project Analytics

- Portfolio displays active-project count, completed and remaining effort, and
  weighted progress when at least two active or completed projects qualify.
- Projects shows progress for a selected project and a forecast based on
  completed planned effort per day when the target and history support it.
- The [metrics reference](metrics.md#goal-completion-forecast) describes when a
  forecast is available, including the effort-target-reached case.

## Data Model Design

The following fields are implemented. See the [ERD](data_model.md#mermaid-erd)
for same-owner relationships.

### goals

| Field | Purpose |
| --- | --- |
| `id` | Primary key. |
| `title` | Goal/project name shown to the user. |
| `description` | Optional detail. |
| `category_id` | Foreign key to `categories.id`; current service/UI creation requires it. |
| `planned_total_minutes` | Total planned effort for the goal. `0` means no time target has been set yet. |
| `start_date` | Optional start date. |
| `target_end_date` | Optional target completion date. |
| `status` | `Active`, `Completed`, or `Archived`. |
| `created_at` | Timestamp set when the goal is created. |
| `updated_at` | Timestamp updated when the goal changes. |

### quests update

| Field | Purpose |
| --- | --- |
| `goal_id` | Nullable foreign key to `goals.id`. Implemented for one-time scheduled quests. |
| `goal_session_number` | Nullable stable session number scoped to a goal. |

`QuestCheckin.xp_awarded` records XP earned by linked sessions.

## Safe Deletion / Archive Rules

- Archiving keeps the project and its session links for project reporting.
- Deleting a project detaches all sessions in the same transaction. Their titles,
  schedules, check-in history, and awarded XP are preserved. They appear as
  one-time tasks in Planner and Analytics.

## Historical Implementation Phases

1. `docs: add long-term goals design` - implemented.
2. `feat: add goal/project model and service layer` - implemented.
3. `feat: link one-time quests to goals` - implemented.
4. `feat: add goal progress UI in Projects & Routines` - implemented.
5. `feat: add goal creation UI in Projects & Routines` - implemented.
6. `feat: add goal lifecycle actions in Projects & Routines` - implemented.
7. `feat: add unified one-time goal session flow` - implemented.
8. `feat: add goal session planner` - implemented.
9. `feat: add project comparison` - implemented in Projects & Routines.
10. `docs: update long-term goals documentation` - implemented.

## Test Plan

The [goal service](../tests/test_goal_service.py),
[bulk planner](../tests/test_goal_session_planner_service.py), and
[analytics](../tests/test_analytics_service.py) suites cover these cases.

- create goal,
- update goal,
- archive goal,
- link one-time quest to goal,
- completed linked quest contributes minutes and XP,
- planned linked quest does not contribute completed minutes,
- skipped or failed linked quest does not contribute completed minutes,
- reset linked check-in removes contribution,
- goal progress percent calculates correctly,
- goal earned XP sums `QuestCheckin.xp_awarded`,
- deleting or archiving goals preserves completed history,
- existing quest/check-in/XP tests still pass.

## Scope decisions

Bulk generation requires preview and confirmation. Linked sessions provide
the work breakdown for personal projects. See the [roadmap](roadmap.md) for
future assistant and calendar work, and the deferred backlog for project
dependencies, subtasks, sharing, and bonus rewards.

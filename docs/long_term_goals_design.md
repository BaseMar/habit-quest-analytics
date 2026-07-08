# Long-term Goals / Projects Design

This document designs a future Long-term Goals / Projects feature for Habit
Quest Analytics. It is a planning document only; the feature is not implemented
yet.

## Problem

Some habits and quests are not single isolated tasks. They are sessions inside a
larger goal or project.

Example:

A Portfolio Project planned for 20 hours can be split into 10 sessions of 2
hours.

The app should eventually understand:

- total planned effort,
- completed effort,
- remaining effort,
- progress percentage,
- XP earned through completed sessions,
- linked quest/session history.

## Core Concept

Add a future entity named `Goal` or `Project`.

Suggested fields:

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

A goal/project should not award XP directly by default. XP should be earned
through completed linked quest sessions.

## Quest / Session Relationship

A quest can optionally belong to a goal/project.

Suggested future field:

- `Quest.goal_id`, nullable foreign key

Rules:

- One-time quests can be linked to a goal.
- Recurring habits can remain separate for v1.
- Generated recurring habit quests do not need goal linking in v1 unless that is
  explicitly added later.
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
- Goal planned XP can be the sum of planned XP for linked/planned sessions or a
  value calculated from `planned_total_minutes`.
- Completing the goal itself should not automatically award extra XP in v1.
- Optional completion bonus XP can be future work, but it is out of scope for
  v1.

Current XP formula remains unchanged:

```text
XP = max(5, round(planned_minutes / 60 * 20))
```

## Progress Calculation

Planned metrics for each goal:

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
- `progress_percent = completed_minutes / planned_total_minutes * 100`, capped
  at 100% for display.

## UI Design

### Quest Planner

Future Quest Planner capabilities:

- Create a goal/project.
- Link a one-time quest/session to a goal/project.
- View goal progress.
- Create a new session for a goal.

Example flow:

1. Create Goal: Portfolio Project, 20h total.
2. Add Session: 2h on Monday.
3. Add Session: 2h on Wednesday.
4. Complete sessions in Monthly Checklist.
5. Goal progress updates automatically.

### Goal Dashboard / Project Board

A future page or section could show:

- active goals list,
- progress bar per goal,
- completed/total hours,
- earned XP,
- remaining hours,
- target date,
- status.

### Character Profile

Potential future addition:

- Show major active goals or completed goals.
- Avoid overcomplicating the current Character Profile.

### Habit Analytics

Potential future metrics:

- goal progress over time,
- XP by goal,
- completed minutes by goal,
- most progressed goal,
- stalled goals.

## Data Model Design

Possible model additions:

### goals

| Field | Purpose |
| --- | --- |
| `id` | Primary key. |
| `title` | Goal/project name shown to the user. |
| `description` | Optional detail. |
| `category_id` | Optional foreign key to `categories.id`. |
| `planned_total_minutes` | Total planned effort for the goal. |
| `start_date` | Optional start date. |
| `target_end_date` | Optional target completion date. |
| `status` | `Active`, `Completed`, or `Archived`. |
| `created_at` | Timestamp set when the goal is created. |
| `updated_at` | Timestamp updated when the goal changes. |

### quests update

| Field | Purpose |
| --- | --- |
| `goal_id` | Nullable foreign key to `goals.id`. |

No new XP table should be added in v1. `QuestCheckin.xp_awarded` remains the XP
source of truth.

## Safe Deletion / Archive Rules

Goals should follow the same conservative deletion philosophy as recurring
habits and planned quest cleanup.

Rules:

- Goals with no linked quests can be hard-deleted.
- Goals with linked history should be archived, not hard-deleted.
- Deleting a goal should not delete completed quest/check-in history by default.
- Unlinking unresolved planned sessions may be allowed.
- Completed, skipped, failed, and XP-awarded history must be preserved.

## Implementation Phases

1. `docs: add long-term goals design`
2. `feat: add goal/project model and service layer`
3. `feat: link one-time quests to goals`
4. `feat: add goal progress UI in Quest Planner`
5. `feat: add goal analytics`
6. `docs: update long-term goals documentation`

## Test Plan

Future tests should cover:

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

## Out Of Scope For V1

- Automatic AI goal planning.
- Automatic session generation from total planned hours.
- Completion bonus XP.
- Dependencies between goals.
- Subtasks beyond linked quest sessions.
- Team/shared goals.
- Google Calendar sync.
- PostgreSQL migration.

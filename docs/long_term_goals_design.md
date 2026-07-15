# Long-term Goals / Projects Design

This document designs the Long-term Goals / Projects feature for Habit Quest
Analytics.

Current implementation status:

- `Goal` model and service-layer foundation are implemented.
- One-time scheduled quests can link to active goals through `Quest.goal_id`.
- Goal-linked quest sessions receive stable per-goal session numbers through
  `Quest.goal_session_number`.
- Goal progress is derived from linked quest sessions and
  `QuestCheckin.xp_awarded`.
- Quest Planner includes a compact goal creation form.
- Quest Planner includes read-only active goal progress cards.
- Active goal cards include a compact Add Session flow for planned one-time
  quest sessions linked to that goal.
- Goal session titles are generated automatically as
  `{Goal Title} Session {N}`.
- Quest Planner includes compact lifecycle actions to archive, complete, reopen,
  and safely delete unused goals.
- Recurring habits are not linked to goals.
- Full Goal Dashboard / Project Board UI is not implemented yet.

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

The backend foundation adds an entity named `Goal`.

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
- When `planned_total_minutes > 0`, `progress_percent = completed_minutes /
  planned_total_minutes * 100`, capped at 100% for display.
- When `planned_total_minutes = 0`, progress percent remains `0` and completed
  effort is still tracked from linked sessions.

## UI Design

### Quest Planner

Current backend/minimal UI behavior:

- Goals can be created in Quest Planner with title, optional planned total time,
  optional notes, required category, start date, and target date.
- A one-time scheduled quest can optionally be linked to an active goal/project
  at creation time.
- Active goals are shown in a compact read-only Goal Progress section in Quest
  Planner.
- Goal progress cards show completed/planned effort, progress percentage,
  earned/expected XP, session counts, category, status, and target date.
- Active goal cards can quick-add a normal one-time scheduled quest session for
  that goal. The session creates a normal planned `QuestCheckin` and awards no
  XP until completed.
- The quick-add flow shows a read-only preview of the generated session title
  instead of asking the user to name the session manually.
- Goal/project creation and linked goal sessions reject missing categories.
- A compact Manage Goals section supports Archive, Complete, Reopen, and Delete.
- Delete is allowed only for goals with no linked quests; goals with linked
  quest sessions should be archived instead.
- Recurring habit template creation does not show or set a goal link.
- Linked quest sessions continue to create normal planned `QuestCheckin` rows.

Future Quest Planner capabilities:

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

Current implementation:

- Habit Analytics has a `Goals / Projects` tab.
- Goal KPIs include active goals, completed goals, planned effort, completed
  effort, weighted overall progress, and earned goal XP.
- Goal progress comparison uses completed and remaining effort from linked
  one-time quest sessions.
- XP by goal is derived from `QuestCheckin.xp_awarded` for linked sessions.
- Session outcomes show completed, planned, skipped, and failed linked sessions.
- Completed goal effort by week uses `QuestCheckin.checkin_date`.

Future analytics ideas:

- most progressed goal,
- stalled goals,
- deeper goal-level drilldowns in a standalone dashboard.

## Data Model Design

Possible model additions:

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

No new XP table is added in v1. `QuestCheckin.xp_awarded` remains the XP source
of truth.

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

1. `docs: add long-term goals design` - implemented.
2. `feat: add goal/project model and service layer` - implemented.
3. `feat: link one-time quests to goals` - implemented.
4. `feat: add goal progress UI in Quest Planner` - implemented.
5. `feat: add goal creation UI in Quest Planner` - implemented.
6. `feat: add goal lifecycle actions in Quest Planner` - implemented.
7. `feat: add goal session quick-add flow` - implemented.
8. `feat: add goal analytics` - implemented in Habit Analytics.
9. `docs: update long-term goals documentation`

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

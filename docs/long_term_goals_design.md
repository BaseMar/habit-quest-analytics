# Long-term Goals / Projects Design

This document designs the Long-term Goals / Projects feature for Habit Quest
Analytics.

Current implementation status:

- `Goal` model and service-layer foundation are implemented.
- One-time scheduled quests can link to active goals through `Quest.goal_id`.
- Goal-linked quest sessions receive stable per-goal session numbers through
  `Quest.goal_session_number`.
- Goal progress is derived from linked quest sessions and their check-ins.
- Projects & Routines owns project creation, editing, progress, lifecycle, and
  comparison.
- Quest Planner can link one-time sessions to an existing project.
- The selected-project workspace includes a Goal Session Planner for previewing
  and bulk creating multiple planned one-time sessions.
- Goal session titles are generated automatically as
  `{Goal Title} Session {N}`.
- The same project workspace includes lifecycle actions to archive, complete,
  reopen, and safely delete unused goals.
- Recurring habits are not linked to goals.
- A deeper standalone project dashboard is not implemented yet.

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

### Planner And Projects Workspace

Current backend/minimal UI behavior:

- Projects can be created inline in Planner with title, optional planned total time,
  optional notes, required category, start date, and target date.
- A one-time scheduled quest can optionally be linked to an active goal/project
  at creation time.
- Users select one project workspace in Projects & Routines; it shows
  completed/planned effort, progress percentage,
  earned/expected XP, session counts, category, status, and target date.
- The unified Add to plan form can select an active project or create one
  inline from its optional project section. A selected project creates a normal
  one-time scheduled quest session with a planned `QuestCheckin` and awards no
  XP until completed.
- Project-linked sessions use generated session titles instead of asking the
  user to name each session manually.
- Goal/project creation and linked goal sessions reject missing categories.
- Project lifecycle actions appear in the selected project workspace alongside
  progress and session-planning controls.
- Delete is allowed only for goals with no linked quests; goals with linked
  quest sessions should be archived instead.
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
2. Open the project, then select Plan Multiple Sessions.
3. Preview 2h sessions on Monday, Wednesday, and Friday.
4. Confirm generation of 10 separate planned quest sessions.
5. Complete sessions in Command Center.
6. Goal progress updates automatically.

### Projects & Routines

The implemented Projects & Routines page provides project creation, editing,
the selected-project workspace, lifecycle actions, compact comparison, and bulk
session planning.

### Character Profile

Potential future addition:

- Show major active goals or completed goals.
- Avoid overcomplicating the current Character Profile.

### Project Analytics

Current implementation:

- Projects & Routines provides a compact comparison of active and completed
  projects.
- Goal KPIs include active goals, completed goals, planned effort, completed
  effort, weighted overall progress, and earned goal XP.
- The comparison uses completed and remaining effort from linked one-time quest
  sessions.
- A project with target effort, target date, and completed session history shows
  a completion forecast based on its completed planned effort per day.

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
4. `feat: add goal progress UI in Projects & Routines` - implemented.
5. `feat: add goal creation UI in Projects & Routines` - implemented.
6. `feat: add goal lifecycle actions in Projects & Routines` - implemented.
7. `feat: add unified one-time goal session flow` - implemented.
8. `feat: add goal session planner` - implemented.
9. `feat: add project comparison` - implemented in Projects & Routines.
10. `docs: update long-term goals documentation` - implemented.

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
- Automatic session generation without explicit preview and confirmation.
- Completion bonus XP.
- Dependencies between goals.
- Subtasks beyond linked quest sessions.
- Team/shared goals.
- Google Calendar sync.
- PostgreSQL migration.

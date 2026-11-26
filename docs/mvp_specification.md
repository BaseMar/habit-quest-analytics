# MVP Specification

The original MVP established the loop for planning quests, tracking daily
completion, earning XP, leveling up, and reviewing productivity patterns.
This specification preserves the original scope and the decisions it produced.
See the [repository baseline](project_overview.md) for current behavior and the
[development roadmap](roadmap.md) for planned work.

## MVP Scope

The core loop included the following capabilities by the end of its initial
implementation.

- calendar-based scheduled quest creation,
- daily quest completion through Planner check-ins,
- recurring habit templates with creation-month and future-month planned-day generation,
- categories for organizing work,
- time-based XP for new scheduled quests and recurring habit templates,
- XP rewards stored per completed check-in,
- player profile with XP, nonlinear level, avatar, and RPG stat levels,
- Summary actions and KPIs,
- Habit Analytics trends and consistency metrics,
- pytest coverage for business rules.

## User Stories

- As a user, I want to schedule a quest so I can plan a task or habit for a specific day.
- As a user, I want to mark a planned quest day as completed, skipped, failed, or planned.
- As a user, I want completed quest days to award XP only once.
- As a user, I want recurring habits to generate planned quest days for selected weekdays.
- As a user, I want to review today's planned and resolved quest check-ins.
- As a user, I want to see my level and RPG stats grow from completed activity.
- As a user, I want analytics that show trends, categories, consistency, and planned workload.

## Current App Sections

- `Planner` - default workspace with a clickable calendar, unified planning form,
  inline editing, daily check-in actions, and a read-only Monthly checklist.
- `Summary` - today's progress, overdue work, and past check-ins.
- `Projects & Routines` - project creation, editing, lifecycle, comparison,
  bulk project-session planning, routine templates, and future-month routine
  generation.
- `Habit Analytics` - period comparisons, consistency, workload execution,
  and category and routine performance.
- `Character Profile` - avatar, XP, level, RPG stats, and radar chart.

## User-Facing Language

The planner uses simple terms in its interface:

- `Task` - one planned item, including a one-time item or a project session.
- `Routine` - repeated work that can add scheduled days to a selected month.
- `Project` - a longer outcome made up of task sessions.

`Quest`, `QuestCheckin`, and recurring-template names remain internal model terms
or part of the RPG presentation. They should not be needed to complete daily
planning work.

## Historical Implementation Phases

### Phase 1: Scaffold

Implemented in the initial scaffold or subsequent setup work.

- Create project structure.
- Add Streamlit pages.
- Add SQLAlchemy models.
- Add default category seeding.
- Add XP and level formulas.
- Add initial tests.

### Phase 2: Quest Planning

Status: implemented for scheduled one-time quests and recurring habit templates.

- Create scheduled quests from Planner using the selected day as the
  default schedule.
- Store title, notes, category, planned date, planned start/end times, estimated minutes, and XP reward.
- Validate that end time is after start time.
- Display quests on the calendar and selected day schedule.
- Create recurring habit templates for selected weekdays.
- Edit recurring habit templates without changing already generated days or
  their completed, skipped, failed, or planned history.
- Generate recurring habit planned days for a selected month.
- Stop/resume recurring habit templates with generated history, with optional
  cleanup of future unresolved planned days when stopping.
- Delete unused recurring habit templates.
- Delete unresolved one-time planned quests while preserving historical or
  XP-awarded records.
- Delete a single unresolved generated recurring occurrence while preserving
  historical or XP-awarded records.
- Remove future unresolved planned generated days while preserving completed,
  skipped, failed, and XP-awarded history.

The design limited editing and deletion to unresolved work. The roadmap's
[deferred backlog](roadmap.md#deferred-backlog) covers historical edits and soft hide.

### Phase 3: Monthly Checklist

Status: implemented v1.

- Add `QuestCheckin` model with unique `quest_id + checkin_date`.
- Create planned check-ins for scheduled quests.
- Build monthly checklist data with rows for tasks, routines, and projects, and
  columns for days.
- Render a compact read-only matrix preview in Planner.
- Provide status transitions for today's and past check-ins in Planner and Summary.
- Keep XP idempotent with `QuestCheckin.xp_awarded`.

The monthly grid is read-only. Planner and Summary provide date-specific
status actions. The stale planned failure helper has no automatic trigger.

### Phase 4: Summary

Status: implemented with check-ins.

- Planned Today counts planned check-ins for today.
- Completed Today counts completed check-ins for today.
- Overdue counts planned check-ins before today.
- Failed counts failed check-ins through today.
- Today's Focus reads parent quest metadata and `QuestCheckin.status`.
- Summary provides status actions for daily work and overdue check-ins.

### Phase 5: Habit Analytics

Status: implemented with check-ins when available.

- Weekly XP from `QuestCheckin.xp_awarded`.
- Completed and failed quest days for the current week.
- Weekly completion rate using completed / (completed + failed).
- XP trend by check-in date.
- Check-ins by status.
- Check-ins by category.
- Completion rate by weekday.
- Planned minutes by category.
- Insight summaries from check-in data.

Legacy fallback in this view applies when no check-ins are visible to the account.

### Phase 6: Character Profile

Status: implemented with check-ins when available.

- Total XP from `QuestCheckin.xp_awarded`.
- Level and XP-to-next-level from check-in XP.
- Completed Quest Days from completed check-ins.
- RPG stat XP from completed check-ins joined to quest categories.
- RPG stat levels and radar chart from stat levels.
- Local avatar upload path stored on the player profile.

Legacy fallback in this view applies when no check-ins are visible to the account.

## Changes Beyond The Original MVP

Subsequent work added PostgreSQL persistence and Alembic migrations, a SQLite
backup importer, Google authentication and account ownership, a resettable
guest demo, and project planning and forecasting. Date filters, period
comparison, and routine streaks also now ship. See the
[repository baseline](project_overview.md) for evidence.

## MVP Success Criteria

- A user can schedule work in Planner.
- Scheduled quests create planned check-ins.
- Users can complete, skip, fail, or reset eligible check-ins in Planner and
  Summary. The Monthly Checklist provides a read-only record.
- A user can safely remove unresolved planned records without deleting
  completed, skipped, failed, or XP-awarded history.
- Completed check-ins award XP once.
- Summary, Habit Analytics, and Character Profile use check-ins when available.
- Core formulas and service behavior remain covered by tests.

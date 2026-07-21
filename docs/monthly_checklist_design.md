# Monthly Habit Checklist v1 Design

This document records the approved design and current implementation status for the checklist-based daily completion workflow in Quest Planner.

## Status

Monthly Checklist v1 is implemented.

Implemented:

- `QuestCheckin` data model.
- Unique `quest_id + checkin_date` constraint.
- Checklist status service.
- Scheduled quest -> planned check-in integration.
- Monthly checklist data builder.
- Quest Planner Monthly Checklist UI.
- Monthly Checklist blocks status updates for not-scheduled cells.
- Quest Planner calendar and selected day schedule using check-in status.
- Command Center metrics using check-ins.
- Character Profile XP/progression using check-in XP.
- Habit Analytics using check-ins.
- Generated recurring habit days grouped into one logical checklist row per
  template.
- Goal-linked one-time sessions grouped into one logical checklist row per
  goal/project.

Not implemented:

- automatic app/page-level stale planned failure,
- production database,
- authentication,
- Google Calendar sync,
- AI planning assistant,
- voice input.

## Goal

Monthly Checklist v1 replaces the old temporary Quest Planner status workflow with a daily completion system.

Target flow:

- Plan quests in Quest Planner.
- Scheduled quests create planned check-ins for their scheduled date.
- Review a selected month.
- Resolve today's or overdue planned work in Command Center.
- Award XP once for completed daily check-ins.
- Feed check-in data into Command Center, Habit Analytics, and Character Profile.

## Product Behavior

The checklist tracks completion per quest per day. Completion status should not be stored only in `Quest.status`, because one quest can eventually have many daily results.

Core behavior:

- User selects a month and year.
- Rows represent planned quests, recurring habit templates, or goals/projects.
- Columns represent days of the selected month.
- Each non-goal cell represents one quest on one date.
- Goal cells can represent one or more linked session check-ins for that goal on
  that date.
- The monthly matrix is a read-only history and does not expose status actions.
- Command Center marks an eligible check-in `Completed`, `Skipped`, `Failed`, or
  resets it to `Planned`.
- Unresolved planned cells remain `Planned`.
- Empty days remain neutral/blank and are locked.
- Completed check-ins award XP once.
- Skipped and failed check-ins award no XP.

Status safeguards:

- Status actions never create check-ins for unscheduled dates.
- The service rejects updates for a quest/date pair without a scheduled
  check-in.
- Command Center exposes status actions only for eligible today's and overdue
  check-ins.

## Status Semantics

- `Planned` - The quest is expected for that date but has not been resolved yet.
- `Completed` - The user completed the quest on that date. XP is awarded once.
- `Skipped` - The user intentionally skipped the quest. No XP is awarded, and it should remain separate from failure.
- `Failed` - The quest was planned but not completed or skipped. No XP is awarded, and it should count as a missed planned action.

## Data Model

The checklist uses `quest_checkins`.

Fields:

- `id`
- `quest_id`
- `checkin_date`
- `status`
- `xp_awarded`
- `completed_at`
- `skipped_at`
- `failed_at`
- `created_at`
- `updated_at`

Constraint:

- Unique constraint on `quest_id + checkin_date`.

Relationships:

- `QuestCheckin.quest_id` references `quests.id`.
- `Quest.checkins` links a quest to its daily check-ins.

Why this table is needed:

- `Quest.status` can only represent one global state.
- A checklist needs one status per quest per day.
- Future recurring habits need one check-in per generated habit date.
- Long-term goal sessions remain separate `Quest` and `QuestCheckin` records
  even when Monthly Checklist groups them into one visual goal row.
- Analytics and XP calculations need stable daily completion records.

## XP Rules

- `Completed` awards XP once.
- `Skipped` gives no XP.
- `Failed` gives no XP.
- Resetting to `Planned` clears timestamps and sets `xp_awarded = 0`.
- XP is stored in `QuestCheckin.xp_awarded` to preserve historical values.
- Completing the same check-in twice must not duplicate XP.

Current behavior:

- First completion sets `xp_awarded` to the parent quest's `xp_reward` if the value is currently `0`.
- Repeating a completion action keeps the stored XP value.
- Skip, Fail, and Reset set XP back to `0`.

## Auto-Fail Helper

The service function exists:

```python
mark_stale_planned_checkins_failed(today, grace_days=3)
```

Recommended default:

```python
grace_days = 3
```

Behavior:

- Find `Planned` check-ins with `checkin_date <= today - grace_days`.
- Mark them `Failed`.
- Set `failed_at`.
- Return the number of updated check-ins.
- Do not alter completed, skipped, or already failed check-ins.

Important:

- This helper is not called automatically from app startup or page load yet.
- A future activation workflow should be designed before enabling it automatically.

## UI Direction

Monthly Checklist lives in Quest Planner.

Current structure:

- Section title: `Monthly Review`.
- Subtitle: `View the planned and completed work for the selected month.`
- Month selector.
- Year selector.
- Status legend.
- Matrix preview:
  - rows are quests, recurring habits, or goals/projects,
  - columns are days of the month,
  - cells show simple status symbols.
- The matrix is read-only. Daily status actions belong to Command Center and
  future-month routine generation belongs to Projects & Routines.

Goal row display:

- One linked session on a date shows the normal `P`, `C`, `S`, or `F` marker.
- Multiple linked sessions with the same status show a count, such as `P2`.
- Mixed statuses show compact counts, such as `C1 F1`.
- These markers are presentation only; no check-ins are merged.

The matrix intentionally avoids a fragile fully editable 31-column widget grid.
It is a compact monthly history and planning view.

## Quest Planner Impact

Planner is the calendar and planning surface.

Current behavior:

- Calendar planning and the New Quest form remain.
- Creating a scheduled quest creates a planned check-in for the scheduled date.
- Selected Day Schedule edits or removes unresolved planned work only.
- Monthly Review remains a read-only month-level history and planning matrix.
- The old Maintenance, Quest Ledger, and Legacy Status Controls UI were removed.
- Calendar events display check-in status for the event date when available.
- Selected Day Schedule displays the check-in status for the selected date.
- Goal-linked sessions are grouped visually into one project row.
- Safe deletion is available from the selected-day plan for unresolved work.
- `Quest.status` is not synchronized from check-in status.

## Command Center Impact

Command Center uses check-ins for operational metrics.

Current behavior:

- Today's Focus uses today's check-ins.
- `Completed Today` counts completed check-ins for today.
- `Planned Today` counts planned check-ins for today.
- `Failed` counts failed check-ins through today.
- `Overdue` means unresolved planned check-ins before today.
- Skipped remains separate from failed.
- Command Center exposes Complete, Skip, Fail, and Reset for today's and
  overdue planned check-ins.

## Habit Analytics Impact

Habit Analytics uses check-ins when any check-ins exist.

Current behavior:

- Weekly XP sums `QuestCheckin.xp_awarded`.
- Completed This Week counts completed check-ins.
- Failed This Week counts failed check-ins.
- Weekly completion rate uses completed / (completed + failed).
- XP trend groups awarded XP by `checkin_date`.
- Status breakdown counts check-in statuses.
- Category breakdown joins check-ins to quests and categories.
- Weekday completion rate uses check-in dates.
- Planned minutes by category uses parent quest `estimated_minutes`.

Legacy quest-based fallback remains only for databases with no check-ins.

## Character Profile Impact

Character Profile uses check-ins when any check-ins exist.

Current behavior:

- Total XP sums `QuestCheckin.xp_awarded`.
- Level and XP to next level use check-in XP.
- Completed Quest Days counts completed check-ins.
- RPG stat XP groups completed check-in XP by parent quest category.
- RPG stat levels and radar chart are derived from stat XP.
- Resetting a completed check-in to planned removes its XP contribution because `xp_awarded` becomes `0`.

Legacy quest-based fallback remains only for databases with no check-ins.

## Implementation Phases

Current phase status:

1. Data model - implemented.
2. Checklist service - implemented.
3. Quest creation integration - implemented.
4. Quest Planner UI - implemented.
5. Command Center metrics - implemented.
6. Habit Analytics metrics - implemented.
7. Character Profile XP/stat calculations - implemented.
8. Docs cleanup - current documentation refresh.

Future phases:

1. Optional auto-fail activation workflow.
2. Production persistence and migration strategy.
3. Authentication and user-specific data.
4. External calendar sync.
5. AI and voice planning extensions.
6. Legacy `Quest.status` cleanup.

## Test Plan

Covered by current tests:

- `quest_checkins` model creation.
- Unique `quest_id + checkin_date` constraint.
- Quest/check-in relationships.
- Planned check-in creation.
- Idempotent `ensure_checkin`.
- Status-dependent Complete, Skip, Fail, and Reset behavior.
- XP idempotency.
- Stale planned failure helper.
- Scheduled quest creation creates planned check-ins.
- Monthly checklist data builder.
- Command Center metrics from check-ins.
- Quest Planner calendar/day status helpers.
- Monthly Checklist unscheduled-date blocking in the service layer.
- Character Profile XP/stat calculations from check-ins.
- Habit Analytics metrics from check-ins.
- Monthly Checklist recurring habit grouping from generated instances.
- Monthly Checklist goal session grouping while preserving separate
  `Quest`/`QuestCheckin` records.

Manual verification focus:

- Create scheduled quest.
- Confirm planned check-in appears in Monthly Checklist.
- Confirm unscheduled dates cannot create check-ins through the service.
- Mark Complete, Skip, Fail, and Reset in Command Center.
- Confirm matrix, calendar, selected day schedule, Command Center, Habit Analytics, and Character Profile reflect the expected check-in data.

## Non-Goals For V1

- No PostgreSQL migration.
- No authentication.
- No Google Calendar sync.
- No AI planning assistant.
- No voice input.
- No fragile 31-column editable widget grid.

# Recurring Habits v1 Design

This document defines the Recurring Habits v1 feature and its intended boundaries.

The app has completed its migration to `QuestCheckin`-based daily tracking. Quest Planner,
Command Center, Character Profile, and Habit Analytics now use `QuestCheckin` records as the
main source of truth for daily status, XP, and progression.

## Status

Recurring Habits v1 is implemented for selected-weekday templates and explicit
creation-month generation from Planner and future-month generation from
Projects & Routines.

Template management is also implemented:

- unused recurring habit templates can be hard-deleted,
- templates with generated history are archived/deactivated instead of
  hard-deleted,
- routine lifecycle controls combine stopping with optional cleanup of future
  unresolved planned days,
- future unresolved planned generated days can be removed safely while
  preserving completed, skipped, failed, and XP-awarded history,
- a single unresolved generated recurring occurrence can be deleted safely,
- templates can be edited without mutating existing generated days.

Still not implemented:

- true `N times per week` auto-scheduling,
- automatic background generation,
- generation from analytics, profile, Command Center, or app startup.

## Product Rule

Recurring habits are templates. They are not completed directly.

The interface calls these templates `routines` and calls their persisted
occurrences `scheduled routine days`; the technical model names remain in this
document for precision.

The implemented flow is:

```text
RecurringHabit template
  -> generated Quest
  -> planned QuestCheckin
  -> completion through Monthly Checklist
```

Generated habit days should appear naturally in the existing check-in workflow:

- Quest Planner calendar
- Selected Day Board
- Monthly Checklist
- Command Center
- Character Profile after completion
- Habit Analytics

Completion, skipping, failing, resetting, XP awards, and RPG stat progress should continue to
use the existing `QuestCheckin` status rules.

## Product Behavior

A recurring habit template describes the reusable plan for a habit.

Template fields:

- habit title
- category
- XP reward derived from estimated/planned minutes
- estimated minutes
- optional planned start/end time
- optional notes/description
- recurrence pattern
- start date
- optional end date
- active/inactive status

The user should manage templates separately from generated quest days. Generated quest days are
normal planned quests with planned check-ins.

Monthly Checklist groups generated recurring quest days into one logical row per recurring
habit template. Dates where the habit was not generated remain neutral/empty, not skipped.

## Supported Recurrence Patterns

Recurring Habits v1 implements selected weekdays first.

Supported v1 presets:

- `Every day` - selected weekdays Monday through Sunday.
- `Weekdays` - selected weekdays Monday through Friday.
- `Custom selected weekdays` - user-selected weekdays.

Weekdays should use Python-compatible weekday numbers:

| Value | Day |
| --- | --- |
| `0` | Monday |
| `1` | Tuesday |
| `2` | Wednesday |
| `3` | Thursday |
| `4` | Friday |
| `5` | Saturday |
| `6` | Sunday |

True `N times per week` recurrence is deferred because it requires either user-selected days or
auto-scheduling logic. For v1, "Gym Workout 4 times per week" should be represented as a custom
selected-weekdays habit such as Monday, Tuesday, Thursday, and Saturday.

## Data Model

Recurring Habits v1 uses two models.

### RecurringHabit

Stores the recurring habit template.

Fields:

| Field | Purpose |
| --- | --- |
| `id` | Primary key. |
| `title` | Habit name shown to the user. |
| `description` | Optional notes. |
| `category_id` | Optional foreign key to `categories.id`. |
| `xp_reward` | Time-based XP value copied to generated quests. |
| `estimated_minutes` | Planned minutes copied to generated quests. |
| `recurrence_type` | Recurrence type, initially `selected_weekdays`. |
| `weekdays` | Serialized weekday list for SQLite v1, preferably a JSON string. |
| `start_date` | First date the habit can generate. |
| `end_date` | Optional final date the habit can generate. |
| `planned_start_time` | Optional start time copied into generated quest datetime windows. |
| `planned_end_time` | Optional end time copied into generated quest datetime windows. |
| `is_active` | Whether the template should generate new quest days. |
| `created_at` | Timestamp set when the template is created. |
| `updated_at` | Timestamp updated when the template changes. |

For SQLite v1, `weekdays` should be stored as a serialized weekday list, preferably a JSON string
such as `[0, 2, 4]`.

### RecurringHabitInstance

Links one generated habit date to the generated quest.

Fields:

| Field | Purpose |
| --- | --- |
| `id` | Primary key. |
| `recurring_habit_id` | Foreign key to `recurring_habits.id`. |
| `scheduled_date` | Date generated from the template. |
| `quest_id` | Foreign key to the generated `quests.id`. |
| `created_at` | Timestamp set when the instance is generated. |

Constraints:

- Unique `recurring_habit_id + scheduled_date`.
- Unique `quest_id`.

The `RecurringHabitInstance` table is the duplicate-prevention and traceability layer. It lets
the app know which generated `Quest` came from which recurring habit and date.

## Generated Records

For each eligible recurring habit date, generation should create:

- one `Quest` row,
- one planned `QuestCheckin` row,
- one `RecurringHabitInstance` row linking the template/date to the generated quest.

The generated `Quest` copies the template's title, description, category, XP
reward, estimated minutes, and optional time window. The generated quest is
scheduled for the generated date.

Generated `QuestCheckin` records start with:

- `status = Planned`
- `xp_awarded = 0`
- `checkin_date = scheduled_date`

Generation must not:

- generate infinite future records,
- create check-ins for every possible day unless the recurrence says that day is planned,
- overwrite existing completed, skipped, or failed check-ins.

## Generation Strategy

Recurring Habits v1 uses explicit month-based generation.

User flow:

1. User selects a month in Projects & Routines.
2. User clicks `Generate routines for <month>`.
3. The system generates planned quest days only inside that month.
4. Inactive habits are skipped.
5. `start_date` and `end_date` are respected.
6. Duplicate generation is prevented by `RecurringHabitInstance`.

The generation service is idempotent. Clicking the generation button multiple times for
the same month should not create duplicate quests or check-ins.

Do not auto-generate recurring records from:

- Command Center,
- Habit Analytics,
- Character Profile,
- app startup.

Those surfaces should only display already-generated `QuestCheckin` records.

## Planner And Management Impact

Planner remains the calendar and creation surface. Projects & Routines owns
template management and future-month generation.

Current UI:

- Use the unified `Add to plan` form for one-time work and recurring routines.
- Create a routine through the unified Add to plan form and automatically
  generate its eligible days for the creation month.
- Keep recurring routine management under `Projects & Routines`.
- Provide a recurring routines table and selected routine management controls.
- Allow template fields to be edited under `Projects & Routines`; changes affect later
  generation only and leave existing generated days unchanged.
- Keep deletion, stopping, optional future-day cleanup, and resuming together
  under one routine lifecycle control.
- Provide the selected-month generation button in `Projects & Routines`.
- Allows unused templates to be deleted after confirmation.
- Archives/deactivates templates with generated history instead of hard-deleting
  them.
- Removes future unresolved planned generated days when the generated check-in is
  still `Planned`, has `xp_awarded = 0`, and has no completed/skipped/failed
  timestamps.
- Removes one selected generated day under the same unresolved `Planned`
  safety rule.
- Show generated habits in calendar, day schedule, and Monthly Checklist as normal planned quest days.

The routine-management view should stay compact and practical for the MVP. It should avoid
advanced scheduling, drag-and-drop recurrence editing, streak dashboards, or automatic day
selection in v1.

## Archive, Delete, And Future Cleanup

Deletion is intentionally conservative.

- If a template has no `RecurringHabitInstance` rows, it can be hard-deleted.
- If a template has generated history, it is archived/deactivated by setting
  `is_active = False`; existing generated quests, check-ins, and instances stay
  in place.
- Archived/inactive templates do not generate new planned days.
- Future generated planned days can be removed only when their scheduled
  `QuestCheckin` is still `Planned`, has `xp_awarded = 0`, and has no
  completed/skipped/failed timestamp.
- A single generated recurring occurrence can be removed by deleting its
  generated `QuestCheckin`, `RecurringHabitInstance`, and generated `Quest` when
  that occurrence is still unresolved `Planned` history.
- Completed, skipped, failed, past historical records, and any check-in with
  awarded XP are preserved.
- If a generated row is ambiguous, the cleanup keeps it.

## Monthly Checklist Impact

Monthly Checklist should not calculate recurrence itself.

It displays persisted generated `QuestCheckin` records exactly like other planned quest
days, grouped into one logical row per recurring habit template. Empty days should remain blank.
Generated recurring habit days use the same Command Center status actions as
other planned work.

Monthly Checklist should preserve existing completed, skipped, failed, and planned check-ins.
It should not create a new check-in when the selected recurring habit is not scheduled for the
selected date.

## Command Center Impact

Command Center should not generate recurring habits.

It should only display already-generated check-ins:

- generated planned check-ins for today appear in Planned Today,
- generated completed check-ins for today appear in Completed Today,
- generated failed check-ins appear in Failed,
- generated unresolved past planned check-ins appear in Overdue,
- generated check-ins for today appear in Today's Focus.

## Habit Analytics Impact

Habit Analytics should continue using `QuestCheckin` records.

Recurring habit completions naturally affect:

- weekly pulse,
- XP trends,
- check-ins by category,
- completion rate by weekday,
- planned minutes by category,
- insights.

Recurring-habit-specific charts, streaks, and adherence reports are out of scope for v1.

## Character Profile Impact

Character Profile continues using `QuestCheckin.xp_awarded`.

Completed generated habit check-ins should award XP and RPG stat progress like normal quest
check-ins. Skipped, failed, and planned generated check-ins should award no XP.

## Auto-Fail Interaction

Recurring habit check-ins should follow the existing check-in rules.

The stale planned failure helper remains available:

```python
mark_stale_planned_checkins_failed(today, grace_days=3)
```

Recommended default:

```python
grace_days = 3
```

Recurring Habits v1 should not automatically enable stale planned failure from app startup or
page load. A future activation workflow should be designed before automatic failure is enabled.

## Implementation Phases

Implemented small commits:

1. `docs: add recurring habits design`
2. `feat: add recurring habit models`
3. `feat: add recurring habit service`
4. `feat: generate recurring habit instances for month`
5. `feat: add recurring habits UI`
6. `feat: add recurring habit archive/delete workflow`
7. `test/docs cleanup`

## Test Plan

Covered by focused pytest coverage for:

- creating a recurring habit template,
- selected weekdays generation,
- every day preset,
- weekdays preset,
- start date boundary,
- end date boundary,
- inactive habits do not generate,
- no duplicate generated quests/check-ins,
- generated quest fields,
- generated check-in starts as `Planned`,
- generated rows appear in Monthly Checklist,
- generated today rows appear in Command Center after generation,
- completed generated check-ins award XP once,
- Character Profile includes generated check-in XP,
- Habit Analytics includes generated check-ins.
- unused recurring habits can be deleted,
- recurring habits with generated history are archived instead of hard-deleted,
- future unresolved planned generated days can be removed,
- single unresolved generated recurring occurrences can be removed,
- completed, skipped, failed, and XP-awarded history is preserved,
- archived/inactive recurring habits do not generate new planned days.
- template updates affect only future generation and preserve generated quests,
  check-ins, and instances.

## Risks And Decisions

Key risks:

- accidentally generating infinite future records,
- creating duplicate generated quest/check-in records,
- allowing template edits to mutate completed historical check-ins,
- breaking compatibility between one-time quests and generated recurring habit quests,
- adding ambiguous `times_per_week` behavior too early.

Decisions for v1:

- Use explicit month-based generation only.
- Use `RecurringHabitInstance` to prevent duplicate generated records.
- Generate normal `Quest` and `QuestCheckin` rows so existing app surfaces keep working.
- Do not mutate completed, skipped, or failed historical check-ins from template edits.
- Keep one-time quests and recurring habits compatible but conceptually separate.
- Defer true `times_per_week` auto-scheduling.

## Non-Goals For V1

- No automatic background generation.
- No generation from analytics, profile, Command Center, or app startup.
- No true `N times per week` auto-scheduling.
- No external calendar sync.
- No authentication or multi-user scheduling.
- No machine learning or AI planning.
- No production database migration framework.

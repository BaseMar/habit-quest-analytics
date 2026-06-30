# Monthly Habit Checklist v1 Design

This document describes a future design for replacing the temporary Quest Planner status dropdown with a checklist-based daily completion system.

Status: planned design only. This feature is not implemented.

## Goal

Monthly Habit Checklist v1 should make daily completion feel like a planner workflow instead of a manual status maintenance task.

Target flow:

- Plan quests in Quest Planner.
- Review a selected month.
- Mark whether a planned quest or habit was completed, skipped, or failed on a specific day.
- Award XP once for completed daily check-ins.
- Feed check-in data into Command Center, Habit Analytics, and Character Profile.

## Product Behavior

The checklist should track completion per quest per day. Completion status should not be stored only in `Quest.status`, because one quest can eventually have many daily results.

Core behavior:

- User selects a month.
- Rows represent planned quests or habits.
- Columns represent days of the selected month.
- Each cell represents one quest on one date.
- User can mark a cell as `Completed`, `Skipped`, or `Failed`.
- Unresolved cells remain `Planned`.
- Completed check-ins award XP once.
- Skipped and failed check-ins award no XP.
- A planned check-in can automatically become failed after a short grace period.

Recommended auto-fail default:

```python
grace_days = 3
```

The auto-fail rule should use 3 days as the default grace period. For example, a planned check-in older than `today - 3 days` can become `Failed` if it is still unresolved.

## Status Semantics

- `Planned` - The quest is expected for that date but has not been resolved yet.
- `Completed` - The user completed the quest on that date. XP is awarded once.
- `Skipped` - The user intentionally skipped the quest. No XP is awarded, and it should be treated separately from failure.
- `Failed` - The quest was planned but not completed or skipped. No XP is awarded, and it should count as a missed planned action.

## Future Data Model Concept

Add a future table concept named `quest_checkins`.

Proposed `QuestCheckin` fields:

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

Constraints:

- Unique constraint on `quest_id + checkin_date`.

Recommended relationships:

- `QuestCheckin.quest_id` references `quests.id`.
- `Quest.checkins` links a quest to its daily check-ins.

Why this table is needed:

- `Quest.status` can only represent one global state.
- A checklist needs one status per quest per day.
- Future recurring habits will need one check-in per generated habit date.
- Analytics and XP calculations need stable daily completion records.

## XP Rules

- `Completed` awards XP once.
- `Skipped` gives no XP.
- `Failed` gives no XP.
- XP should be stored in `xp_awarded` to preserve historical values.
- Completing the same check-in twice must not duplicate XP.

Recommended behavior:

- When a check-in first changes to `Completed`, set `xp_awarded` to the quest XP reward.
- If a completed check-in is completed again, leave `xp_awarded` unchanged.
- If future UI allows changing `Completed` back to another status, the product must explicitly decide whether XP is revoked. V1 can avoid this complexity by limiting reversal actions or requiring confirmation.

## UI Direction

Monthly Checklist should live in Quest Planner and replace the temporary status controls.

Recommended layout:

- Section title: `Monthly Checklist`
- Month selector.
- Compact status legend.
- Matrix preview:
  - rows are quests or habits,
  - columns are days of the month,
  - cells use simple status symbols and colors.
- Selected quest/date action controls:
  - choose quest,
  - choose date,
  - mark `Completed`, `Skipped`, `Failed`, or reset to `Planned`.

V1 should avoid a fragile 31-column interactive widget grid. A matrix preview plus selected quest/date controls is simpler, easier to test, and more reliable in Streamlit.

## Quest Planner Impact

Quest Planner remains the planning surface.

Expected changes:

- Keep calendar planning and the New Quest form.
- Remove `Temporary Status Controls`.
- Add `Monthly Checklist`.
- Creating a scheduled quest should create or lazily ensure a planned check-in for the planned date.
- Selected Day Board can show check-in status when available.
- Day Schedule can eventually include quick actions for today's check-ins.

Compatibility:

- Existing quests with `due_date` can create check-ins lazily when the checklist loads.
- One-time scheduled quests should normally have one check-in for their planned date.
- Recurring habits are not required for v1, but this design leaves room for them later.

## Command Center Impact

Command Center should eventually use check-ins for operational metrics.

Expected changes:

- Today's focus should use today's check-ins.
- `Completed Today` should count completed check-ins.
- `Failed` should count failed check-ins.
- `Overdue` should mean unresolved planned check-ins before today.
- Auto-failed check-ins after `grace_days = 3` should appear as failed, not overdue.
- Skipped should remain separate from failed.

During transition, Command Center can use legacy quest status as a fallback when no check-ins exist.

## Habit Analytics Impact

Habit Analytics should eventually use check-ins as the source of truth for completion behavior.

Expected changes:

- XP trend should use completed check-ins and `xp_awarded`.
- Status breakdown should count check-in statuses.
- Weekday completion rate should use check-in dates.
- Category analytics should join check-ins to quests and categories.
- Skipped should be handled separately from failed so intentional skips do not distort failure analysis.

During transition, analytics can keep legacy quest-based fallback behavior until check-in data is available.

## Character Profile Impact

Character Profile XP and RPG stats should eventually come from completed check-ins.

Expected changes:

- Total XP should sum `xp_awarded` from completed check-ins.
- Level should use check-in XP totals.
- RPG stat XP should group completed check-in XP by the parent quest category.
- Repeated completions of the same future habit on different days should each be able to award XP once.

Labeling may need refinement later. For example, `Completed Quests` may become `Completed Check-ins` or `Completed Quest Days` once repeated habit completion exists.

## Implementation Phases

Recommended commit breakdown:

1. Data model
   - Add `QuestCheckin` model.
   - Add SQLite table creation or migration support.
   - Add relationship from quests to check-ins.

2. Checklist service
   - Add check-in creation and lookup helpers.
   - Add status transition functions.
   - Add XP award idempotency.
   - Add `grace_days = 3` auto-fail service logic.

3. Quest creation integration
   - Create or lazily ensure planned check-ins for scheduled quests.
   - Preserve current scheduled quest behavior.

4. Quest Planner UI
   - Replace temporary status controls with Monthly Checklist.
   - Render matrix preview.
   - Add selected quest/date action controls.

5. Command Center metrics
   - Use check-ins for today, completed, failed, skipped, and overdue operational counts.
   - Keep legacy fallback if needed during migration.

6. Habit Analytics metrics
   - Use check-ins for XP trend, status breakdown, weekday completion, and category analysis.

7. Character Profile XP/stat calculations
   - Use completed check-ins and `xp_awarded` for XP, level, and RPG stat growth.

8. Docs cleanup
   - Update README and planning docs after implementation.
   - Document final status and XP rules.

## Test Plan

Data model:

- Creates `quest_checkins`.
- Enforces unique `quest_id + checkin_date`.
- Loads quest and category relationships.

Checklist service:

- Creates planned check-in.
- Completing a check-in sets `Completed`, `completed_at`, and `xp_awarded`.
- Completing twice does not duplicate XP.
- Skipping sets `Skipped` and no XP.
- Failing sets `Failed` and no XP.
- Auto-fail changes only old unresolved `Planned` check-ins.
- Completed and skipped check-ins are not auto-failed.

Quest Planner:

- Scheduled quest appears in the monthly checklist.
- Existing scheduled quest can produce a planned check-in.
- Status actions update the correct quest/date cell.
- Temporary status controls are removed.

Command Center:

- Today's focus reflects check-in status.
- Completed Today uses completed check-ins.
- Failed and skipped are counted separately.
- Overdue uses unresolved past check-ins.

Habit Analytics:

- XP trend uses completed check-ins.
- Status breakdown uses check-in statuses.
- Weekday completion rate uses check-in dates.
- Empty states still work.

Character Profile:

- Total XP sums completed check-in `xp_awarded`.
- Level uses check-in XP.
- RPG stats group check-in XP by quest category.
- Repeated completions on different dates can each award XP once.

## Non-Goals For V1

- No recurring habit engine.
- No PostgreSQL migration.
- No authentication.
- No Google Calendar sync.
- No AI planning assistant.
- No voice input.
- No fragile 31-column widget grid as the first implementation.

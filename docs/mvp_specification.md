# MVP Specification

The MVP proves the core loop: plan quests, track daily completion, earn XP, level up, and review productivity patterns.

## MVP Scope

The current usable version includes:

- calendar-based scheduled quest creation,
- daily quest completion through Monthly Checklist check-ins,
- recurring habit templates with explicit planned-day generation,
- categories for organizing work,
- time-based XP for new scheduled quests and recurring habit templates,
- XP rewards stored per completed check-in,
- player profile with XP, nonlinear level, avatar, and RPG stat levels,
- Command Center operational KPIs,
- Habit Analytics trends and consistency metrics,
- local SQLite persistence,
- pytest coverage for business rules.

## User Stories

- As a user, I want to schedule a quest so I can plan a task or habit for a specific day.
- As a user, I want to mark a planned quest day as completed, skipped, failed, or planned.
- As a user, I want completed quest days to award XP only once.
- As a user, I want recurring habits to generate planned quest days for selected weekdays.
- As a user, I want to review today's planned and resolved quest check-ins.
- As a user, I want to see my level and RPG stats grow from completed activity.
- As a user, I want analytics that show trends, categories, consistency, and planned workload.

## App Sections

- `Home Base` - onboarding, quick start, app map, and local-first MVP note.
- `Command Center` - read-only operational overview using daily check-ins.
- `Quest Planner` - calendar planner, selected day schedule, new quest form, Recurring Habits, and Monthly Checklist.
- `Habit Analytics` - weekly pulse, XP trend, check-in breakdowns, consistency, planned minutes, and insights.
- `Character Profile` - avatar, XP, level, completed quest days, RPG stats, radar chart, and achievements placeholder.

## Implementation Phases

### Phase 1: Scaffold

Status: implemented.

- Create project structure.
- Add Streamlit pages.
- Add SQLAlchemy models.
- Add SQLite initialization.
- Add default category seeding.
- Add XP and level formulas.
- Add initial tests.

### Phase 2: Quest Planning

Status: implemented for scheduled one-time quests and recurring habit templates.

- Create scheduled quests from Quest Planner.
- Store title, notes, category, planned date, planned start/end times, estimated minutes, and XP reward.
- Validate that end time is after start time.
- Display quests on the calendar and selected day schedule.
- Create recurring habit templates for selected weekdays.
- Generate recurring habit planned days for a selected month.
- Archive/deactivate recurring habit templates with generated history.
- Delete unused recurring habit templates.
- Delete unresolved one-time planned quests while preserving historical or
  XP-awarded records.
- Delete a single unresolved generated recurring occurrence while preserving
  historical or XP-awarded records.
- Remove future unresolved planned generated days while preserving completed,
  skipped, failed, and XP-awarded history.

Still planned:

- quest editing,
- one-time quest archive/soft-delete workflow for historical records,
- recurring habit editing beyond active/archive/delete controls.

### Phase 3: Monthly Checklist

Status: implemented v1.

- Add `QuestCheckin` model with unique `quest_id + checkin_date`.
- Create planned check-ins for scheduled quests.
- Build monthly checklist data with rows as quests and columns as days.
- Render a compact matrix preview in Quest Planner.
- Allow Complete, Skip, Fail, and Reset actions for a selected quest/date.
- Block status updates for unscheduled/blank cells so the Monthly Checklist
  cannot create check-ins for dates where the quest is not scheduled/generated.
- Keep XP idempotent with `QuestCheckin.xp_awarded`.

Not implemented:

- fully editable 31-column widget grid,
- automatic app-level stale planned failure.

### Phase 4: Command Center Metrics

Status: implemented with check-ins.

- Planned Today counts planned check-ins for today.
- Completed Today counts completed check-ins for today.
- Overdue counts planned check-ins before today.
- Failed counts failed check-ins through today.
- Today's Focus reads parent quest metadata and `QuestCheckin.status`.
- Command Center remains read-only.

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

Legacy quest-based fallback remains only for databases with no check-ins.

### Phase 6: Character Profile

Status: implemented with check-ins when available.

- Total XP from `QuestCheckin.xp_awarded`.
- Level and XP-to-next-level from check-in XP.
- Completed Quest Days from completed check-ins.
- RPG stat XP from completed check-ins joined to quest categories.
- RPG stat levels and radar chart from stat levels.
- Local avatar upload path stored on the player profile.

Legacy quest-based fallback remains only for databases with no check-ins.

## Future Features Outside MVP

- Long-term Goals / Projects.
- Recurring habit editing and true N-times-per-week scheduling.
- PostgreSQL / production persistence.
- Authentication and user-specific data isolation.
- Google Calendar sync.
- AI planning assistant.
- Voice quest capture.
- Streak system / bonus XP.
- Achievement unlock rules.
- Date filters and richer analytics comparisons.
- Data export/import.

## MVP Success Criteria

- A user can schedule quests locally.
- Scheduled quests create planned check-ins.
- A user can resolve daily check-ins as completed, skipped, failed, or planned.
- A user cannot resolve a quest on an unscheduled Monthly Checklist date.
- A user can safely remove unresolved planned records without deleting
  completed, skipped, failed, or XP-awarded history.
- Completed check-ins award XP once.
- Command Center, Habit Analytics, and Character Profile use check-ins when available.
- Quest records and check-ins persist in SQLite.
- Core formulas and service behavior remain covered by tests.

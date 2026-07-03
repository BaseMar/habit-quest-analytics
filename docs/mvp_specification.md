# MVP Specification

The MVP proves the core loop: plan quests, track daily completion, earn XP, level up, and review productivity patterns.

## MVP Scope

The current usable version includes:

- calendar-based scheduled quest creation,
- daily quest completion through Monthly Checklist check-ins,
- categories for organizing work,
- difficulty levels: Easy, Medium, Hard, Boss,
- XP rewards stored per completed check-in,
- player profile with XP, level, avatar, and RPG stats,
- Command Center operational KPIs,
- Habit Analytics trends and consistency metrics,
- local SQLite persistence,
- pytest coverage for business rules.

## User Stories

- As a user, I want to schedule a quest so I can plan a task or habit for a specific day.
- As a user, I want to set quest difficulty so harder work gives more XP.
- As a user, I want to mark a planned quest day as completed, skipped, failed, or planned.
- As a user, I want completed quest days to award XP only once.
- As a user, I want to review today's planned and resolved quest check-ins.
- As a user, I want to see my level and RPG stats grow from completed activity.
- As a user, I want analytics that show trends, categories, consistency, and planned workload.

## App Sections

- `Home Base` - onboarding, quick start, app map, and local-first MVP note.
- `Command Center` - read-only operational overview using daily check-ins.
- `Quest Planner` - calendar planner, selected day schedule, new quest form, and Monthly Checklist.
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

Status: implemented for scheduled one-time quests.

- Create scheduled quests from Quest Planner.
- Store title, notes, category, difficulty, planned date, planned start/end times, estimated minutes, and XP reward.
- Validate that end time is after start time.
- Display quests on the calendar and selected day schedule.

Still planned:

- quest editing,
- delete/archive workflow,
- recurring habits.

### Phase 3: Monthly Checklist

Status: implemented v1.

- Add `QuestCheckin` model with unique `quest_id + checkin_date`.
- Create planned check-ins for scheduled quests.
- Build monthly checklist data with rows as quests and columns as days.
- Render a compact matrix preview in Quest Planner.
- Allow Complete, Skip, Fail, and Reset actions for a selected quest/date.
- Keep XP idempotent with `QuestCheckin.xp_awarded`.

Not implemented:

- recurring habit generation,
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
- Radar chart from RPG stat XP.
- Local avatar upload path stored on the player profile.

Legacy quest-based fallback remains only for databases with no check-ins.

## Future Features Outside MVP

- Recurring habits and templates.
- PostgreSQL / production persistence.
- Authentication and user-specific data isolation.
- Google Calendar sync.
- AI planning assistant.
- Voice quest capture.
- Achievement unlock rules.
- Date filters and richer analytics comparisons.
- Data export/import.

## MVP Success Criteria

- A user can schedule quests locally.
- Scheduled quests create planned check-ins.
- A user can resolve daily check-ins as completed, skipped, failed, or planned.
- Completed check-ins award XP once.
- Command Center, Habit Analytics, and Character Profile use check-ins when available.
- Quest records and check-ins persist in SQLite.
- Core formulas and service behavior remain covered by tests.

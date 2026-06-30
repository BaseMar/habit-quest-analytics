# Temporary Feature Ideas Backlog

This file stores proposed future features for Habit Quest Analytics, sorted from highest to lowest implementation priority.

Rule: do not implement any item from this list without explicit user confirmation. Before implementation, discuss scope, priority, data model impact, UI impact, and tests.

## Priority 1. Professional UX / Visual Design Upgrade

What it adds:

- Improve the interface with a more polished visual system: consistent spacing, typography, colors, section hierarchy, chart layout, forms, and empty states.

Why it matters:

- The current app is functional, but a portfolio-ready project should look intentional and consistent.
- Better UX makes the RPG/productivity concept easier to understand and more pleasant to use.

Positive value:

- Makes the project stronger as a portfolio piece.
- Improves first impression for recruiters, users, or reviewers.
- Reduces friction in daily use across every existing screen.

Implementation note:

- This should stay practical and app-like, not become a marketing landing page.
- Improve existing screens before adding new ones.

## Priority 2. Quest Status Flow

What it adds:

- Clear product rules for quest statuses:
  - Planned: scheduled but not yet historically evaluated.
  - Completed: finished and grants XP.
  - Failed: not completed despite being planned and grants no XP.
  - Skipped: consciously skipped, grants no XP, and may be excluded from selected metrics.

Why it matters:

- Status rules affect XP, dashboard KPIs, analytics charts, weekly reviews, and user trust.
- Planned quests should not distort historical performance before their date has passed.

Positive value:

- Makes analytics more accurate.
- Prevents unclear interpretation of failed vs skipped work.
- Creates a stronger product foundation before adding more metrics.

Implementation note:

- This is partly product design and partly code.
- Start by documenting rules, then align KPI and analytics calculations.

## Priority 3. Quest Editing

What it adds:

- Ability to edit an existing quest title, notes, category, difficulty, planned date, and estimated minutes.

Why it matters:

- Users often create tasks quickly and refine them later.
- It makes the Quest Log feel practical instead of one-shot.
- It reduces the need for delete/recreate workflows.

Positive value:

- Improves usability and trust in persisted data.
- Makes the app more realistic as a daily productivity tool.

## Priority 4. Quest Archive / Soft Delete

What it adds:

- Ability to hide quests from active views without permanently deleting records.

Why it matters:

- Users need cleanup, but analytics should not lose historical context.
- Soft delete avoids accidental data loss.

Positive value:

- Keeps the UI clean while preserving analytics integrity.
- Supports better long-term tracking.

## Priority 5. Today View / Daily Command Center

What it adds:

- A daily operational section showing:
  - today's quests,
  - quick status updates for Completed, Failed, and Skipped,
  - XP available today,
  - daily progress,
  - daily completion rate.

Why it matters:

- A habit app is not only for analyzing history. Users need a daily answer to: what should I do today?
- This makes the app useful as a daily workflow tool, not just an analytics dashboard.

Positive value:

- Increases real-world daily usefulness.
- Makes the app feel actionable immediately after opening.
- Connects planning, execution, XP, and analytics in one flow.

Implementation note:

- This can live at the top of Dashboard or become a separate page later.
- Keep the first version simple and based on existing quest dates/statuses.

## Priority 6. Date Filters for Dashboard and Analytics

What it adds:

- Filter views by date range such as this week, this month, last 30 days, or custom range.

Why it matters:

- As quest history grows, all-time views become less useful.
- Filters make existing KPI cards and charts more actionable.

Positive value:

- Makes analytics more useful without changing the core quest model.
- Helps compare recent behavior against long-term trends.

## Priority 7. Recurring Quests / Habit Templates

What it adds:

- Reusable quests for repeated habits such as workouts, reading, sleep, or weekly planning.

Why it matters:

- Habit tracking depends on repetition.
- Manually recreating the same quest every day is friction.

Positive value:

- Makes the product more useful for daily habit loops.
- Increases retention because recurring behavior becomes easier to track.

## Priority 8. Streak Tracking

What it adds:

- Current streak and best streak for completed habit quests.

Why it matters:

- Streaks are a simple motivation mechanic.
- They fit the RPG progression theme without adding heavy complexity.

Positive value:

- Makes consistency visible.
- Adds emotional reward beyond raw XP.

Dependency note:

- More valuable after recurring quests or clearer habit tracking exists.

## Priority 9. Weekly Review

What it adds:

- A weekly review page or section showing:
  - planned quests,
  - completed quests,
  - completion rate,
  - XP earned,
  - strongest category,
  - neglected category,
  - largest time estimation gap,
  - simple rule-based recommendation for next week.

Why it matters:

- It turns raw analytics into a useful productivity review.
- It gives the app a strong data analyst / productivity angle without machine learning.

Positive value:

- Makes the project more impressive as a portfolio piece.
- Helps users reflect and improve weekly planning.
- Creates a clear narrative from quest data.

Implementation note:

- Do not use ML for this.
- Use simple deterministic rules.
- Best implemented after status rules, date filters, and enough weekly data are stable.

## Priority 10. Achievement Rules

What it adds:

- Basic unlock rules such as first quest completed, 500 XP reached, first Boss quest completed, or seven completed habit days.

Why it matters:

- Achievement models already exist, but unlocking is not implemented yet.

Positive value:

- Gives users milestone feedback.
- Makes progression feel more complete.

## Priority 11. XP Progress Timeline

What it adds:

- Timeline chart showing accumulated XP over time.

Why it matters:

- XP by day shows activity spikes, but cumulative XP shows long-term growth.

Positive value:

- Makes progress easier to understand at a glance.
- Reinforces the level-up mechanic.

## Priority 12. Category Balance View

What it adds:

- A simple view showing whether XP and completed quests are balanced across categories.

Why it matters:

- Users may over-focus on Work while neglecting Health, Learning, or Recovery.

Positive value:

- Turns the app from a task list into a personal balance dashboard.
- Helps users notice neglected areas earlier.

## Priority 13. Production Database

What it adds:

- Replace or complement the local SQLite database with a production-ready database such as PostgreSQL.

Why it matters:

- SQLite is good for local MVP work, but it is not ideal for multi-device usage, hosted deployments, backups, or concurrent users.
- A real hosted database would make the app more reliable outside local development.

Positive value:

- Makes the project more deployment-ready.
- Improves persistence on Streamlit Cloud or other hosted environments.
- Opens the path for future multi-user support if explicitly requested later.

Implementation note:

- This should be planned carefully because it affects configuration, migrations, deployment, secrets, and possibly tests.
- Do not implement without confirming the target provider and migration strategy.

## Priority 14. Data Export

What it adds:

- Export quests and analytics source data to CSV.

Why it matters:

- Local-first tools should make user data portable.

Positive value:

- Builds trust.
- Allows further personal analysis outside the app.

## Priority 15. Planned vs Actual Time

What it adds:

- Ability to compare estimated minutes with actual time spent.

Why it matters:

- The app already stores estimated minutes, but not actual minutes.
- This would help users improve planning accuracy.

Positive value:

- Adds productivity insight beyond completion.
- Helps users understand whether they underestimate tasks.

## Priority 16. Quest Priority

What it adds:

- Separate quest importance from quest difficulty:
  - Difficulty: how much effort a quest costs.
  - Priority: how important the quest is.

Possible values:

- Low
- Medium
- High

Why it matters:

- Difficulty and importance are different concepts.
- A short walk can be Easy but High priority; a large refactor can be Hard but Medium priority.

Positive value:

- Improves planning quality.
- Enables future analytics around high-priority completion.

Implementation note:

- This requires a model change and UI updates.
- Do not implement too early; first stabilize editing, status flow, and daily usage.

## Priority 17. Quest Difficulty Review

What it adds:

- Small analytics section showing how many Easy, Medium, Hard, and Boss quests are completed.

Why it matters:

- Users may complete many low-effort quests but avoid harder ones.

Positive value:

- Helps evaluate challenge balance.
- Supports better XP tuning later.

## Priority 18. Character Profile Customization

What it adds:

- Editable character name and possibly a small class/title selector.

Why it matters:

- Personalization strengthens the RPG theme.
- Users are more likely to engage with a character they can name.

Positive value:

- Improves emotional connection to the dashboard.
- Adds polish without changing the analytics engine.

## Priority 19. Optional Design Patterns

What it adds:

- Introduce lightweight design patterns where they solve real duplication or complexity, such as repository-style database access, service objects, or small view helper modules.

Why it matters:

- As the app grows, repeated session handling, query logic, and dataframe preparation can become harder to maintain.
- Patterns can improve consistency if added carefully.

Positive value:

- Better maintainability.
- Cleaner separation between UI, services, persistence, and metrics.
- Easier testing as business logic grows.

Implementation note:

- This is optional and should not be over-engineered.
- Do not add patterns just for architecture aesthetics.
- Introduce a pattern only when there is clear duplication or complexity to reduce.

## Advanced Future Extensions

These are later roadmap ideas. They should not be implemented until the core planner, habit flow, persistence strategy, and MVP analytics are stable.

### Google Calendar Integration

What it adds:

- Sync scheduled quests with Google Calendar.
- Allow planned habits and tasks to appear alongside real calendar events.

Implementation note:

- This is future work and is not currently implemented.
- It introduces an external API dependency, account permissions, token handling, and calendar conflict questions.

### User Authentication

What it adds:

- Login support so each user has separate quests, calendar, character profile, and analytics.

Implementation note:

- This is future work and is not currently implemented.
- It would likely require a production database, user-specific data model changes, and careful migration planning.

### AI Planning Assistant

What it adds:

- An LLM-powered assistant that understands natural language planning requests.
- Example: a user writes "Schedule gym tomorrow from 9 to 11" and the assistant creates a scheduled quest.

Implementation note:

- This is future work and is not currently implemented.
- It should come after the planner rules, status flow, and persistence model are stable.

### Voice Quest Capture

What it adds:

- Microphone or voice input so users can speak tasks or habit plans.
- The assistant could convert spoken requests into scheduled quests.

Implementation note:

- This is future work and is not currently implemented.
- It depends on the future AI planning assistant and should come after the core planner is stable.

### Suggested Implementation Order

1. Monthly habit checklist
2. Recurring habits
3. PostgreSQL / production persistence
4. Authentication
5. Google Calendar sync
6. AI planning assistant
7. Voice input

## Deferred Ideas

These are intentionally not near-term MVP items:

- Authentication.
- External API integrations.
- Cloud sync.
- Machine learning predictions.
- Google Calendar sync.
- AI planning assistant.
- Voice input.
- Social or multiplayer features.

They may be useful later, but only after the local MVP is stable.

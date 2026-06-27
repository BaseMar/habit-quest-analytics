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

## Priority 2. Quest Editing

What it adds:

- Ability to edit an existing quest title, notes, category, difficulty, planned date, and estimated minutes.

Why it matters:

- Users often create tasks quickly and refine them later.
- It makes the Quest Log feel practical instead of one-shot.
- It reduces the need for delete/recreate workflows.

Positive value:

- Improves usability and trust in persisted data.
- Makes the app more realistic as a daily productivity tool.

## Priority 3. Quest Archive / Soft Delete

What it adds:

- Ability to hide quests from active views without permanently deleting records.

Why it matters:

- Users need cleanup, but analytics should not lose historical context.
- Soft delete avoids accidental data loss.

Positive value:

- Keeps the UI clean while preserving analytics integrity.
- Supports better long-term tracking.

## Priority 4. Date Filters for Dashboard and Analytics

What it adds:

- Filter views by date range such as this week, this month, last 30 days, or custom range.

Why it matters:

- As quest history grows, all-time views become less useful.
- Filters make existing KPI cards and charts more actionable.

Positive value:

- Makes analytics more useful without changing the core quest model.
- Helps compare recent behavior against long-term trends.

## Priority 5. Recurring Quests / Habit Templates

What it adds:

- Reusable quests for repeated habits such as workouts, reading, sleep, or weekly planning.

Why it matters:

- Habit tracking depends on repetition.
- Manually recreating the same quest every day is friction.

Positive value:

- Makes the product more useful for daily habit loops.
- Increases retention because recurring behavior becomes easier to track.

## Priority 6. Streak Tracking

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

## Priority 7. Achievement Rules

What it adds:

- Basic unlock rules such as first quest completed, 500 XP reached, first Boss quest completed, or seven completed habit days.

Why it matters:

- Achievement models already exist, but unlocking is not implemented yet.

Positive value:

- Gives users milestone feedback.
- Makes progression feel more complete.

## Priority 8. XP Progress Timeline

What it adds:

- Timeline chart showing accumulated XP over time.

Why it matters:

- XP by day shows activity spikes, but cumulative XP shows long-term growth.

Positive value:

- Makes progress easier to understand at a glance.
- Reinforces the level-up mechanic.

## Priority 9. Category Balance View

What it adds:

- A simple view showing whether XP and completed quests are balanced across categories.

Why it matters:

- Users may over-focus on Work while neglecting Health, Learning, or Recovery.

Positive value:

- Turns the app from a task list into a personal balance dashboard.
- Helps users notice neglected areas earlier.

## Priority 10. Production Database

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

## Priority 11. Data Export

What it adds:

- Export quests and analytics source data to CSV.

Why it matters:

- Local-first tools should make user data portable.

Positive value:

- Builds trust.
- Allows further personal analysis outside the app.

## Priority 12. Planned vs Actual Time

What it adds:

- Ability to compare estimated minutes with actual time spent.

Why it matters:

- The app already stores estimated minutes, but not actual minutes.
- This would help users improve planning accuracy.

Positive value:

- Adds productivity insight beyond completion.
- Helps users understand whether they underestimate tasks.

## Priority 13. Quest Difficulty Review

What it adds:

- Small analytics section showing how many Easy, Medium, Hard, and Boss quests are completed.

Why it matters:

- Users may complete many low-effort quests but avoid harder ones.

Positive value:

- Helps evaluate challenge balance.
- Supports better XP tuning later.

## Priority 14. Character Profile Customization

What it adds:

- Editable character name and possibly a small class/title selector.

Why it matters:

- Personalization strengthens the RPG theme.
- Users are more likely to engage with a character they can name.

Positive value:

- Improves emotional connection to the dashboard.
- Adds polish without changing the analytics engine.

## Priority 15. Optional Design Patterns

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

## Deferred Ideas

These are intentionally not near-term MVP items:

- Authentication.
- External API integrations.
- Cloud sync.
- Machine learning predictions.
- Social or multiplayer features.

They may be useful later, but only after the local MVP is stable.

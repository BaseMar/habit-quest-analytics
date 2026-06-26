# MVP Specification

The MVP should prove the core loop: create quests, complete quests, earn XP, level up, and review basic productivity patterns.

## MVP Scope

The first usable version should include:

- quest creation and editing,
- quest completion with XP rewards,
- categories for organizing work,
- difficulty levels: Easy, Medium, Hard, Boss,
- player profile with total XP and level,
- basic dashboard KPIs,
- simple habit consistency metrics,
- local SQLite persistence,
- tests for business rules.

## User Stories

- As a user, I want to create a quest so that I can track a habit or task.
- As a user, I want to set quest difficulty so that harder work gives more XP.
- As a user, I want to mark a quest complete so that my XP and progress update.
- As a user, I want to view active and completed quests so that I can review my workload.
- As a user, I want to see my level so that long-term progress is visible.
- As a user, I want to review completion rates so that I can understand consistency.
- As a user, I want categories so that I can see which areas of life are balanced or neglected.

## App Sections

- `Dashboard` - summary cards for active quests, completed quests, total XP, level, and consistency.
- `Quest Log` - quest creation, filtering, completion, and history.
- `Habit Analytics` - completion rate, weekly XP, category distribution, and streak-oriented charts.
- `Character Profile` - character name, total XP, level, XP to next level, and achievements.

## Implementation Phases

### Phase 1: Scaffold

Status: implemented.

- Create project structure.
- Add placeholder Streamlit pages.
- Add SQLAlchemy models.
- Add SQLite initialization.
- Add default category seeding.
- Add XP and level formulas.
- Add initial tests.

### Phase 2: Quest Management

Status: partially implemented.

- Add quest creation form.
- Persist quests to SQLite.
- List active and completed quests.
- Mark quests complete.
- Calculate and store XP rewards.

Implemented so far:

- create quests from the Quest Log page,
- store title, description, category, difficulty, planned date, estimated minutes, status, and XP reward,
- list persisted quests,
- update status to Planned, Completed, Failed, or Skipped,
- set `completed_at` when a quest is completed for the first time.

Still planned:

- edit existing quests,
- delete or archive quests,
- habit flag controls,
- player profile XP updates.

### Phase 3: Dashboard Metrics

Status: partially implemented.

- Load quest records into Pandas.
- Add KPI cards for completion, XP, and level progress.
- Add completion rate and weekly XP summaries.
- Add basic category breakdowns.

Implemented so far:

- total quests,
- completed quests,
- completion rate,
- total XP from completed quests,
- weekly XP from quests completed in the current week,
- current level,
- XP to next level.

Still planned:

- category breakdowns,
- trend charts,
- dashboard filtering.

### Phase 4: Character And Achievements

Status: planned.

- Show character profile details.
- Calculate XP to next level.
- Define achievement rules.
- Store and display unlocked achievements.

## Future Features Outside MVP

- Authentication and multi-user support.
- Cloud database deployment.
- External calendar or task integrations.
- Machine learning recommendations.
- Completion probability prediction.
- Advanced recurring quest scheduling.
- Data import and export workflows.

## MVP Success Criteria

- A user can create and complete quests locally.
- XP and level update predictably.
- Quest records persist in SQLite.
- The dashboard summarizes real quest data.
- Core formulas remain covered by tests.

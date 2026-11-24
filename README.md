# Habit Quest Analytics

An RPG-inspired habit planner and analytics dashboard that turns scheduled tasks
into daily quests, awards XP for completed quest days, and shows progress through
operational metrics, trend analysis, and character growth.

![Python](https://img.shields.io/badge/Python-3.11-blue)
![Streamlit](https://img.shields.io/badge/Streamlit-App-ff4b4b)
![Pandas](https://img.shields.io/badge/Pandas-Data%20Analysis-purple)
![Tests](https://img.shields.io/badge/tests-pytest-brightgreen)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Supabase-003B57)
![Plotly](https://img.shields.io/badge/Plotly-Charts-3F4F75)
![Deployment](https://img.shields.io/badge/Deployment-Streamlit%20Cloud-ff4b4b)

## Table of Contents

- [Project Goal](#project-goal)
- [My Role](#my-role)
- [Live Demo](#live-demo)
- [Project Status](#project-status)
- [Preview](#preview)
- [Tech Stack](#tech-stack)
- [What It Does](#what-it-does)
- [Example Insights](#example-insights)
- [Features](#features)
- [App Sections](#app-sections)
- [Key Technical Decisions](#key-technical-decisions)
- [Data Flow](#data-flow)
- [Architecture](#architecture)
- [Data Model](#data-model)
- [Requirements](#requirements)
- [Installation](#installation)
- [Running The App](#running-the-app)
- [Google Sign-In](#google-sign-in)
- [Tests](#tests)
- [Design Principles](#design-principles)
- [Limitations & Future Work](#limitations--future-work)

## Project Goal

Habit apps often track whether tasks were done, but they do not always connect
planning, completion, XP, progression, and analytics in one workflow.

Habit Quest Analytics explores that loop as a portfolio MVP. It lets a user
schedule daily quests, mark each quest day as planned, completed, skipped, or
failed, earn XP from completed check-ins, grow RPG-style stats, and review
behavior through dashboards and charts.

## My Role

I designed and implemented the current MVP, including:

- SQLAlchemy persistence with PostgreSQL and an importer for SQLite backups.
- Streamlit app shell, custom navigation, and dark RPG dashboard UI.
- Quest planning workflow with calendar scheduling.
- Monthly Checklist tracking system backed by daily `QuestCheckin` records.
- Checklist status service with idempotent XP rules.
- Command Center, Habit Analytics, and Character Profile data services.
- Long-term goal/project planning services, including bulk goal session preview
  and generation.
- RPG XP, level, and stat progression logic.
- Pytest coverage for models, services, metrics, and migration behavior.
- Project documentation and roadmap.

## Live Demo

Live app: https://habit-quest-analytics-sai5h3bl7wjykw4fbruabd.streamlit.app

The Streamlit Community Cloud deployment uses PostgreSQL on Supabase. See
[Google Sign-In](#google-sign-in) for configuring the account-enabled version.
Uploaded avatars use local storage and may reset when the Streamlit instance changes.

## Project Status

The MVP is functional and deployed.

In the interface, everyday work is called a **task**, repeated work a
**routine**, and a larger outcome a **project**. RPG terminology remains part of
the product name and progression system, not a requirement for using the planner.

Implemented:

- Command Center as the default operational workspace.
- Custom Streamlit navigation/sidebar with explicit page labels.
- Full-screen loading indicator when opening the workspace or switching pages.
- Calendar-based Planner.
- Monthly Checklist UI for daily quest/checkin tracking.
- Recurring Habit templates with automatic generation for the creation month and
  explicit future-month generation from Projects & Routines.
- Recurring habit template editing, a unified stop/resume lifecycle, unused-template
  deletion, single generated-day deletion, and safe future planned-day cleanup.
- `QuestCheckin` model for per-day completion status.
- Checklist service for `Planned`, `Completed`, `Skipped`, `Failed`, reset
  behavior, XP idempotency, unscheduled-date blocking, and a stale planned
  failure helper.
- Scheduled quest creation that creates a planned check-in for the scheduled
  date.
- Safe deletion for unresolved one-time planned quests.
- Long-term Goals / Projects with a `Goal` model, service layer, one-time
  session linking, and a dedicated workspace for project creation and editing.
- Goal/project creation and linked goal sessions require a category.
- Goal/project planned total time can be left unset when the total effort is not
  known yet.
- The unified Add to plan form can link a one-time work session to an existing
  project, with automatic per-goal session numbering and generated session
  titles.
- The project workspace combines creation, editing, progress, lifecycle
  actions, project comparison, and a Goal Session Planner that previews and
  bulk creates multiple scheduled one-time sessions from remaining unscheduled
  goal effort.
- Goal lifecycle controls in Projects & Routines include archiving, completing,
  reopening, and deleting projects. When a project is deleted, its sessions
  become one-time tasks in Planner and keep their check-ins and earned XP.
- Monthly Checklist groups goal-linked sessions into one visual row per goal
  while preserving separate underlying `Quest` and `QuestCheckin` records.
- Time-based quest XP for new scheduled quests and recurring habit templates.
- Nonlinear character leveling and RPG stat leveling.
- Command Center operational actions and metrics powered by check-ins.
- Character Profile XP, level, and RPG stats powered by check-in XP.
- Habit Analytics date filters, plan-versus-completion trends, category and
  routine performance, and insight data powered by check-ins.
- PostgreSQL persistence with Alembic migrations and a SQLite importer.
- Google sign-in and per-account data, including categories, check-ins, and XP.
- Legacy `Quest.status` compatibility/fallback while the migration remains
  stable.

Still evolving:

- External calendar sync.
- AI and voice planning assistants.
- Bonus XP for streaks.
- Optional automatic stale planned failure workflow.
- Eventual cleanup of legacy `Quest.status` once the check-in migration is fully
  stable.

## Preview

No screenshot files are currently committed. Use the live demo above to review
the current UI.

## Tech Stack

- Python
- Streamlit
- PostgreSQL
- SQLAlchemy
- Pandas
- Plotly
- streamlit-calendar
- pytest
- Streamlit Community Cloud

## What It Does

Habit Quest Analytics turns productivity tracking into a compact RPG loop:

- Schedule quests on a calendar.
- Divide long-term goals/projects into multiple planned work sessions.
- Track daily completion in a Monthly Checklist.
- Complete quest days to earn XP.
- Grow RPG stats through quest categories.
- Review today's operational status in Command Center.
- Analyze consistency, plan versus completion, category and routine activity,
  and planned workload in Habit Analytics.
- View level, XP progress, avatar, stat-level bars, radar chart, and RPG stats
  in Character Profile.

## Example Insights

The app is designed to answer questions such as:

- Which habits or quest categories are completed most consistently?
- Which categories generate the most XP?
- Which weekdays are strongest or weakest?
- How much planned time is assigned by category?
- How many quest days were completed, failed, skipped, or still planned?
- Which RPG stats grow from completed quest days?

## Features

### Quest Planning

- Calendar-based scheduled quest creation.
- One `Add to plan` form for one-time tasks, repeating routines, and sessions
  linked to an existing goal/project.
- One-time tasks default to the selected day; schedule timing, project linking,
  and notes are available only when needed.
- XP reward calculation from planned time.
- Estimated duration calculation from the scheduled time window.
- Calendar and selected day schedule views that display check-in status.
- Command Center is the only screen for completing, skipping, failing, or
  resetting today's and overdue planned work.
- Recurring Habit templates for Every day, Weekdays, and custom selected
  weekdays.
- Creating a routine generates its days for the selected creation month.
- Projects & Routines generates missing routine days for future months.
- The Monthly checklist tab is a read-only matrix of planned and completed work.
- Recurring habits can be all-day or use a planned start/end time window.
- Routine templates can be edited without changing already generated days or
  their history; new settings apply to later month generation.
- Unused recurring habits can be deleted.
- Recurring habits with generated history can be archived/deactivated.
- Stopping a routine can optionally remove its future unresolved planned days in
  the same action, while resolved history remains intact.
- Future unresolved planned generated days can be removed while completed,
  skipped, failed, and XP-awarded history is preserved.
- Single unresolved generated recurring days can be removed safely.
- One-time planned quests can be deleted only while they have no resolved
  history or awarded XP.
- Unresolved one-time quests and project sessions can be edited from the day
  plan, including title, category, date, duration, and notes.
- Goal/project sessions can be added one at a time from Add to plan or generated
  in bulk from the selected project workspace after an explicit preview and
  confirmation.
- Bulk goal planning respects selected weekdays, start time, optional planning
  end date, the goal target date, and shorter final session behavior.
- Planner-generated sessions remain normal one-time `Quest` records with one
  planned `QuestCheckin` each and no XP awarded until completion.

### Monthly Checklist

- Month and year selection.
- Month-level review and status history for scheduled quest days.
- Matrix preview with quests as rows and days as columns.
- Recurring habits appear as one logical row with generated dates populated.
- Status legend for empty, planned, completed, skipped, and failed days.
- Read-only monthly status history; daily status actions belong to Command
  Center.
- Selected-day planning controls handle editing or removing unresolved work.
- `QuestCheckin.xp_awarded` prevents duplicate XP from repeated completion
  actions.

### Command Center

- Default operational workspace for today's and overdue quest check-ins.
- Planned Today, Completed Today, Failed, and Overdue metrics from
  `QuestCheckin`.
- Status actions for today's and overdue planned work.

### Habit Analytics

- Weekly XP from check-in XP.
- Completed and failed quest days for the current week.
- Weekly completion rate using completed / (completed + failed).
- XP trend by check-in date.
- Check-ins by status and category.
- Completion rate by weekday.
- Planned minutes by category.
- Date-range period review with prior-period comparison, active-day consistency,
  workload execution, weekday patterns, category performance, and one clear focus item.
- Current and best streaks for routines, calculated from their scheduled history through today.
- Project completion forecasts based on completed planned effort and target dates.
- Insight summaries based on completed and failed check-ins.

### Character Profile

- Avatar upload stored locally in each account's own directory.
- Total XP from `QuestCheckin.xp_awarded`.
- Level, XP to next level, and level progress.
- RPG stat XP from completed check-ins joined to quest categories.
- RPG stat levels with progress bars.
- Radar chart for stat-level balance.

### Navigation / UI

- Explicit Streamlit navigation using polished page labels.
- Light and dark themes with a sidebar switch.
- Tabs for related views and dialogs for editing, generation, and confirmations.
- Tile-like sidebar navigation styling.
- Card-based sections and compact helper text.

### Testing

- Pytest coverage for XP rules, metrics, model relationships, check-in
  constraints, checklist services, quest creation integration, analytics
  services, and profile calculations.
- Compile check used before code handoff.

## App Sections

- `Command Center` - Today and Review tabs for daily work, overdue check-ins, and past dates.
- `Planner` - Calendar and Monthly checklist tabs. Use Add item to plan work and
  the selected-day list to edit or remove unresolved items.
- `Projects & Routines` - Projects, Routines, and Portfolio tabs, with dialogs for
  editing, lifecycle actions, and generating scheduled work.
- `Habit Analytics` - Overview, Categories, and Routines tabs with shared filters.
- `Character Profile` - avatar, XP, level, RPG stats, and radar chart. Use Change
  avatar to upload or remove the profile image.

## Key Technical Decisions

- `QuestCheckin` is the source of truth for daily completion status when
  check-ins exist.
- `Quest.status` remains in the model for compatibility/fallback during
  migration.
- XP is stored in `QuestCheckin.xp_awarded` so historical XP values are
  preserved and repeated completion does not duplicate XP.
- New scheduled quest and recurring habit template XP is time-based:
  `max(5, round(planned_minutes / 60 * 20))`.
- Scheduled quests create a planned check-in for the scheduled date.
- Goal Session Planner uses remaining scheduling effort, not XP, to decide how
  much work can still be planned:
  `max(planned_total_minutes - completed_minutes - currently_planned_minutes, 0)`.
- Failed and skipped goal sessions do not reduce remaining scheduling effort,
  so replacement work can be planned.
- Monthly Checklist is a read-only monthly history. Status transitions occur in
  Command Center; unresolved planning changes occur from Planner's selected-day
  panel.
- Deletion workflows are conservative: completed, skipped, failed, and
  XP-awarded records are preserved.
- Business logic lives in service layers instead of Streamlit page code.
- Metrics are covered by pytest before the UI consumes them.
- Auto-fail service logic exists with `grace_days = 3`, but it is not
  automatically enabled from app startup or page load.
- The app remains local-first until production persistence is explicitly
  designed.

## Data Flow

```text
Scheduled Quest
  -> Planned QuestCheckin
  -> Command Center status action
  -> Command Center operational metrics
  -> Character Profile XP/progression
  -> Habit Analytics trends and consistency
```

```text
Goal Session Planner Preview
  -> Explicit confirmation
  -> Normal scheduled goal-linked Quest rows
  -> Planned QuestCheckin per session
  -> Existing checklist, calendar, XP, and analytics flows
```

Streamlit pages are presentation surfaces. Services prepare workflow and
analytics data. SQLAlchemy models own persistence. Tests cover the behavior that
should remain stable as the UI evolves.

## Architecture

```text
habit-quest-analytics/
  app/
    main.py                  # Streamlit entrypoint and explicit navigation
    pages/                   # Command Center, Planner, Projects & Routines, Analytics, Profile
  src/
    analysis/                # Pure metric helpers
    database/                # SQLAlchemy models, database setup, SQLite import, seed data
    services/                # Quest, checklist, analytics, profile, and XP business logic
    constants.py             # Statuses, categories, RPG stat mapping
    ui.py                    # Shared Streamlit UI/style helpers
  docs/                      # Project, model, metrics, and design documentation
  tests/                     # Pytest coverage
  data/                      # Local uploads and optional SQLite backups
```

## Data Model

Core entities:

- `Category` - groups quests into areas such as Health, Work, Learning, Home,
  and Social.
- `Quest` - scheduled task or habit plan with XP reward, due date, optional
  time window, optional goal link, stable goal session number, and legacy status.
- `Goal` - long-term project container with planned effort, lifecycle status,
  target dates, and linked one-time quest sessions.
- `QuestCheckin` - daily status record for one quest on one date.
- `RecurringHabit` - reusable selected-weekday habit template.
- `RecurringHabitInstance` - link from one generated habit date to one generated
  quest.
- `PlayerProfile` - local character profile name, avatar path, and legacy total
  XP field.
- `Achievement` - planned milestone definition.
- `UnlockedAchievement` - join table connecting profiles to unlocked
  achievements.

Important relationship:

- One `Quest` can have many `QuestCheckin` records.
- One `Goal` can have many one-time `Quest` sessions.
- Goal-linked quests use `Quest.goal_id` and `Quest.goal_session_number`.
- A `QuestCheckin` tracks the status for a specific `quest_id` and
  `checkin_date`.
- `QuestCheckin.xp_awarded` is used for XP, progression, RPG stats, and
  analytics when check-ins exist.
- One `RecurringHabit` can have many generated `RecurringHabitInstance` rows.
- One `RecurringHabitInstance` points to one generated `Quest`.

```mermaid
erDiagram
    categories ||--o{ quests : groups
    categories ||--o{ recurring_habits : groups
    categories ||--o{ goals : groups
    goals ||--o{ quests : links
    quests ||--o{ quest_checkins : has
    recurring_habits ||--o{ recurring_habit_instances : generates
    quests ||--o| recurring_habit_instances : generated_as
    player_profiles ||--o{ unlocked_achievements : earns
    achievements ||--o{ unlocked_achievements : unlocks

    categories {
        int id PK
        string name
        text description
    }

    quests {
        int id PK
        string title
        text description
        string status
        boolean is_habit
        int xp_reward
        date due_date
        datetime planned_start_at
        datetime planned_end_at
        int estimated_minutes
        datetime completed_at
        datetime created_at
        int category_id FK
        int goal_id FK
        int goal_session_number
    }

    goals {
        int id PK
        string title
        text description
        int planned_total_minutes
        date start_date
        date target_end_date
        string status
        datetime created_at
        datetime updated_at
        int category_id FK
    }

    quest_checkins {
        int id PK
        int quest_id FK
        date checkin_date
        string status
        int xp_awarded
        datetime completed_at
        datetime skipped_at
        datetime failed_at
        datetime created_at
        datetime updated_at
    }

    recurring_habits {
        int id PK
        string title
        text description
        int xp_reward
        int estimated_minutes
        string recurrence_type
        text weekdays
        date start_date
        date end_date
        time planned_start_time
        time planned_end_time
        boolean is_active
        datetime created_at
        datetime updated_at
        int category_id FK
    }

    recurring_habit_instances {
        int id PK
        int recurring_habit_id FK
        date scheduled_date
        int quest_id FK
        datetime created_at
    }

    player_profiles {
        int id PK
        string character_name
        int total_xp
        string avatar_path
        datetime created_at
        datetime updated_at
    }

    achievements {
        int id PK
        string name
        text description
        int xp_required
    }

    unlocked_achievements {
        int id PK
        int player_profile_id FK
        int achievement_id FK
        datetime unlocked_at
    }
```

See [docs/data_model.md](docs/data_model.md) for deeper model notes.

## Requirements

- Python 3.11, as specified in `runtime.txt`.
- Dependencies from `requirements.txt`:
  - Streamlit
  - SQLAlchemy
  - Alembic and Psycopg for PostgreSQL
  - pandas
  - Plotly
  - streamlit-calendar
  - pytest
- A PostgreSQL database configured through `DATABASE_URL`.

## Installation

```bash
git clone https://github.com/BaseMar/habit-quest-analytics.git
cd habit-quest-analytics
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Running The App

```bash
python run_streamlit.py
```

The launcher uses the project's `.venv` when present. You can also run
`streamlit run app/main.py` from an environment with Streamlit 1.66.1 or newer.

## Google Sign-In

Create a **Web application** client in Google Auth Platform. Register
`http://localhost:8501/oauth2callback` for local development and the deployed
app URL with the same `/oauth2callback` path for Community Cloud. While the client
is in Testing mode, add the Google accounts you intend to use as test users.
[Streamlit's Google setup guide](https://docs.streamlit.io/develop/tutorials/authentication/google)

Keep `DATABASE_URL` at the top level in the gitignored
`.streamlit/secrets.toml`. Add the following section, replacing the example
values. Generate `cookie_secret` with `python -c "import secrets; print(secrets.token_urlsafe(48))"`.

```toml
[auth]
redirect_uri = "http://localhost:8501/oauth2callback"
cookie_secret = "your-generated-cookie-secret"
client_id = "your-google-client-id"
client_secret = "your-google-client-secret"
server_metadata_url = "https://accounts.google.com/.well-known/openid-configuration"
```

Configure the same section in Community Cloud secrets with that deployment's
redirect URI and a separate cookie secret. Use a separate database for local
testing while any single-user deployment is still running. During rollout,
stop the single-user app on every instance that shares the database, apply the
latest PostgreSQL migration, then start the account-enabled versions.

Use a server-side database role for the connection. The migration enables
row-level security on app tables so direct queries from public API roles are
denied. The app scopes its server-side sessions to the signed-in account.

New accounts receive their own default categories and profile. For an existing
database or an imported SQLite backup, sign in once as the intended owner. Before
adding items to that account, assign the previous records from a shell with the
appropriate `DATABASE_URL`.

```bash
python -m src.database.claim_legacy --email "owner@example.com"
```

The command matches the verified Google email of an existing account. Previously
unassigned rows remain hidden in the app until this step. Keep any existing
avatar files available at their stored paths during the transition.

## PostgreSQL

Set `DATABASE_URL` in your shell to the target PostgreSQL connection URL, for
example `postgresql://user:password@db.example.com/habit_quest?sslmode=require`.
The app accepts `postgresql://` and `postgres://` URLs using Psycopg. Apply the
schema before starting the app, and apply later upgrades when deploying a new
version. [SQLAlchemy PostgreSQL documentation](https://docs.sqlalchemy.org/en/20/dialects/postgresql.html#module-sqlalchemy.dialects.postgresql.psycopg)

```bash
python -m alembic upgrade head
```

To move an existing SQLite database, stop writes to the source and run the import
after the schema upgrade and before the first sign-in. The import reads a
snapshot and copies all app data in one transaction. It keeps IDs, relationships,
check-ins and XP, and requires an empty destination. After importing, assign the
records with the [legacy claim command](#google-sign-in).

```bash
python -m src.database.import_sqlite data/habit_quest.db
```

Database records and avatar file paths are copied. Avatar image files are stored
separately under `data/uploads/`. For local Streamlit runs, set `DATABASE_URL`
in the shell or as a top-level key in the gitignored `.streamlit/secrets.toml`.
On Streamlit Community Cloud, use a top-level app secret. The Alembic, import,
and legacy claim commands read the shell environment.
[Streamlit Community Cloud secrets](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management)

## Tests

```bash
python -m pytest
python -m compileall -q app src tests migrations
```

Set `TEST_POSTGRESQL_URL` to run the PostgreSQL integration tests. They create
and remove an isolated schema in that database.

On Windows, if local pycache permissions cause compile issues, run with a
temporary pycache prefix:

```powershell
$env:PYTHONPYCACHEPREFIX="$env:TEMP\habit_quest_pycache"
python -m compileall -q app src tests
```

## Design Principles

- Daily completion tracking belongs to `QuestCheckin`.
- UI pages should read prepared service data instead of owning business rules.
- Service functions own status transitions, XP idempotency, and query
  preparation.
- XP changes must be idempotent.
- Analytics should avoid double-counting legacy quest status and check-in
  records.
- The app reads and writes PostgreSQL. SQLite is used for imports and tests.

## Limitations & Future Work

Current limitations:

- Recurring Habits supports selected weekdays, template editing, and explicit
  month generation.
- Projects & Routines provides a selected-project workspace. A broader portfolio
  dashboard with deeper drilldowns remains future work; the design is documented
  in [docs/long_term_goals_design.md](docs/long_term_goals_design.md).
- Database records can persist in PostgreSQL. Uploaded avatar files use local
  storage.
- Google Calendar sync is not implemented.
- AI planning assistant and voice quest capture are not implemented.
- Streaks currently provide analytics. Bonus XP for streaks is planned.
- Achievement unlock rules are not implemented.
- Auto-fail exists as service logic but is not automatically enabled.
- `Quest.status` still exists for compatibility/fallback and should be cleaned
  up only after the check-in migration is stable.

Suggested future order:

1. Google Calendar sync
2. AI planning assistant
3. Voice quest capture / microphone input
4. Bonus XP for streaks
5. Achievement system
6. Optional auto-fail activation workflow
7. Legacy `Quest.status` cleanup

# Habit Quest Analytics

An RPG-inspired habit planner and analytics dashboard that turns scheduled tasks
into daily quests, awards XP for completed quest days, and shows progress through
operational metrics, trend analysis, and character growth.

![Python](https://img.shields.io/badge/Python-3.11-blue)
![Streamlit](https://img.shields.io/badge/Streamlit-App-ff4b4b)
![Pandas](https://img.shields.io/badge/Pandas-Data%20Analysis-purple)
[![CI](https://github.com/BaseMar/habit-quest-analytics/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/BaseMar/habit-quest-analytics/actions/workflows/ci.yml)
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
- [PostgreSQL](#postgresql)
- [Tests](#tests)
- [Design Principles](#design-principles)
- [Current Limitations](#current-limitations)
- [Development Roadmap](docs/roadmap.md)

## Project Goal

Habit apps often track whether tasks were done, but they do not always connect
planning, completion, XP, progression, and analytics in one workflow.

Habit Quest Analytics brings that loop into one planner and analytics app. It lets a user
schedule daily quests, mark each quest day as planned, completed, skipped, or
failed, earn XP from completed check-ins, grow RPG-style stats, and review
behavior through dashboards and charts.

## My Role

I designed and implemented the application, including the following work.

- SQLAlchemy persistence with PostgreSQL and an importer for SQLite backups.
- Streamlit app shell, custom navigation, and dark RPG dashboard UI.
- Quest planning workflow with calendar scheduling.
- Monthly Checklist tracking system backed by daily `QuestCheckin` records.
- Checklist status service with idempotent XP rules.
- Summary, Habit Analytics, and Character Profile data services.
- Google sign-in, per-account data ownership, and a resettable guest demo.
- Long-term goal/project planning services, including bulk goal session preview
  and generation.
- RPG XP, level, and stat progression logic.
- Pytest coverage for models, services, metrics, and migration behavior.
- Project documentation and roadmap.

## Live Demo

Live app: https://habit-quest-analytics-sai5h3bl7wjykw4fbruabd.streamlit.app

Choose **Try live demo** to open Planner as Alex Morgan, with sample tasks,
routine history, a project, and earned XP. You can edit the plan and try other
features. Each demo session starts fresh, and its data stays in memory for the
duration of that session. Click **Reset demo** in the sidebar to restore the
sample data and continue exploring. Demo mode is also available when running locally.

The account-enabled Streamlit Community Cloud deployment uses PostgreSQL on
Supabase. See the [Google sign-in setup](#google-sign-in) and
[PostgreSQL setup](#postgresql) for configuration.
Uploaded account avatars use local storage and may reset when the Streamlit
instance changes.

## Project Status

The planner, account workspaces, guest demo, and analytics are implemented.
The documented deployment uses Streamlit Community Cloud and Supabase
PostgreSQL. See the [repository baseline](docs/project_overview.md) for audit
evidence and verification limits.

In the interface, everyday work is called a **task**, repeated work a
**routine**, and a larger outcome a **project**. RPG terminology remains part of
the product name and progression system, not a requirement for using the planner.

Implemented:

- Planner as the default workspace for scheduling and daily check-ins.
- Custom Streamlit navigation/sidebar with explicit page labels.
- Full-screen loading indicator when opening the workspace or switching pages.
- Interactive monthly calendar and selected-day agenda with check-in actions
  and editing for unresolved items.
- Built-in categories for tasks, routines, and projects.
- Read-only Monthly Checklist grouped by routine or project where applicable.
- Recurring Habit templates with automatic generation for the creation month and
  explicit future-month generation from Projects & Routines.
- Recurring habit template editing, a unified stop/resume lifecycle, unused-template
  deletion, single generated-day deletion, and safe future planned-day cleanup.
- `QuestCheckin` model for per-day completion status.
- Checklist service for `Planned`, `Completed`, `Skipped`, `Failed`, reset
  behavior and XP idempotency. Planner and Summary validate status actions
  against the displayed check-in. A stale planned failure helper exists.
- Scheduled quest creation that creates a planned check-in for the scheduled
  date.
- Safe deletion for unresolved one-time planned quests.
- Long-term Goals / Projects with a `Goal` model, service layer, one-time
  session linking, and a dedicated workspace for project creation and editing.
- Goal/project creation and linked goal sessions require a category.
- Goal/project planned total time can be left unset when the total effort is not
  known yet.
- The unified Add to plan form can link a one-time work session to an existing
  active project, with automatic per-goal session numbering and generated
  session titles.
- The project workspace combines creation, editing, progress, lifecycle
  actions, and a Goal Session Planner that previews and bulk creates scheduled
  one-time sessions from remaining unscheduled effort. The Portfolio tab
  compares project progress, and the Projects tab includes a rule-based
  completion forecast.
- Goal lifecycle controls in Projects & Routines include archiving, completing,
  reopening, and deleting projects. When a project is deleted, its sessions
  become one-time tasks in Planner and keep their check-ins and earned XP.
- Monthly Checklist groups goal-linked sessions into one visual row per goal
  while preserving separate underlying `Quest` and `QuestCheckin` records.
- Time-based quest XP for new scheduled quests and recurring habit templates.
- Nonlinear character leveling and RPG stat leveling.
- Summary with daily metrics and a review of overdue work and past check-ins.
- Character Profile XP, level, and RPG stats powered by check-in XP.
- Habit Analytics with date, category, and work-type filters, period-over-period
  comparisons, planned versus completed planned effort, category and routine
  performance, and current and best routine streaks.
- PostgreSQL persistence with Alembic migrations and a SQLite importer.
- Google sign-in and per-account data, including categories, check-ins, and XP.
- Per-session in-memory SQLite guest demo, with sample data and a reset action.
- Light and Dark themes and shared Streamlit presentation components.
- Legacy `Quest.status` compatibility/fallback while the migration remains
  stable.

Planned work and release criteria are tracked in the [development roadmap](docs/roadmap.md).

## Preview

Use the [live demo](#live-demo) to explore the interface. Screenshot capture is
tracked in the [roadmap](docs/roadmap.md).

## Tech Stack

- Python
- Streamlit
- PostgreSQL on Supabase
- SQLAlchemy, Alembic, and Psycopg
- Pandas
- Plotly
- pytest
- Streamlit Community Cloud

## What It Does

Habit Quest Analytics turns productivity tracking into a compact RPG loop:

- Schedule quests on a calendar.
- Divide long-term goals/projects into multiple planned work sessions.
- Track daily completion in a Monthly Checklist.
- Complete quest days to earn XP.
- Grow RPG stats through quest categories.
- Review today's status and overdue work in Summary.
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
- The creation form defaults to the selected day and provides a start and end
  time. One-time tasks can link to an existing active project. Notes are optional.
- XP reward calculation from planned time.
- Estimated duration calculation from the scheduled time window.
- Select a calendar date to see its tasks, routines, and project sessions.
- Edit an unresolved item in the selected-day list. A routine-day edit applies
  to that occurrence, while its dates are managed by the routine's schedule.
- Complete, skip, fail, or reset check-ins for today and past dates in Planner or
  Summary.
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

- Month navigation shared with the calendar.
- Month-level review and status history for scheduled quest days.
- Matrix preview with quests as rows and days as columns.
- Recurring habits appear as one logical row with generated dates populated.
- Status legend for empty, planned, completed, skipped, and failed days.
- Read-only monthly status history. Use Planner or Summary for daily status actions.
- Selected-day planning controls handle editing or removing unresolved work.
- `QuestCheckin.xp_awarded` prevents duplicate XP from repeated completion
  actions.

### Summary

- Overview of today's progress and overdue quest check-ins.
- Planned Today, Completed Today, Failed, and Overdue metrics from
  `QuestCheckin`.
- Status actions for today's and overdue planned work.

### Habit Analytics

- Date, category, and work-type filters with 7-, 30-, and 90-day presets and a
  custom range.
- Completion rate and completed check-in count compared with the preceding
  period of the same length, plus active-day consistency and a review focus.
- Weekly scheduled and completed planned minutes, with completion rate by weekday.
- Category and routine performance, including current and best routine streaks
  from scheduled history through today.
- Completion forecasts appear in Projects & Routines. See the
  [metrics reference](docs/metrics.md) for calculations and units.

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
- Dedicated sign-in screen and a themed loading screen on initial page load and
  route changes.

### Testing

- Pytest coverage for XP rules, metrics, model relationships, check-in
  constraints, checklist services, quest creation integration, analytics
  services, and profile calculations.
- Compile check used before code handoff.

## App Sections

- `Planner` - start page with Calendar and Monthly checklist tabs. Use the
  selected-day list to edit tasks and record check-ins.
- `Summary` - Today and Review tabs for daily work, overdue check-ins, and past dates.
- `Projects & Routines` - Projects for creation, editing, lifecycle, session
  planning, and forecasting. Routines for template management and generation.
  Portfolio compares active and completed projects when at least two qualify.
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
- Monthly Checklist is a read-only monthly history. Planner's selected-day panel
  supports edits to unresolved items and status transitions. Summary also
  supports status transitions.
- Deletion workflows are conservative: completed, skipped, failed, and
  XP-awarded records are preserved.
- Business logic lives in service layers instead of Streamlit page code.
- Metrics are covered by pytest before the UI consumes them.
- Auto-fail service logic exists with `grace_days = 3`, but it is not
  automatically enabled from app startup or page load.
- Signed-in work uses PostgreSQL and an account-scoped SQLAlchemy session.
  Guest work uses a separate in-memory SQLite database for each session.

## Data Flow

```text
Scheduled Quest
  -> Planned QuestCheckin
  -> Planner or Summary status action
  -> Summary metrics
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
    pages/                   # Planner, Summary, Projects & Routines, Analytics, Profile
    components/              # Planning forms, checklist, sign-in, and loading UI
  src/
    auth.py                  # Google identity and guest session management
    analysis/                # Pure metric helpers
    database/                # Models, scoped sessions, SQLite import, and seed data
    services/                # Quest, checklist, analytics, profile, and XP business logic
    constants.py             # Statuses, categories, RPG stat mapping
    ui.py                    # Shared Streamlit UI/style helpers
  migrations/                # Alembic PostgreSQL schema revisions
  docs/                      # Baseline, data model, metrics, and roadmap
  tests/                     # Pytest coverage
  data/                      # Local uploads and optional SQLite backups
```

## Data Model

The [data model and ERD](docs/data_model.md) show the `UserAccount` ownership
relationships, the planning tables, and `QuestCheckin` as the daily status and
XP record. An account owns its categories, tasks, projects, routine templates
and instances, check-ins, profile, and achievement unlock records. Achievement
definitions are shared. Achievement unlock processing is tracked in the
[development roadmap](docs/roadmap.md).

## Requirements

- Python 3.11, as specified in `runtime.txt`.
- Dependencies from `requirements.txt`:
  - Streamlit
  - SQLAlchemy
  - Alembic and Psycopg for PostgreSQL
  - pandas
  - Plotly
  - pytest
- A PostgreSQL database configured through `DATABASE_URL` for Google accounts.

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

Use a server-side database role for the connection. The account migration
adds same-owner foreign keys and enables row-level security on app tables.
Public API roles without a policy or bypass cannot directly access those rows. The app scopes its server-side sessions to the signed-in account.

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
python -m pytest -ra
python -m compileall -q app src tests migrations
```

Run PostgreSQL integration tests locally against a disposable database. Set
`TEST_POSTGRESQL_URL` to its connection URL using a test role that can create
schemas, create a disposable unprivileged role, and switch to that role for
the row-level security test. The fixture upgrades an isolated schema to Alembic
head, checks for drift, and drops the schema after each test.

```powershell
$env:TEST_POSTGRESQL_URL = 'postgresql://test_user:test_password@127.0.0.1:5432/habit_quest_test'
python -m pytest -ra tests/test_postgresql.py tests/test_account_scope.py
```

Without `TEST_POSTGRESQL_URL`, pytest skips the cases that need a running
PostgreSQL server.

On Windows, if local pycache permissions cause compile issues, run with a
temporary pycache prefix:

```powershell
$env:PYTHONPYCACHEPREFIX="$env:TEMP\habit_quest_pycache"
python -m compileall -q app src tests migrations
```

### Continuous integration

The [GitHub Actions CI workflow](.github/workflows/ci.yml) runs on pushes, pull
requests, and manual dispatch. It installs `requirements.txt` on Ubuntu with
Python 3.11, runs the full pytest suite and compilation checks, and reruns the
PostgreSQL and account scope modules. CI checks the report for the required
database cases, including ownership, row-level security, and concurrency, and
fails if cases skip in those modules.

Each job starts a temporary PostgreSQL 18 service with its own test database
and credentials. The service is independent of Supabase and requires no
production database or Google authentication secrets.

## Design Principles

- Daily completion tracking belongs to `QuestCheckin`.
- UI pages should read prepared service data instead of owning business rules.
- Service functions own status transitions, XP idempotency, and query
  preparation.
- XP changes must be idempotent.
- Analytics should avoid double-counting legacy quest status and check-in
  records.
- The app reads and writes PostgreSQL. SQLite is used for imports and tests.

## Current Limitations

- Workload and project forecasts use planned duration. The app does not record
  measured actual duration.
- Uploaded account avatars use local server storage. Guest changes last for
  the current session.
- Routine streaks are reporting metrics. Achievement tables support definitions
  and unlock records.
- The stale planned failure helper is available in the service layer and has
  no automatic trigger. `Quest.status` remains for legacy compatibility.
- Local PostgreSQL integration tests require a disposable database. Hosted
  end-to-end verification remains release work.

See the [development roadmap](docs/roadmap.md) for planned features, release
criteria, and deferred ideas.

# Project Overview

Habit Quest Analytics is an RPG-inspired productivity planner and analytics
dashboard. It connects scheduled work, daily check-ins, project progress, and
character progression so people can see how planning and follow-through change
over time.

## Product and audience

The app is for individuals tracking personal routines, focused work, and
longer-term projects. Each signed-in user has a private workspace. A seeded
guest workspace lets visitors try the same core workflow without signing in.

## Verified repository baseline

The baseline below was checked against commit `34742dc` and the local pytest
suite. Streamlit Community Cloud and Supabase PostgreSQL are the documented
deployment. An unauthenticated health request redirected to Streamlit's
authentication endpoint. Hosted sign-in, guest access and reset, and database
connectivity still need end-to-end verification.

| Area | Verified behavior | Implementation evidence |
| --- | --- | --- |
| Planner and Calendar | Select a date in the interactive month grid, add timed one-time tasks, repeating routines, or an individual session for an existing project, then manage the selected day's agenda. Unresolved items can be edited. An individual routine occurrence can be edited without changing its template or date. Projects are created in Projects & Routines. | [Planner](../app/pages/2_Quest_Log.py), [planning form](../app/components/plan_form.py), [quest service](../src/services/quest_service.py) |
| Routines | Create templates for every day, weekdays, or selected weekdays. Planner generates occurrences for the start month. Projects & Routines generates later months on demand, edits templates, stops or resumes routines, and deletes unused templates or eligible planned occurrences. Template edits apply to later generation. | [Project and routine workspace](../app/components/project_routine_workspace.py), [routine service](../src/services/recurring_habit_service.py) |
| Monthly Checklist | A read-only matrix groups routines by template and project sessions by project. Daily status changes happen in Planner or Summary on eligible current or past work. The checklist service can create a missing scheduled check-in for legacy data while assembling the matrix. | [Matrix UI](../app/components/planner_month_review.py), [checklist service](../src/services/checklist_service.py), [Summary](../app/pages/1_Dashboard.py) |
| Check-ins and retention | `QuestCheckin` holds one status and awarded XP per quest/date. Completion is idempotent and Reset returns the check-in to Planned with zero awarded XP. Cleanup preserves resolved or XP-awarded history. Project deletion detaches linked sessions and preserves their schedules, titles, check-ins, and XP. | [Check-in model](data_model.md#quest_checkins), [checklist service](../src/services/checklist_service.py), [goal service](../src/services/goal_service.py) |
| Projects and session planning | Create, edit, complete, archive, reopen, or delete projects. Linked sessions receive automatic per-project numbers and generated names. Bulk planning previews dates and durations and creates sessions after explicit confirmation and a fresh effort calculation. | [Project workspace](../app/components/project_routine_workspace.py), [quest service](../src/services/quest_service.py), [bulk planning service](../src/services/goal_session_planner_service.py) |
| Project analytics and forecasting | The Projects tab shows selected-project progress and a rule-based forecast when the necessary targets and history are available. Portfolio compares active and completed projects when at least two qualify, with completed and remaining effort and weighted progress. Effort is based on scheduled estimates. | [Goal service](../src/services/goal_service.py), [analytics service](../src/services/analytics_service.py), [project workspace](../app/components/project_routine_workspace.py) |
| Habit analytics | Compare a selected date range with the preceding equal-length period. Review scheduled versus completed planned effort, category and routine performance, and current and best routine streaks. Streaks use scheduled history through today for routines shown in the selected view. | [Habit Analytics](../app/pages/3_Habit_Analytics.py), [analytics service](../src/services/analytics_service.py), [metrics reference](metrics.md) |
| XP and character progression | Planned duration sets XP for new scheduled work. Completed check-ins drive nonlinear character and stat levels, progress bars, and a stat-level radar chart. Signed-in avatar files use local server storage. | [XP service](../src/services/xp_service.py), [Character Profile](../app/pages/4_Character_Profile.py), [profile service](../src/services/profile_service.py) |
| Navigation and appearance | Dedicated sign-in screen, themed route-loading screen, Light and Dark themes, and shared UI components. The visible pages are Planner, Summary, Projects & Routines, Habit Analytics, and Character Profile. | [App entry point](../app/main.py), [sign-in](../app/components/sign_in.py), [loading screen](../app/components/loading_screen.py), [shared UI](../src/ui.py) |
| PostgreSQL and migrations | Signed-in data uses PostgreSQL via SQLAlchemy and Psycopg. The documented hosted backend is Supabase. Alembic manages the schema. The SQLite importer snapshots source data and transfers it to an empty PostgreSQL destination, with an explicit claim step for legacy ownership. | [Database configuration](../src/database/db.py), [migrations](../migrations/versions), [SQLite importer](../src/database/import_sqlite.py), [setup](../README.md#postgresql) |
| Google sign-in and ownership | Streamlit verifies Google identity. App sessions filter personal ORM reads and enforce ownership on writes and deletes. PostgreSQL has owner-aware foreign keys and RLS enabled as defense against direct public-role access. Unclaimed legacy rows remain hidden from account sessions. | [Authentication](../src/auth.py), [account session](../src/database/user_session.py), [account migration](../migrations/versions/0002_accounts.py), [ownership model](data_model.md#user_accounts) |
| Guest demo | Each Streamlit session gets its own in-memory SQLite database with sample tasks, routine history, a project, and XP. Reset replaces the demo data and preserves the theme. Exit disposes of the demo engine. | [Demo seed](../src/services/demo_service.py), [demo session management](../src/auth.py), [UI tests](../tests/test_ui_components.py) |
| Automated tests and deployment | Pytest covers models, business rules, analytics, and Streamlit UI flows. PostgreSQL integration cases are available with `TEST_POSTGRESQL_URL`. There is no GitHub Actions workflow in this baseline. The README links to the configured Streamlit Community Cloud app. | [Tests](../tests), [PostgreSQL cases](../tests/test_postgresql.py), [requirements](../requirements.txt), [live demo](../README.md#live-demo) |

## Baseline limitations and release checks

- The local suite on Python 3.12.2 passed 368 tests with zero failures and
  three PostgreSQL integration tests skipped because `TEST_POSTGRESQL_URL` was
  unset. SQLite tests and mocked sign-in flows do not exercise the real
  PostgreSQL role configuration or hosted Google OAuth deployment.
- Ownership and independent demo/reset tests exist. PostgreSQL concurrency,
  broader cross-account operation coverage, and hosted smoke tests remain
  release work.
- Loading Monthly Checklist can backfill missing scheduled check-ins, making
  its query cost and concurrency behavior relevant to the release review.
- Signed-in avatar files are local to the server and can disappear when the
  hosted instance changes. Guest changes last for the current session.
- `Quest.status` remains as a compatibility fallback. Calculations that use
  check-ins must preserve historical XP and avoid counting the legacy status
  a second time.
- Current workload and forecast metrics use planned effort. The app does not
  measure actual duration. See the [metrics reference](metrics.md) for units
  and forecast rules.

Planned development and release gates live in the [roadmap](roadmap.md).
The [MVP specification](mvp_specification.md) records the original product scope
and the design goals that shaped the current application.

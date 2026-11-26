# Agent Notes

Habit Quest Analytics is a deployed Streamlit planner and analytics app with
PostgreSQL for signed-in accounts and an isolated in-memory SQLite guest demo.

## Planning and scope

- Read [the roadmap](docs/roadmap.md) before implementing new features, then
  inspect the relevant implementation and tests. Treat implemented code as the
  source of truth for current behavior.
- Work on one explicitly approved feature or milestone task at a time, following
  its dependencies and acceptance criteria. Get explicit approval before
  implementing future milestones or adding external APIs, cloud services, or ML.
- Keep code simple and readable. Avoid speculative abstractions and unrelated
  refactoring. Keep application behavior unchanged during documentation-only work.
- Keep commits focused. Commit or push only when explicitly requested.

## Architecture and invariants

- Keep Streamlit pages and components focused on presentation. Put business
  rules in `src/services/`, reusable metric formulas in `src/analysis/`, and
  SQLAlchemy models and connection logic in `src/database/`. Keep persistence
  separate from calculations.
- Derive identity from the authenticated application context and keep personal
  data scoped to the account. Preserve ownership constraints and guest isolation.
- Preserve historical check-ins and awarded XP. Use `QuestCheckin` for daily
  status and XP when check-ins exist. Preserve unique quest/date check-ins,
  idempotent completion, and the existing reset and safe-deletion rules.

## Testing and documentation

- Update behavioral pytest coverage and relevant documentation with implemented
  changes. Record PostgreSQL skips accurately and use a disposable database
  with `TEST_POSTGRESQL_URL` for database integration checks.
- Run these checks before handing off code changes.

```bash
python -m pytest
python -m compileall -q app src tests migrations
```

- Keep documentation aligned with actual behavior, including data ownership,
  metrics, app sections, and commands. Keep planned work in the roadmap and
  update each task's status after implementation and verification.

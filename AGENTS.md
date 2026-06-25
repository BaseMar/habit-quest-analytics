# Agent Notes

Habit Quest Analytics is an MVP scaffold for a Streamlit application. Keep future work small, testable, and aligned with the current architecture.

## Project Rules

- Keep the code simple and readable.
- Prefer small commits with one clear purpose.
- Do not over-engineer abstractions before the MVP needs them.
- Do not add authentication unless explicitly requested.
- Do not add machine learning unless explicitly requested.
- Do not add external APIs unless explicitly requested.
- Do not introduce cloud services while the app is still local-first.
- Do not modify application logic when the task is documentation-only.

## Architecture Guidance

- Keep Streamlit pages focused on presentation.
- Keep business logic in `src/services/`.
- Keep metric formulas in `src/analysis/`.
- Keep database connection and SQLAlchemy models in `src/database/`.
- Keep persistence concerns separate from calculation logic.
- Use SQLite as the default local database until a different storage target is requested.

## Testing Guidance

- Add or update pytest coverage when business rules change.
- Keep tests focused on behavior rather than implementation details.
- Run these checks before handing off code changes:

```bash
python -m pytest
python -m compileall -q app src tests
```

## Documentation Guidance

- Keep README and docs honest about implementation status.
- Mark unfinished features as planned or in progress.
- Update docs when data model fields, metrics, commands, or app sections change.
- Avoid claiming CRUD, charts, achievements, ML, or deployment are implemented before they exist.

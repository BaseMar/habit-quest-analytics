# Habit Quest Analytics development roadmap

This is the authoritative source for planned development. The version numbers
below are provisional milestone labels. See the [repository baseline](project_overview.md)
for implemented capabilities, [data model](data_model.md) for ownership and
retention rules, and [metrics](metrics.md) for current definitions.

Use **Planned**, **In Progress**, **Implemented**, or **Deferred** as milestone
statuses. Work on one explicitly approved task at a time. Check off tasks and
update implementation status after verifying the work against its acceptance
criteria. Checked documentation tasks in version 1.0 reflect the baseline
audit. The release criteria still apply.

## Milestone dependencies

- Version 1.0 stabilizes planning, check-ins, account isolation, and deployment.
  It is the foundation for all later milestones.
- Version 1.1 builds Calendar synchronization on verified ownership and
  scheduling services. Its authorization is separate from Google sign-in.
- Version 1.2 depends on the stable planning services and account context from
  version 1.0. Calendar integration comes first in the proposed order, but the
  text assistant's initial actions do not require it.
- Version 1.3 depends on version 1.2's text, preview, and confirmation workflow.
- Versions 1.4 and 1.5 depend on version 1.0's verified metric, check-in, and XP
  behavior. Measured-duration analysis depends on that data being collected,
  and any reward changes depend on reliable history and idempotency tests.

## Milestone 1 — Version 1.0 · Stabilization and portfolio release

**Status** · Planned

**Objective and value.** Establish a reliable baseline and prepare the first
portfolio release. Users can trust their history and visitors can try the main
workflows with a sample account.

**Technical scope.** GitHub Actions, PostgreSQL integration tests, ownership and
guest-session coverage, deployment verification, measured maintenance, and
release documentation.

**Dependencies.** Existing PostgreSQL migrations, account-scoped services,
guest fixture, and pytest suite. CI needs a disposable PostgreSQL database.
Hosted verification needs an accessible Streamlit deployment and two authorized
test accounts for cross-account checks.

### Implementation tasks

- [ ] Add GitHub Actions to run pytest on pushes and pull requests. Provision a
  PostgreSQL service and set `TEST_POSTGRESQL_URL` for integration tests.
  Implemented locally, including manual dispatch. Workflow lint and all required
  integration cases passed locally against disposable PostgreSQL 18. Confirm
  the first successful GitHub Actions run before closing this task.
- [ ] Expand account isolation coverage for cross-account reads, writes,
  deletes, and relationship links. Test relevant concurrent provisioning,
  scheduling, and check-in operations on PostgreSQL.
- [ ] Extend the existing independent guest session and reset tests to cover
  interleaved changes, repeated resets, and guest isolation from account data.
- [ ] Verify migrations on an empty database and an upgrade from the original
  schema. Verify SQLite imports, rollback, ID preservation, and legacy ownership
  assignment on PostgreSQL.
- [ ] Review `analytics_service.py` and other large modules for concrete
  maintainability problems. Refactor only where the review justifies a change.
  Measure query counts and performance before addressing redundant reads.
- [ ] Run end-to-end functional checks across planning, routine lifecycle,
  project sessions, check-ins, analytics, progression, and account switching.
  Review status labels, form errors, empty states, and chart readability in
  both themes and representative viewport sizes.
- [ ] Review error handling, dependency management, and deployment
  configuration, including database roles and secrets.
- [x] Reconcile the README and architecture documentation with the current
  implementation. Recheck them against the release candidate.
- [x] Update the ERD with `UserAccount` and ownership relationships.
- [ ] Capture current app screenshots with synthetic or guest data.
- [ ] Verify the deployed app, Google sign-in, and guest demo end to end.
- [ ] Prepare release `v1.0.0` with setup instructions, release notes, and
  known limitations.

**Acceptance criteria.** Core workflows pass locally and in the deployed app.
CI runs for both pushes and pull requests, and PostgreSQL integration tests
execute without skips in the database job. Account isolation has no known
critical issues. Documentation and screenshots match the release, and a
visitor can launch, use, and reset the demo without signing in.

**Testing requirements.** Run the suite against a disposable PostgreSQL
database and check schema upgrades, constraints, imports, ownership assignment,
role permissions, and concurrency. Use independent guest sessions and
separate test accounts for UI verification. Record pass, fail, and skip counts
and the app version used for the hosted smoke test.

## Milestone 2 — Version 1.1 · Google Calendar integration

**Status** · Planned

**Objective and value.** Let users bring calendar commitments into their
planning workflow and share scheduled work with Google Calendar.

**Technical scope.** Separate Calendar OAuth authorization, account-owned
connection and event mappings, and staged synchronization through existing
scheduling services. Google sign-in establishes identity. Calendar API access
requires a separate grant.

**Dependencies.** Version 1.0 ownership and migration checks, a Google Calendar
API configuration, approved scopes, and calendar-specific data ownership and
token storage decisions.

### Implementation tasks

1. [ ] Design the integration, connection ownership, and sync boundaries.
2. [ ] Implement a separate Google Calendar OAuth authorization flow.
3. [ ] Use and verify least-privilege scopes for the supported operations.
4. [ ] Secure per-account access and refresh tokens, including expiry and renewal.
5. [ ] Import events in a read-only view.
6. [ ] Add an explicit action to convert selected events into validated planned tasks.
7. [ ] Export scheduled tasks, routines, and project sessions.
8. [ ] Map external event IDs to their owning account, calendar, and local records.
9. [ ] Prevent duplicates and make synchronization idempotent under retries.
10. [ ] Handle timezones, daylight-saving transitions, and all-day events.
11. [ ] Define conflict resolution, partial failure recovery, and external deletion rules.
12. [ ] Enable bidirectional synchronization after verifying the prior phases.
13. [ ] Provide disconnect and revoke-access controls, with documented handling
    of local records and event mappings.

**Acceptance criteria.** Users grant and revoke Calendar access independently
of login. A connection can only read or sync records owned by the active
account. Repeating the same sync preserves one mapping per event. Import and
sync create no XP or completion status. Historical check-ins change only
through explicit, validated application actions.

**Testing requirements.** Exercise the phases with a mocked Calendar API and
an authorized test calendar. Cover scopes, expiry and revocation, account
boundaries, duplicate imports, retry and conflict behavior, all-day and
timezone cases, remote deletions, and preservation of check-ins and XP.

## Milestone 3 — Version 1.2 · Local LLM planning assistant

**Status** · Planned

**Objective and value.** Turn Polish and English planning requests into
reviewable drafts that reduce the time it takes to schedule work.

**Technical scope.** Evaluate a local runtime such as Ollama and choose a
provider through a provider-independent interface. Proposal schemas and
service validation form the write boundary.

**Dependencies.** Version 1.0's authenticated context, scheduling and validation
services, and verified ownership rules. The local mode needs a reachable
inference runtime. Hosted mode needs its own deployment design.

```text
Natural language input
  -> LLM provider
  -> Structured action proposal
  -> Schema validation
  -> Business rule validation
  -> Preview
  -> Explicit user confirmation
  -> Existing application services
  -> Database
```

### Implementation tasks

- [ ] Evaluate local runtimes and document local and hosted configurations. A
  model running on a user's computer is not automatically reachable from
  Streamlit Cloud. Keep any unauthenticated local endpoint off the public
  internet and keep the hosted app fully functional without a provider.
- [ ] Define a strict action schema and use the signed-in application context
  to supply identity. Reject model-provided identity, direct SQL, unrestricted
  database access, and arbitrary code execution.
- [ ] Propose one-time tasks, recurring routines, projects, and individual or
  bulk project sessions. Interpret dates, durations, categories, and recurrence
  patterns. Ask for clarification when required values are missing.
- [ ] Show a validated preview and require explicit confirmation before any
  write. Revalidate against current state and call the existing application
  services for all business rules and persistence.
- [ ] Handle provider timeouts and unavailable models gracefully. Build a
  Polish and English evaluation dataset before enabling the assistant.
- [ ] After the initial actions are stable, evaluate daily or weekly scheduling
  suggestions, replacement sessions for skipped or failed work, explanations
  of analytics insights, and workload suggestions based on existing metrics.

**Acceptance criteria.** Supported requests produce a valid preview or a
clarification. A declined, invalid, or unconfirmed proposal leaves data
unchanged. Confirmed actions use the same ownership and scheduling rules as
manual planning. Manual workflows remain usable when the model is unavailable
or unconfigured.

**Testing requirements.** Use stub providers and a versioned bilingual
evaluation dataset. Test ambiguous, malformed, contradictory, and invalid
requests, stale previews, confirmation and cancellation, provider failures,
and attempted cross-account references. Verify that app services own all writes.

## Milestone 4 — Version 1.3 · Voice planning assistant

**Status** · Planned

**Objective and value.** Let users capture plans by speaking Polish or English
and review the interpreted request before it changes their schedule.

**Technical scope.** Microphone capture and a speech-to-text provider interface
feed editable text into the existing planning assistant.

**Dependencies.** Version 1.2's tested bilingual assistant and confirmation
flow, browser microphone support, and an approved audio privacy and retention
policy.

### Implementation tasks

- [ ] Add microphone input and the speech-to-text provider interface. Evaluate
  local Whisper-based transcription for Polish and English.
- [ ] Define how microphone permission, audio processing, and retention work.
  Handle denied access, unavailable providers, and unusable audio.
- [ ] Show editable transcription before passing it into the text assistant.
  Reuse its structured preview, confirmation, and business services.
- [ ] Evaluate transcription quality and error recovery for representative
  planning requests in both languages.

**Acceptance criteria.** Users can review and correct a transcript or discard
it. Voice and typed requests follow the same validation and confirmation
path. A recording or transcription error leaves scheduled records unchanged.
Audio handling matches the documented privacy and retention rules.

**Testing requirements.** Test provider behavior with fixtures and permitted
sample audio in both languages. Cover silence, noisy or ambiguous audio, denied
permission, provider failures, edits, cancellation, confirmation, and
retention behavior.

## Milestone 5 — Version 1.4 · Advanced analytics

**Status** · Planned

**Objective and value.** Help users estimate work more accurately, balance
workload, and understand how well project forecasts perform.

**Technical scope.** Actual-duration model evaluation, expanded period review,
interpretable recommendations and forecasts, and account-scoped CSV export.

**Dependencies.** Version 1.0's verified analytics and retained check-in
history. Duration analysis needs measured observations, and forecast
backtesting needs sufficient historical project outcomes.

### Implementation tasks

- [ ] Evaluate a separate actual-duration tracking model. Keep scheduled effort,
  completed planned effort, and measured actual effort distinct in storage,
  metrics, and labels.
- [ ] Add planned-versus-actual duration and estimation accuracy analysis when
  measured duration is available. Define how reports handle missing durations.
- [ ] Improve weekly review, workload balance, category and routine
  recommendations, and progress visibility using existing metrics.
- [ ] Improve project forecasts with interpretable methods. Backtest against the
  existing deterministic forecast and report coverage and forecast error.
- [ ] Add an account-scoped CSV export with documented columns and metric units.
- [ ] Consider statistical or ML models only when sufficient data exists and a
  defined prediction target, evaluation protocol, baseline, and measurable
  user benefit justify the added complexity.

**Acceptance criteria.** Reports label estimated and measured effort accurately,
and legacy or unmeasured records remain usable. Users can interpret the basis
of recommendations and forecasts. Any new forecasting method has documented
backtest results against a baseline. Exports contain only authorized data.

**Testing requirements.** Cover missing and zero values, aggregate definitions,
period boundaries, existing histories, and CSV ownership and encoding. Backtest
with time-ordered data, recording target, baseline, sample size, metrics, and
coverage without using future observations to train or evaluate earlier
predictions.

## Milestone 6 — Version 1.5 · Gamification and technical maintenance

**Status** · Planned

**Objective and value.** Make progression more personal and reliable while
reducing the cost of maintaining compatibility paths.

**Technical scope.** Achievement rules and history, a streak bonus design,
character customization and durable avatar storage, optional stale-plan
automation, and verified retirement of legacy status paths.

**Dependencies.** Version 1.0's verified XP and ownership behavior, rules for
historical reward eligibility, an approved storage provider and access model,
and a migration plan for legacy records.

### Implementation tasks

- [ ] Define and implement achievement unlock rules, idempotent processing, and
  account-owned achievement history. Decide eligibility for existing records.
- [ ] Design streak bonus XP, including resets, repeated events, backfills, and
  historical eligibility. Preserve awarded XP and prevent duplicate rewards.
- [ ] Add character customization and persistent avatars through Supabase
  Storage or another suitable provider. Define ownership and migration of
  existing avatar files.
- [ ] Evaluate an optional automatic stale planned failure workflow. Define
  the grace period, opt-in behavior, and safeguards for historical records.
- [ ] Audit remaining legacy `Quest.status` reads. Plan and verify the data
  migration before eventual removal. Remove unused compatibility code only
  after callers and imports are verified.
- [ ] Continue architecture and performance improvements based on measured
  bottlenecks and concrete maintenance issues.

**Acceptance criteria.** Processing the same event repeatedly awards each
eligible reward once. Prior check-ins and earned XP retain their meaning after
upgrades. Avatars persist across deployments and stay scoped to the owner.
Legacy cleanup preserves existing records and supported import paths.

**Testing requirements.** Test duplicate and concurrent reward processing,
reset and re-completion, upgrades with historical data, storage access across
accounts, optional automation boundaries, and compatibility across migration
and import paths. Compare before/after XP totals and query metrics where
relevant.

## Deferred backlog

These ideas have no scheduled milestone. Revisit them only after explicit
prioritization and an ownership and data-retention review where relevant.

| Idea | Reason to defer |
| --- | --- |
| One-time task archive or soft hide, and historical task corrections | Define how hidden or corrected records affect reporting, timestamps, and XP. |
| Flexible N-times-per-week routines or background routine generation | Define occurrence identity, missed-week semantics, and generation timing. |
| Task priority independent of duration and XP | Establish a planning use case and how priority would be reported. |
| Cumulative XP timeline, project highlights in Character Profile, and project completion bonus XP | Prioritize against existing progression and achievement work. |
| Deeper project drilldowns, stalled-project signals, and project dependencies or subtasks | Use the existing Projects and Portfolio tabs until more scope is justified. |
| Social, multiplayer, or shared projects | Sharing requires a distinct ownership and permissions design. |
| External integrations beyond Calendar or additional sync providers | Revisit once there is a specific use case and the Calendar experience is verified. |

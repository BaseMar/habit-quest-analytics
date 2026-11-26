# Performance and architecture review

The v1.0 Phase 5 baseline is commit `10bfc4fdfd8bfda6baaae8b93d6a2caf21697477`.
The review measures the account-scoped services behind the main pages and uses
query counts, elapsed time, and execution plans to choose release changes.

## Reproduce the benchmark

Install [project dependencies](../requirements.txt). On a disposable local
PostgreSQL server, create an empty database named `habit_quest_benchmark` and
mark it with the comment below. Use a local role that can create and drop
schemas and apply the app migrations inside them. The example assumes a
disposable server and test credentials already configured for port 54320.

```bash
createdb -h 127.0.0.1 -p 54320 -U bench habit_quest_benchmark
psql -h 127.0.0.1 -p 54320 -U bench -d habit_quest_benchmark \
  -c "COMMENT ON DATABASE habit_quest_benchmark IS 'Habit Quest Analytics disposable benchmark'"
export BENCHMARK_POSTGRESQL_URL='postgresql+psycopg://bench:disposable_password@127.0.0.1:54320/habit_quest_benchmark'
python -m scripts.benchmark_performance --repeats 25 --explain --output benchmark.json
```

In PowerShell, set the variable with `$env:BENCHMARK_POSTGRESQL_URL = '…'`.
The [runner](../scripts/benchmark_performance.py) requires an explicit
loopback address, port, credentials, database name, and matching server-side
marker. Use a dedicated cluster and database, independent of Supabase and
`TEST_POSTGRESQL_URL`. The app's `DATABASE_URL` is ignored. Each profile
migrates, populates, analyzes, and drops a uniquely named schema. To measure
one size, pass `--sizes small`, `--sizes medium`, `--sizes large`, or
`--sizes medium-many-projects`. The JSON includes first and warmed times,
query counts, result indicators and fingerprints, and optional plans. Write
generated reports outside the repository or keep them untracked.

To compare service code revisions, use the same runner, dataset, dependencies,
and command in both checkouts. Copy the runner into a clean checkout of the
baseline commit when reproducing the original measurements.

## Environment and methodology

- Windows 10 22H2 (build 19045), Intel Core i5-7600K at 3.80 GHz, 4 logical CPUs,
  16 GiB RAM. Python 3.12.2, local PostgreSQL 18.3, SQLAlchemy 2.1.9,
  Alembic 1.17.2, Psycopg 3.3.2, Pandas 3.1.1, NumPy 2.5.5, Streamlit 1.67.0,
  and Plotly 7.1.0.
- The first service invocation is recorded after migrations, inserts, and
  PostgreSQL `ANALYZE`. One additional warm-up precedes 25 timed repetitions.
  Each invocation creates and closes a fresh account-scoped `UserSession`.
  Connections and database pages may already be warm at first invocation.
  P95 is the nearest-rank 24th observation out of 25 warmed calls. It is a
  descriptive tail measurement for one local run.
- Wall time includes SQL, ORM hydration, computation, and session close.
  SQLAlchemy cursor events count executed application statements, including
  writes. Driver-level pool pings and transaction protocol calls are outside
  that count. Seeding, migration, statistics collection, JSON serialization,
  memory tracing, and plan analysis run outside timed samples.
- Peak allocation is one separate warmed `tracemalloc` run per operation. It
  reports Python-tracked allocations during that call. Total application
  process memory (RSS), PostgreSQL process memory, and some native allocations
  are outside this measurement. Selected warmed SELECT shapes from the large dataset
  are replayed with `EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)`. Plans describe
  PostgreSQL execution. ORM construction, Python work, and data transfer can
  add substantially to the service latency.
  [PostgreSQL EXPLAIN reference](https://www.postgresql.org/docs/18/sql-explain.html)
- Planner loads the visible calendar grid for July 2026. Checklist builds the
  July matrix. Summary uses the reference day and all applicable history.
  Habit Analytics runs current and preceding inclusive windows of 30 or 365
  days, with the independent weekly pulse. The filtered case uses Work and
  project sessions over 365 days. The routine case uses a 30-day routine-only
  report plus full prior occurrence history for streaks. Portfolio uses its UI
  default of active and completed projects. The single-project case makes both
  progress and forecast calls. Profile uses all the account's check-ins.
- This is a local, single-worker comparison. It excludes browser work, chart
  rendering, Streamlit widget reruns, Supabase networking, and hosted
  concurrency. Standard timing profiles have every scheduled check-in.
  A separate medium scenario records creation of 24 missing legacy check-ins
  and one steady call after creation for each affected service.

## Synthetic workload

The reference date is July 15, 2026. Each profile creates two accounts of
equal size with independently seeded work and XP in the same schema. Each
account has five categories and one profile. Check-ins are distributed across
the dated horizon through July 29, 2026, with one check-in per quest. Project
sessions have stable numbering and routines have unique template/date
occurrences. Durations range from 15 to 90 minutes. Past check-ins mix all
four statuses. Current and future check-ins are planned. Only completions
earn the application's duration-based XP.

| Dataset | Start | Tasks / routine occurrences / project sessions | Active / completed / archived projects | Routine templates |
| --- | --- | ---: | ---: | ---: |
| Small | 2025-01-21 | 534 / 248 / 218 | 6 / 1 / 1 | 6 |
| Medium | 2023-07-16 | 5,253 / 2,429 / 2,318 | 15 / 5 / 4 | 12 |
| Large | 2021-07-16 | 27,134 / 11,388 / 11,478 | 30 / 9 / 9 | 24 |
| Medium with more projects | 2023-07-16 | 5,253 / 2,429 / 2,318 | 44 / 14 / 14 | 12 |

| Dataset | Completed | Skipped | Failed | Planned | Lifetime XP |
| --- | ---: | ---: | ---: | ---: | ---: |
| Small | 753 | 120 | 80 | 47 | 10,407 |
| Medium | 7,558 | 1,185 | 936 | 321 | 104,608 |
| Large | 37,808 | 5,927 | 4,903 | 1,362 | 525,248 |
| Medium with more projects | 7,558 | 1,185 | 936 | 321 | 104,608 |

## Baseline performance

Wall-clock milliseconds are shown as first invocation / warmed median /
warmed P95. Dataset sizes are 1,000, 10,000, 50,000, and 10,000 check-ins per
account, respectively. The last profile varies project count at the same
activity volume.

| Operation | Small | Medium | Large | Medium with more projects |
| --- | ---: | ---: | ---: | ---: |
| Planner calendar | 55.0 / 6.7 / 8.1 | 68.6 / 18.8 / 20.7 | 79.5 / 63.3 / 102.1 | 33.2 / 19.8 / 57.6 |
| Monthly Checklist | 65.2 / 56.4 / 63.8 | 241.8 / 213.5 / 281.8 | 912.9 / 698.1 / 763.8 | 236.0 / 230.9 / 291.2 |
| Summary | 20.8 / 8.5 / 10.0 | 35.0 / 28.1 / 29.7 | 187.2 / 126.8 / 172.1 | 37.4 / 29.2 / 31.5 |
| Habit Analytics (30 days) | 56.7 / 32.9 / 36.3 | 70.7 / 62.3 / 118.9 | 235.2 / 215.2 / 239.3 | 76.5 / 65.6 / 110.9 |
| Habit Analytics (365 days) | 111.3 / 73.5 / 120.0 | 334.6 / 414.9 / 576.1 | 1,248.7 / 1,235.6 / 1,473.3 | 450.1 / 431.6 / 484.6 |
| Habit Analytics (Work, projects, 365 days) | 49.5 / 49.0 / 89.1 | 370.8 / 276.2 / 367.6 | 795.0 / 818.3 / 884.4 | 267.5 / 268.4 / 328.0 |
| Project portfolio | 28.0 / 23.0 / 27.3 | 175.5 / 132.1 / 170.3 | 625.5 / 658.4 / 675.1 | 245.8 / 251.4 / 260.6 |
| Project progress and forecast | 10.0 / 11.3 / 15.3 | 22.5 / 21.7 / 23.3 | 52.3 / 51.4 / 53.6 | 16.7 / 16.1 / 18.0 |
| Character Profile | 57.0 / 56.1 / 114.2 | 536.7 / 543.5 / 680.8 | 2,735.2 / 2,708.6 / 3,001.0 | 556.3 / 546.6 / 574.8 |
| Routine performance and streaks | 34.8 / 35.7 / 61.3 | 57.7 / 57.4 / 101.1 | 158.9 / 156.0 / 208.3 | 56.7 / 57.8 / 99.3 |

Each cell below shows warmed SQL statements / the operation's returned
workload indicator. SQL counts were stable across the 25 repetitions.

| Operation | Small | Medium | Large | Medium with more projects |
| --- | ---: | ---: | ---: | ---: |
| Planner calendar (scheduled entries) | 2 / 55 | 2 / 279 | 3 / 842 | 2 / 279 |
| Monthly Checklist (matrix rows) | 54 / 41 | 263 / 174 | 790 / 496 | 263 / 214 |
| Summary (total due to date) | 3 / 975 | 3 / 9,874 | 3 / 49,620 | 3 / 9,874 |
| Habit Analytics (30 days) (period check-ins) | 2 / 54 | 2 / 270 | 2 / 815 | 2 / 270 |
| Habit Analytics (365 days) (period check-ins) | 2 / 657 | 2 / 3,288 | 2 / 9,918 | 2 / 3,288 |
| Habit Analytics (Work, projects, 365 days) (matching check-ins) | 1 / 35 | 1 / 159 | 1 / 472 | 1 / 158 |
| Project portfolio (included projects) | 15 / 7 | 41 / 20 | 79 / 39 | 117 / 58 |
| Project progress and forecast (linked sessions) | 8 / 28 | 8 / 97 | 8 / 240 | 8 / 33 |
| Character Profile (completed check-ins) | 3 / 753 | 3 / 7,558 | 3 / 37,808 | 3 / 7,558 |
| Routine performance and streaks (routine rows) | 2 / 6 | 2 / 12 | 2 / 24 | 2 / 12 |

Baseline peak Python allocations in MiB, from separate traced invocations.

| Operation | Small | Medium | Large | Medium with more projects |
| --- | ---: | ---: | ---: | ---: |
| Planner calendar | 0.30 | 1.45 | 3.61 | 1.33 |
| Monthly Checklist | 0.71 | 3.06 | 8.94 | 3.61 |
| Summary | 0.11 | 0.57 | 2.62 | 0.57 |
| Habit Analytics (30 days) | 0.40 | 1.92 | 6.98 | 1.94 |
| Habit Analytics (365 days) | 3.09 | 21.98 | 67.52 | 21.98 |
| Habit Analytics (Work, projects, 365 days) | 3.09 | 21.98 | 67.52 | 22.06 |
| Project portfolio | 0.16 | 0.62 | 2.11 | 0.54 |
| Project progress and forecast | 0.12 | 0.35 | 0.78 | 0.14 |
| Character Profile | 3.19 | 33.51 | 171.82 | 33.51 |
| Routine performance and streaks | 0.41 | 1.92 | 6.97 | 1.92 |

## Confirmed bottlenecks and execution plans

- **Monthly Checklist.** Its 790 large-profile statements came from checking
  for an existing scheduled-day check-in on every applicable quest. PostgreSQL
  returned 788 quest rows with an estimate of 25,839. The bulk check-in read
  already used `uq_quest_checkin_date`. The change uses that read to identify
  genuinely missing check-ins and keeps the existing creation path for those.
- **Project portfolio.** At 10,000 check-ins, raising the project count from 24
  to 72 with the same total project-session count increased included projects
  from 20 to 58 and statements from 41 to 117. A large-profile per-project quest
  plan took 7.2 ms and returned 239 rows. It used `ix_quests_user_id` and then
  filtered by project. The change reads quests and check-ins in batches and
  applies the same single-project calculation to each group.
- **Character Profile.** The extra quest query returned 50,000 rows in 19.6 ms
  in PostgreSQL, while the check-in join returned 50,000 in 57.2 ms. The end-to-end
  baseline was 2.71 s, consistent with substantial work in transferring and
  hydrating full histories. The quest-only query now runs only when the account
  has no check-ins. Lifetime and weekly XP, levels, stats, and completion use the
  same inputs and formulas as before.
- **Habit Analytics.** The large 365-day SQL query returned 19,946 rows
  (estimate 19,693) in 48.6 ms, with owner-indexed activity scans and hash joins.
  The streak query processed 11,296 prior occurrences (estimate 5,673) in
  23.1 ms. The Work/project filter emitted 472 reporting-period rows after
  loading the same broad activity window in the application. Both 365-day
  paths peaked at 67.52 MiB. Materializing relationship graphs and building
  DataFrames contribute to the remaining latency. Filtering earlier must keep
  both comparison windows, the unfiltered weekly pulse, full-history streaks,
  and account-scoped legacy fallback.
- **Planner and indexes.** The main planner query estimated 25,966 rows and
  returned 842 in 21.6 ms using owner and related indexes. Check-in lookups
  also used the composite quest/date key. Small lookup tables used sequential
  scans. The estimates identify areas for more plan testing with different
  activity distributions. This review's proven changes address query fan-out
  and redundant reads without a schema change. Any proposed date or project
  index needs a separate comparison of plans, write overhead, and storage.

## Before and after

The same runner and profile definitions were used in both runs. All 40 result
fingerprints and workload indicators matched, one per operation across ten
operations and four dataset profiles. The planner fingerprint covers
visible quest IDs and check-in states. Other fingerprints cover the returned
service payload, including DataFrame contents.

| Operation | Check-ins per account | Median ms | P95 ms | SQL | Peak MiB |
| --- | ---: | ---: | ---: | ---: | ---: |
| Monthly Checklist | 1,000 | 56.4 → 10.7 | 63.8 → 11.6 | 54 → 2 | 0.71 → 0.68 |
| Monthly Checklist | 10,000 | 213.5 → 30.1 | 281.8 → 71.6 | 263 → 2 | 3.06 → 2.94 |
| Monthly Checklist | 50,000 | 698.1 → 118.8 | 763.8 → 145.7 | 790 → 2 | 8.94 → 8.65 |
| Monthly Checklist | 10,000 / 72 projects | 230.9 → 32.8 | 291.2 → 76.8 | 263 → 2 | 3.61 → 3.56 |
| Project portfolio | 1,000 | 23.0 → 9.9 | 27.3 → 11.3 | 15 → 3 | 0.16 → 0.50 |
| Project portfolio | 10,000 | 132.1 → 58.9 | 170.3 → 102.9 | 41 → 3 | 0.62 → 4.91 |
| Project portfolio | 50,000 | 658.4 → 342.1 | 675.1 → 392.2 | 79 → 3 | 2.11 → 25.14 |
| Project portfolio | 10,000 / 72 projects | 251.4 → 51.8 | 260.6 → 91.8 | 117 → 3 | 0.54 → 5.20 |
| Character Profile | 1,000 | 56.1 → 34.1 | 114.2 → 74.6 | 3 → 2 | 3.19 → 2.81 |
| Character Profile | 10,000 | 543.5 → 402.1 | 680.8 → 813.5 | 3 → 2 | 33.51 → 28.30 |
| Character Profile | 50,000 | 2,708.6 → 1,965.5 | 3,001.0 → 2,160.0 | 3 → 2 | 171.82 → 144.56 |
| Character Profile | 10,000 / 72 projects | 546.6 → 391.6 | 574.8 → 424.2 | 3 → 2 | 33.51 → 28.30 |

Portfolio batches reduced round trips but retain the selected project inputs
in memory together. On the large profile the scoped check-in query joined
9,326 rows in 21.9 ms (estimate 4,588), and the batched quest read returned
9,326 in 9.2 ms. Peak Python allocation rose from 2.11 to 25.14 MiB. Profile
medians fell at every size. The medium-profile P95 rose in this run despite
the lower median and stable two-statement count.

### Legacy first read

The medium scenario adds 24 scheduled legacy tasks without check-ins for each
service. Each first call created exactly 24 rows. The next call used that
resulting state. Times below are single observations, in milliseconds.

| Service | First ms, before → after | First SQL | Next ms, before → after | Next SQL |
| --- | ---: | ---: | ---: | ---: |
| Summary | 140.7 → 131.4 | 99 → 99 | 27.6 → 75.1 | 3 → 3 |
| Monthly Checklist | 789.7 → 634.6 | 691 → 407 | 301.3 → 32.4 | 311 → 2 |

A disposable PostgreSQL probe synchronized two Summary reads just before
inserting the same legacy check-in. One completed, and one got unique-constraint
error `23505`. The database retained one planned row with zero XP. A fresh
read succeeded. The compatibility write still needs a retry when that race occurs.

This is a targeted `v1.0.0` release gate. Add a focused PostgreSQL concurrency
regression and make the legacy backfill safe for concurrent Summary and Monthly
Checklist reads before release. Both reads should succeed and leave exactly one
account-scoped planned check-in with zero XP while preserving existing statuses
and XP. [Release roadmap](roadmap.md)

## Architecture findings

| Area | Responsibilities and maintenance implications |
| --- | --- |
| Analytics | The service validates filters, loads scoped activity, and builds DataFrame payloads. Most aggregation helpers can be tested with supplied rows. SQL, orchestration, and chart-ready transforms share one module, which makes cross-cutting edits risky when they also touch legacy fallback or date semantics. The tests already exercise period boundaries, unfiltered weekly pulse, full-history streaks, and XP. Keep that coverage before reorganizing transforms. |
| Summary and Checklist | Summary already uses database-side aggregation and limits hydrated rows to today's and overdue work. Both services retain compatibility writes for scheduled legacy quests without check-ins. Each missing row uses its own transaction. The unique quest/date constraint prevents duplicates. The reproduced first-read conflict is tracked separately as a pre-release fix. |
| Projects | The portfolio, single-project progress, and forecast share the same effort and XP rules. The scheduler delegates locking and row access to `goal_session_data.py` and keeps preview separate from the transactional write. A project Workspace render still makes separate progress and forecast calls, and forecast may re-read linked data. This path is distinct from portfolio batching. |
| Planner and routines | `schedule_service.py` is a calendar helper. Quest and routine services own writes, recurrence rules, and occurrence generation. Planner bounds its visible date range but loads all check-ins for each matching quest. The benchmark uses one check-in per quest, so it leaves open the cost on a long multi-check-in legacy quest. Routine lifecycle history in the management tab has a per-occurrence read loop. The timed routine operation is the Habit Analytics view and includes streaks. |
| Call sites and reruns | Planner and the Projects & Routines workspace gate expensive work on the active tab. Habit Analytics builds its payload once per rerun and uses the same result for the active tab. Summary reuses today's results and adds a read only when reviewing a different date. Profile fetches once per rerun. The review keeps account and guest data out of global caches. |
| Compatibility | Ripgrep call-site review found the old dashboard and calendar helpers in tests, while the UI calls Summary and the bounded Planner API. The old progress-dataset wrapper is also test-covered, and goal session backfilling is still used by SQLite import. Removing these paths would need a separate compatibility decision. |

The targeted changes keep the existing page-to-service-to-database flow and
the pure calculations in use. A future refactor could extract related
analytics transforms behind the existing public functions when changes
repeatedly need to touch the same metric families. The 1,442-line analytics
module's responsibilities and test coverage give clearer refactoring criteria
than its size.

## Deferred work and limitations

- Profile the row projection and Python aggregation of the 365-day Habit
  Analytics response and of very long Character Profile histories. Use cases
  with disjoint weeks, previous-period-only data, and legacy fallback to
  preserve current semantics when testing an earlier filter.
- Retest Planner and Checklist plans with uneven account sizes and multiple
  check-ins per quest before proposing an index or changing date predicates.
  Measure routine lifecycle history and just the shared progress/forecast
  inputs separately before changing those paths.
- Phase 6 will verify hosted process memory and representative concurrent-session
  behavior with authorized synthetic accounts and guest sessions. Record the
  available process RSS or platform memory metric, response behavior and
  connection usage, and verify session isolation. The local benchmarks cover
  service calls under a single worker.

## Correctness and release verification

The two new regressions bound steady-state Checklist and portfolio statement
counts and assert statuses, effort, and XP. The extended Profile regression
asserts two statements when check-ins exist. Existing tests cover the legacy
fallback, analytics date and filter semantics, account and guest isolation,
and PostgreSQL concurrency and migrations.

| Local check | Passed | Failed | Skipped |
| --- | ---: | ---: | ---: |
| Full pytest with disposable PostgreSQL 18.3 | 394 | 0 | 0 |
| Full pytest without `TEST_POSTGRESQL_URL` | 376 | 0 | 18 |
| Explicit CI integration selection | 26 | 0 | 0 |

The existing CI JUnit guard verified all 18 required PostgreSQL cases locally.
`compileall` and `git diff --check` passed. Phase 5 awaits its published CI run.

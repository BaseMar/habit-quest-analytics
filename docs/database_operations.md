# Database operations and recovery

## Setup and migrations

1. Use a dedicated PostgreSQL database for Habit Quest Analytics and a separate,
   disposable database for tests and restore rehearsals. Keep `DATABASE_URL`
   and `TEST_POSTGRESQL_URL` separate. Before a maintenance command, verify the
   host and project, then confirm the database and role with `psql -c 'SELECT
   current_database(), current_user;'` using the same target. Keep connection
   strings and passwords out of command history, logs, and Git.
2. Use an authorized maintenance role that can create and alter the app schema,
   lock its tables, reset identity columns, and read and write all app rows under
   RLS. A full logical backup needs read access to all app rows and sequences.
   A restore role needs permission to create the archived objects in the target.
   Keep maintenance credentials separate from the app's trusted server role where
   possible. Keep the app's PostgreSQL credentials server-side.
3. Before upgrading an existing database, stop app writers, capture a backup,
   and verify that it restores in isolation. Check the current revision against
   the intended release and apply the migrations from that release checkout.

```bash
python -m alembic heads
python -m alembic current
python -m alembic upgrade head
python -m alembic current
python -m alembic check
```

`DATABASE_URL` comes from the shell for these commands. The current chain is
`0001` (baseline) → `0002` (accounts and ownership). `alembic check` compares
supported schema objects against the current models. Verify RLS flags, policies,
and grants separately. See the [data model](data_model.md) for ownership rules.

## Connections and diagnostics

- The app normalizes `postgres://` and `postgresql://` to the Psycopg SQLAlchemy
  driver and preserves connection parameters, including SSL. For Supabase, use
  a direct connection where reachable, or the shared session pooler from an
  IPv4-only host. Prefer direct for maintenance and verify any session-pooler
  fallback in staging. The shared transaction pooler is unsuitable with the
  current default Psycopg prepared statement behavior. For hosted use, verify TLS
  using `sslmode=verify-full` and the appropriate CA. [Supabase connection modes and TLS](https://supabase.com/docs/guides/database/connecting-to-postgres) · [Psycopg prepared statements](https://www.psycopg.org/psycopg3/docs/advanced/prepare.html)
- Authenticated sessions share a process-level SQLAlchemy engine. The default
  queue pool keeps up to five connections and allows ten more during bursts.
  Service-owned sessions close at the end of the operation. Pool checkout
  checks for stale connections with `pool_pre_ping`. An interrupted transaction
  still fails. Verify hosted connection limits and observe usage and checkout
  errors under representative concurrent sessions before tuning the pool.
  [SQLAlchemy connection pooling](https://docs.sqlalchemy.org/en/20/core/pooling.html#connection-pool-configuration)
- RLS with no policies blocks ordinary roles. The trusted server role may
  bypass RLS as owner or through elevated privileges, so application access
  depends on account-scoped sessions and ownership constraints. Confirm the
  actual hosted roles, grants, and RLS behavior before release. The engine hides
  SQLAlchemy-bound parameters and sign-in logs the error class and SQLSTATE.
  PostgreSQL error details and maintenance CLI output can still contain row
  values. Review and redact diagnostics before sharing them.

## Back up and verify a restore

For a standalone PostgreSQL rehearsal, point the PostgreSQL client environment
(`PGHOST`, `PGPORT`, `PGUSER`, TLS settings, and credentials from a safe source)
to a disposable server. Create `habit_quest_restore` as a fresh, empty database.
Use a `pg_dump` client that supports the source server's major version and
rehearse on the intended restore version. Run the commands with synthetic data.

```bash
pg_dump --format=custom --no-owner --no-privileges \
  --file=habit_quest.dump --dbname=habit_quest_source
pg_restore --exit-on-error --single-transaction --no-owner --no-privileges \
  --dbname=habit_quest_restore habit_quest.dump
```

The archive includes schema, rows, sequence state, and `alembic_version`. Restore
into an empty database before running Alembic. The restore assigns object
ownership to the restore role and skips source grants. Review target role
memberships, object ownership, RLS, and grants before exposure. Store authorized
backup files encrypted with restricted access. Back up `data/uploads/` separately
if the deployment relies on local avatar files. [PostgreSQL `pg_dump`](https://www.postgresql.org/docs/18/app-pgdump.html) · [PostgreSQL `pg_restore`](https://www.postgresql.org/docs/18/app-pgrestore.html)

Point `DATABASE_URL` to the disposable restore. Check `alembic current` against
the source revision and run `alembic check` from the matching checkout. Compare
row counts, sample IDs and foreign keys, assigned and unassigned ownership,
check-in statuses and XP, and profile data. Verify that a new insert gets an ID
above restored IDs, and that RLS and account isolation work with the intended
roles. Verify any separate avatar restore. Upgrade a restored copy first when
rehearsing a migration.

For Supabase, determine which daily backups, retention, restore targets, and
optional point-in-time recovery the actual project has. If managed recovery is
unavailable, establish an authorized logical backup procedure for the project.
Follow the provider's instructions for managed schemas and roles. A database
restore can require downtime and does not restore avatar files, secrets, or
Storage API object contents. [Supabase database backups](https://supabase.com/docs/guides/platform/backups) · [Supabase CLI backup and restore](https://supabase.com/docs/guides/platform/migrating-within-supabase/backup-restore)

## Import a single-user SQLite backup

1. Stop legacy writers and keep a separate SQLite backup made with SQLite's
   `.backup` command or backup API so committed WAL data is included. Rehearse
   against a fresh PostgreSQL destination at Alembic head. All app tables must
   be empty, including `user_accounts`. Run the import before signing in or
   running the legacy seed command.
2. Run `python -m src.database.import_sqlite path/to/legacy.db`. The source
   opens read-only and the importer upgrades a temporary SQLite backup snapshot.
   It accepts the known older table and column shapes listed in the
   [data model](data_model.md#sqlite-import-compatibility). Existing tables need
   compatible columns and valid relationships. Missing histories stay empty,
   and existing numbered sessions keep their numbers. Imported IDs must leave
   room for the next value in the target integer identity. The tool copies one
   legacy dataset and leaves its rows unassigned. Google identities and account
   merges are outside its scope. Avatar paths are retained, so move the files separately.
3. Verify the reported counts, IDs, historical check-ins and XP, and numbering
   before opening sign-in. Let the intended owner sign in once with verified
   Google credentials and leave that account at its defaults. Confirm exactly
   one account matches the known owner email. Then run
   `python -m src.database.claim_legacy --email 'owner@example.invalid'` with
   the authorized maintenance connection. The command assigns all unowned app
   rows to that account together. An unknown or ambiguous email, multiple legacy
   profiles, or existing custom data on the target account requires operator
   review. Check the new owner can see the records and another account cannot.

The importer locks app tables across the empty check, inserts, and identity
restarts. A failed copy rolls back both inserted rows and transactional `RESTART`
changes. With a lost connection or uncertain commit, inspect revision, counts,
and identity state before retrying. Retrying a completed import into the same
database is rejected. [PostgreSQL sequence restart semantics](https://www.postgresql.org/docs/18/sql-altersequence.html)

## Recover from a failed operation

Keep writers stopped and record the target, release, revision, and redacted error.
Check `alembic current` and compare the schema and representative data against
the pre-operation evidence. For a rolled-back import, correct the source or
target issue and retry only after confirming the target is empty. For a failed
upgrade, fix the verified cause and re-run against a restored copy first. If
state or data integrity is uncertain, restore the last known-good backup into a
separate database, verify it, and obtain approval before switching the app. An
Alembic stamp changes revision metadata without applying schema changes.

Production recovery uses a verified restore or forward repair. `0002` refuses a
downgrade while account rows exist. Even with no accounts, going back to `0001`
leaves RLS enabled on surviving tables, which differs from a fresh `0001` schema.
Downgrading `0001` to `base` drops the application tables and their data. Treat
these downgrade paths as unsupported for production recovery.

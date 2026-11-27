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

### Streamlit Community Cloud TLS

The production Supabase Free project runs PostgreSQL 17.12 and uses the
Session Pooler on port `5432` with SSL Enforcement enabled. The deployed
configuration verifies the certificate chain and Session Pooler hostname
using the [public Supabase CA](../certs/prod-ca-2021.crt). The operator
confirmed Google sign-in, database-backed reads and writes, and Guest Demo
after deployment.

```text
sslmode=verify-full&sslrootcert=certs/prod-ca-2021.crt
```

1. Publish the CA file to the branch deployed by Community Cloud. Community
   Cloud starts the app from the repository root, so the relative path is
   correct even when the entry point is in a subdirectory. Use forward slashes
   and start local commands from the repository root when using this path.
   [Streamlit Community Cloud file organization](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/file-organization)
2. In Community Cloud Secrets, have the authorized operator replace the
   existing `sslmode` and set `sslrootcert` in the top-level `DATABASE_URL`.
   Keep the exact Session Pooler hostname from Supabase's **Connect** panel,
   port `5432`, and the other connection fields. Use `?` for the first URL
   query parameter and `&` between parameters. The app passes both TLS
   parameters through to Psycopg. [Supabase Session Pooler TLS example](https://supabase.com/docs/guides/database/psql) · [PostgreSQL TLS parameters](https://www.postgresql.org/docs/18/libpq-ssl.html)
3. Reboot the app to start with fresh database connections. Sign in with an
   authorized test account and open a database-backed page. Repeat the Guest
   Demo smoke test separately. The guest demo uses SQLite, so it verifies
   guest availability. Record the hosted PostgreSQL verification against the
   deployed revision and keep any diagnostics free of connection secrets.

The bundled root is valid until **2031-04-26 10:56:53 UTC**. Track expiration
and Supabase CA rotation notices, and replace the certificate before expiry
or when Supabase announces a replacement. Download the successor from the
project's **Database Settings** in the official dashboard. Verify its CA
constraints, validity dates, and SHA-256 fingerprint before publishing.
Deploy the replacement and repeat the authenticated smoke test with
`verify-full` enabled. If the path changes, update `sslrootcert` in Secrets
with the deployment. [Supabase SSL Enforcement](https://supabase.com/docs/guides/platform/ssl-enforcement)

### Hosted database access

The Data API is disabled, and the application connects directly through
the Session Pooler as `postgres`. All ten application tables have RLS
enabled without policies or FORCE RLS. The privileged runtime role relies
on `UserSession` for account scoping and on database ownership constraints
for relationship integrity. Existing API-role grants and separation of
runtime and maintenance roles remain release follow-ups. Disabling the
Data API leaves the grants in place.

## Back up and verify a restore

### Production logical backup

From the repository root, use the Session Pooler endpoint from the official
dashboard and an approved backup role that can read all selected rows and
sequences. Set the placeholders below with the approved host, role, database,
and destination. Use an interactive password prompt. The table selection
covers the ten application tables and `alembic_version` and leaves provider
schemas outside the archive. Refresh the allowlist when migrations add tables.

```powershell
$poolerHost = '<session-pooler-host>'
$backupRole = '<approved-backup-role>'
$database = '<database-name>'
$archive = '<protected-backup-location>'
$tables = @(
    'public.achievements', 'public.alembic_version', 'public.categories',
    'public.goals', 'public.player_profiles', 'public.quest_checkins',
    'public.quests', 'public.recurring_habit_instances', 'public.recurring_habits',
    'public.unlocked_achievements', 'public.user_accounts'
)
$tableArgs = @($tables | ForEach-Object { "--table=$_" })
$env:PGSSLMODE = 'verify-full'
$env:PGSSLROOTCERT = (Resolve-Path -LiteralPath 'certs/prod-ca-2021.crt').Path
pg_dump --host=$poolerHost --port=5432 --username=$backupRole --dbname=$database `
    --password --format=custom --no-privileges --quote-all-identifiers --strict-names `
    @tableArgs --file=$archive
if ($LASTEXITCODE -ne 0) { throw 'Logical backup failed.' }
Get-FileHash -LiteralPath $archive -Algorithm SHA256
```

Record the SHA-256, size, timestamp, versions, and table inventory in a
restricted backup manifest. Verify the hash after copying and immediately
before restoration. Encrypt the archive and any restored data at rest, restrict
access to authorized operators, and keep an encrypted off-site copy. Keep
archives, plaintext exports, connection secrets, and raw diagnostics outside
Git. [PostgreSQL `pg_dump`](https://www.postgresql.org/docs/18/app-pgdump.html)

Supabase Free has no managed daily backups or point-in-time recovery. For
this project, take a logical backup daily while production data is changing
and immediately before migrations or bulk changes. Start with seven daily
and four weekly copies, and adjust the schedule to the agreed recovery point
and retention requirements. Rehearse restoration periodically and after
changing the backup tool, database version, or table selection. [Supabase Free backups](https://supabase.com/kb/faqs/platform/free-plan-backups)

### Restore to an isolated server

Use a supported PostgreSQL release and current minor patches for both client
and server. The `pg_dump` major version must support the source. For a new
export from PostgreSQL 17.12, use a patched 17.12 or 18.7 client and rehearse
with a patched 18.7 destination. Use the current minor release for the
chosen supported major version as new fixes are released.
[PostgreSQL versioning policy](https://www.postgresql.org/support/versioning/) · [PostgreSQL `pg_dump`](https://www.postgresql.org/docs/18/app-pgdump.html)

Create a fresh `habit_quest_restore` database on a separate loopback-only
server with a distinct port, a disposable restore role, and SCRAM
authentication. Verify the binary version and the archive hash from the
manifest, check the archive inventory with `pg_restore --list`, and confirm
the destination has no user tables. Set `$restorePort` and `$restoreRole`
for this isolated instance. Use the matching patched `pg_restore` client.

```powershell
pg_restore --host=127.0.0.1 --port=$restorePort --username=$restoreRole `
    --dbname=habit_quest_restore --password --single-transaction --exit-on-error `
    --no-owner --no-privileges $archive
if ($LASTEXITCODE -ne 0) { throw 'Restore failed. Verify the target before retrying.' }
```

Run the restore in a private terminal and keep raw output out of shared logs.
The destination role owns the restored objects because of `--no-owner`.
`--no-privileges` skips grants, and this table-scoped archive omits source
roles, provider configuration, avatar files, and secrets. Back up avatar
files separately if needed. Review privileges separately before any restored
database is exposed. [PostgreSQL `pg_restore`](https://www.postgresql.org/docs/18/app-pgrestore.html)

On November 27, 2026, the original custom-format archive from Supabase
PostgreSQL 17.12, exported by `pg_dump` 18.3, failed to restore on 18.3.
The older client emitted the newer internal `pg_attver` attribute option.
The older server rejected it and the single transaction rolled back. A
catalog check confirmed the failed destination was empty. The original
archive kept its SHA-256 and restored successfully on PostgreSQL 18.7 with
exit code 0. [PostgreSQL 17.12 release notes](https://www.postgresql.org/docs/release/17.12/) · [PostgreSQL 18.7 release notes](https://www.postgresql.org/docs/18/release-18-7.html) · [PostgreSQL source change](https://www.postgresql.org/message-id/E1xQQFr-000000003OT-3txh%40gemulon.postgresql.org)

### Verify the restored copy

1. Confirm the exact local server and authenticate in a private terminal.
   Use a read-only transaction. Verify the 11 expected tables, local owners,
   validated primary, unique, check, and foreign-key constraints, and valid
   indexes. Run `alembic heads`, inspect the current revision, and run
   `alembic check` with an explicit restore-only connection.
2. Compare aggregate row counts, full-row fingerprints and primary keys,
   ownership including unassigned legacy rows, check-in statuses and XP, and
   profile and project, routine, and achievement relationships against the
   archive or a trusted export manifest. Derive the archive comparison in
   memory and keep individual rows and identifiers out of reports. Archive
   agreement verifies the backup snapshot. Live production counts require
   independent source-side evidence.
3. Compare each archived sequence state with restored `last_value` and
   `is_called`. Derive the next ID from that state and the increment, then
   compare it with the highest existing key. Actual inserts for identity
   testing belong in a separate authorized copy because a rollback can
   leave a sequence advanced. [PostgreSQL sequence functions](https://www.postgresql.org/docs/18/functions-sequence.html)
4. Verify RLS flags and policies as catalog metadata. In the read-only
   transaction, test the existing PostgreSQL `pg_read_all_data` role with
   `SET LOCAL ROLE`. Verify that the restore owner can read through its
   privileges and the non-bypass role is subject to RLS. Check application
   isolation separately through account-scoped `UserSession` reads. Keep
   role changes and grant experiments for a separate synthetic environment.
   [PostgreSQL predefined roles](https://www.postgresql.org/docs/18/predefined-roles.html)

The rehearsal passed these checks after restarting the isolated 18.7
instance. PostgreSQL reported all 11 tables with the intended restore owner,
33 valid indexes, and validated constraints. Alembic current and head were
`0002`, and `alembic check` reported no drift. Row counts, primary keys and
full-row fingerprints matched the archive for every table. The checks found
no orphans or same-owner mismatches, and all ten identity sequences matched
the archive and passed the next-ID calculation. The role with
`pg_read_all_data` privileges saw no rows in the ten RLS-enabled tables.
Separate `UserSession` checks matched the expected keys for each restored
account and returned an empty result for a nonexistent account.

After review, stop the isolated instance with `pg_ctl` against its exact data
directory. With operator approval, dispose of the restored production data
according to the encrypted-storage retention policy. Retain the original
archive according to its backup schedule.

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

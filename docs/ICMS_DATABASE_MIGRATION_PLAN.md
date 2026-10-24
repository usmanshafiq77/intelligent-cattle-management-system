# ICMS Controlled Database Migration Plan

Prepared: 2026-10-23 (Asia/Karachi)
Protected database: `icms_db` on `localhost:5432`, schema `public`
Current revision: `a8b3c4d5e6f7`
Explicit target revision: `c8d0e1f2a703`
Execution status: **NOT AUTHORIZED / NOT EXECUTED**

## Decision

The migration is technically ready for a controlled maintenance window, subject to explicit owner approval and the preconditions below. Do not use `alembic upgrade head`; the reviewed operation targets `c8d0e1f2a703` explicitly.

The protected database was inspected read-only and remains unchanged. The protected GUI schema `icms_test_gui_20261017103146_ca6015f2` was not used or modified.

## Verified source state

- PostgreSQL server and client tools: 18.6.
- Connected database/user/schema: `icms_db` / `icms_app` / `public`.
- Database owner: `icms_app`; role does not have `CREATEDB`.
- Search path: `"$user", public`.
- Alembic revision: `a8b3c4d5e6f7`.
- Physical tables: 27, including `alembic_version`.
- Aggregate records: 2 users, 2 farms, 2 farm memberships, 37 permissions.
- Cattle, health, vaccination, and milk production tables are present. Their current business-record counts are zero.
- Invalid indexes: zero. Unvalidated constraints: zero.
- `users.token_version`, `password_reset_tokens`, and feed/nutrition tables are absent, as expected at `a8`.

No email addresses, password hashes, tokens, secrets, or other account details were printed during inspection.

## Reviewed migration chain

The Alembic history is linear:

1. `a8b3c4d5e6f7` — current milk-production revision.
2. `b7c9d2e4f601` — password-reset security; depends on `a8`.
3. `c8d0e1f2a703` — feed and nutrition management; depends on `b7` and is the single current head.

Application code expects `c8d0e1f2a703`. `/api/v1/health/db` returns 503 when the database revision differs. The latest application must therefore remain stopped or unavailable until migration and smoke testing finish.

## Pending operations and compatibility

### `b7c9d2e4f601`

- Adds `users.token_version INTEGER NOT NULL DEFAULT 0`.
- Creates `password_reset_tokens` with its foreign key, unique token-hash constraint, user index, and one-active-token partial unique index.
- Does not update or delete existing business rows.

### `c8d0e1f2a703`

- Adds six PostgreSQL enum types.
- Adds seven granular feed permissions while preserving the existing `feed.view` and `feed.manage` permissions.
- Creates `feed_items`, `feed_stock_movements`, `feeding_schedules`, `feed_consumption_records`, `nutrition_plans`, and `nutrition_plan_items` with farm-scoped foreign keys, checks, uniqueness constraints, and indexes.
- Does not update or delete existing user, farm, membership, cattle, health, vaccination, or milk rows.

Both upgrades are additive and backward-compatible with the old application schema. The new application is not fully compatible with `a8`: authentication models expect `users.token_version`, and feed routes require the new tables.

Downgrades are destructive to newly created state. Downgrading `c8` deletes feed/nutrition data and its seven permissions; downgrading `b7` deletes reset tokens and JWT invalidation state. Prefer restore-based recovery once traffic resumes.

## Verified backup

- Archive: `D:\ICMS_Project\backups\icms_db_20261023_171259_598.dump`
- Format: PostgreSQL custom archive, `--no-owner --no-privileges`.
- Size: 108,454 bytes.
- SHA-256: `7FA3F9E84BD21C93E2B42D72E06B404BCFF27D5FB5E9C48D1E93DCB135F73527`.
- Archive catalog: readable by `pg_restore --list`; 246 catalog lines.
- Source revision restored from archive: `a8b3c4d5e6f7`.
- Restored table count: 27.
- Existing backups were not overwritten or deleted.

The archive is on the same host as the database. Copy it to approved encrypted off-host storage before treating it as a production-grade disaster-recovery copy. If any writes occur after this timestamp, stop writes and create another uniquely named backup during the maintenance window.

## Isolated restore and migration rehearsal

The named archive was restored into a new `test_restore_feed_<uuid>` schema inside `icms_test`. The restore schema was distinct from the protected GUI schema and was removed after verification.

Verified sequence:

1. Restore at `a8b3c4d5e6f7` with 27 tables.
2. Upgrade explicitly through `b7c9d2e4f601` to `c8d0e1f2a703`.
3. Confirm 34 physical tables and ORM/Alembic metadata parity.
4. Confirm all 26 pre-existing application-table row counts were preserved; permissions increased only by the expected seven rows.
5. Confirm user, farm, and membership ID fingerprints were unchanged.
6. Confirm existing users received non-null `token_version = 0`.
7. Confirm reset-token and all feed tables existed and began empty.
8. Confirm no invalid indexes, unvalidated constraints, orphan memberships, or orphan cattle.
9. Re-run the same target upgrade and confirm it was a no-op.
10. Downgrade only the disposable restore to `a8`, confirm original counts, and re-upgrade successfully to `c8`.

The application role cannot create a separate database, so the rehearsal used an isolated test schema. A separate-database restore remains recommended for a full disaster-recovery drill because it additionally validates database creation, ownership, and database-level grants.

## Application compatibility evidence

- Backend: 236 tests passed, including registration, login, verification, password reset, JWT invalidation, farms, memberships, RBAC, cattle, health, vaccination, milk, feed management, concurrency, migrations, and cross-farm isolation.
- Outbound email: forced to `memory`; no real messages were sent.
- Frontend: 303 Jest tests and 13 structure/design checks passed.
- Expo web production export: passed, 915 modules bundled.
- Reviewed API contract: 79 paths, 108 operations.
- Frontend API configuration rejects credential-bearing URLs, requires HTTPS in production, and appends `/api/v1` through the API client contract.

## Preconditions for the maintenance window

1. Obtain explicit approval for `icms_db: a8b3c4d5e6f7 -> c8d0e1f2a703` and the named backup/recovery plan.
2. Schedule 10–15 minutes of maintenance; block API writes and background jobs.
3. Keep the latest backend stopped. Confirm no process is writing to `icms_db`.
4. If the database changed after the verified backup, create a new non-overwriting custom-format archive and record its SHA-256.
5. Copy the accepted backup to approved encrypted off-host storage.
6. Confirm PostgreSQL 18 tools are used and the archive catalog remains readable.
7. Confirm the exact host, port, database, user, schema, current revision, and Alembic head.
8. Confirm a PostgreSQL administrator is available to create a new recovery database if restore-based recovery is needed.
9. Keep external email disabled for smoke tests unless separately approved.

## Approval-gated production procedure

Run only after explicit approval. Credentials must be supplied interactively and never embedded in commands or documentation.

```powershell
Set-Location D:\ICMS_Project

$targetHost = 'localhost'
$targetPort = 5432
$targetDatabase = 'icms_db'
$targetUser = 'icms_app'
$credential = Get-Credential -UserName $targetUser

$env:PGPASSWORD = $credential.GetNetworkCredential().Password
$env:DB_HOST = $targetHost
$env:DB_PORT = [string]$targetPort
$env:DB_NAME = $targetDatabase
$env:DB_USER = $targetUser
$env:DB_PASSWORD = $env:PGPASSWORD
```

Verify the target independently of Alembic:

```powershell
& 'C:\Program Files\PostgreSQL\18\bin\psql.exe' -X -v ON_ERROR_STOP=1 `
  -h $targetHost -p $targetPort -U $targetUser -d $targetDatabase `
  -c 'SELECT current_database(), current_user, current_schema(); SELECT version_num FROM public.alembic_version;'
```

Expected database/schema/revision: `icms_db`, `public`, `a8b3c4d5e6f7`. Stop if any value differs.

Verify the accepted backup again:

```powershell
Get-FileHash -Algorithm SHA256 `
  'D:\ICMS_Project\backups\icms_db_20261023_171259_598.dump'

& 'C:\Program Files\PostgreSQL\18\bin\pg_restore.exe' --list `
  'D:\ICMS_Project\backups\icms_db_20261023_171259_598.dump' | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Backup catalog validation failed.' }
```

Verify the checked-out Alembic chain, then execute the single reviewed target operation:

```powershell
Set-Location D:\ICMS_Project\backend
& .\.venv\Scripts\alembic.exe heads
& .\.venv\Scripts\alembic.exe current

# Approval-dependent database write:
& .\.venv\Scripts\alembic.exe upgrade c8d0e1f2a703
if ($LASTEXITCODE -ne 0) { throw 'Migration failed; keep traffic stopped.' }
```

Expected head/current before execution: head `c8d0e1f2a703`, current `a8b3c4d5e6f7`. Do not substitute `upgrade head`.

## Post-migration SQL checks

```sql
SELECT version_num FROM public.alembic_version;

SELECT column_name, is_nullable, column_default
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name = 'users'
  AND column_name = 'token_version';

SELECT to_regclass('public.password_reset_tokens'),
       to_regclass('public.feed_items'),
       to_regclass('public.feed_stock_movements'),
       to_regclass('public.feeding_schedules'),
       to_regclass('public.feed_consumption_records'),
       to_regclass('public.nutrition_plans'),
       to_regclass('public.nutrition_plan_items');

SELECT count(*) AS users_with_invalid_token_version
FROM public.users
WHERE token_version IS NULL OR token_version <> 0;

SELECT count(*) AS feed_permissions
FROM public.permissions
WHERE code IN (
  'feed.record', 'feed.inventory.manage', 'feed.schedule.manage',
  'feed.nutrition.view', 'feed.nutrition.manage',
  'feed.cost.view', 'feed.reports.view'
);

SELECT count(*) AS invalid_indexes
FROM pg_index i
JOIN pg_class t ON t.oid = i.indrelid
JOIN pg_namespace n ON n.oid = t.relnamespace
WHERE n.nspname = 'public' AND NOT i.indisvalid;

SELECT count(*) AS unvalidated_constraints
FROM pg_constraint c
JOIN pg_namespace n ON n.oid = c.connamespace
WHERE n.nspname = 'public' AND NOT c.convalidated;
```

Expected: revision `c8d0e1f2a703`, all seven new tables present, token-version check zero, feed-permission count seven, invalid indexes zero, and unvalidated constraints zero. Re-run aggregate counts for users, farms, memberships, cattle, health, vaccinations, and milk and compare them with the accepted backup snapshot.

## Application smoke tests before reopening traffic

1. Start one backend instance with external email disabled.
2. Confirm `/api/v1/health` and `/api/v1/health/db` return 200; database health must report `c8d0e1f2a703`.
3. Use a designated non-production test account: login, `/auth/me`, forgot-password enumeration-safe response, one reset, rejection of the old password/pre-reset JWT, and login with the new password.
4. Verify one controlled signup/verification flow without sending real email.
5. Verify farm selection and membership, cattle listing, health/vaccination access, milk access, feed inventory, and cross-farm denial.
6. Verify the frontend points to the intended HTTPS API and complete login/dashboard/feed navigation on web and one mobile device.
7. Re-enable traffic only after database and application checks pass.

## Failure handling

- If preflight values differ, stop without migrating.
- If Alembic fails, keep traffic stopped, capture the error and current revision, and do not stamp the database.
- PostgreSQL transactional DDL should roll back a failed transaction, but verify revision and object presence rather than assuming rollback.
- Before any new reset/feed data exists, a downgrade may be technically possible but still requires explicit authorization.
- After traffic resumes, do not downgrade. Preserve the failed database and restore the accepted backup into a newly created recovery database, validate it, then switch configuration as described in `ICMS_DATABASE_RECOVERY_PLAN.md`.

Clear temporary secrets when the window ends:

```powershell
Remove-Item Env:PGPASSWORD, Env:DB_PASSWORD -ErrorAction SilentlyContinue
```

## Remaining risks and blockers

- Production migration has not been authorized or executed.
- The latest backend cannot be activated against `a8`; readiness correctly remains unavailable until migration.
- The verified database backup is local, not an off-host encrypted copy.
- The application role owns `icms_db`; a dedicated owner/migrator/backup-role design would reduce operational risk.
- The application role lacks `CREATEDB`; an administrator is required for preferred separate-database recovery.
- Database backup does not include uploaded media. Current database inspection found zero cattle-media records, but the upload tree should still receive an independently verified archive before a broader deployment.
- Real-account credentials were not used, and no real email was sent; production smoke testing requires a designated test account and explicit email policy.

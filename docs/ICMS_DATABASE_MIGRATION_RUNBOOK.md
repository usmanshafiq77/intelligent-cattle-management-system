# ICMS Database Migration Runbook

Target transition: `a8b3c4d5e6f7 -> b7c9d2e4f601`
Protected database: `icms_db`
Status: prepared and tested; protected execution requires explicit approval

## Verified current state

- Checked-in Alembic head: `b7c9d2e4f601`.
- Protected database revision: `a8b3c4d5e6f7`.
- Protected `users.token_version`: absent.
- Protected `password_reset_tokens`: absent.
- Existing protected row counts observed read-only: 2 users and 2 farms.
- Backup: `D:\ICMS_Project\backups\icms_db_20261022_234512_743.dump`.
- Backup SHA-256: `D3AF0004F1B827DD0C41C3EEB8D7E7398BF38E2490B9246CF5A2F8FF1A796FF6`.
- Archive catalog verification: passed.
- Isolated restore verification: passed at revision `a8b3c4d5e6f7` with 27 physical tables.
- Isolated migration upgrade, downgrade, data-preservation, and re-upgrade: passed.

## Migration SQL review

Upgrade `b7c9d2e4f601` performs only additive security changes:

1. Adds `users.token_version INTEGER NOT NULL DEFAULT 0`.
2. Creates `password_reset_tokens` with UUID primary key, user foreign key, hashed token, expiry, creation, used, and revoked timestamps.
3. Adds a unique constraint on the 64-character token hash.
4. Adds an index on `user_id`.
5. Adds a partial unique index allowing only one unused, unrevoked reset token per user.
6. Uses `ON DELETE CASCADE` from reset tokens to users.

There is no update/delete of existing users, farms, memberships, cattle, health, or milk data. Existing users receive `token_version = 0` through the server default.

Downgrade is destructive to reset state: it drops both indexes, the reset-token table, and `users.token_version`. Do not use downgrade after password resets have begun unless loss of reset/session-invalidation state is explicitly accepted.

## Maintenance impact and risk

- Expected downtime: a short maintenance window, conservatively 5–10 minutes including checks and smoke tests.
- PostgreSQL must acquire DDL locks while adding the user column and creating schema objects.
- The current database is small, so the operation itself should be brief.
- Keep the API stopped or unavailable during the upgrade; readiness already returns 503 while the revision is stale.
- Do not start normal traffic between migration and smoke-test completion.

## Preflight commands

Run from PowerShell without placing a password in command history:

```powershell
Set-Location D:\ICMS_Project
$credential = Get-Credential -UserName icms_app
$env:PGPASSWORD = $credential.GetNetworkCredential().Password

powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\backup-postgres.ps1 `
  -DatabaseName icms_db `
  -DatabaseHost localhost `
  -Port 5432 `
  -DatabaseUser icms_app `
  -Destination .\backups `
  -RetentionDays 30
```

The script refuses overwrite, creates a unique timestamp, checks nonzero size, and runs `pg_restore --list`. Confirm the reported path before continuing.

Read-only revision check:

```powershell
Set-Location D:\ICMS_Project\backend
.\.venv\Scripts\alembic.exe current
.\.venv\Scripts\alembic.exe heads
```

Expected: current `a8b3c4d5e6f7`, head `b7c9d2e4f601`.

## Approval gate

Stop here until the owner explicitly approves:

- the named backup;
- this exact one-revision upgrade;
- the maintenance window;
- the recovery approach below.

## Approved upgrade commands

Only after explicit approval:

```powershell
Set-Location D:\ICMS_Project\backend
.\.venv\Scripts\alembic.exe upgrade b7c9d2e4f601
.\.venv\Scripts\alembic.exe current
```

Do not use `upgrade head` for this protected operation unless the reviewed head is re-confirmed as exactly `b7c9d2e4f601` immediately beforehand.

## Post-upgrade verification

Verify read-only:

```sql
SELECT version_num FROM alembic_version;

SELECT column_name, is_nullable, column_default
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name = 'users'
  AND column_name = 'token_version';

SELECT to_regclass('public.password_reset_tokens');

SELECT indexname, indexdef
FROM pg_indexes
WHERE schemaname = 'public'
  AND tablename = 'password_reset_tokens'
ORDER BY indexname;
```

Expected:

- Revision `b7c9d2e4f601`.
- Non-null `token_version` with default zero.
- Reset-token table present.
- Primary key, unique token hash, user index, and one-active-token partial unique index present.

Application smoke tests:

1. `/api/v1/health` returns 200.
2. `/api/v1/health/db` returns 200 and revision `b7c9d2e4f601`.
3. Existing verified user login succeeds.
4. `/auth/me` succeeds with the new JWT.
5. Forgot-password response remains enumeration-safe.
6. A controlled test account completes reset once.
7. The old password and pre-reset JWT are rejected.
8. New password login and normal farm access succeed.
9. Unauthorized and cross-farm requests remain rejected.

## Recovery

Preferred recovery after traffic or password resets have occurred:

1. Stop application traffic.
2. Preserve the failed database for investigation.
3. Have a PostgreSQL administrator restore the verified backup into a new database.
4. Validate revision, row counts, constraints, and application smoke tests.
5. Switch the application to the restored database only after validation.

The recovery database must be created by a PostgreSQL administrator because the
application role intentionally has no `CREATEDB` privilege. Use a new database;
never restore over `icms_db`:

```powershell
$pgBin = 'C:\Program Files\PostgreSQL\18\bin'
$backup = 'D:\ICMS_Project\backups\icms_db_20261022_234512_743.dump'
$recoveryDb = 'icms_db_recovery_20261023'

& "$pgBin\createdb.exe" -h localhost -p 5432 -U <admin-user> `
  --owner=icms_app $recoveryDb
& "$pgBin\pg_restore.exe" --exit-on-error --no-owner --no-privileges `
  -h localhost -p 5432 -U icms_app -d $recoveryDb $backup
& "$pgBin\psql.exe" -X -v ON_ERROR_STOP=1 -h localhost -p 5432 `
  -U icms_app -d $recoveryDb `
  -c 'SELECT version_num FROM alembic_version;'
```

Supply credentials through the normal PostgreSQL credential mechanism or a
temporary `PGPASSWORD` environment variable; never put them in the command or
the runbook. Validate row counts and application smoke tests before changing the
application database URL. The database-name/date placeholder must be changed if
that recovery database already exists.

Immediate schema rollback, only before reset state matters and only with explicit authorization:

```powershell
Set-Location D:\ICMS_Project\backend
.\.venv\Scripts\alembic.exe downgrade a8b3c4d5e6f7
```

This drops the reset-token table and token-version column. Never execute it casually.

Clear the temporary password environment after maintenance:

```powershell
Remove-Item Env:PGPASSWORD
```

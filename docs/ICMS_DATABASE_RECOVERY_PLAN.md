# ICMS Database Recovery Plan

Prepared: 2026-10-23 (Asia/Karachi)
Recovery strategy: restore into a new database, validate, then switch; never restore over `icms_db`
Execution status: documented and schema-rehearsed; separate-database recovery requires a PostgreSQL administrator

## Recovery objectives and evidence

The recovery point is the accepted PostgreSQL custom archive. Its timestamp defines the recoverable database state; transactions after that point are not present unless PostgreSQL WAL/PITR is configured separately. No WAL/PITR configuration was found in this repository.

Verified archive:

- Path: `D:\ICMS_Project\backups\icms_db_20261023_171259_598.dump`
- PostgreSQL version: server/client 18.6.
- Size: 108,454 bytes.
- SHA-256: `7FA3F9E84BD21C93E2B42D72E06B404BCFF27D5FB5E9C48D1E93DCB135F73527`.
- Catalog check: `pg_restore --list` passed with 246 lines.
- Restored revision: `a8b3c4d5e6f7`.
- Restored physical tables: 27.
- Recovery-point aggregates: 2 users, 2 farms, 2 farm memberships, and 37 permissions.
- Restored-copy migration to `c8d0e1f2a703`: passed with source rows preserved.

Existing backup files were not overwritten or deleted. Store a copy on encrypted media or approved off-host storage and record its checksum and custody before production migration.

## Recovery triggers

Use restore-based recovery when any of the following occurs:

- A migration completes but application validation fails and new reset/feed traffic may already exist.
- Schema objects or production data are damaged.
- Revision stamping or manual changes make the live schema untrustworthy.
- A downgrade would discard or invalidate security/feed state.

Do not immediately delete or overwrite the failed database. Stop traffic, preserve logs and the failed state for diagnosis, and recover beside it.

## Roles and approvals

- Incident owner: authorizes recovery and application cutover.
- PostgreSQL administrator: creates the new database and manages ownership/connections.
- Application operator: restores the archive and runs application smoke tests.
- Reviewer: verifies checksum, row counts, isolation, and cutover decision.

The `icms_app` role has no `CREATEDB`, so database creation requires an administrator. Never grant broad privileges merely to bypass this control.

## Backup validity check

```powershell
$backup = 'D:\ICMS_Project\backups\icms_db_20261023_171259_598.dump'
$expectedHash = '7FA3F9E84BD21C93E2B42D72E06B404BCFF27D5FB5E9C48D1E93DCB135F73527'

$actualHash = (Get-FileHash -LiteralPath $backup -Algorithm SHA256).Hash
if ($actualHash -ne $expectedHash) { throw 'Backup checksum mismatch.' }

& 'C:\Program Files\PostgreSQL\18\bin\pg_restore.exe' --list $backup | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Backup catalog is unreadable.' }
```

Stop if either check fails. Do not repair or rewrite the original archive in place.

## Preferred separate-database restoration

Choose a unique, unused recovery database name. The example date/name must be changed if it already exists.

```powershell
$pgBin = 'C:\Program Files\PostgreSQL\18\bin'
$backup = 'D:\ICMS_Project\backups\icms_db_20261023_171259_598.dump'
$recoveryDatabase = 'icms_recovery_20261023_171259'
$applicationRole = 'icms_app'
$adminRole = '<postgres-admin-role>'

# Obtain credentials interactively. Do not paste them into history.
$credential = Get-Credential -UserName $adminRole
$env:PGPASSWORD = $credential.GetNetworkCredential().Password

& "$pgBin\createdb.exe" -h localhost -p 5432 -U $adminRole `
  --owner=$applicationRole $recoveryDatabase
if ($LASTEXITCODE -ne 0) { throw 'Recovery database creation failed.' }
```

Switch to the application/restore credential, then restore without owners or grants from the archive:

```powershell
$credential = Get-Credential -UserName $applicationRole
$env:PGPASSWORD = $credential.GetNetworkCredential().Password

& "$pgBin\pg_restore.exe" --exit-on-error --no-owner --no-privileges `
  -h localhost -p 5432 -U $applicationRole -d $recoveryDatabase $backup
if ($LASTEXITCODE -ne 0) { throw 'Recovery restore failed.' }
```

Do not use `--clean` against `icms_db`. If recovery-database creation or restore fails, preserve the error output and have the administrator remove only the newly created, explicitly verified recovery database.

## Recovery-point verification

Connect only to the new recovery database and verify:

```sql
SELECT current_database(), current_user, current_schema();
SELECT version_num FROM public.alembic_version;

SELECT 'users' AS object, count(*) FROM public.users
UNION ALL SELECT 'farms', count(*) FROM public.farms
UNION ALL SELECT 'farm_members', count(*) FROM public.farm_members
UNION ALL SELECT 'permissions', count(*) FROM public.permissions;

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

Expected recovery point: revision `a8b3c4d5e6f7`; 2 users, 2 farms, 2 memberships, 37 permissions; zero invalid indexes and zero unvalidated constraints. Also compare cattle, health, vaccination, milk, invitation, verification-token, and other table counts with the incident snapshot. Do not print emails, hashes, or tokens.

## Bringing a restored database to the application revision

If the recovered application build expects `c8d0e1f2a703`, migrate the recovery database—not `icms_db`—using explicit environment values and target revision:

```powershell
$env:DB_HOST = 'localhost'
$env:DB_PORT = '5432'
$env:DB_NAME = $recoveryDatabase
$env:DB_USER = $applicationRole
$env:DB_PASSWORD = $env:PGPASSWORD

Set-Location D:\ICMS_Project\backend
& .\.venv\Scripts\alembic.exe current
& .\.venv\Scripts\alembic.exe heads
& .\.venv\Scripts\alembic.exe upgrade c8d0e1f2a703
```

Verify the exact target database before the write. Do not use `upgrade head`. Apply the post-migration SQL checks in `ICMS_DATABASE_MIGRATION_PLAN.md` and repeat aggregate/fingerprint comparisons.

## Application recovery validation

1. Configure one isolated backend instance for the recovery database with `EMAIL_DELIVERY_MODE=memory` or `console`; do not send external email.
2. Confirm `/api/v1/health` and `/api/v1/health/db` return 200 and report `c8d0e1f2a703`.
3. Use a designated test account to verify login, `/auth/me`, reset/JWT invalidation, farm selection, and membership.
4. Verify cattle, health/vaccination, milk, and feed APIs.
5. Confirm unauthorized and cross-farm access remain denied.
6. Verify frontend web/mobile clients point to the isolated recovery backend before testing.
7. Compare audit logs and aggregate counts; document any accepted data loss after the archive timestamp.

## Cutover

1. Keep writes to the failed database stopped.
2. Take a final incident snapshot/backup of the failed database for forensics if safe.
3. Approve the validated recovery database as the new target.
4. Update secret-managed application database configuration; do not edit committed files with credentials.
5. Start one backend instance and repeat readiness/smoke checks.
6. Reopen traffic gradually and monitor authentication errors, 5xx responses, connection saturation, and data counts.
7. Retain the old database and the accepted backup until recovery is formally signed off.

## Media recovery

PostgreSQL archives do not contain files under `backend/uploads`. The inspected database currently has zero `cattle_media` rows, reducing immediate referential recovery risk, but the upload tree is still a separate asset.

The existing `cattle_media_20261022_234716_228.zip` is a small previously recorded archive and must not be assumed to be a complete production media backup. Before broader deployment:

1. Repair unreadable pre-existing upload/test directories.
2. Create a new non-overwriting media archive with `scripts/backup-media.ps1`.
3. Record size and SHA-256.
4. Test extraction into a new directory.
5. Restore the database and matching media recovery point together when media rows exist.

## Limitations and residual risks

- The successful rehearsal restored into an isolated schema in `icms_test`, not a separate database, because `icms_app` lacks `CREATEDB`.
- Database ownership, database-level grants, and an actual application cutover remain to be tested with an administrator-created recovery database.
- The verified archive is stored locally and has no repository-managed encryption/off-host replication evidence.
- No WAL/PITR procedure is configured here; RPO is the accepted archive timestamp.
- Recovery time depends on administrator availability and environment size; record actual RTO during the first separate-database drill.
- Downgrades delete password-reset and feed/nutrition state and should not be used as routine recovery.

Clear temporary credentials after the drill:

```powershell
Remove-Item Env:PGPASSWORD, Env:DB_PASSWORD -ErrorAction SilentlyContinue
```

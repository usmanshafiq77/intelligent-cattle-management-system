# ICMS Backup and Restore Guide

## Assets in scope

1. PostgreSQL logical data and schema.
2. Uploaded cattle media.
3. Deployment configuration references—not secret values.

Database and media backups must be taken as a coordinated recovery set when record/media consistency matters.

## PostgreSQL backup

`scripts/backup-postgres.ps1` creates PostgreSQL custom-format archives with unique millisecond timestamps. It refuses overwrite, checks file size, and verifies the archive catalog with `pg_restore --list`.

Credential-safe PowerShell setup:

```powershell
$credential = Get-Credential -UserName icms_app
$env:PGPASSWORD = $credential.GetNetworkCredential().Password
```

Backup command:

```powershell
Set-Location D:\ICMS_Project
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\backup-postgres.ps1 `
  -DatabaseName icms_db `
  -DatabaseHost localhost `
  -Port 5432 `
  -DatabaseUser icms_app `
  -Destination .\backups `
  -RetentionDays 30
```

`RetentionDays` reports old candidates but never deletes them. Retention deletion must be implemented by reviewed external operations after restore history and legal retention are agreed.

Verified P0 archive:

- `D:\ICMS_Project\backups\icms_db_20261022_234512_743.dump`
- 108,454 bytes.
- Revision `a8b3c4d5e6f7`.
- 27 physical tables.

The `backups/` directory and common dump/archive extensions are ignored by Git.

## Restore validation

Preferred disposable database mode requires a PostgreSQL role with `CREATEDB`:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate-postgres-restore.ps1 `
  -BackupPath .\backups\icms_db_TIMESTAMP.dump `
  -TestDatabaseName test_icms_restore_TIMESTAMP `
  -DatabaseHost localhost `
  -Port 5432 `
  -DatabaseUser restore_operator
```

When the application role lacks `CREATEDB`, isolated-schema mode is supported only inside a test database:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate-postgres-restore.ps1 `
  -BackupPath .\backups\icms_db_TIMESTAMP.dump `
  -TargetDatabaseName icms_test `
  -TestSchemaName test_restore_TIMESTAMP `
  -DatabaseHost localhost `
  -Port 5432 `
  -DatabaseUser icms_app
```

Safety controls require `test_` database names or `test_restore_` schemas inside a test-named database. The disposable target is removed unless `-KeepDatabase` is explicitly supplied.

The P0 restore used isolated-schema mode because `icms_app` correctly lacks `CREATEDB`. It passed and left zero restore schemas behind.

## Production restoration

Use a PostgreSQL administrator and restore into a new database; do not overwrite the damaged database in place.

1. Stop writes and preserve the failed database.
2. Create a new restricted restore database.
3. Run `pg_restore --exit-on-error --no-owner --no-privileges` into it.
4. Verify Alembic revision, tables, constraints, row counts, and ownership/grants.
5. Run authentication and farm-isolation smoke tests.
6. Restore the matching media archive.
7. Switch application configuration only after sign-off.
8. Retain the old database until recovery is accepted.

## Media backup

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\backup-media.ps1 `
  -Source .\backend\uploads `
  -Destination .\backups `
  -RetentionDays 30
```

The script creates a unique zip, refuses overwrite, deletes only its own incomplete output if archiving fails, verifies nonzero size, and reports retention candidates without deleting them.

P0 results:

- Disposable media fixture archive: passed, 200 bytes.
- Actual `backend/uploads`: blocked by unreadable pre-existing pytest directories, including `pytest_milk_lactation_updated_01`.

Before production, ensure the backup operator has read access to every media object and the application has only the minimum write permissions required. Repeat a complete media backup and test extraction after permissions are repaired.

## Scheduling guidance

- Schedule backups through Windows Task Scheduler, cron, or the hosting provider—not from the API process.
- Use a dedicated backup identity with minimum privileges.
- Send backups to encrypted storage separate from the application host.
- Monitor last-success time and archive size.
- Perform recurring restore drills; a successful `pg_dump` alone is insufficient.
- Clear temporary credentials after each interactive operation:

```powershell
Remove-Item Env:PGPASSWORD
```

No unattended schedule or destructive retention cleanup was enabled by this implementation.

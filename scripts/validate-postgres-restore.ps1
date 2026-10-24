param(
    [Parameter(Mandatory = $true)][string]$BackupPath,
    [string]$TestDatabaseName,
    [string]$TargetDatabaseName,
    [string]$TestSchemaName,
    [string]$DatabaseHost = "localhost",
    [int]$Port = 5432,
    [string]$DatabaseUser = "icms_app",
    [switch]$KeepDatabase
)

$ErrorActionPreference = "Stop"

$databaseMode = -not [string]::IsNullOrWhiteSpace($TestDatabaseName)
$schemaMode = (
    -not [string]::IsNullOrWhiteSpace($TargetDatabaseName) -and
    -not [string]::IsNullOrWhiteSpace($TestSchemaName)
)
if ($databaseMode -eq $schemaMode) {
    throw "Choose exactly one mode: TestDatabaseName, or TargetDatabaseName with TestSchemaName."
}
if ($databaseMode -and $TestDatabaseName -notmatch '^test_[A-Za-z0-9_]+$') {
    throw "Restore validation databases must begin with test_."
}
if ($schemaMode) {
    if ($TargetDatabaseName -notmatch '(^test_)|(_test$)') {
        throw "Schema restore validation is restricted to a test database."
    }
    if ($TestSchemaName -notmatch '^test_restore_[A-Za-z0-9_]+$') {
        throw "Restore validation schemas must begin with test_restore_."
    }
}

$resolvedBackup = (Resolve-Path -LiteralPath $BackupPath).Path
$createdb = (Get-Command createdb -ErrorAction Stop).Source
$dropdb = (Get-Command dropdb -ErrorAction Stop).Source
$pgRestore = (Get-Command pg_restore -ErrorAction Stop).Source
$psql = (Get-Command psql -ErrorAction Stop).Source
$created = $false
$schemaCreated = $false
$temporarySql = $null

try {
    if ($databaseMode) {
        & $createdb --host $DatabaseHost --port $Port --username $DatabaseUser $TestDatabaseName
        if ($LASTEXITCODE -ne 0) {
            throw "Could not create disposable restore database."
        }
        $created = $true
        & $pgRestore --host $DatabaseHost --port $Port --username $DatabaseUser --dbname $TestDatabaseName --exit-on-error --no-owner --no-privileges $resolvedBackup
        if ($LASTEXITCODE -ne 0) {
            throw "pg_restore failed with exit code $LASTEXITCODE."
        }
        $inspectionDatabase = $TestDatabaseName
        $revisionQuery = "SELECT version_num FROM alembic_version"
        $tableQuery = "SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE'"
        $targetLabel = "database=$TestDatabaseName"
    }
    else {
        $inspectionDatabase = $TargetDatabaseName
        & $psql --host $DatabaseHost --port $Port --username $DatabaseUser --dbname $inspectionDatabase --set ON_ERROR_STOP=1 --command "CREATE SCHEMA `"$TestSchemaName`""
        if ($LASTEXITCODE -ne 0) {
            throw "Could not create disposable restore schema."
        }
        $schemaCreated = $true
        $temporarySql = Join-Path ([System.IO.Path]::GetTempPath()) ("icms_restore_{0}.sql" -f [guid]::NewGuid().ToString("N"))
        & $pgRestore --no-owner --no-privileges --file $temporarySql $resolvedBackup
        if ($LASTEXITCODE -ne 0) {
            throw "Could not render the backup for isolated-schema restore."
        }
        $sql = Get-Content -Raw -LiteralPath $temporarySql
        $qualifiedSchema = '"' + $TestSchemaName + '".'
        $sql = $sql.Replace("public.", $qualifiedSchema)
        Set-Content -LiteralPath $temporarySql -Value $sql -Encoding UTF8
        & $psql --host $DatabaseHost --port $Port --username $DatabaseUser --dbname $inspectionDatabase --set ON_ERROR_STOP=1 --file $temporarySql | Out-Null
        if ($LASTEXITCODE -ne 0) {
            throw "Isolated-schema restore failed."
        }
        $revisionQuery = "SELECT version_num FROM `"$TestSchemaName`".alembic_version"
        $tableQuery = "SELECT count(*) FROM information_schema.tables WHERE table_schema='$TestSchemaName' AND table_type='BASE TABLE'"
        $targetLabel = "database=$TargetDatabaseName schema=$TestSchemaName"
    }

    $revision = (& $psql --host $DatabaseHost --port $Port --username $DatabaseUser --dbname $inspectionDatabase --tuples-only --no-align --command $revisionQuery).Trim()
    if ($LASTEXITCODE -ne 0 -or -not $revision) {
        throw "Restored database has no readable Alembic revision."
    }

    $tableCount = (& $psql --host $DatabaseHost --port $Port --username $DatabaseUser --dbname $inspectionDatabase --tuples-only --no-align --command $tableQuery).Trim()
    if ($LASTEXITCODE -ne 0) {
        throw "Could not inspect restored database."
    }

    Write-Output ("RESTORE_VERIFIED {0} revision={1} tables={2}" -f $targetLabel, $revision, $tableCount)
}
finally {
    if ($temporarySql -and (Test-Path -LiteralPath $temporarySql)) {
        Remove-Item -LiteralPath $temporarySql -Force
    }
    if ($schemaCreated -and -not $KeepDatabase) {
        & $psql --host $DatabaseHost --port $Port --username $DatabaseUser --dbname $TargetDatabaseName --set ON_ERROR_STOP=1 --command "DROP SCHEMA `"$TestSchemaName`" CASCADE" | Out-Null
        if ($LASTEXITCODE -ne 0) {
            Write-Error "Disposable restore schema cleanup failed: $TestSchemaName"
        }
    }
    if ($created -and -not $KeepDatabase) {
        & $dropdb --host $DatabaseHost --port $Port --username $DatabaseUser --if-exists $TestDatabaseName
        if ($LASTEXITCODE -ne 0) {
            Write-Error "Disposable restore database cleanup failed: $TestDatabaseName"
        }
    }
}

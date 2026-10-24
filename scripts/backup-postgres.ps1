param(
    [Parameter(Mandatory = $true)][string]$DatabaseName,
    [string]$DatabaseHost = "localhost",
    [int]$Port = 5432,
    [string]$DatabaseUser = "icms_app",
    [string]$Destination = (Join-Path $PSScriptRoot "..\backups"),
    [int]$RetentionDays = 0
)

$ErrorActionPreference = "Stop"

if ($DatabaseName -notmatch '^[A-Za-z0-9_-]+$') {
    throw "DatabaseName contains unsupported characters."
}

$pgDump = (Get-Command pg_dump -ErrorAction Stop).Source
$pgRestore = (Get-Command pg_restore -ErrorAction Stop).Source
$destinationPath = [System.IO.Path]::GetFullPath($Destination)
New-Item -ItemType Directory -Path $destinationPath -Force | Out-Null

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss_fff"
$backupPath = Join-Path $destinationPath ("{0}_{1}.dump" -f $DatabaseName, $timestamp)
if (Test-Path -LiteralPath $backupPath) {
    throw "Refusing to overwrite an existing backup."
}

& $pgDump --host $DatabaseHost --port $Port --username $DatabaseUser --dbname $DatabaseName --format custom --no-owner --no-privileges --file $backupPath
if ($LASTEXITCODE -ne 0) {
    throw "pg_dump failed with exit code $LASTEXITCODE."
}

$backup = Get-Item -LiteralPath $backupPath
if ($backup.Length -le 0) {
    throw "Backup file is empty."
}

& $pgRestore --list $backupPath | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "pg_restore could not read the backup catalog."
}

Write-Output ("BACKUP_VERIFIED path={0} bytes={1}" -f $backup.FullName, $backup.Length)

if ($RetentionDays -gt 0) {
    $cutoff = (Get-Date).AddDays(-$RetentionDays)
    $candidates = @(
        Get-ChildItem -LiteralPath $destinationPath -Filter "${DatabaseName}_*.dump" -File |
            Where-Object { $_.LastWriteTime -lt $cutoff }
    )
    Write-Output ("RETENTION_REPORT days={0} deletion_disabled=true candidates={1}" -f $RetentionDays, $candidates.Count)
}

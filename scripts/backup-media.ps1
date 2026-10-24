param(
    [string]$Source = (Join-Path $PSScriptRoot "..\backend\uploads"),
    [string]$Destination = (Join-Path $PSScriptRoot "..\backups"),
    [int]$RetentionDays = 0
)

$ErrorActionPreference = "Stop"
$sourcePath = (Resolve-Path -LiteralPath $Source).Path
$destinationPath = [System.IO.Path]::GetFullPath($Destination)
New-Item -ItemType Directory -Path $destinationPath -Force | Out-Null

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss_fff"
$archivePath = Join-Path $destinationPath ("cattle_media_{0}.zip" -f $timestamp)
if (Test-Path -LiteralPath $archivePath) {
    throw "Refusing to overwrite an existing media backup."
}

try {
    Compress-Archive -Path $sourcePath -DestinationPath $archivePath -CompressionLevel Optimal
}
catch {
    if (Test-Path -LiteralPath $archivePath) {
        Remove-Item -LiteralPath $archivePath -Force
    }
    throw
}
$archive = Get-Item -LiteralPath $archivePath
if ($archive.Length -le 0) {
    throw "Media backup is empty."
}
Write-Output ("MEDIA_BACKUP_VERIFIED path={0} bytes={1}" -f $archive.FullName, $archive.Length)

if ($RetentionDays -gt 0) {
    $cutoff = (Get-Date).AddDays(-$RetentionDays)
    $candidates = @(
        Get-ChildItem -LiteralPath $destinationPath -Filter "cattle_media_*.zip" -File |
            Where-Object { $_.LastWriteTime -lt $cutoff }
    )
    Write-Output ("RETENTION_REPORT days={0} deletion_disabled=true candidates={1}" -f $RetentionDays, $candidates.Count)
}

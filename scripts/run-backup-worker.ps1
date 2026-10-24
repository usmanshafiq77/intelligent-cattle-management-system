[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$backendRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\backend")).Path
$python = Join-Path $backendRoot ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "Backend virtual-environment Python was not found at the expected path."
}

Push-Location $backendRoot
try {
    & $python -m app.commands.process_backup_jobs
    if ($LASTEXITCODE -ne 0) {
        throw "The ICMS backup worker exited with code $LASTEXITCODE."
    }
}
finally {
    Pop-Location
}

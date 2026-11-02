$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    Write-Host "Creating build environment..."
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Failed to create .venv. Install Python 3.11+ first."
        Read-Host "Press Enter to close"
        exit 1
    }
}

Write-Host "Installing build dependencies..."
& $python -m pip install -r requirements-build.txt
if ($LASTEXITCODE -ne 0) {
    Write-Host "Dependency installation failed."
    Read-Host "Press Enter to close"
    exit 1
}

# PyInstaller --clean rebuilds dist. Preserve the portable vault across builds.
$dataDir = Join-Path $PSScriptRoot "dist\APIKeyLedger\data"
$backup = Join-Path $env:TEMP "api-key-ledger-build-data"
if (Test-Path $backup) {
    Remove-Item -LiteralPath $backup -Recurse -Force
}
if (Test-Path $dataDir) {
    Write-Host "Backing up portable data..."
    Copy-Item -LiteralPath $dataDir -Destination $backup -Recurse -Force
}

$result = 1
try {
    Write-Host "Generating version resource..."
    & $python tools/generate_version_info.py
    Write-Host "Building..."
    & $python -m PyInstaller --noconfirm --clean api_key_ledger.spec
    $result = $LASTEXITCODE
}
finally {
    if (Test-Path $backup) {
        Write-Host "Restoring portable data..."
        New-Item -ItemType Directory -Force -Path $dataDir | Out-Null
        Copy-Item -Path (Join-Path $backup "*") -Destination $dataDir -Recurse -Force
        Remove-Item -LiteralPath $backup -Recurse -Force
    }
}

if ($result -ne 0) {
    Write-Host "Build failed."
    Read-Host "Press Enter to close"
    exit 1
}

Write-Host ""
Write-Host "Build complete:"
Write-Host "  dist\APIKeyLedger\ (launch the exe inside)"
Write-Host ""
Write-Host "Keep the whole folder together. Delete data before sharing."
Read-Host "Press Enter to close"

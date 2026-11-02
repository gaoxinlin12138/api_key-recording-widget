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

Write-Host "Generating version resource..."
& $python tools/generate_version_info.py

Write-Host "Building single-file exe..."
& $python -m PyInstaller --noconfirm --clean api_key_ledger_onefile.spec
if ($LASTEXITCODE -ne 0) {
    Write-Host "Build failed."
    Read-Host "Press Enter to close"
    exit 1
}

Write-Host ""
Write-Host "Build complete:"
Write-Host "  dist\ (single-file exe inside)"
Write-Host ""
Write-Host "Vault: %LOCALAPPDATA%\ApiKeyLedger\data"
Read-Host "Press Enter to close"

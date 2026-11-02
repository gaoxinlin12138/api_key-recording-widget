$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$isccCandidates = @(
    (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe"),
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    "C:\Program Files\Inno Setup 6\ISCC.exe"
)
$iscc = $isccCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) {
    $command = Get-Command iscc -ErrorAction SilentlyContinue
    if ($command) { $iscc = $command.Source }
}
if (-not $iscc) {
    Write-Host "Inno Setup 6 was not found."
    Write-Host "Install it with: winget install JRSoftware.InnoSetup"
    Read-Host "Press Enter to close"
    exit 1
}

$onefile = Join-Path $PSScriptRoot "dist\API钥匙簿.exe"
if (-not (Test-Path $onefile)) {
    Write-Host "dist\API钥匙簿.exe was not found."
    Write-Host "Run build_onefile.bat first."
    Read-Host "Press Enter to close"
    exit 1
}

$versionLine = Select-String -Path (Join-Path $PSScriptRoot "core\version.py") -Pattern '__version__\s*=\s*"([^"]+)"'
if (-not $versionLine) {
    Write-Host "Could not read version from core\version.py."
    Read-Host "Press Enter to close"
    exit 1
}
$version = $versionLine.Matches[0].Groups[1].Value

Write-Host "Building installer for version $version..."
& $iscc "/DMyAppVersion=$version" "installer.iss"
if ($LASTEXITCODE -ne 0) {
    Write-Host "Installer build failed."
    Read-Host "Press Enter to close"
    exit 1
}

$setup = Join-Path $PSScriptRoot "dist\installer\APIKeyLedger-$version-setup.exe"
$exeHash = (Get-FileHash -LiteralPath $onefile -Algorithm SHA256).Hash.ToLower()
$setupHash = (Get-FileHash -LiteralPath $setup -Algorithm SHA256).Hash.ToLower()
$sums = @(
    "$exeHash  API钥匙簿.exe",
    "$setupHash  APIKeyLedger-$version-setup.exe"
)
$sums | Set-Content -Path (Join-Path $PSScriptRoot "dist\installer\SHA256SUMS.txt") -Encoding UTF8

Write-Host ""
Write-Host "Installer complete:"
Write-Host "  $setup"
Write-Host "  dist\installer\SHA256SUMS.txt"
Write-Host ""
Write-Host "The installer uses %LOCALAPPDATA%\Programs\ApiKeyLedger."
Write-Host "Vault data stays in %LOCALAPPDATA%\ApiKeyLedger\data."
Read-Host "Press Enter to close"

# One-time setup for Athena. Run from the repo root:  .\scripts\setup.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
Set-Location $root

Write-Host "== Athena setup ==" -ForegroundColor Cyan

# Python backend
if (-not (Test-Path "$root\.venv")) {
    Write-Host "Creating Python venv..." -ForegroundColor Yellow
    python -m venv .venv
}
& "$root\.venv\Scripts\pip" install -r services\api\requirements.txt pytest

# Frontend
Write-Host "Installing npm dependencies..." -ForegroundColor Yellow
npm install

if (-not (Test-Path "$root\.env")) {
    Copy-Item "$root\.env.example" "$root\.env"
    Write-Host "Created .env from .env.example (all keys optional)." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Setup complete. Start Athena with:  .\scripts\dev.ps1" -ForegroundColor Green

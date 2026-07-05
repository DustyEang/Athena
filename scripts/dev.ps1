# Start Athena for development: backend (port 8765) + desktop UI (port 5173).
# Run from the repo root:  .\scripts\dev.ps1
$root = Split-Path $PSScriptRoot -Parent

Start-Process pwsh -ArgumentList "-NoExit", "-Command",
    "Set-Location '$root\services\api'; & '$root\.venv\Scripts\uvicorn' athena_api.main:app --port 8765 --reload"

Start-Process pwsh -ArgumentList "-NoExit", "-Command",
    "Set-Location '$root'; npm run dev:desktop"

Write-Host "Athena starting:" -ForegroundColor Cyan
Write-Host "  Backend  -> http://127.0.0.1:8765  (API docs: /docs)"
Write-Host "  Desktop  -> http://localhost:5173  (browser dev mode)"
Write-Host "  Tauri    -> 'npm run tauri:dev' once Rust is installed"

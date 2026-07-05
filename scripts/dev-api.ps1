# Start only the Athena backend.  Run from repo root:  .\scripts\dev-api.ps1
$root = Split-Path $PSScriptRoot -Parent
Set-Location "$root\services\api"
& "$root\.venv\Scripts\uvicorn" athena_api.main:app --port 8765 --reload

# Starts the Athena stack silently at login (wired to a HKCU Run registry key).
# Backend binds 0.0.0.0 so phones/tablets on the same network can reach her.
$root = Split-Path $PSScriptRoot -Parent

Start-Process -WindowStyle Hidden -FilePath "$root\.venv\Scripts\uvicorn.exe" `
    -ArgumentList "athena_api.main:app", "--host", "0.0.0.0", "--port", "8765" `
    -WorkingDirectory "$root\services\api"

Start-Process -WindowStyle Hidden -FilePath "cmd.exe" `
    -ArgumentList "/c", "npm run dev:desktop" `
    -WorkingDirectory $root

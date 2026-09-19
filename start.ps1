param([string]$Python = "python", [string]$EnvFile = ".env")
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$env:A11Y_ENV_FILE = (Resolve-Path -LiteralPath $EnvFile).Path
& $Python -m uvicorn app:create_app --factory --host 127.0.0.1 --port 8090

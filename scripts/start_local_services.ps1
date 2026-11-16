$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
& .\.venv\Scripts\python.exe scripts/setup_local.py
docker compose up -d postgres
if ($LASTEXITCODE -ne 0) { throw 'PostgreSQL startup failed' }
& .\.venv\Scripts\python.exe scripts/start_mlflow.py

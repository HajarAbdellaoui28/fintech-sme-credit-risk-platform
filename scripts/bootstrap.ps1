$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
    py -3.11 -m venv .venv
}
& .\.venv\Scripts\python.exe -m pip install -c constraints.txt -e '.[mlops,spark,dev]'
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed' }
if (-not (Test-Path -LiteralPath '.env')) {
    & .\.venv\Scripts\python.exe scripts/setup_local.py
}
Write-Host 'Environment ready. Follow README.md for training and startup.'

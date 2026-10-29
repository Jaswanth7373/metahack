# Windows equivalent of scripts/demo.sh
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
$port = if ($env:PORT) { $env:PORT } else { "8010" }
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
if (-not (Test-Path .venv)) { python -m venv .venv }
.\.venv\Scripts\pip install -q -r backend\requirements.txt
if (Test-Path backend\data) { Remove-Item -Recurse -Force backend\data }
.\.venv\Scripts\python scripts\make_samples.py
.\.venv\Scripts\python scripts\build_demo_cache.py
Push-Location frontend; npm install --silent; npm run build --silent; Pop-Location
Push-Location backend; ..\.venv\Scripts\python -m pytest -q -p no:warnings
Write-Host "PaperPilot -> http://127.0.0.1:$port"
..\.venv\Scripts\uvicorn app.main:app --host 127.0.0.1 --port $port

#!/usr/bin/env bash
# One command: install, reset data, rebuild samples + demo cache, build the UI, start PaperPilot.
# Usage: scripts/demo.sh            (PORT=8010 by default)
set -euo pipefail
cd "$(dirname "$0")/.."
PORT="${PORT:-8010}"
PY="${PYTHON:-python3}"

[ -f .env ] || cp .env.example .env
[ -d .venv ] || "$PY" -m venv .venv
.venv/bin/pip install -q -r backend/requirements.txt
command -v tesseract >/dev/null || echo "note: tesseract not found - photo OCR disabled (PDFs still work)"

rm -rf backend/data                                   # reset: database, uploads, outputs
.venv/bin/python scripts/make_samples.py              # fictional sample PDFs
.venv/bin/python scripts/build_demo_cache.py          # DEMO_MODE response cache

(cd frontend && npm install --silent && npm run build --silent)
(cd backend && ../.venv/bin/python -m pytest -q -p no:warnings)

echo "PaperPilot -> http://127.0.0.1:${PORT}"
cd backend && exec ../.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port "$PORT"

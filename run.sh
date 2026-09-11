#!/usr/bin/env bash
# SAT-SA one-command launcher: installs deps, builds frontend if needed, starts server.
set -e
cd "$(dirname "$0")"

python3 -m pip install --quiet -r backend/requirements.txt

if [ ! -f frontend/dist/index.html ]; then
  echo "[run.sh] building frontend…"
  (cd frontend && npm install --no-audit --no-fund && npm run build)
fi

echo "[run.sh] starting SAT-SA on :8000"
cd backend
exec python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000

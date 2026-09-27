#!/usr/bin/env bash
# Start StudyQuest on http://localhost:8765 (local only).
set -euo pipefail
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then
  echo "First run: creating .venv and installing requirements…"
  python3 -m venv .venv
  .venv/bin/pip install -q -r requirements.txt
fi
[ -f data/plan.json ] || { [ -f study_checklist.csv ] && .venv/bin/python -m studyquest.cli import study_checklist.csv; }
ls data/corpus/*/ >/dev/null 2>&1 || .venv/bin/python -m studyquest.corpus
PORT="${PORT:-8765}"
( sleep 1.5 && open "http://localhost:$PORT" ) >/dev/null 2>&1 &
exec .venv/bin/uvicorn studyquest.app:app --host 127.0.0.1 --port "$PORT"

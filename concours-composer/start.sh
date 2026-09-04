#!/usr/bin/env bash
# ConcoursComposer 실행 — 서버를 띄우고 브라우저를 연다.
set -euo pipefail
cd "$(dirname "$0")"
[ -x .venv/bin/python ] || { echo "먼저 ./install.sh 를 실행하라." >&2; exit 1; }

PORT="${PORT:-8000}"
URL="http://localhost:${PORT}/"
echo "ConcoursComposer 를 http://localhost:${PORT} 에서 연다. 끄려면 Ctrl+C."

( sleep 2
  command -v open    >/dev/null 2>&1 && open "$URL"    && exit 0
  command -v xdg-open >/dev/null 2>&1 && xdg-open "$URL" && exit 0
  true ) &

exec .venv/bin/python -m uvicorn app.main:app --app-dir server --host 127.0.0.1 --port "$PORT"

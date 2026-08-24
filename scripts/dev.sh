#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="$ROOT/backend/.venv/bin/python"

if [[ ! -x "$PYTHON" || ! -d "$ROOT/frontend/node_modules" ]]; then
  echo "Dependencies are missing. Run: make setup" >&2
  exit 1
fi

cleanup() {
  if [[ -n "${BACKEND_PID:-}" ]]; then
    kill "$BACKEND_PID" 2>/dev/null || true
    wait "$BACKEND_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

echo "Starting Xultron API on http://127.0.0.1:${PORT:-5000}"
(
  cd "$ROOT/backend"
  PYTHONUNBUFFERED=1 "$PYTHON" run.py
) &
BACKEND_PID=$!

echo "Starting Xultron interface on http://127.0.0.1:5173"
npm --prefix "$ROOT/frontend" run dev


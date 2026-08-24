#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="$ROOT/backend/.venv"

if [[ ! -d "$VENV" ]]; then
  if [[ "${PREFIX:-}" == *com.termux* ]] && python -c 'import cryptography' >/dev/null 2>&1; then
    echo "Creating a Termux virtual environment with the trusted system cryptography package..."
    python -m venv --system-site-packages "$VENV"
  else
    echo "Creating backend virtual environment..."
    python -m venv "$VENV"
  fi
fi

echo "Installing backend dependencies..."
"$VENV/bin/python" -m pip install -r "$ROOT/backend/requirements.txt"

echo "Installing frontend dependencies..."
if [[ -f "$ROOT/frontend/package-lock.json" ]]; then
  npm --prefix "$ROOT/frontend" ci
else
  npm --prefix "$ROOT/frontend" install
fi

echo "Applying database migrations..."
(
  cd "$ROOT/backend"
  .venv/bin/flask --app run.py db upgrade
)

echo "Xultron is ready. Run: make dev"


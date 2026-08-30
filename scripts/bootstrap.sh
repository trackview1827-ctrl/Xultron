#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "${BASH_SOURCE[0]%/*}/.." && pwd)"
VENV="$ROOT/backend/.venv"

if command -v python >/dev/null 2>&1; then
  PYTHON_BIN="python"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="python3"
else
  echo "Python 3.11+ bulunamadı. Ubuntu/Debian: sudo apt install python3 python3-venv" >&2
  exit 1
fi

if [[ "${PREFIX:-}" == *com.termux* ]] && ! command -v ffmpeg >/dev/null 2>&1; then
  echo "Installing ffmpeg for browser WebM/Opus voice input..."
  pkg install -y ffmpeg
fi

if [[ ! -d "$VENV" ]]; then
  if [[ "${PREFIX:-}" == *com.termux* ]] && "$PYTHON_BIN" -c 'import cryptography' >/dev/null 2>&1; then
    echo "Creating a Termux virtual environment with the trusted system cryptography package..."
    "$PYTHON_BIN" -m venv --system-site-packages "$VENV"
  else
    echo "Creating backend virtual environment..."
    "$PYTHON_BIN" -m venv "$VENV"
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

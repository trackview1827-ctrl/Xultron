#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="$ROOT/backend/.venv/bin/python"
FLASK="$ROOT/backend/.venv/bin/flask"
DIST="$ROOT/frontend/dist"
SCRATCH_ROOT="${JCODE_SCRATCH_DIR:-${TMPDIR:-/tmp}}"

if [[ ! -x "$PYTHON" || ! -x "$FLASK" ]]; then
  echo "Backend dependencies are missing. Run: make setup" >&2
  exit 1
fi
if [[ ! -s "$DIST/index.html" ]]; then
  echo "Frontend production build is missing. Run: make build" >&2
  exit 1
fi

mkdir -p "$SCRATCH_ROOT"
SMOKE_DIR="$(mktemp -d "$SCRATCH_ROOT/xultron-smoke.XXXXXX")"
DATABASE_PATH="$SMOKE_DIR/xultron.sqlite3"
SERVER_LOG="$SMOKE_DIR/server.log"
SERVER_PID=""

cleanup() {
  local status=$?
  if [[ -n "$SERVER_PID" ]]; then
    kill "$SERVER_PID" 2>/dev/null || true
    wait "$SERVER_PID" 2>/dev/null || true
  fi
  if [[ $status -ne 0 ]]; then
    echo "Release smoke failed. Server log:" >&2
    tail -n 120 "$SERVER_LOG" >&2 2>/dev/null || true
    echo "Artifacts kept at: $SMOKE_DIR" >&2
  elif [[ "${KEEP_SMOKE_ARTIFACTS:-0}" == "1" ]]; then
    echo "Smoke artifacts kept at: $SMOKE_DIR"
  else
    rm -rf "$SMOKE_DIR"
  fi
  exit "$status"
}
trap cleanup EXIT INT TERM

PORT="$($PYTHON - <<'PY'
import socket
with socket.socket() as sock:
    sock.bind(("127.0.0.1", 0))
    print(sock.getsockname()[1])
PY
)"
SECRET_KEY="$($PYTHON -c 'import secrets; print(secrets.token_urlsafe(48))')"
ENCRYPTION_KEY="$($PYTHON -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')"

export XULTRON_ENV=production
export SECRET_KEY ENCRYPTION_KEY
export DATABASE_URL="sqlite:///$DATABASE_PATH"
export SESSION_COOKIE_SECURE=false
export PROVIDER_TIMEOUT_SECONDS=2
export RATE_LIMIT_PER_MINUTE=1000
export FRONTEND_DIST_DIR="$DIST"
export PYTHONUNBUFFERED=1

printf 'Applying clean production migrations...\n'
(
  cd "$ROOT/backend"
  "$FLASK" --app run.py db upgrade
) >"$SERVER_LOG" 2>&1

printf 'Starting isolated production server on http://127.0.0.1:%s...\n' "$PORT"
(
  cd "$ROOT/backend"
  "$FLASK" --app run.py run --host 127.0.0.1 --port "$PORT" --no-reload --no-debugger
) >>"$SERVER_LOG" 2>&1 &
SERVER_PID=$!

READY=0
for _ in $(seq 1 100); do
  if ! kill -0 "$SERVER_PID" 2>/dev/null; then
    break
  fi
  if "$PYTHON" - "$PORT" >/dev/null 2>&1 <<'PY'
import json
import sys
from urllib.request import urlopen

with urlopen(f"http://127.0.0.1:{sys.argv[1]}/api/v1/system/health", timeout=1) as response:
    body = json.load(response)
    assert response.status == 200 and body["status"] == "online"
PY
  then
    READY=1
    break
  fi
  sleep 0.1
done

if [[ "$READY" != "1" ]]; then
  echo "Xultron server did not become ready." >&2
  exit 1
fi

"$PYTHON" "$ROOT/scripts/release_smoke.py" \
  --base "http://127.0.0.1:$PORT" \
  --database "$DATABASE_PATH" \
  --log "$SERVER_LOG"

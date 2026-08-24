#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "[1/7] Backend tests"
(
  cd "$ROOT/backend"
  .venv/bin/pytest -q
)

echo "[2/7] Backend compile check"
(
  cd "$ROOT/backend"
  .venv/bin/python -m compileall -q app tests
)

echo "[3/7] Frontend strict typecheck"
npm --prefix "$ROOT/frontend" run typecheck

echo "[4/7] Frontend tests"
npm --prefix "$ROOT/frontend" test

echo "[5/7] Frontend production build"
npm --prefix "$ROOT/frontend" run build

echo "[6/7] PWA artifact checks"
node -e "JSON.parse(require('fs').readFileSync('$ROOT/frontend/dist/manifest.webmanifest', 'utf8'))"
node --check "$ROOT/frontend/dist/sw.js"
test -s "$ROOT/frontend/dist/icons/xultron-192.png"
test -s "$ROOT/frontend/dist/icons/xultron-512.png"

echo "[7/7] Isolated production HTTP smoke"
bash "$ROOT/scripts/release-smoke.sh"

echo "All automated Xultron checks passed."

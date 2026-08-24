#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "[1/6] Backend tests"
(
  cd "$ROOT/backend"
  .venv/bin/pytest -q
)

echo "[2/6] Backend compile check"
(
  cd "$ROOT/backend"
  .venv/bin/python -m compileall -q app tests
)

echo "[3/6] Frontend strict typecheck"
npm --prefix "$ROOT/frontend" run typecheck

echo "[4/6] Frontend tests"
npm --prefix "$ROOT/frontend" test

echo "[5/6] Frontend production build"
npm --prefix "$ROOT/frontend" run build

echo "[6/6] PWA artifact checks"
node -e "JSON.parse(require('fs').readFileSync('$ROOT/frontend/dist/manifest.webmanifest', 'utf8'))"
node --check "$ROOT/frontend/dist/sw.js"
test -s "$ROOT/frontend/dist/icons/xultron-192.png"
test -s "$ROOT/frontend/dist/icons/xultron-512.png"

echo "All automated Xultron checks passed."


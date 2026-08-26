#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "[1/8] Clean source profile"
bash "$ROOT/scripts/check-clean-tree.sh"

echo "[2/8] Backend tests"
(
  cd "$ROOT/backend"
  .venv/bin/pytest -q
)

echo "[3/8] Backend compile check"
(
  cd "$ROOT/backend"
  .venv/bin/python -m compileall -q app tests
)

echo "[4/8] Frontend strict typecheck"
npm --prefix "$ROOT/frontend" run typecheck

echo "[5/8] Frontend tests"
npm --prefix "$ROOT/frontend" test

echo "[6/8] Frontend production build"
npm --prefix "$ROOT/frontend" run build

echo "[7/8] PWA artifact checks"
node -e "JSON.parse(require('fs').readFileSync('$ROOT/frontend/dist/manifest.webmanifest', 'utf8'))"
node --check "$ROOT/frontend/dist/sw.js"
test -s "$ROOT/frontend/dist/icons/xultron-192.png"
test -s "$ROOT/frontend/dist/icons/xultron-512.png"

echo "[8/8] Isolated production HTTP smoke"
bash "$ROOT/scripts/release-smoke.sh"

echo "All automated Xultron checks passed."

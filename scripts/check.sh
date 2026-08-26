#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "[1/9] Clean source profile"
bash "$ROOT/scripts/check-clean-tree.sh"

echo "[2/9] Xultron CLI tests and npm package check"
npm --prefix "$ROOT" test
npm --prefix "$ROOT" run pack:check >/dev/null

echo "[3/9] Backend tests"
(
  cd "$ROOT/backend"
  .venv/bin/pytest -q
)

echo "[4/9] Backend compile check"
(
  cd "$ROOT/backend"
  .venv/bin/python -m compileall -q app tests
)

echo "[5/9] Frontend strict typecheck"
npm --prefix "$ROOT/frontend" run typecheck

echo "[6/9] Frontend tests"
npm --prefix "$ROOT/frontend" test

echo "[7/9] Frontend production build"
npm --prefix "$ROOT/frontend" run build

echo "[8/9] PWA artifact checks"
node -e "JSON.parse(require('fs').readFileSync('$ROOT/frontend/dist/manifest.webmanifest', 'utf8'))"
node --check "$ROOT/frontend/dist/sw.js"
test -s "$ROOT/frontend/dist/icons/xultron-192.png"
test -s "$ROOT/frontend/dist/icons/xultron-512.png"

echo "[9/9] Isolated production HTTP smoke"
bash "$ROOT/scripts/release-smoke.sh"

echo "All automated Xultron checks passed."

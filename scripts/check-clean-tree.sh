#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

forbidden_paths="$({
  git ls-files | grep -E '(^|/)(instance|node_modules|dist|\.venv)/|(^|/)\.env($|\.)|\.(sqlite3|db|log|pem|key|p12|pfx)$' || true
} | grep -v '^backend/\.env\.example$' || true)"

if [[ -n "$forbidden_paths" ]]; then
  echo "Tracked runtime or private-data paths are forbidden:" >&2
  echo "$forbidden_paths" >&2
  exit 1
fi

if git grep -I -n -E 'LOCAL_PIN_LOGIN_ENABLED=true|LOCAL_PIN_HASH=.+|VITE_LOCAL_(USERNAME|DISPLAY_NAME)=.+' -- ':!scripts/check-clean-tree.sh' >/dev/null; then
  echo "A real local identity appears to be tracked. Keep it in ignored runtime files." >&2
  exit 1
fi

echo "Clean source profile passed: no tracked runtime data or local identity secrets."

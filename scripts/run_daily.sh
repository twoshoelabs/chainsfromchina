#!/bin/bash
# Daily pass. Refuses to start on a broken interpreter rather than falling back to system
# Python, which is how the sibling project lost two days of collection in September 2026.
set -uo pipefail
cd "$(dirname "$0")/.."
[ -f .env ] && set -a && . ./.env && set +a
PY=".venv/bin/python"
if ! "$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)' 2>/dev/null; then
  echo "$(date -u +%FT%TZ) venv interpreter missing or too old: $PY" >&2
  exit 78
fi
"$PY" -m us_chain_atlas run
rc=$?
"$PY" -m us_chain_atlas export
exit $rc

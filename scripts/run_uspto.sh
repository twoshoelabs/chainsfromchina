#!/bin/bash
# Weekly USPTO trademark pipeline-signal pass. Independent of the daily collection: it writes only
# to pipeline_signals in the local archive and NEVER touches the census or the published site.
# Dormant until USPTO_API_KEY is set in .env — with no key the collector skips cleanly (manual
# fallback), so scheduling it now is safe.
set -uo pipefail
cd "$(dirname "$0")/.."
[ -f .env ] && set -a && . ./.env && set +a
PY=".venv/bin/python"
if ! "$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)' 2>/dev/null; then
  echo "$(date -u +%FT%TZ) venv interpreter missing or too old: $PY" >&2
  exit 78
fi
echo "$(date -u +%FT%TZ) uspto pass start"
"$PY" -m chain_atlas uspto
echo "$(date -u +%FT%TZ) uspto pass done"

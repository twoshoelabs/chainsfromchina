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
"$PY" -m chain_atlas run
rc=$?
"$PY" -m chain_atlas export
# PRO alerts (pillar 2): detect today's changes across every layer (census + sightings + register +
# scale + filings) and surface any NOT yet delivered — a new US entrant, an outlet open/close, an
# abroad market, a scale change, a new filing. Runs AFTER export so it sees the fresh census, and
# BEFORE deploy.sh so the updated event log + baseline ride the same Refresh commit. Writes a durable
# digest to $CHAIN_ATLAS_DATA/alerts/digest.md, posts a local notification, and advances the cursor.
# Non-fatal: an alert failure must never fail collection.
"$PY" -m chain_atlas alerts notify --with-filings || true
# Launch-watch: quiet until a blocked chain's page changes state (e.g. Tai Er's staged US
# site going live). Never affects the run's exit code; a signal is logged to
# $CHAIN_ATLAS_DATA/launch_alerts.log and printed to this daily log.
"$PY" -m chain_atlas watch || true
# Publish the fresh site to chainsfromchina.com (gh-pages). Non-fatal: a failed deploy must
# never fail collection.
"$(dirname "$0")/deploy.sh" || echo "$(date -u +%FT%TZ) deploy failed (collection unaffected)" >&2
exit $rc

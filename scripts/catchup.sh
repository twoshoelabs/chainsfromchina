#!/bin/bash
# Catch-up net for the daily collection.
#
# The scheduled agent (com.dansilver.chain_atlas) fires at fixed times, but launchd does NOT wake a
# sleeping Mac, so if the laptop is asleep/closed at those times the day collection is silently
# skipped. That is what froze the site as-of date at 2026-10-19 for six days (Oct 20-25).
#
# This guard is driven by an HOURLY StartInterval agent (com.dansilver.chain_atlas.catchup) plus
# RunAtLoad. launchd coalesces any StartInterval fires missed while asleep into a single fire on
# wake, so within ~an hour of the Mac next being used an overdue collection self-corrects. It is
# cheap and idempotent:
#   - exits immediately if a run (scheduled or catch-up) is already in progress;
#   - exits immediately if the last recorded run is fresher than STALE_HOURS;
#   - otherwise runs the normal full pipeline (scripts/run_daily.sh) exactly once.
# It never shortens the normal daily cadence: with the ~daily scheduled runs the last run is always
# fresher than STALE_HOURS, so this only ever acts after a genuinely missed day.
set -uo pipefail
cd "$(dirname "$0")/.."
REPO="$(pwd)"
PY=".venv/bin/python"
STALE_HOURS="${CHAIN_ATLAS_STALE_HOURS:-20}"
stamp() { date -u +%FT%TZ; }

# Already collecting? (a scheduled run_daily, or a previous catch-up that execed into it)
if pgrep -f "scripts/run_daily.sh" >/dev/null 2>&1; then
  echo "$(stamp) catchup: a run is already in progress, skipping"; exit 0
fi

# Whole hours since the last recorded collection run (max(finished) in the runs table). Empty on any
# error, which the numeric guard below turns into a safe no-op (never spam runs on a read failure).
AGE_H=$("$PY" -c 'import os,sqlite3,datetime;from pathlib import Path;db=Path(os.environ.get("CHAIN_ATLAS_DATA",Path.home()/"chain_atlas_data"))/"chain_atlas.sqlite";r=sqlite3.connect(db).execute("select max(finished) from runs").fetchone()[0];print(10**6 if not r else int((datetime.datetime.now(datetime.timezone.utc)-datetime.datetime.fromisoformat(r)).total_seconds()//3600))' 2>/dev/null)

case "$AGE_H" in ""|*[!0-9]*) AGE_H="";; esac          # keep only a clean non-negative integer
if [ -z "$AGE_H" ]; then
  echo "$(stamp) catchup: could not read last run, skipping"; exit 0
fi
if [ "$AGE_H" -lt "$STALE_HOURS" ]; then
  echo "$(stamp) catchup: last run ${AGE_H}h ago (< ${STALE_HOURS}h), fresh, nothing to do"; exit 0
fi

echo "$(stamp) catchup: last run ${AGE_H}h ago (>= ${STALE_HOURS}h), running the daily pipeline"
exec /bin/bash "$REPO/scripts/run_daily.sh"

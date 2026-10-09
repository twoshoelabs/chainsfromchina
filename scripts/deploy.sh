#!/bin/bash
# Publish the static site (map/, WITH its exported data) to the gh-pages branch, which GitHub Pages
# serves at chainsfromchina.com. map/data/*.json is gitignored on main (it is derived), so it lives
# only here, on the deploy branch. Idempotent: re-run any time, and the nightly job can call it.
# Also syncs the SOURCE (main) to origin, so the GitHub source of truth never drifts behind what we
# publish — the register, sightings and code are backed up and the cloud routines see the real data.
set -euo pipefail
cd "$(dirname "$0")/.."
REPO="https://github.com/twoshoelabs/chainsfromchina.git"
PY=".venv/bin/python"

# Keep the source of truth (main) in step with what we publish. Best-effort: a deploy must still
# succeed if main can't fast-forward (diverged upstream, e.g. a merged routine PR) or we are offline.
if git push -q origin main 2>/dev/null; then
  echo "pushed source to origin/main"
else
  echo "WARNING: could not push main to origin (diverged or offline) — reconcile and push manually"
fi

"$PY" -m chain_atlas export >/dev/null           # fresh data into map/data

# The demographics snapshot (map/data/demographics.json) is a SLOW periodic job — a Census tract
# lookup per outlet — not part of the daily census, so it drifts behind the live roster between runs.
# Refresh it ONCE PER NY DAY (the census cadence), from the fresh stores.geojson export just wrote, so
# its "N of M storefronts" tracks the live open-outlet count rather than going stale. The first deploy
# of each NY day regenerates it; later deploys that day skip it. If an attempt is cut short (the Census
# endpoint rate-limits bursts), it BACKS OFF ~4h before retrying, so repeated deploys don't hammer a
# throttled endpoint and keep it from recovering — the cache means each attempt still makes progress.
# Never fails the deploy.
STALE="$("$PY" - <<'PYEOF' 2>/dev/null || echo yes
import json, os, time
try:
    from chain_atlas.config import today_ny
    g = json.load(open("demographics.json")).get("generated", "")
    if g and g == today_ny():
        print("no")                                       # already fresh today
    else:
        last = os.path.getmtime(".demo_attempt") if os.path.exists(".demo_attempt") else 0
        print("no" if (time.time() - last) < 4 * 3600 else "yes")   # back off 4h after an attempt
except Exception:
    print("yes")
PYEOF
)"
if [ "$STALE" = "yes" ]; then
  echo "refreshing demographics snapshot (not yet generated today, NY)…"
  touch .demo_attempt                                     # record the attempt for the 4h back-off
  # The Census pass can be very slow on a bad day, so CAP it — it must never hang the deploy. The
  # pass caches its coord/tract lookups as it goes, so a capped run still makes progress and the next
  # run resumes; the snapshot updates once the cache is warm enough to finish within the cap. (macOS
  # has no `timeout`, so a background job + a watchdog kill does the same portably.)
  "$PY" -m chain_atlas demographics >/dev/null 2>&1 &
  DEMO_PID=$!
  ( sleep 900; kill "$DEMO_PID" ) >/dev/null 2>&1 &
  WATCH_PID=$!
  if wait "$DEMO_PID" 2>/dev/null; then
    "$PY" -c "from pathlib import Path; from chain_atlas import demographics as d; d.export(Path('map/data'))" >/dev/null 2>&1 \
      && echo "  demographics refreshed" || echo "  demographics export skipped (error)"
  else
    echo "  demographics pass capped or failed — keeping previous snapshot (cache progress saved)"
  fi
  kill "$WATCH_PID" >/dev/null 2>&1 || true
fi

TMP="$(mktemp -d)"
cp -R map/. "$TMP"/
rm -f "$TMP"/img/README.md                        # a dev note, not part of the site
# Co-tenancy is a PAID/Pro feature: never publish its data or its renderer. export already omits
# centers.json; this removes the leftover renderer and guards the data file belt-and-suspenders.
# (centers.html stays — it is the public Pro gate.) See cfc-analytics-paywall.
rm -f "$TMP"/centers.js "$TMP"/data/centers.json
echo "chainsfromchina.com" > "$TMP"/CNAME         # custom domain
touch "$TMP"/.nojekyll                            # serve data/ and dot-paths as-is

# Cache-bust local CSS/JS: append a per-deploy version query to every style.css/app.js
# reference. Without this the CDN and browsers keep serving a stale stylesheet, so a redesign
# sits invisible until a manual hard refresh. perl -pi is used (not sed -i) to stay portable.
STAMP="$(date -u +%Y%m%d%H%M%S)"
# Logo cache-bust: a short content hash of all icon files. It changes only when an icon changes, so
# brand logos are cached normally but a swapped logo appears on a plain reload (no hard refresh). Each
# page carries window.CFC_ICON_V="?v=__ICONV__"; the JS appends it to every icons/<id>.png request.
ICONV="$(cat "$TMP"/icons/*.png 2>/dev/null | shasum | cut -c1-10)"
find "$TMP" -name '*.html' -print0 | xargs -0 perl -pi -e \
  "s{(href=\"[\w.-]+\.css)\"}{\$1?v=$STAMP\"}g; s{(src=\"[\w.-]+\.js)\"}{\$1?v=$STAMP\"}g; s{__ICONV__}{$ICONV}g"
(
  cd "$TMP"
  git init -q
  git checkout -q -b gh-pages
  git add -A
  git -c user.name="Twoshoe Labs" -c user.email="hello@twoshoelabs.com" \
      commit -q -m "Deploy $(date -u +%FT%TZ)"
  git push -qf "$REPO" gh-pages
)
rm -rf "$TMP"
echo "deployed to gh-pages ($(date -u +%FT%TZ))"

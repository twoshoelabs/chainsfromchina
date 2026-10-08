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
# Refresh it here AT MOST WEEKLY, from the fresh stores.geojson export just wrote, so the published
# section can't lag far. Throttled on the snapshot's own `generated` date; never fails the deploy.
STALE="$("$PY" - <<'PYEOF' 2>/dev/null || echo yes
import json, datetime as dt
try:
    g = json.load(open("demographics.json")).get("generated", "")
    print("yes" if (not g or (dt.date.today() - dt.date.fromisoformat(g)).days >= 7) else "no")
except Exception:
    print("yes")
PYEOF
)"
if [ "$STALE" = "yes" ]; then
  echo "refreshing demographics snapshot (>= 7 days old)…"
  "$PY" -m chain_atlas demographics >/dev/null 2>&1 \
    && "$PY" -c "from pathlib import Path; from chain_atlas import demographics as d; d.export(Path('map/data'))" >/dev/null 2>&1 \
    || echo "  demographics refresh skipped (error) — keeping the previous snapshot"
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

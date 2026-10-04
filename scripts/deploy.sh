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

TMP="$(mktemp -d)"
cp -R map/. "$TMP"/
rm -f "$TMP"/img/README.md                        # a dev note, not part of the site
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

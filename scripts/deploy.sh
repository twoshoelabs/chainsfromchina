#!/bin/bash
# Publish the static site (map/, WITH its exported data) to the gh-pages branch, which GitHub Pages
# serves at chainsfromchina.com. map/data/*.json is gitignored on main (it is derived), so it lives
# only here, on the deploy branch. Idempotent: re-run any time, and the nightly job can call it.
set -euo pipefail
cd "$(dirname "$0")/.."
REPO="https://github.com/twoshoelabs/chainsfromchina.git"
PY=".venv/bin/python"

"$PY" -m chain_atlas export >/dev/null           # fresh data into map/data

TMP="$(mktemp -d)"
cp -R map/. "$TMP"/
rm -f "$TMP"/img/README.md                        # a dev note, not part of the site
echo "chainsfromchina.com" > "$TMP"/CNAME         # custom domain
touch "$TMP"/.nojekyll                            # serve data/ and dot-paths as-is
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

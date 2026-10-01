#!/bin/bash
# Build a US Protomaps basemap (PMTiles) and upload it to Cloudflare R2 — no tile server, no API fees.
#
# WHAT IT DOES (one-time; re-run whenever you want a fresher basemap):
#   1. Finds Protomaps' latest daily global OSM build (a single hosted .pmtiles).
#   2. Extracts ONLY the US from it with `pmtiles extract`, which pulls just the US tiles over HTTP
#      range requests — no multi-GB download of the whole planet.
#   3. Uploads the US .pmtiles to your R2 bucket (R2 speaks the S3 API).
#   4. Sets CORS on the bucket so the browser can range-request the file.
#   5. Prints the public URL to paste into map/atlas.js (BASEMAP.pmtiles).
#
# PREREQS (install once):
#   • pmtiles CLI (go-pmtiles):  brew install pmtiles    (or a release from github.com/protomaps/go-pmtiles)
#   • aws CLI:                    brew install awscli
#
# CONFIG — set these env vars before running (secrets stay OUT of the repo; e.g. in your shell or a
# local, gitignored file you `source` first):
#   R2_ACCOUNT_ID    Cloudflare account id
#   R2_BUCKET        the R2 bucket name (create first: `wrangler r2 bucket create <name>` or the dashboard)
#   R2_ACCESS_KEY    an R2 API token's Access Key ID   (Cloudflare → R2 → Manage R2 API Tokens)
#   R2_SECRET_KEY    that token's Secret Access Key
#   R2_PUBLIC_BASE   the bucket's PUBLIC base URL — enable public access (an r2.dev URL) or attach a
#                    custom domain; e.g. https://pub-xxxxxxxx.r2.dev  or  https://tiles.chainsfromchina.com
# Optional:
#   PMTILES_SRC      override the source global build (default: latest build.protomaps.com daily)
#   US_BBOX          minlon,minlat,maxlon,maxlat (default covers CONUS + Alaska + Hawaii + Puerto Rico)
#   OUT_NAME         object key (default: us.pmtiles)
#   SITE_ORIGIN      origin allowed by CORS (default: https://chainsfromchina.com)
#
# USAGE:  R2_ACCOUNT_ID=... R2_BUCKET=... R2_ACCESS_KEY=... R2_SECRET_KEY=... R2_PUBLIC_BASE=... \
#           bash scripts/build_basemap.sh
set -euo pipefail

: "${R2_ACCOUNT_ID:?set R2_ACCOUNT_ID}"
: "${R2_BUCKET:?set R2_BUCKET}"
: "${R2_ACCESS_KEY:?set R2_ACCESS_KEY}"
: "${R2_SECRET_KEY:?set R2_SECRET_KEY}"
: "${R2_PUBLIC_BASE:?set R2_PUBLIC_BASE to the bucket public URL}"

US_BBOX="${US_BBOX:--179.9,15.0,-64.5,72.0}"   # CONUS + AK (incl. most Aleutians) + HI + PR
MAXZOOM="${MAXZOOM:-13}"                        # z13 ≈ street-level; plenty behind pins, ~a few GB.
                                               #   Raise to 14/15 for more detail (much bigger), or
                                               #   lower to 12 for a smaller file.
OUT_NAME="${OUT_NAME:-us.pmtiles}"
SITE_ORIGIN="${SITE_ORIGIN:-https://chainsfromchina.com}"
# The extract is cached here so a failed/retried upload does NOT re-download it. Delete to reclaim
# space, or set FORCE_EXTRACT=1 to rebuild it.
CACHE_DIR="${BASEMAP_CACHE:-$HOME/.cache/chain_atlas_basemap}"
LOCAL="$CACHE_DIR/$OUT_NAME"

command -v pmtiles >/dev/null || { echo "ERROR: install the pmtiles CLI (brew install pmtiles)"; exit 1; }
command -v aws     >/dev/null || { echo "ERROR: install the aws CLI (brew install awscli)"; exit 1; }
command -v curl    >/dev/null || { echo "ERROR: curl is required"; exit 1; }

WORK="$(mktemp -d)"; trap 'rm -rf "$WORK"' EXIT   # temp holds only the small CORS json
mkdir -p "$CACHE_DIR"

export AWS_ACCESS_KEY_ID="$R2_ACCESS_KEY"
export AWS_SECRET_ACCESS_KEY="$R2_SECRET_KEY"
ENDPOINT="https://${R2_ACCOUNT_ID}.r2.cloudflarestorage.com"

# 0) Preflight: verify the R2 token can reach the bucket BEFORE the ~10-minute extract, so an auth
#    problem fails in seconds, not after a big download.
echo "checking R2 access to bucket '$R2_BUCKET' ..."
if ! aws s3api head-bucket --bucket "$R2_BUCKET" --endpoint-url "$ENDPOINT" --region auto 2>/tmp/r2err; then
  echo "ERROR: cannot access the bucket with these credentials:"
  sed 's/^/    /' /tmp/r2err
  echo "    Fix: in Cloudflare → R2 → Manage R2 API Tokens, create an R2 API token with"
  echo "    'Object Read & Write' permission for bucket '$R2_BUCKET' (or All buckets), then pass its"
  echo "    Access Key ID as R2_ACCESS_KEY and Secret as R2_SECRET_KEY. (A generic Cloudflare API"
  echo "    token will NOT work here — it must be an R2 token that gives S3 credentials.)"
  exit 1
fi
echo "R2 access OK."

# 1) Resolve the latest Protomaps daily build unless one was given.
if [ -z "${PMTILES_SRC:-}" ]; then
  SRC=""
  for d in $(seq 0 7); do
    DATE=$(date -u -v-"${d}"d +%Y%m%d 2>/dev/null || date -u -d "-${d} day" +%Y%m%d)
    URL="https://build.protomaps.com/${DATE}.pmtiles"
    if curl -fsI "$URL" >/dev/null 2>&1; then SRC="$URL"; break; fi
  done
  [ -n "$SRC" ] || { echo "ERROR: no recent build found at build.protomaps.com; set PMTILES_SRC"; exit 1; }
  PMTILES_SRC="$SRC"
fi
echo "source build : $PMTILES_SRC"
echo "us bbox      : $US_BBOX  (max zoom $MAXZOOM)"
echo "output key   : $OUT_NAME"

# 2) Extract only the US, capped at MAXZOOM (range reads; no full-planet download). Cached so a
#    retried upload does NOT re-download it.
if [ -s "$LOCAL" ] && [ -z "${FORCE_EXTRACT:-}" ]; then
  echo "using cached extract: $LOCAL ($(ls -lh "$LOCAL" | awk '{print $5}')).  Set FORCE_EXTRACT=1 to rebuild."
else
  echo "extracting US subset to z$MAXZOOM (streams only the US tiles; a few minutes) ..."
  pmtiles extract "$PMTILES_SRC" "$LOCAL" --bbox="$US_BBOX" --maxzoom="$MAXZOOM"
  echo "built: $(ls -lh "$LOCAL" | awk '{print $5}')  $LOCAL"
fi

# 3) Upload to R2 (S3-compatible). application/octet-stream keeps range requests working.
echo "uploading -> s3://$R2_BUCKET/$OUT_NAME via R2 ..."
aws s3 cp "$LOCAL" "s3://$R2_BUCKET/$OUT_NAME" \
  --endpoint-url "$ENDPOINT" --region auto --content-type application/octet-stream

# 4) CORS so the browser can range-request the tiles.
CORS="$WORK/cors.json"
cat > "$CORS" <<JSON
{ "CORSRules": [ {
  "AllowedOrigins": ["$SITE_ORIGIN", "http://localhost:*", "http://127.0.0.1:*"],
  "AllowedMethods": ["GET", "HEAD"],
  "AllowedHeaders": ["Range", "If-Match", "If-None-Match"],
  "ExposeHeaders": ["ETag", "Content-Length", "Content-Range", "Accept-Ranges"],
  "MaxAgeSeconds": 86400
} ] }
JSON
aws s3api put-bucket-cors --bucket "$R2_BUCKET" --cors-configuration "file://$CORS" \
  --endpoint-url "$ENDPOINT" --region auto && echo "CORS set for $SITE_ORIGIN."

PUBLIC="${R2_PUBLIC_BASE%/}/$OUT_NAME"
echo
echo "=================================================================="
echo "DONE. Public PMTiles URL:"
echo "    $PUBLIC"
echo
echo "Switch the map onto it by editing map/atlas.js:"
echo "    BASEMAP.pmtiles = '$PUBLIC';"
echo "then redeploy (bash scripts/deploy.sh). Quick CORS check:"
echo "    curl -sI -H 'Range: bytes=0-0' -H 'Origin: $SITE_ORIGIN' '$PUBLIC' | grep -i 'access-control\\|content-range'"
echo "=================================================================="

"""
chain_atlas configuration.

Single rule, inherited from the sibling project store_atlas: every byte of collected state
lives under DATA_DIR. Code lives in git. Moving machines = copy DATA_DIR + clone repo.
"""
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

# The footprint is American; the collection day is therefore an American day. US/Eastern is
# chosen over UTC so that "stores as of the 14th" means what a US reader assumes it means.
# SITE-WIDE RULE: every date or time the site presents, and every date this pipeline generates for
# it, is New York time — never the host's clock (the publishing Mac runs on Asia/Taipei, so a bare
# date.today()/time.strftime() would stamp the wrong day). Use today_ny()/now_ny() below, not the
# stdlib's local-time helpers. The only sanctioned exception is a genuinely other-zone fact — a
# China-dated company announcement, or a late-night Honolulu opening already on tomorrow's NY date —
# where the event's own zone IS the fact; those are carried explicitly, not by accident of the host.
# (Machine provenance — financial_anchors/pipeline_signals `retrieved_at` — stays UTC-with-Z: it is
# never shown on the site, and a stable 'Z' keeps existing rows lexically sortable.)
TZ = ZoneInfo("America/New_York")


def today_ny() -> str:
    """Today's calendar date (YYYY-MM-DD) in New York time — the site's default zone."""
    return datetime.now(TZ).date().isoformat()


def now_ny(timespec: str = "seconds") -> str:
    """Current timestamp in New York time, ISO-8601 with offset (e.g. ...-04:00). Unambiguous NY."""
    return datetime.now(TZ).isoformat(timespec=timespec)

DATA_DIR = Path(os.environ.get("CHAIN_ATLAS_DATA", Path.home() / "chain_atlas_data")).expanduser()
DB_PATH = DATA_DIR / "chain_atlas.sqlite"
RAW_DIR = DATA_DIR / "raw"          # raw/<chain>/<YYYY-MM-DD>.<ext>.gz — immutable
LOG_DIR = DATA_DIR / "logs"

USER_AGENT = os.environ.get(
    "CHAIN_ATLAS_UA",
    "chain_atlas/0.1 (+mailto:set-me@example.com; daily first-party locator census)",
)
REQUEST_TIMEOUT = 30
DELAY_MIN_S = float(os.environ.get("CHAIN_ATLAS_DELAY_MIN", 4))
DELAY_MAX_S = float(os.environ.get("CHAIN_ATLAS_DELAY_MAX", 8))
MAX_RETRIES = 3

# USPTO trademark collector (Phase-1 pipeline signals). Official US-government data — public
# records, an official API, no third-party scraping. The current API requires a free key from the
# USPTO developer hub; without one the collector skips (manual fallback), never invents data.
# The base URL and response shape should be confirmed against USPTO's live API docs before the
# first live run — parse() is the only piece that depends on the exact field names.
USPTO_API_KEY = os.environ.get("USPTO_API_KEY", "").strip()
USPTO_API_BASE = os.environ.get("USPTO_API_BASE", "https://api.uspto.gov").rstrip("/")

# Capacity / official-receipts probe (Phase-2 revenue reality check). All sources are official
# open-data portals (TX Comptroller, city building/fire departments) read through their public
# Socrata/ArcGIS APIs — no third-party scraping. A Socrata "app token" is OPTIONAL: it only lifts
# the anonymous rate limit. Without one the probe still runs (just throttled); it never invents data.
SOCRATA_APP_TOKEN = os.environ.get("SOCRATA_APP_TOKEN", "").strip()


def ensure_dirs():
    """
    name:      ensure_dirs
    purpose:   Create the data-directory tree if absent.
    arguments: none
    returns:   None
    effects:   Creates DATA_DIR, RAW_DIR, LOG_DIR on disk.
    other:     Idempotent; safe to call on every run.
    """
    for p in (DATA_DIR, RAW_DIR, LOG_DIR):
        p.mkdir(parents=True, exist_ok=True)

"""
chain_atlas configuration.

Single rule, inherited from the sibling project store_atlas: every byte of collected state
lives under DATA_DIR. Code lives in git. Moving machines = copy DATA_DIR + clone repo.
"""
import os
from pathlib import Path
from zoneinfo import ZoneInfo

# The footprint is American; the collection day is therefore an American day. US/Eastern is
# chosen over UTC so that "stores as of the 14th" means what a US reader assumes it means.
TZ = ZoneInfo("America/New_York")

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

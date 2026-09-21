"""
The archive's shape. Observations are evidence and are never updated; stores and events
are derived from them and can be rebuilt.

Differences from the Taiwan sibling, all deliberate:
  * `name` replaces `name_zh` — these brands trade in English in the US, and their Chinese
    name is metadata about the parent, not about the store.
  * `status` gains `pre_opening`, because at least one chain (Mixue) publishes its pipeline:
    a store appears as `coming_soon` weeks before it trades. An announcement is not an opening
    and is never counted as one, but the transition between them is the most precise opening
    date this project can ever get, so both states are recorded.
"""
import sqlite3
from .config import DB_PATH, ensure_dirs

SCHEMA = """
CREATE TABLE IF NOT EXISTS chains (
    chain_id        TEXT PRIMARY KEY,      -- 'mixue', 'chagee', ...
    name            TEXT NOT NULL,         -- as it trades in the US
    name_zh         TEXT,                  -- parent's Chinese name, for the record
    origin          TEXT NOT NULL,         -- 'CN' — mainland-China-origin is this project's scope
    parent          TEXT,                  -- listed entity / franchisor
    format          TEXT NOT NULL,         -- 'tea','coffee','fastfood','lifestyle','toys','other'
    closure_n_days  INTEGER NOT NULL DEFAULT 7   -- consecutive absent days before 'closed'
);

-- One row per store identity. store_key = chain-provided code, else normalised address.
CREATE TABLE IF NOT EXISTS stores (
    store_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    chain_id    TEXT NOT NULL REFERENCES chains(chain_id),
    store_key   TEXT NOT NULL,
    store_code  TEXT,
    name        TEXT,
    addr_raw    TEXT,
    addr_norm   TEXT,
    city        TEXT,
    state       TEXT,                      -- USPS two-letter
    zip         TEXT,
    lat         REAL,
    lon         REAL,
    coord_src   TEXT,                      -- 'published' | 'geocoded' | NULL
    cell100     TEXT,                      -- 100 m Albers cell, NULL when unlocated
    first_seen  TEXT NOT NULL,             -- YYYY-MM-DD
    last_seen   TEXT NOT NULL,
    opened_on   TEXT,                      -- first day seen trading, as opposed to announced
    status      TEXT NOT NULL DEFAULT 'active',
                                           -- active | pre_opening | closed | temp_closed | withdrawn
    UNIQUE(chain_id, store_key)
);

-- One row per (day, chain, store). Never updated.
CREATE TABLE IF NOT EXISTS observations (
    obs_date    TEXT NOT NULL,
    chain_id    TEXT NOT NULL,
    store_key   TEXT NOT NULL,
    store_code  TEXT,
    name        TEXT,
    addr_raw    TEXT,
    addr_norm   TEXT,
    city        TEXT,
    state       TEXT,
    zip         TEXT,
    lat         REAL,
    lon         REAL,
    trading     INTEGER NOT NULL DEFAULT 1,  -- 0 = listed but not yet open (announced)
    temp_closed INTEGER NOT NULL DEFAULT 0,
    run_id      INTEGER,
    PRIMARY KEY (obs_date, chain_id, store_key)
);

CREATE TABLE IF NOT EXISTS events (
    event_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    detected_date TEXT NOT NULL,           -- the run date
    event_date    TEXT NOT NULL,           -- best estimate of the true date
    chain_id      TEXT NOT NULL,
    store_id      INTEGER NOT NULL,
    event_type    TEXT NOT NULL,           -- announced | opening | closure | reopen
                                           -- | relocation | withdrawn | temp_closed
    details       TEXT                     -- JSON
);

-- Every attempt, success or failure. A missing (date, chain) row = the collector never ran.
CREATE TABLE IF NOT EXISTS runs (
    run_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    obs_date    TEXT NOT NULL,
    chain_id    TEXT NOT NULL,
    started     TEXT NOT NULL,
    finished    TEXT,
    status      TEXT NOT NULL,             -- ok | failed | suppressed | blocked
    n_records   INTEGER,
    delta       INTEGER,
    raw_path    TEXT,
    raw_sha256  TEXT,
    error       TEXT
);

CREATE INDEX IF NOT EXISTS ix_obs_chain_date ON observations(chain_id, obs_date);
CREATE INDEX IF NOT EXISTS ix_stores_chain_status ON stores(chain_id, status);
CREATE INDEX IF NOT EXISTS ix_events_chain_date ON events(chain_id, event_date);
CREATE INDEX IF NOT EXISTS ix_runs_date ON runs(obs_date, chain_id);
"""


def connect() -> sqlite3.Connection:
    """
    name:      connect
    purpose:   Open the archive, creating it and its schema on first use.
    arguments: none
    returns:   sqlite3.Connection with row_factory set to sqlite3.Row
    effects:   Creates DATA_DIR and the database file; enables WAL.
    other:     WAL means the file must never be copied while a run is in flight; snapshot first.
    """
    ensure_dirs()
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA foreign_keys=ON")
    con.executescript(SCHEMA)
    return con


def upsert_chain(con, a):
    """
    name:      upsert_chain
    purpose:   Record the adapter's own description of its chain.
    arguments: con, a (Adapter)
    returns:   None
    effects:   Writes one row to chains.
    other:     The adapter is the single source of truth for chain metadata, so this
               overwrites rather than merges.
    """
    con.execute(
        "INSERT INTO chains (chain_id,name,name_zh,origin,parent,format,closure_n_days)"
        " VALUES (?,?,?,?,?,?,?)"
        " ON CONFLICT(chain_id) DO UPDATE SET name=excluded.name, name_zh=excluded.name_zh,"
        " origin=excluded.origin, parent=excluded.parent, format=excluded.format,"
        " closure_n_days=excluded.closure_n_days",
        (a.chain_id, a.name, a.name_zh, a.origin, a.parent, a.format, a.closure_n_days),
    )

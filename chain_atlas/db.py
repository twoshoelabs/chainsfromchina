"""
The archive's shape. Observations are evidence and are never updated; stores and events
are derived from them and can be rebuilt.

Differences from the Taiwan sibling, all deliberate:
  * `name` replaces `name_zh` — these brands trade in English in the US, and their Chinese
    name is metadata about the parent, not about the store.
  * Every row carries a `country`. The archive began as a US census and the US map still reads
    only US rows, but a chain is a chain wherever it trades: MINISO UAE publishes a locator of
    exactly the same kind, and refusing it because the schema said "state" would have been the
    schema choosing what the project is allowed to see.
  * `status` gains `pre_opening`, because at least one chain (Mixue) publishes its pipeline:
    a store appears as `coming_soon` weeks before it trades. An announcement is not an opening
    and is never counted as one, but the transition between them is the most precise opening
    date this project can ever get, so both states are recorded.
"""
import sqlite3
from .config import DB_PATH, ensure_dirs

SCHEMA = """
CREATE TABLE IF NOT EXISTS chains (
    chain_id        TEXT PRIMARY KEY,      -- 'mixue', 'chagee', 'miniso_ae', ...
    country         TEXT NOT NULL DEFAULT 'US',   -- ISO-3166-1 alpha-2 of the market collected
    name            TEXT NOT NULL,         -- as it trades in that market
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
    country     TEXT NOT NULL DEFAULT 'US',
    store_key   TEXT NOT NULL,
    store_code  TEXT,
    name        TEXT,
    addr_raw    TEXT,
    addr_norm   TEXT,
    city        TEXT,                      -- or the emirate / province outside the US
    state       TEXT,                      -- USPS two-letter; NULL outside the US
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
CREATE INDEX IF NOT EXISTS ix_stores_country ON stores(country, status);
CREATE INDEX IF NOT EXISTS ix_stores_chain_status ON stores(chain_id, status);
CREATE INDEX IF NOT EXISTS ix_events_chain_date ON events(chain_id, event_date);
CREATE INDEX IF NOT EXISTS ix_runs_date ON runs(obs_date, chain_id);
"""


def _migrate(con):
    """
    name:      _migrate
    purpose:   Add columns that CREATE TABLE IF NOT EXISTS cannot add to an existing archive.
    arguments: con
    returns:   None
    effects:   ALTERs chains and stores in place.
    other:     Runs against an archive that may predate any given column, so every lookup
               tolerates the table not existing yet (a fresh database has none of them).
               Deliberately additive only. An archive is the asset; a migration that could drop
               or rewrite a column has no business running automatically on connect.
    """
    for table, col, ddl in (("chains", "country", "TEXT NOT NULL DEFAULT 'US'"),
                            ("stores", "country", "TEXT NOT NULL DEFAULT 'US'")):
        have = {r[1] for r in con.execute(f"PRAGMA table_info({table})")}
        if have and col not in have:
            con.execute(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}")
            con.commit()


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
    # Migrate BEFORE the schema script: the script creates an index over stores(country), and
    # on an archive predating that column the index cannot be built until the column exists.
    _migrate(con)
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
        "INSERT INTO chains (chain_id,country,name,name_zh,origin,parent,format,closure_n_days)"
        " VALUES (?,?,?,?,?,?,?,?)"
        " ON CONFLICT(chain_id) DO UPDATE SET country=excluded.country, name=excluded.name,"
        " name_zh=excluded.name_zh, origin=excluded.origin, parent=excluded.parent,"
        " format=excluded.format, closure_n_days=excluded.closure_n_days",
        (a.chain_id, a.country, a.name, a.name_zh, a.origin, a.parent, a.format, a.closure_n_days),
    )

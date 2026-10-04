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

Phase 1 (intelligence) extends this archive across sectors without forking it: `chains` gains
cross-sector brand fields, `stores` gains pipeline/landlord location detail, `events` gains
first-class provenance, and four tables land empty for later phases — `shopping_centers`,
`entities`, `pipeline_signals`, `financial_anchors`. All additive; see docs/phase1_spec.md §4.
"""
import sqlite3
from .config import DB_PATH, ensure_dirs

SCHEMA = """
CREATE TABLE IF NOT EXISTS chains (
    chain_id        TEXT PRIMARY KEY,      -- 'mixue', 'chagee', 'miniso_ae', ...
    country         TEXT NOT NULL DEFAULT 'US',   -- ISO-3166-1 alpha-2 of the market collected
    name            TEXT NOT NULL,         -- as it trades in that market
    name_zh         TEXT,                  -- parent's Chinese name, for the record
    origin          TEXT NOT NULL,         -- 'CN' — China-origin is this project's scope
    parent          TEXT,                  -- listed entity / franchisor
    format          TEXT NOT NULL,         -- 'tea','coffee','fastfood','lifestyle','toys','other'
    closure_n_days  INTEGER NOT NULL DEFAULT 7,  -- consecutive absent days before 'closed'
    -- Phase 1 (intelligence): cross-sector brand fields. See docs/phase1_spec.md §4.2.
    sector                  TEXT,     -- food_drink|tea|coffee|bakery|grocery_convenience|snacks|
                                      -- apparel|beauty|lifestyle_variety|electronics|home
    sub_category            TEXT,
    tickers                 TEXT,     -- JSON array, e.g. ["HKEX:2020"]; NULL/[] for private
    us_entry_date           TEXT,     -- first US store open date; NULL if not in US
    operating_model         TEXT,     -- company_owned|franchise|master_franchise|license|jv|wholesale|dealer
    fdd_available           INTEGER,  -- 0/1/NULL(unknown): US franchise disclosure document on file
    franchise_available_us  INTEGER   -- 0/1/NULL
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
    coord_src   TEXT,                      -- 'published' | 'geocoded' | 'manual' | NULL
    cell100     TEXT,                      -- 100 m Albers cell, NULL when unlocated
    first_seen  TEXT NOT NULL,             -- YYYY-MM-DD
    last_seen   TEXT NOT NULL,
    opened_on   TEXT,                      -- first day seen trading, as opposed to announced
    status      TEXT NOT NULL DEFAULT 'active',
                                           -- active | pre_opening | closed | temp_closed | withdrawn
    -- Phase 1 (intelligence): location detail for the pipeline / landlord views. §4.3.
    metro               TEXT,      -- Census CBSA code
    center_id           TEXT,      -- soft FK -> shopping_centers.id (NULL for street/standalone)
    format              TEXT,      -- flagship|standard|mall_inline|street|food_hall|kiosk|pop_up|
                                   -- shop_in_shop|vending_robo|showroom
    square_footage      INTEGER,
    operator_entity_id  TEXT,      -- soft FK -> entities.id (the US LLC/franchisee that runs it)
    closed_on           TEXT,      -- mirrors opened_on
    popup_start         TEXT,      -- required when format='pop_up'
    popup_end           TEXT,
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
    format      TEXT,                         -- per-store format when the adapter knows it
                                              -- (e.g. 'vending_robo' for a POP MART ROBO SHOP)
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
    details       TEXT,                    -- JSON
    -- Phase 1 (intelligence): first-class provenance on every status change (= status_events). §4.4.
    source        TEXT,
    source_url    TEXT,
    retrieved_at  TEXT,                    -- UTC ISO-8601
    confidence    TEXT,                    -- high | medium | low
    evidence      TEXT,                    -- locator_appeared|locator_disappeared|permit|news|lease|
                                           -- review_silence|manual_visit
    supersedes_id INTEGER                  -- append-only: the event row this correction replaces
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

-- Phase 1 (intelligence). See docs/phase1_spec.md §4.5. These land EMPTY in Phase 1 and fill in
-- later phases; every row carries source/source_url/retrieved_at(UTC)/confidence, and corrections
-- are new rows (history is the product), never overwrites.

-- Shopping centers, for the co-tenancy / landlord view.
CREATE TABLE IF NOT EXISTS shopping_centers (
    id           TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    owner_reit   TEXT,
    class_tier   TEXT,                       -- A|B|C tier rubric (see docs); avoid subjective drift
    metro        TEXT,                       -- Census CBSA
    anchors      TEXT,                       -- JSON array
    source       TEXT,
    source_url   TEXT,
    retrieved_at TEXT,
    confidence   TEXT
);

-- US operating entities: the LLCs/corporations that run outlets (operator, franchisee, licensee...).
CREATE TABLE IF NOT EXISTS entities (
    id               TEXT PRIMARY KEY,
    kind             TEXT NOT NULL,          -- operator|franchisee|master_franchisee|licensee|
                                             -- us_subsidiary|importer_of_record
    name             TEXT NOT NULL,
    state            TEXT,
    file_number      TEXT,
    registered_agent TEXT,
    officers         TEXT,                   -- JSON array
    linked_brand_ids TEXT,                   -- JSON array of chain_id
    source           TEXT,
    source_url       TEXT,
    retrieved_at     TEXT,
    confidence       TEXT,
    supersedes_id    TEXT                    -- append-only: the entity row this correction replaces
);

-- Pipeline signals: USPTO filings, entity registrations, permits, mall listings, jobs, customs, news.
CREATE TABLE IF NOT EXISTS pipeline_signals (
    signal_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    signal_type  TEXT NOT NULL,              -- uspto|entity|permit|mall_listing|job_posting|customs|lease|news
    brand_id     TEXT,                       -- chain_id when matched; NULL = unlinked discovery lead
    location_id  INTEGER,                    -- soft FK -> stores.store_id
    filed_date   TEXT,
    summary      TEXT,
    raw_ref      TEXT,                       -- raw capture: path + sha256
    source       TEXT,
    source_url   TEXT,
    retrieved_at TEXT,
    confidence   TEXT
);

-- Financial anchors: filing- and FDD-derived numbers used to calibrate revenue models. §4.5.
CREATE TABLE IF NOT EXISTS financial_anchors (
    anchor_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    brand_id     TEXT REFERENCES chains(chain_id),
    period       TEXT,
    metric       TEXT,                       -- us_revenue|americas_revenue|auv|store_count|sss|
                                             -- overseas_segment|spend_per_guest|table_turnover
    value        REAL,
    unit         TEXT,
    page_ref     TEXT,
    source       TEXT,
    source_url   TEXT,
    retrieved_at TEXT,
    confidence   TEXT
);

-- Revenue estimates: MODELED outputs (anchors x store count). Always modeled, always a range,
-- always traceable to the financial_anchors it used. See docs/phase2_revenue_spec.md §3.2.
CREATE TABLE IF NOT EXISTS revenue_estimates (
    estimate_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    brand_id         TEXT REFERENCES chains(chain_id),
    scope            TEXT,                    -- us_total | outlet
    store_id         INTEGER REFERENCES stores(store_id),   -- set for outlet scope, else NULL
    period           TEXT,
    low              REAL,
    mid              REAL,
    high             REAL,
    unit             TEXT,                    -- USD
    method_version   TEXT,
    anchors_used     TEXT,                    -- JSON: anchor ids, weights, FX, apportionment
    store_count_used INTEGER,
    store_count_as_of TEXT,
    modeled          INTEGER DEFAULT 1,       -- always 1
    notes            TEXT,
    generated_at     TEXT
);
CREATE INDEX IF NOT EXISTS ix_revest_brand ON revenue_estimates(brand_id, scope, period);

CREATE INDEX IF NOT EXISTS ix_obs_chain_date ON observations(chain_id, obs_date);
CREATE INDEX IF NOT EXISTS ix_stores_country ON stores(country, status);
CREATE INDEX IF NOT EXISTS ix_stores_chain_status ON stores(chain_id, status);
CREATE INDEX IF NOT EXISTS ix_events_chain_date ON events(chain_id, event_date);
CREATE INDEX IF NOT EXISTS ix_runs_date ON runs(obs_date, chain_id);
CREATE INDEX IF NOT EXISTS ix_pipeline_brand ON pipeline_signals(brand_id);
CREATE INDEX IF NOT EXISTS ix_pipeline_type ON pipeline_signals(signal_type);
CREATE INDEX IF NOT EXISTS ix_entities_state ON entities(state);
CREATE INDEX IF NOT EXISTS ix_financhor_brand ON financial_anchors(brand_id, period);
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
               Each new column must ALSO appear in SCHEMA's CREATE (for fresh databases, where
               _migrate is a no-op because the table does not exist yet). The new intelligence
               tables (shopping_centers, entities, pipeline_signals, financial_anchors) need no
               entry here — CREATE TABLE IF NOT EXISTS in SCHEMA makes them on both paths.
    """
    # One-time rename to American spelling. The `shopping_centres` table and `stores.centre_id`
    # column were introduced 2026-09-30 and are empty and unused everywhere, so renaming them is
    # safe (the only exception to "additive only"). Guarded so it runs at most once per archive.
    tabs = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if "shopping_centres" in tabs and "shopping_centers" not in tabs:
        con.execute("ALTER TABLE shopping_centres RENAME TO shopping_centers")
        con.commit()
    scols = {r[1] for r in con.execute("PRAGMA table_info(stores)")}
    if "centre_id" in scols and "center_id" not in scols:
        con.execute("ALTER TABLE stores RENAME COLUMN centre_id TO center_id")
        con.commit()

    columns = (
        ("chains", "country", "TEXT NOT NULL DEFAULT 'US'"),
        ("stores", "country", "TEXT NOT NULL DEFAULT 'US'"),
        # Phase 1 — cross-sector brand fields on chains (docs/phase1_spec.md §4.2)
        ("chains", "sector", "TEXT"),
        ("chains", "sub_category", "TEXT"),
        ("chains", "tickers", "TEXT"),
        ("chains", "us_entry_date", "TEXT"),
        ("chains", "operating_model", "TEXT"),
        ("chains", "fdd_available", "INTEGER"),
        ("chains", "franchise_available_us", "INTEGER"),
        # Phase 1 — location detail on stores (§4.3)
        ("stores", "metro", "TEXT"),
        ("stores", "center_id", "TEXT"),
        ("stores", "format", "TEXT"),
        ("stores", "square_footage", "INTEGER"),
        ("stores", "operator_entity_id", "TEXT"),
        ("stores", "closed_on", "TEXT"),
        ("stores", "popup_start", "TEXT"),
        ("stores", "popup_end", "TEXT"),
        # A per-store format the adapter can assign (e.g. POP MART tells a staffed store from a
        # ROBO SHOP vending machine). Carried on the daily observation so the roster can keep it
        # current, and so a machine is never counted as a storefront.
        ("observations", "format", "TEXT"),
        # Phase 1 — provenance on events (= status_events) (§4.4)
        ("events", "source", "TEXT"),
        ("events", "source_url", "TEXT"),
        ("events", "retrieved_at", "TEXT"),
        ("events", "confidence", "TEXT"),
        ("events", "evidence", "TEXT"),
        ("events", "supersedes_id", "INTEGER"),
    )
    for table, col, ddl in columns:
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

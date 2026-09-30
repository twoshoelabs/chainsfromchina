"""
Phase-1 schema migration (docs/phase1_spec.md §4). The archive is the asset, so the migration
must be safe on both paths and never lossy:

  a FRESH database (executescript SCHEMA) has every intelligence column and table
  an OLD database (base columns only) gains the new columns via _migrate
  _migrate is idempotent — running it twice is a no-op, never an error
  the four new tables land EMPTY and round-trip a row carrying its provenance

These hold the line that the extension is additive: it adds fields and tables, it does not fork
the census or rewrite what is already recorded.

Run: .venv/bin/python tests/test_schema.py
"""
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from chain_atlas import db  # noqa: E402

CHAINS_NEW = {"sector", "sub_category", "tickers", "us_entry_date",
              "operating_model", "fdd_available", "franchise_available_us"}
STORES_NEW = {"metro", "center_id", "format", "square_footage",
              "operator_entity_id", "closed_on", "popup_start", "popup_end"}
EVENTS_NEW = {"source", "source_url", "retrieved_at", "confidence", "evidence", "supersedes_id"}
NEW_TABLES = {"shopping_centers", "entities", "pipeline_signals", "financial_anchors"}

# An archive as it looked BEFORE Phase 1 — base columns only.
OLD_SCHEMA = """
CREATE TABLE chains(chain_id TEXT PRIMARY KEY, country TEXT NOT NULL DEFAULT 'US', name TEXT NOT NULL,
  name_zh TEXT, origin TEXT NOT NULL, parent TEXT, format TEXT NOT NULL, closure_n_days INTEGER NOT NULL DEFAULT 7);
CREATE TABLE stores(store_id INTEGER PRIMARY KEY AUTOINCREMENT, chain_id TEXT NOT NULL, country TEXT NOT NULL DEFAULT 'US',
  store_key TEXT NOT NULL, first_seen TEXT NOT NULL, last_seen TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'active');
CREATE TABLE events(event_id INTEGER PRIMARY KEY AUTOINCREMENT, detected_date TEXT NOT NULL, event_date TEXT NOT NULL,
  chain_id TEXT NOT NULL, store_id INTEGER NOT NULL, event_type TEXT NOT NULL, details TEXT);
"""


def cols(con, t):
    return {r[1] for r in con.execute(f"PRAGMA table_info({t})")}


def tables(con):
    return {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def main():
    fails = []

    def check(label, got, want=True):
        ok = got == want
        print(f"  {'PASS' if ok else 'FAIL'}  {label}" + ("" if ok else f"  (got {got!r}, want {want!r})"))
        if not ok:
            fails.append(label)

    # Fresh path: executescript(SCHEMA) yields the full shape.
    fresh = sqlite3.connect(":memory:")
    fresh.executescript(db.SCHEMA)
    check("fresh DB has the four new tables", NEW_TABLES <= tables(fresh))
    check("fresh chains has the brand fields", CHAINS_NEW <= cols(fresh, "chains"))
    check("fresh stores has the location fields", STORES_NEW <= cols(fresh, "stores"))
    check("fresh events has the provenance fields", EVENTS_NEW <= cols(fresh, "events"))

    # Upgrade path: an old archive gains every new column, and _migrate is idempotent.
    old = sqlite3.connect(":memory:")
    old.executescript(OLD_SCHEMA)
    db._migrate(old)
    try:
        db._migrate(old)  # second run must be a clean no-op
        check("_migrate is idempotent", True)
    except sqlite3.OperationalError as e:
        check("_migrate is idempotent", f"raised {e}")
    check("migrated chains gains the brand fields", CHAINS_NEW <= cols(old, "chains"))
    check("migrated stores gains the location fields", STORES_NEW <= cols(old, "stores"))
    check("migrated events gains the provenance fields", EVENTS_NEW <= cols(old, "events"))

    # The new tables land empty and round-trip a provenance-carrying row.
    for t in NEW_TABLES:
        check(f"{t} lands empty", fresh.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0], 0)
    fresh.execute("INSERT INTO chains(chain_id,name,origin,format,sector,operating_model) "
                  "VALUES('anta','Anta','CN','apparel','apparel','company_owned')")
    fresh.execute("INSERT INTO entities(id,kind,name,state,source,retrieved_at,confidence) "
                  "VALUES('e1','licensee','Sightclassic LLC','WA','manual','2026-09-30T00:00:00Z','high')")
    fresh.execute("INSERT INTO pipeline_signals(signal_type,brand_id,source,retrieved_at,confidence) "
                  "VALUES('uspto','anta','USPTO','2026-09-30T00:00:00Z','high')")
    fresh.commit()
    check("entities round-trips a row", fresh.execute("SELECT name FROM entities").fetchone()[0], "Sightclassic LLC")
    check("pipeline_signals links to a brand", fresh.execute("SELECT brand_id FROM pipeline_signals").fetchone()[0], "anta")

    print("\n" + ("ALL PASS" if not fails else f"{len(fails)} FAILED: {fails}"))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())

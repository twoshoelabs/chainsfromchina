"""
Brand-identity unification (docs/phase1_spec.md §4.1, deliverable 2). register.json is the canonical
brand registry; sync_brands_to_db pushes its intelligence fields into the DB `chains` table and gives
every collected chain a sector. These tests hold:

  a register-listed brand gets its explicit intelligence fields (sector, tickers, operating_model...)
  a US-only adapter chain the register does not list still gets a sector, mapped from its `format`
  the sync only UPDATES — it never invents or deletes chains
  it is idempotent

Run: .venv/bin/python tests/test_brands.py
"""
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from chain_atlas import db, register  # noqa: E402

REG = {
    "chains": {
        # a register brand with explicit intelligence fields
        "anta": {"name": "Anta", "format": "apparel", "sector": "apparel",
                 "sub_category": "sportswear", "tickers": ["HKEX:2020"],
                 "operating_model": "company_owned", "us_entry_date": "2026-02-13",
                 "fdd_available": 0, "franchise_available_us": 0},
        # a register brand with no explicit sector -> mapped from format
        "mixue": {"name": "MIXUE", "format": "tea"},
    },
    "markets": {}, "entries": [],
}


def main():
    fails = []

    def check(label, got, want=True):
        ok = got == want
        print(f"  {'PASS' if ok else 'FAIL'}  {label}" + ("" if ok else f"  (got {got!r}, want {want!r})"))
        if not ok:
            fails.append(label)

    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row
    con.executescript(db.SCHEMA)
    # three collected chains: two the register lists, one US-only (grandmashome) it does not.
    con.executescript("""
      INSERT INTO chains(chain_id,name,origin,format) VALUES('anta','Anta','CN','apparel');
      INSERT INTO chains(chain_id,name,origin,format) VALUES('mixue','MIXUE','CN','tea');
      INSERT INTO chains(chain_id,name,origin,format) VALUES('grandmashome','Grandmas Home','CN','restaurant');
    """)
    con.commit()

    n = register.sync_brands_to_db(con, REG)
    check("sync touched all three collected chains", n, 3)

    row = con.execute("SELECT * FROM chains WHERE chain_id='anta'").fetchone()
    check("anta sector", row["sector"], "apparel")
    check("anta sub_category", row["sub_category"], "sportswear")
    check("anta tickers stored as JSON", row["tickers"], '["HKEX:2020"]')
    check("anta operating_model", row["operating_model"], "company_owned")
    check("anta us_entry_date", row["us_entry_date"], "2026-02-13")

    check("mixue sector mapped from format", con.execute(
        "SELECT sector FROM chains WHERE chain_id='mixue'").fetchone()["sector"], "tea")
    check("US-only grandmashome gets a sector from its format", con.execute(
        "SELECT sector FROM chains WHERE chain_id='grandmashome'").fetchone()["sector"], "food_drink")

    # only updates: no new/removed chains
    check("no chains invented or dropped", con.execute("SELECT COUNT(*) FROM chains").fetchone()[0], 3)
    # idempotent
    register.sync_brands_to_db(con, REG)
    check("idempotent — anta unchanged on re-run", con.execute(
        "SELECT tickers FROM chains WHERE chain_id='anta'").fetchone()["tickers"], '["HKEX:2020"]')

    # sector_of unit behaviour
    check("sector_of prefers explicit sector", register.sector_of({"sector": "beauty", "format": "tea"}), "beauty")
    check("sector_of falls back to format", register.sector_of({"format": "hotpot"}), "food_drink")
    check("sector_of unknown -> None", register.sector_of({"format": "mystery"}), None)

    print("\n" + ("ALL PASS" if not fails else f"{len(fails)} FAILED: {fails}"))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())

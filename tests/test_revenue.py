"""
The revenue model turns disclosed anchors + our store count into MODELED revenue ranges. Because
every number it emits is an estimate a Pro customer may lean on, the math must be exact, reproducible,
and honest about uncertainty. These tests pin the model: AUV from a disclosed daily rate, the derived
cross-check, the band widths, idempotency, and the "no anchor -> skip, never guess" rule.

Run: .venv/bin/python tests/test_revenue.py
"""
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from chain_atlas import revenue  # noqa: E402


def fresh():
    con = sqlite3.connect(":memory:")
    con.executescript("""
    CREATE TABLE stores(store_id INTEGER PRIMARY KEY AUTOINCREMENT, chain_id TEXT, country TEXT,
                        status TEXT, last_seen TEXT);
    CREATE TABLE financial_anchors(anchor_id INTEGER PRIMARY KEY AUTOINCREMENT, brand_id TEXT,
                        period TEXT, metric TEXT, value REAL, unit TEXT, page_ref TEXT, source TEXT,
                        source_url TEXT, retrieved_at TEXT, confidence TEXT);
    CREATE TABLE revenue_estimates(estimate_id INTEGER PRIMARY KEY AUTOINCREMENT, brand_id TEXT,
                        scope TEXT, store_id INTEGER, period TEXT, low REAL, mid REAL, high REAL,
                        unit TEXT, method_version TEXT, anchors_used TEXT, store_count_used INTEGER,
                        store_count_as_of TEXT, modeled INTEGER, notes TEXT, generated_at TEXT);
    """)
    return con


def anchors(con, brand, rows):
    for metric, value, unit in rows:
        con.execute("INSERT INTO financial_anchors(brand_id,period,metric,value,unit) VALUES(?,?,?,?,?)",
                    (brand, "2025", metric, value, unit))
    con.commit()


def stores(con, brand, n):
    for _ in range(n):
        con.execute("INSERT INTO stores(chain_id,country,status,last_seen) VALUES(?,?,?,?)",
                    (brand, "US", "active", "2026-10-01"))
    con.commit()


def main():
    fails = []

    def check(label, got, want=True):
        ok = got == want
        print(("PASS" if ok else "FAIL"), label, "" if ok else f"(got {got!r}, want {want!r})")
        if not ok:
            fails.append(label)

    # Case 1 — disclosed daily AUV + a segment cross-check (the Super Hi shape).
    con = fresh()
    anchors(con, "x", [("auv", 22.6, "USD_thousands_per_day"),
                       ("americas_revenue", 164695.0, "USD_thousands"),
                       ("store_count", 20.0, "restaurants")])
    stores(con, "x", 15)
    r = revenue.estimate(con, "x", "2025")
    check("per-outlet = 22.6k x 1000 x 365", r["per_outlet_usd_mid"], round(22.6 * 1000 * 365))
    check("US total = AUV x 15 (our count, not the filing's 20)", r["us_total_usd_mid"], round(22.6 * 1000 * 365 * 15))
    check("disclosed AUV -> tighter band 0.12", r["band"], 0.12)
    check("two-method cross-check agrees <1%", r["crosscheck_disagreement"] < 0.01, True)
    tot = con.execute("SELECT low,mid,high FROM revenue_estimates WHERE brand_id='x' AND scope='us_total'").fetchone()
    check("band low = mid x 0.88", round(tot[0]), round(tot[1] * 0.88))
    check("band high = mid x 1.12", round(tot[2]), round(tot[1] * 1.12))
    check("1 us_total + 15 outlet rows", con.execute("SELECT COUNT(*) FROM revenue_estimates WHERE brand_id='x'").fetchone()[0], 16)
    check("every estimate is modeled=1", con.execute("SELECT COUNT(*) FROM revenue_estimates WHERE brand_id='x' AND modeled=1").fetchone()[0], 16)
    revenue.estimate(con, "x", "2025")  # re-run
    check("idempotent (still 16 rows)", con.execute("SELECT COUNT(*) FROM revenue_estimates WHERE brand_id='x'").fetchone()[0], 16)

    # Case 2 — no disclosed daily rate: AUV derived from segment revenue / stores, wider band.
    con = fresh()
    anchors(con, "y", [("americas_revenue", 100000.0, "USD_thousands"), ("store_count", 10.0, "restaurants")])
    stores(con, "y", 8)
    r = revenue.estimate(con, "y", "2025")
    check("derived AUV = 100000k x 1000 / 10", r["per_outlet_usd_mid"], round(100000.0 * 1000 / 10))
    check("US total = derived AUV x 8", r["us_total_usd_mid"], round(100000.0 * 1000 / 10 * 8))
    check("derived-only -> wider band 0.25", r["band"], 0.25)

    # Case 3 — no anchors: skip, never guess.
    con = fresh()
    stores(con, "z", 3)
    r = revenue.estimate(con, "z", "2025")
    check("no anchor -> skipped (no row written)", "skipped" in r, True)
    check("no estimate rows written", con.execute("SELECT COUNT(*) FROM revenue_estimates WHERE brand_id='z'").fetchone()[0], 0)

    print("\n" + ("ALL PASS" if not fails else f"{len(fails)} FAIL: " + ", ".join(fails)))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())

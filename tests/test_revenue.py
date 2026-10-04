"""
The revenue model turns disclosed anchors + our store count into MODELED revenue ranges. Because every
number it emits is an estimate a Pro customer may lean on, the math must be exact and reproducible, and
a nonsensical AUV must be FLAGGED, not published. These tests pin: AUV from a disclosed daily rate, the
derived fallback, the band widths, idempotency, the unit-economics reality check (implied customers vs
a plausible / fire-code-bounded house), and the "no anchor -> skip, never guess" rule.

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
                        status TEXT, last_seen TEXT, square_footage REAL);
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


def stores(con, brand, n, sqft=None):
    for _ in range(n):
        con.execute("INSERT INTO stores(chain_id,country,status,last_seen,square_footage) VALUES(?,?,?,?,?)",
                    (brand, "US", "active", "2026-10-01", sqft))
    con.commit()


def rows(con, brand):
    return con.execute("SELECT COUNT(*) FROM revenue_estimates WHERE brand_id=?", (brand,)).fetchone()[0]


def main():
    fails = []

    def check(label, got, want=True):
        ok = got == want
        print(("PASS" if ok else "FAIL"), label, "" if ok else f"(got {got!r}, want {want!r})")
        if not ok:
            fails.append(label)

    # Case 1 — the Super Hi shape: disclosed daily AUV + spend/guest + turnover.
    con = fresh()
    anchors(con, "x", [("auv", 22.6, "USD_thousands_per_day"),
                       ("spend_per_guest", 39.9, "USD"), ("table_turnover", 4.0, "turns_per_day")])
    stores(con, "x", 15)
    r = revenue.estimate(con, "x", "2025")
    check("per-outlet = 22.6k x 1000 x 365", r["per_outlet_usd_mid"], round(22.6 * 1000 * 365))
    check("US total = AUV x 15", r["us_total_usd_mid"], round(22.6 * 1000 * 365 * 15))
    check("disclosed AUV -> band 0.12", r["band"], 0.12)
    check("reality check passed", r["checked"], True)
    check("guests/day = 22600 / 39.9", r["unit_economics"]["guests_per_day"], round(22600 / 39.9))
    check("peak seated = guests/day / 4.0 (party-free)", r["unit_economics"]["peak_seated"], round((22600 / 39.9) / 4.0))
    check("1 us_total + 15 outlet rows", rows(con, "x"), 16)
    revenue.estimate(con, "x", "2025")  # re-run
    check("idempotent (still 16)", rows(con, "x"), 16)

    # Case 2 — an absurd AUV is FLAGGED and NOT written.
    con = fresh()
    anchors(con, "big", [("auv", 500.0, "USD_thousands_per_day"),   # $500k/day -> ~3,100 seated at peak
                         ("spend_per_guest", 39.9, "USD"), ("table_turnover", 4.0, "turns_per_day")])
    stores(con, "big", 5)
    r = revenue.estimate(con, "big", "2025")
    check("implausible AUV -> flagged", "flagged" in r, True)
    check("implausible AUV -> nothing written", rows(con, "big"), 0)

    # Case 3 — square-footage (fire-code proxy) rejects an AUV too big for the house.
    con = fresh()
    anchors(con, "tiny", [("auv", 22.6, "USD_thousands_per_day"),
                          ("spend_per_guest", 39.9, "USD"), ("table_turnover", 4.0, "turns_per_day")])
    stores(con, "tiny", 3, sqft=500)   # 500 sqft -> ~33 occupant load, but peak seated ~142
    r = revenue.estimate(con, "tiny", "2025")
    check("peak seated over occupant load -> flagged", "flagged" in r, True)
    check("occupant-load reject -> nothing written", rows(con, "tiny"), 0)

    # Case 4 — no spend/turnover: can't reality-check, but still write (marked unchecked).
    con = fresh()
    anchors(con, "u", [("auv", 22.6, "USD_thousands_per_day")])
    stores(con, "u", 4)
    r = revenue.estimate(con, "u", "2025")
    check("no spend/turnover -> checked is None", r["checked"], None)
    check("still writes when unchecked", rows(con, "u"), 5)

    # Case 5 — derived AUV from segment revenue / stores, wider band, unchecked (no spend/turnover).
    con = fresh()
    anchors(con, "d", [("americas_revenue", 100000.0, "USD_thousands"), ("store_count", 10.0, "restaurants")])
    stores(con, "d", 8)
    r = revenue.estimate(con, "d", "2025")
    check("derived AUV = 100000k x 1000 / 10", r["per_outlet_usd_mid"], round(100000.0 * 1000 / 10))
    check("derived-only -> band 0.25", r["band"], 0.25)

    # Case 6 — no anchors: skip.
    con = fresh()
    stores(con, "z", 3)
    r = revenue.estimate(con, "z", "2025")
    check("no anchor -> skipped", "skipped" in r, True)
    check("no rows written", rows(con, "z"), 0)

    print("\n" + ("ALL PASS" if not fails else f"{len(fails)} FAIL: " + ", ".join(fails)))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())

"""
The capacity probe pulls OFFICIAL per-store facts (TX alcohol receipts; fire-code occupant load) to
reality-check the modeled revenue AUV. Because a Pro customer may lean on "flagged / not flagged", the
matching must be specific (right permittee, right store), the aggregation exact, the writes idempotent,
and an occupant load must feed the revenue check as a hard cap. These tests pin all of that offline with
an injected fetch_fn — no network.

Run: .venv/bin/python tests/test_capacity.py
"""
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from chain_atlas import capacity, revenue  # noqa: E402


def fresh():
    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row
    con.executescript("""
    CREATE TABLE chains(chain_id TEXT PRIMARY KEY, name TEXT);
    CREATE TABLE stores(store_id INTEGER PRIMARY KEY AUTOINCREMENT, chain_id TEXT, country TEXT,
                        status TEXT, addr_raw TEXT, addr_norm TEXT, city TEXT, state TEXT, zip TEXT,
                        last_seen TEXT, square_footage REAL, occupant_load INTEGER);
    CREATE TABLE pipeline_signals(signal_id INTEGER PRIMARY KEY AUTOINCREMENT, signal_type TEXT,
                        brand_id TEXT, location_id INTEGER, filed_date TEXT, summary TEXT, raw_ref TEXT,
                        source TEXT, source_url TEXT, retrieved_at TEXT, confidence TEXT);
    CREATE TABLE financial_anchors(anchor_id INTEGER PRIMARY KEY AUTOINCREMENT, brand_id TEXT,
                        period TEXT, metric TEXT, value REAL, unit TEXT);
    """)
    con.execute("INSERT INTO chains(chain_id,name) VALUES('haidilao','Haidilao')")
    con.commit()
    return con


def add_store(con, **kw):
    kw.setdefault("chain_id", "haidilao"); kw.setdefault("country", "US")
    kw.setdefault("status", "active"); kw.setdefault("last_seen", "2026-10-01")
    cols = ",".join(kw); ph = ",".join("?" * len(kw))
    cur = con.execute(f"INSERT INTO stores({cols}) VALUES({ph})", list(kw.values()))
    con.commit()
    return cur.lastrowid


# A 13-month TX Comptroller fixture (newest first), shaped like naix-2893 rows.
def tx_fixture(name="HAIDILAO HOT POT DALLAS", zp="75035", permit="RM1123560", monthly=7000):
    rows = []
    for i, ym in enumerate(["2026-08", "2026-07", "2026-06", "2026-05", "2026-04", "2026-03",
                            "2026-02", "2026-01", "2025-12", "2025-11", "2025-10", "2025-09", "2025-08"]):
        rows.append({"location_name": name, "location_zip": zp, "location_address": "9244 PRESTMONT PL STE 200",
                     "tabc_permit_number": permit, "obligation_end_date_yyyymmdd": f"{ym}-01T00:00:00.000",
                     "total_receipts": str(monthly)})
    return rows


def fetch_from(rows):
    """An injected soql transport: ignores the query, returns the fixture (zip filter is pre-applied)."""
    return lambda url, params: rows


def fetch_by_zip(zipmap):
    """An injected transport that honors the zip in the SoQL $where, so distinct stores (distinct
    permits) resolve to distinct rows — the way the live API would."""
    def f(url, params):
        where = params.get("$where", "")
        for zp, rows in zipmap.items():
            if f"location_zip='{zp}'" in where:
                return rows
        return []
    return f


def main():
    fails = []

    def check(label, got, want=True):
        ok = got == want
        print(("PASS" if ok else "FAIL"), label, "" if ok else f"(got {got!r}, want {want!r})")
        if not ok:
            fails.append(label)

    # --- brand tokens ---
    con = fresh()
    check("brand token = HAIDILAO", capacity.brand_tokens(con, "haidilao"), ["HAIDILAO"])

    # --- Case 1: TX receipts parse + trailing-12 aggregate ---
    con = fresh()
    sid = add_store(con, city="Frisco", state="TX", zip="75035", addr_raw="9244 Prestmont Pl")
    rec = capacity.tx_receipts({"store_id": sid, "state": "TX", "zip": "75035"},
                               ["HAIDILAO"], fetch_fn=fetch_from(tx_fixture(monthly=7000)))
    check("trailing 12 = 12 x 7000", rec["trailing_12_usd"], 84000)
    check("latest month = 7000", rec["latest_month_usd"], 7000)
    check("period = newest month", rec["period"], "2026-08")
    check("permit carried", rec["permit"], "RM1123560")
    check("source_url keys permit+period", rec["source_url"].endswith("permit=RM1123560&through=2026-08"), True)

    # --- Case 2: a non-TX store and a wrong-zip store never match ---
    con = fresh()
    sid2 = add_store(con, city="Flushing", state="NY", zip="11354")
    check("non-TX store -> None", capacity.tx_receipts({"store_id": sid2, "state": "NY", "zip": "11354"},
          ["HAIDILAO"], fetch_fn=fetch_from(tx_fixture())), None)
    check("empty source rows -> None", capacity.tx_receipts({"store_id": 1, "state": "TX", "zip": "75035"},
          ["HAIDILAO"], fetch_fn=fetch_from([])), None)

    # --- Case 3: collect() writes one capacity signal per TX store, idempotently ---
    con = fresh()
    add_store(con, city="Frisco", state="TX", zip="75035")
    add_store(con, city="Katy", state="TX", zip="77449")
    add_store(con, city="Flushing", state="NY", zip="11354")   # no TX receipts, no occupant feed
    tx = fetch_by_zip({
        "75035": tx_fixture(name="HAIDILAO HOT POT DALLAS", zp="75035", permit="RM1123560"),
        "77449": tx_fixture(name="HAIDILAO HOT POT", zp="77449", permit="MB200107885"),
    })
    s = capacity.collect(con, "haidilao", now="2026-10-04T00:00:00Z", fetch_fn=tx)
    check("3 stores probed", s["stores"], 3)
    check("2 TX receipts found", s["receipts_found"], 2)
    check("all 3 lack an occupant-load feed", s["unavailable"], 3)
    check("2 signals inserted (distinct permits)", s["inserted"], 2)
    n1 = con.execute("SELECT COUNT(*) FROM pipeline_signals WHERE signal_type='capacity'").fetchone()[0]
    check("2 capacity rows persisted", n1, 2)
    s2 = capacity.collect(con, "haidilao", now="2026-10-05T00:00:00Z", fetch_fn=tx)
    check("re-run inserts nothing", s2["inserted"], 0)
    check("re-run all duplicates", s2["duplicates"], 2)
    n2 = con.execute("SELECT COUNT(*) FROM pipeline_signals WHERE signal_type='capacity'").fetchone()[0]
    check("still 2 rows after re-run", n2, 2)

    # --- Case 4: an occupant-load source sets stores.occupant_load and revenue prefers it ---
    con = fresh()
    sid = add_store(con, city="Testville", state="ZZ", zip="00000", square_footage=9000)

    def fake_occ(store, now, fetch_fn=None):
        return {"occupant_load": 120, "source": "Testville FD", "source_url": "https://fd.test/co/1",
                "filed_date": "2025-01-01"}
    capacity.OCC_SOURCES[("ZZ", "Testville")] = fake_occ
    try:
        s = capacity.collect(con, "haidilao", now="2026-10-04T00:00:00Z", fetch_fn=fetch_from([]))
    finally:
        del capacity.OCC_SOURCES[("ZZ", "Testville")]
    check("occupant load found", s["occupant_found"], 1)
    ol = con.execute("SELECT occupant_load FROM stores WHERE store_id=?", (sid,)).fetchone()[0]
    check("stores.occupant_load set to 120", ol, 120)
    check("revenue median occupant load = 120", revenue._median_occupant_load(con, "haidilao"), 120)
    # unit_economics must use the OFFICIAL load as a hard cap (no 10% slack)
    anc = {"spend_per_guest": {"value": 39.9}, "table_turnover": {"value": 4.0}}
    st, det = revenue.unit_economics(22600, anc, sqft=9000, occupant_load=120)
    check("official load used, not sqft estimate", det["occupant_load_src"], "official")
    check("peak seated ~142 > official 120 -> fail", st, False)
    st2, det2 = revenue.unit_economics(22600, anc, sqft=9000, occupant_load=200)
    check("roomier official load -> pass", st2, True)

    # --- Case 5: reconcile() implied alcohol share + out-of-band flag ---
    con = fresh()
    sid = add_store(con, city="Frisco", state="TX", zip="75035")
    con.execute("INSERT INTO financial_anchors(brand_id,period,metric,value,unit) "
                "VALUES('haidilao','2025','auv',22.6,'USD_thousands_per_day')")
    con.commit()
    capacity.collect(con, "haidilao", now="2026-10-04T00:00:00Z", fetch_fn=fetch_from(tx_fixture(monthly=7336)))
    rc = capacity.reconcile(con, "haidilao", "2025")
    check("AUV annual = 22.6k x 365k", rc["auv_annual_usd"], round(22.6 * 1000 * 365))
    check("one store reconciled", len(rc["checks"]), 1)
    # 12 x 7336 = 88032 over 8.249M -> ~1.07% alcohol share, inside the band -> ok
    check("implied share ~1.07%", rc["checks"][0]["implied_alcohol_share"], round(88032 / (22.6 * 1000 * 365), 4))
    check("in-band -> not flagged", rc["flags"], 0)

    # Same receipts against an absurd 50x AUV -> alcohol share collapses to ~0.02% -> flagged.
    con = fresh()
    add_store(con, city="Frisco", state="TX", zip="75035")
    con.execute("INSERT INTO financial_anchors(brand_id,period,metric,value,unit) "
                "VALUES('haidilao','2025','auv',1130.0,'USD_thousands_per_day')")  # 50x
    con.commit()
    capacity.collect(con, "haidilao", now="2026-10-04T00:00:00Z", fetch_fn=fetch_from(tx_fixture(monthly=7336)))
    rc = capacity.reconcile(con, "haidilao", "2025")
    check("absurd AUV -> share below band", rc["checks"][0]["implied_alcohol_share"] < capacity.ALCOHOL_SHARE_MIN, True)
    check("absurd AUV -> flagged", rc["flags"], 1)

    # --- Case 6: no AUV anchor -> reconcile skips cleanly ---
    con = fresh()
    check("no AUV -> skipped", "skipped" in capacity.reconcile(con, "haidilao", "2025"), True)

    print("\n" + ("ALL PASS" if not fails else f"{len(fails)} FAIL: " + ", ".join(fails)))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())

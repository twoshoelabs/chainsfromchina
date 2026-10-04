"""
The filings collector watches SEC/HKEX/cninfo and signals a NEW annual report so a human re-verifies that
chain's anchors. It must find the right latest document, build the correct URL, prefer the full annual
over its 摘要 summary, fall back to a check-link when a venue can't be auto-queried, and be idempotent
(a filing already seen signals nothing). These tests pin all of that offline with injected fetchers.

Run: .venv/bin/python tests/test_filings.py
"""
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from chain_atlas import filings  # noqa: E402


def fresh():
    con = sqlite3.connect(":memory:")
    con.executescript("""
    CREATE TABLE pipeline_signals(signal_id INTEGER PRIMARY KEY AUTOINCREMENT, signal_type TEXT,
        brand_id TEXT, location_id INTEGER, filed_date TEXT, summary TEXT, raw_ref TEXT, source TEXT,
        source_url TEXT, retrieved_at TEXT, confidence TEXT);
    """)
    return con


SEC_JSON = json.dumps({"name": "MINISO Group Holding Ltd", "filings": {"recent": {
    "form": ["6-K", "20-F", "6-K"],
    "accessionNumber": ["0001104659-26-103582", "0001104659-26-048172", "0001104659-25-000001"],
    "primaryDocument": ["ex99.htm", "mnso-20251231x20f.htm", "old.htm"],
    "filingDate": ["2026-08-31", "2026-04-24", "2025-01-01"]}}})

CNINFO_JSON = json.dumps({"announcements": [
    {"announcementTitle": "2025年年度报告", "adjunctUrl": "finalpage/2026-04-23/1225156279.PDF", "announcementTime": 1777000000000},
    {"announcementTitle": "2025年年度报告摘要", "adjunctUrl": "finalpage/2026-04-23/1225156329.PDF", "announcementTime": 1777000000000}]})

HKEX_JSON = json.dumps({"result": json.dumps([
    {"TITLE": "Annual Report 2025", "DATE_TIME": "2026-04-20 12:00",
     "FILE_LINK": "/listedco/listconews/sehk/2026/0420/2026042000123.pdf"}])})


def main():
    fails = []

    def check(label, got, want=True):
        ok = got == want
        print(("PASS" if ok else "FAIL"), label, "" if ok else f"(got {got!r}, want {want!r})")
        if not ok:
            fails.append(label)

    # --- SEC: latest 20-F, correct URL ---
    s = filings.sec_latest(1815846, "20-F", fetch_fn=lambda: SEC_JSON)
    check("SEC picks the 20-F (not the 6-K)", s["accession"], "0001104659-26-048172")
    check("SEC date", s["date"], "2026-04-24")
    check("SEC URL built from accession+doc", s["url"],
          "https://www.sec.gov/Archives/edgar/data/1815846/000110465926048172/mnso-20251231x20f.htm")
    check("SEC missing form -> None", filings.sec_latest(1, "10-K", fetch_fn=lambda: SEC_JSON), None)

    # --- cninfo: latest full annual (skip 摘要), correct static URL ---
    c = filings.cninfo_latest("603517", "sse", fetch_fn=lambda: CNINFO_JSON, orgid_fn=lambda: "9900029519")
    check("cninfo prefers full over 摘要", c["title"], "2025年年度报告")
    check("cninfo static URL", c["url"], "http://static.cninfo.com.cn/finalpage/2026-04-23/1225156279.PDF")
    check("cninfo no orgId -> None", filings.cninfo_latest("x", fetch_fn=lambda: CNINFO_JSON, orgid_fn=lambda: None), None)

    # --- HKEX: check-link without stockId; parsed with one ---
    h0 = filings.hkex_latest("9992")
    check("HKEX without stockId -> check-link", "manual" in h0, True)
    h1 = filings.hkex_latest("9992", stockid="12345", fetch_fn=lambda: HKEX_JSON)
    check("HKEX with stockId -> parsed title", h1["title"], "Annual Report 2025")
    check("HKEX with stockId -> absolute URL", h1["url"],
          "https://www1.hkexnews.hk/listedco/listconews/sehk/2026/0420/2026042000123.pdf")

    # --- collect: new signal, idempotent, HKEX manual not stored ---
    con = fresh()
    filings_backup = filings.FILERS
    filings.FILERS = [
        {"brand_id": "miniso", "venue": "SEC", "cik": 1815846, "form": "20-F"},
        {"brand_id": "popmart", "venue": "HKEX", "stock": "9992"},   # no stockId -> manual
    ]
    try:
        fns = {"miniso": (lambda: SEC_JSON)}
        r = filings.collect(con, now="2026-10-05T00:00:00Z", fetch_fns=fns)
        check("collect: 1 new (SEC)", r["new"], 1)
        check("collect: 1 check-link (HKEX)", r["manual"], 1)
        check("collect: 1 filing signal stored", con.execute(
            "SELECT COUNT(*) FROM pipeline_signals WHERE signal_type='filing'").fetchone()[0], 1)
        check("collect: HKEX check-link NOT stored", con.execute(
            "SELECT COUNT(*) FROM pipeline_signals WHERE brand_id='popmart'").fetchone()[0], 0)
        r2 = filings.collect(con, now="2026-10-06T00:00:00Z", fetch_fns=fns)
        check("re-run: 0 new", r2["new"], 0)
        check("re-run: SEC now duplicate/current", r2["duplicate"], 1)
        check("re-run: still 1 signal", con.execute(
            "SELECT COUNT(*) FROM pipeline_signals").fetchone()[0], 1)
    finally:
        filings.FILERS = filings_backup

    print("\n" + ("ALL PASS" if not fails else f"{len(fails)} FAIL: " + ", ".join(fails)))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())

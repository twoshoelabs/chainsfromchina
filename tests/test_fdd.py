"""
The FDD collector turns a state franchise registry into the model's best US per-outlet anchor (Item 19)
and a census cross-check (Item 20). The figures feed revenue, so the parsing must be exact and must
NEVER invent a number: an opt-out ("we do not make any representations") yields no AUV, and an ambiguous
section yields no AUV. These tests pin the CARDS results parse, the newest-FDD pick, the Item 19 opt-out
vs figure logic, the Item 20 outlet counts, and collect_one's idempotent writes — all offline.

Run: .venv/bin/python tests/test_fdd.py
"""
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from chain_atlas import fdd  # noqa: E402


def fresh():
    con = sqlite3.connect(":memory:")
    con.executescript("""
    CREATE TABLE pipeline_signals(signal_id INTEGER PRIMARY KEY AUTOINCREMENT, signal_type TEXT,
        brand_id TEXT, location_id INTEGER, filed_date TEXT, summary TEXT, raw_ref TEXT, source TEXT,
        source_url TEXT, retrieved_at TEXT, confidence TEXT);
    CREATE TABLE financial_anchors(anchor_id INTEGER PRIMARY KEY AUTOINCREMENT, brand_id TEXT,
        period TEXT, metric TEXT, value REAL, unit TEXT, page_ref TEXT, source TEXT, source_url TEXT,
        retrieved_at TEXT, confidence TEXT);
    """)
    return con


def row(guid, num, fr, dt, yr):
    return (f'<tr><th>1</th><td><a href="/documents/{guid}/download?documentClass=FRANCHISE_REGISTRATIONS'
            f'&contentSequence=0">{num}</a></td><td>{fr}</td><td>TESTBRAND</td><td>{dt}</td>'
            f'<td>{yr}</td><td>9999</td></tr>')


RESULTS_HTML = "<table>" + row("{AAA-1}", "35686-202603-19", "TEST FRANCHISOR LLC", "Clean FDD", "2026") + \
    row("{BBB-2}", "33491-202504-05", "TEST FRANCHISOR LLC", "Clean FDD", "2025") + \
    row("{CCC-3}", "33491-202504-04", "TEST FRANCHISOR LLC", "Application (Form A)", "2025") + "</table>"

NORESULTS_HTML = "<p>No documents found for the provided criteria.</p>"

# Item 19 opt-out (the Miniso/Cotti pattern) + an Item 20 Table 1.
FDD_OPTOUT = """
TABLE OF CONTENTS ITEM 19 FINANCIAL PERFORMANCE REPRESENTATIONS 40
ITEM 19
FINANCIAL PERFORMANCE REPRESENTATIONS
We do not make any representations about a franchisee's future financial performance or the past
financial performance of company-owned or franchised outlets. We also do not authorize our employees
to make any such representations.
ITEM 20
OUTLETS AND FRANCHISEE INFORMATION
Table 1 Systemwide Outlet Summary
Franchised 2023 8 9 1 2024 9 13 4 2025 13 15 2
Company Owned 2023 2 2 0 2024 2 3 1 2025 3 4 1
Total Outlets 2023 10 11 1 2024 11 16 5 2025 16 19 3
ITEM 21 FINANCIAL STATEMENTS
"""

# Item 19 that DISCLOSES figures.
FDD_FIGURES = """
ITEM 19
FINANCIAL PERFORMANCE REPRESENTATIONS
During the 2025 fiscal year, the average gross sales of the 20 franchised outlets was $1,250,000,
and the median gross sales was $1,100,000. The highest gross sales were $2,400,000.
ITEM 20
OUTLETS AND FRANCHISEE INFORMATION
Franchised 2023 5 10 5 2024 10 20 10 2025 20 24 4
Company Owned 2023 0 0 0 2024 0 0 0 2025 0 0 0
ITEM 21
"""


def main():
    fails = []

    def check(label, got, want=True):
        ok = got == want
        print(("PASS" if ok else "FAIL"), label, "" if ok else f"(got {got!r}, want {want!r})")
        if not ok:
            fails.append(label)

    # --- parse_results + latest_fdd ---
    rows = fdd.parse_results(RESULTS_HTML)
    check("parsed 3 rows", len(rows), 3)
    check("guid decoded", rows[0]["guid"], "{AAA-1}")
    check("doc_type read", rows[0]["doc_type"], "Clean FDD")
    check("year read", rows[0]["year"], 2026)
    check("franchisor read", rows[0]["franchisor"], "TEST FRANCHISOR LLC")
    check("no results -> []", fdd.parse_results(NORESULTS_HTML), [])
    best = fdd.latest_fdd(rows, franchisor="TEST FRANCHISOR")
    check("latest = 2026 Clean FDD", (best["year"], best["doc_type"]), (2026, "Clean FDD"))
    check("latest ignores Form A", best["guid"], "{AAA-1}")
    check("doc_url format", fdd.doc_url("{AAA-1}").endswith("/documents/%7BAAA-1%7D/download?documentClass=FRANCHISE_REGISTRATIONS&contentSequence=0"), True)

    # --- item_section: takes the real section (last header), not the TOC line ---
    sec19 = fdd.item_section(FDD_OPTOUT, 19)
    check("item 19 section excludes item 20", "ITEM 20" not in sec19.replace("ITEM 20", "", 0) or sec19.count("OUTLETS AND FRANCHISEE") == 0, True)
    check("item 19 section has the FPR body", "do not make any representations" in sec19, True)

    # --- parse_item19: opt-out vs figures ---
    o = fdd.parse_item19(fdd.item_section(FDD_OPTOUT, 19))
    check("opt-out detected", o["opt_out"], True)
    check("opt-out -> no AUV", o["auv"], None)
    check("opt-out -> no figures", o["figures"], [])
    f = fdd.parse_item19(fdd.item_section(FDD_FIGURES, 19))
    check("figures: opt-out False", f["opt_out"], False)
    check("figures: average captured", ("average", 1250000.0) in f["figures"], True)
    check("figures: median captured", ("median", 1100000.0) in f["figures"], True)
    check("AUV = the average", f["auv"], 1250000.0)

    # --- parse_item20: latest-year outlet counts, blocks not bleeding ---
    t = fdd.parse_item20(fdd.item_section(FDD_OPTOUT, 20))
    check("item20 year = 2025", t["year"], 2025)
    check("item20 franchised end = 15", t["franchised_end"], 15)
    check("item20 company end = 4", t["company_end"], 4)
    check("item20 total end = 19", t["total_end"], 19)

    # --- collect_one: opt-out franchisor -> fdd signal, NO anchor ---
    con = fresh()
    def fetch_optout(url, raw=False):
        if "franchise-registrations" in url:
            return RESULTS_HTML
        return b"%PDF-fake"            # bytes for the doc; extract_text is monkeypatched below
    orig = fdd.extract_text
    fdd.extract_text = lambda b: FDD_OPTOUT
    try:
        r = fdd.collect_one(con, {"brand_id": "x", "franchisor": "TEST FRANCHISOR"},
                            now="2026-10-04T00:00:00Z", fetch_fn=fetch_optout)
    finally:
        fdd.extract_text = orig
    check("opt-out: status is opt-out", "opt-out" in r["status"], True)
    check("opt-out: 1 fdd signal", con.execute("SELECT COUNT(*) FROM pipeline_signals WHERE signal_type='fdd'").fetchone()[0], 1)
    check("opt-out: NO anchor written", con.execute("SELECT COUNT(*) FROM financial_anchors WHERE metric='fdd_item19_auv'").fetchone()[0], 0)
    check("opt-out: Item 20 in summary", "19 US outlets" in con.execute("SELECT summary FROM pipeline_signals").fetchone()[0], True)
    # idempotent: same FDD url -> nothing new
    fdd.extract_text = lambda b: FDD_OPTOUT
    try:
        r2 = fdd.collect_one(con, {"brand_id": "x", "franchisor": "TEST FRANCHISOR"},
                             now="2026-10-05T00:00:00Z", fetch_fn=fetch_optout)
    finally:
        fdd.extract_text = orig
    check("re-run -> duplicate", "duplicate" in r2, True)
    check("re-run: still 1 signal", con.execute("SELECT COUNT(*) FROM pipeline_signals").fetchone()[0], 1)

    # --- collect_one: disclosing franchisor -> signal + anchor ---
    con = fresh()
    def fetch_fig(url, raw=False):
        return RESULTS_HTML if "franchise-registrations" in url else b"%PDF-fake"
    fdd.extract_text = lambda b: FDD_FIGURES
    try:
        r = fdd.collect_one(con, {"brand_id": "y", "franchisor": "TEST FRANCHISOR"},
                            now="2026-10-04T00:00:00Z", fetch_fn=fetch_fig)
    finally:
        fdd.extract_text = orig
    check("figures: AUV returned", r["auv"], 1250000.0)
    check("figures: anchor written", con.execute("SELECT value FROM financial_anchors WHERE brand_id='y' AND metric='fdd_item19_auv'").fetchone()[0], 1250000.0)
    check("figures: anchor confidence medium", con.execute("SELECT confidence FROM financial_anchors WHERE brand_id='y'").fetchone()[0], "medium")

    print("\n" + ("ALL PASS" if not fails else f"{len(fails)} FAIL: " + ", ".join(fails)))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())

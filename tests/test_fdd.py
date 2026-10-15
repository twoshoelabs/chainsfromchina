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
    CREATE TABLE fdd_extracts(doc_number TEXT PRIMARY KEY, brand_id TEXT, franchisor TEXT, year INTEGER,
        state TEXT, items_json TEXT, needs_human_read INTEGER DEFAULT 0, source_url TEXT, retrieved_at TEXT);
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

# Item 7 estimated initial investment (a low–high total + line items).
FDD_ITEM7 = """
ITEM 7
ESTIMATED INITIAL INVESTMENT
Type of Expenditure Amount Method of Payment When Due To Whom Payment Is To Be Made
Initial Franchise Fee $45,000 Lump Sum Before Opening Us
Leasehold Improvements $120,000 to $350,000 As Incurred Before Opening Suppliers
Equipment and Fixtures $80,000 to $160,000 As Incurred Before Opening Suppliers
Opening Inventory $15,000 to $30,000 Before Opening Suppliers
TOTAL ESTIMATED INITIAL INVESTMENT $300,000 to $675,000
ITEM 8
RESTRICTIONS ON SOURCES OF PRODUCTS AND SERVICES
"""

# A full FDD carrying Item 7 + an Item 19 with figures + Item 20 — for the end-to-end collector test.
FDD_FULL = FDD_ITEM7 + FDD_FIGURES

# Item 21: the body points to an exhibit, and the audited statements follow after Items 22/23. The most
# recent fiscal year is the LEFT column; net income is a parenthesised negative; a going-concern note.
FDD_ITEM21 = """
ITEM 21
FINANCIAL STATEMENTS
Our audited financial statements for the years ended December 31, 2025 and 2024 are attached as
Exhibit E.
ITEM 22 CONTRACTS
ITEM 23 RECEIPTS
EXHIBIT E
TEST FRANCHISOR LLC STATEMENTS OF OPERATIONS
Years Ended December 31, 2025 2024
Total revenues $ 12,500,000 $ 8,200,000
Cost of revenues 7,100,000 4,900,000
Net income (loss) (1,350,000) (2,100,000)
BALANCE SHEETS
Total assets $ 6,400,000 $ 4,200,000
Total stockholders' equity 2,100,000 1,000,000
The accompanying notes raise substantial doubt about the Company's ability to continue as a going concern.
"""

# A full FDD that also carries audited statements (two ITEM 21 headers; item21_scope takes the last).
FDD_FULL21 = FDD_FULL + FDD_ITEM21

# Item 8: a restrictive supply chain — required/approved suppliers, franchisor as sole source,
# proprietary goods, and supplier rebates (the four flags all present).
FDD_ITEM8 = """
ITEM 8
RESTRICTIONS ON SOURCES OF PRODUCTS AND SERVICES
You must purchase all food ingredients, packaging and proprietary sauces only from us or from
suppliers we have approved and designated. We are the sole supplier of our secret recipe seasoning.
We and our affiliates may receive rebates and allowances from approved suppliers based on the
purchases made by franchisees in the system.
ITEM 9
FRANCHISEE'S OBLIGATIONS
"""

# An unrestrictive Item 8 (no flags should fire).
FDD_ITEM8_OPEN = ("ITEM 8 RESTRICTIONS ON SOURCES OF PRODUCTS AND SERVICES "
                  "We do not currently restrict the suppliers you may use. ITEM 9")

# Items 1-4: parent/affiliates, business experience, and clean litigation/bankruptcy.
FDD_ITEM1234 = """
ITEM 1
THE FRANCHISOR, AND ANY PARENTS, PREDECESSORS, AND AFFILIATES
We are TEST FRANCHISOR LLC, a limited liability company organized under the laws of Delaware. We are
a wholly-owned subsidiary of Test Global Holdings Group. Our parent conducts business in China.
ITEM 2
BUSINESS EXPERIENCE
Wei Zhang, Chief Executive Officer. Mr. Zhang has served since 2018.
John Smith, Chief Financial Officer. Mr. Smith has served since 2020.
ITEM 3
LITIGATION
No litigation is required to be disclosed in this Item.
ITEM 4
BANKRUPTCY
No bankruptcy is required to be disclosed in this Item.
ITEM 5
INITIAL FEES
"""

# Items 3/4 with disclosed litigation and a prior bankruptcy.
FDD_ITEM34_POS = ("ITEM 3 LITIGATION Smith v. Test Franchisor LLC, filed in the Superior Court; the "
                  "plaintiff alleges breach of contract. ITEM 4 BANKRUPTCY In 2019, the predecessor "
                  "filed a petition under Chapter 11 of the Bankruptcy Code. ITEM 5 INITIAL FEES")

# An older filer (earliest FDD is 2019/2020) — the new-entrant watch should NOT flag it.
RESULTS_OLD = "<table>" + row("{OLD-1}", "11111-202003-19", "OLD FRANCHISOR LLC", "Clean FDD", "2020") + \
    row("{OLD-2}", "11111-201903-19", "OLD FRANCHISOR LLC", "Clean FDD", "2019") + "</table>"

# A rich Item 20: Table 1 (3-year series), Table 3 (status -> churn), Table 4 (by state), Table 5 (projected).
FDD_ITEM20_FULL = """
ITEM 20
OUTLETS AND FRANCHISEE INFORMATION
Table No. 1 Systemwide Outlet Summary
Franchised 2023 8 9 1 2024 9 13 4 2025 13 15 2
Company Owned 2023 2 2 0 2024 2 3 1 2025 3 4 1
Total Outlets 2023 10 11 1 2024 11 16 5 2025 16 19 3
Table No. 3 Status of Franchised Outlets
Year Start Opened Terminations Non-Renewals Reacquired Ceased-Other End
2023 8 2 0 0 0 1 9
2024 9 5 1 0 0 0 13
2025 13 4 1 1 0 0 15
Table No. 4 Outlets by State
California 6 1 7
New York 5 0 5
Texas 4 0 4
Table No. 5 Projected Openings
State Signed Not Opened Projected New Franchised Projected New Company
California 3 5 1
New York 2 4 0
Totals 6 11 1
ITEM 21
"""


def main():
    fails = []

    def check(label, got, want=True):
        ok = got == want
        print(("PASS" if ok else "FAIL"), label, "" if ok else f"(got {got!r}, want {want!r})")
        if not ok:
            fails.append(label)

    # --- Registry abstraction: MN enabled & scriptable; CA/WI disabled with reasons ---
    check("MN registry enabled", fdd.MN.ENABLED, True)
    check("MN search_url hits franchise-registrations", "franchise-registrations" in fdd.MN.search_url(franchisor="X"), True)
    check("MN doc_url from a row", fdd.MN.doc_url({"guid": "{AAA-1}"}).endswith("contentSequence=0"), True)
    check("CA registry disabled", fdd.REGISTRIES["CA"].ENABLED, False)
    check("CA carries a reason", bool(fdd.REGISTRIES["CA"].BLOCKED_REASON), True)
    check("WI registry disabled", fdd.REGISTRIES["WI"].ENABLED, False)
    # collect_one on a disabled registry: skip with the reason, no network, no rows written
    conx = fresh()
    rskip = fdd.collect_one(conx, {"brand_id": "yangs", "franchise_name": "Yang's Braised Chicken"},
                            now="2026-10-15T00:00:00Z", registry=fdd.REGISTRIES["CA"])
    check("disabled registry -> skipped", "skipped" in rskip, True)
    check("disabled registry -> no signal written", conx.execute("SELECT COUNT(*) FROM pipeline_signals").fetchone()[0], 0)

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

    # --- parse_item7: total low-high + line items, None-on-ambiguity ---
    i7 = fdd.parse_item7(fdd.item_section(FDD_ITEM7, 7))
    check("item7 total low = 300000", i7["low"], 300000)
    check("item7 total high = 675000", i7["high"], 675000)
    check("item7 franchise-fee line", i7["lines"].get("Initial Franchise Fee"), [45000, 45000])
    check("item7 leasehold range line", i7["lines"].get("Leasehold Improvements"), [120000, 350000])
    check("item7 TOTAL not a line item", any("TOTAL" in k.upper() for k in i7["lines"]), False)
    check("item7 clean parse not flagged", i7["needs_human_read"], False)
    check("empty item7 -> no total", fdd.parse_item7("")["low"], None)
    check("empty item7 -> not flagged", fdd.parse_item7("")["needs_human_read"], False)
    amb = fdd.parse_item7("ITEM 7 ESTIMATED INITIAL INVESTMENT See the chart in Exhibit C.")
    check("ambiguous item7 flagged for human", amb["needs_human_read"], True)

    # --- collect_one: Item 7 -> fdd_extracts row + item7 anchors ---
    con = fresh()
    def fetch_full(url, raw=False):
        return RESULTS_HTML if "franchise-registrations" in url else b"%PDF-fake"
    fdd.extract_text = lambda b: FDD_FULL
    try:
        r = fdd.collect_one(con, {"brand_id": "z", "franchisor": "TEST FRANCHISOR"},
                            now="2026-10-14T00:00:00Z", fetch_fn=fetch_full)
    finally:
        fdd.extract_text = orig
    check("item7: invest range returned", r["invest"], (300000, 675000))
    check("item7: one fdd_extracts row", con.execute("SELECT COUNT(*) FROM fdd_extracts").fetchone()[0], 1)
    check("item7: extract keyed on doc_number", con.execute("SELECT doc_number FROM fdd_extracts").fetchone()[0], "35686-202603-19")
    check("item7: extract holds item7 json", '"item7"' in con.execute("SELECT items_json FROM fdd_extracts").fetchone()[0], True)
    check("item7: low anchor written", con.execute("SELECT value FROM financial_anchors WHERE brand_id='z' AND metric='fdd_item7_invest_low'").fetchone()[0], 300000.0)
    check("item7: high anchor written", con.execute("SELECT value FROM financial_anchors WHERE brand_id='z' AND metric='fdd_item7_invest_high'").fetchone()[0], 675000.0)
    check("item7: Item 7 in summary", "Item 7 invest" in con.execute("SELECT summary FROM pipeline_signals WHERE brand_id='z'").fetchone()[0], True)
    # idempotent: re-running the same FDD adds no new extract row or anchors
    fdd.extract_text = lambda b: FDD_FULL
    try:
        fdd.collect_one(con, {"brand_id": "z", "franchisor": "TEST FRANCHISOR"},
                        now="2026-10-15T00:00:00Z", fetch_fn=fetch_full)
    finally:
        fdd.extract_text = orig
    check("item7: re-run still 1 extract row", con.execute("SELECT COUNT(*) FROM fdd_extracts").fetchone()[0], 1)
    check("item7: re-run still 1 low anchor", con.execute("SELECT COUNT(*) FROM financial_anchors WHERE brand_id='z' AND metric='fdd_item7_invest_low'").fetchone()[0], 1)

    # --- parse_item21: measured figures from the audited statements (most-recent/left column) ---
    i21 = fdd.parse_item21(fdd.item21_scope(FDD_ITEM21))
    check("item21 revenue = 12.5M (left column)", i21["revenue"], 12500000)
    check("item21 net income = -1.35M (parens negative)", i21["net_income"], -1350000)
    check("item21 total assets = 6.4M", i21["total_assets"], 6400000)
    check("item21 going-concern flagged", i21["going_concern"], True)
    check("item21 clean parse not flagged", i21["needs_human_read"], False)
    check("item21 skips the year column header", i21["revenue"] != 2025, True)
    # pointer-only Item 21 (statements are an image exhibit we can't read) -> None, flagged
    ptr = fdd.parse_item21("ITEM 21 FINANCIAL STATEMENTS Audited statements are attached as Exhibit E.")
    check("item21 pointer -> no revenue", ptr["revenue"], None)
    check("item21 pointer flagged for human", ptr["needs_human_read"], True)
    check("item21 empty -> not flagged", fdd.parse_item21("")["needs_human_read"], False)

    # --- collect_one: Item 21 -> measured us_revenue anchor + extract + going-concern in summary ---
    con = fresh()
    fdd.extract_text = lambda b: FDD_FULL21
    try:
        r = fdd.collect_one(con, {"brand_id": "w", "franchisor": "TEST FRANCHISOR"},
                            now="2026-10-14T00:00:00Z", fetch_fn=fetch_full)
    finally:
        fdd.extract_text = orig
    check("item21: us_revenue returned", r["us_revenue"], 12500000)
    check("item21: going_concern returned", r["going_concern"], True)
    check("item21: us_revenue anchor written", con.execute("SELECT value FROM financial_anchors WHERE brand_id='w' AND metric='fdd_item21_us_revenue'").fetchone()[0], 12500000.0)
    check("item21: anchor source names Item 21", "Item 21" in con.execute("SELECT source FROM financial_anchors WHERE brand_id='w' AND metric='fdd_item21_us_revenue'").fetchone()[0], True)
    check("item21: revenue in extract json", '"revenue": 12500000' in con.execute("SELECT items_json FROM fdd_extracts WHERE brand_id='w'").fetchone()[0], True)
    check("item21: going-concern in summary", "going-concern" in con.execute("SELECT summary FROM pipeline_signals WHERE brand_id='w'").fetchone()[0], True)
    check("item21: still gets Item 7 anchor too", con.execute("SELECT value FROM financial_anchors WHERE brand_id='w' AND metric='fdd_item7_invest_high'").fetchone()[0], 675000.0)

    # --- parse_item20 (full): series, churn, projected, by-state (backward-compatible keys intact) ---
    t = fdd.parse_item20(fdd.item_section(FDD_ITEM20_FULL, 20))
    check("item20 latest ends unchanged (15/4/19)", (t["franchised_end"], t["company_end"], t["total_end"]), (15, 4, 19))
    check("item20 franchised 3-year series", t["franchised_series"], [(2023, 9), (2024, 13), (2025, 15)])
    check("item20 company 3-year series", t["company_series"], [(2023, 2), (2024, 3), (2025, 4)])
    check("item20 latest-year status row", (t["franchised_status_latest"]["start"], t["franchised_status_latest"]["opened"], t["franchised_status_latest"]["end"]), (13, 4, 15))
    check("item20 gross departures = start+opened-end = 2", t["franchised_status_latest"]["left_system"], 2)
    check("item20 projected signed-not-open = 6", t["projected"]["signed_not_open"], 6)
    check("item20 projected new franchised = 11", t["projected"]["projected_new_franchised"], 11)
    check("item20 by-state parsed", t["by_state"], {"CA": 6, "NY": 5, "TX": 4})
    check("item20 full not flagged", t["needs_human_read"], False)
    # a bare Table 1 (no Table 3/5/state) -> series only, projected/status None, no false by-state
    t1 = fdd.parse_item20(fdd.item_section(FDD_OPTOUT, 20))
    check("item20 bare: projected None", t1["projected"], None)
    check("item20 bare: status None", t1["franchised_status_latest"], None)
    check("item20 bare: by_state empty", t1["by_state"], {})
    check("item20 bare: series still parsed", t1["franchised_series"], [(2023, 9), (2024, 13), (2025, 15)])

    # --- collect_one: Item 20-full stored in extract + projected in summary ---
    con = fresh()
    def fetch_i20(url, raw=False):
        return RESULTS_HTML if "franchise-registrations" in url else b"%PDF-fake"
    fdd.extract_text = lambda b: FDD_ITEM20_FULL
    try:
        fdd.collect_one(con, {"brand_id": "v", "franchisor": "TEST FRANCHISOR"},
                        now="2026-10-14T00:00:00Z", fetch_fn=fetch_i20)
    finally:
        fdd.extract_text = orig
    ij = con.execute("SELECT items_json FROM fdd_extracts WHERE brand_id='v'").fetchone()[0]
    check("item20: projected in extract json", '"projected_new_franchised": 11' in ij, True)
    check("item20: by_state in extract json", '"CA": 6' in ij, True)
    check("item20: projected in summary", "+11 projected next FY" in con.execute("SELECT summary FROM pipeline_signals WHERE brand_id='v'").fetchone()[0], True)

    # --- parse_item8: supply-chain flags (restrictive vs open) ---
    i8 = fdd.parse_item8(fdd.item_section(FDD_ITEM8, 8))
    check("item8 required suppliers", i8["required_suppliers"], True)
    check("item8 franchisor is supplier", i8["franchisor_is_supplier"], True)
    check("item8 rebates", i8["rebates"], True)
    check("item8 proprietary goods", i8["proprietary"], True)
    check("item8 restrictive not flagged", i8["needs_human_read"], False)
    u8 = fdd.parse_item8(fdd.item_section(FDD_ITEM8_OPEN, 8))
    check("item8 open: no flags fire", any([u8["required_suppliers"], u8["franchisor_is_supplier"], u8["rebates"], u8["proprietary"]]), False)
    check("item8 open: flagged for human", u8["needs_human_read"], True)
    check("item8 empty: not flagged", fdd.parse_item8("")["needs_human_read"], False)

    # --- collect_one: Item 8 flags -> extract json + supply note in summary ---
    con = fresh()
    def fetch_i8(url, raw=False):
        return RESULTS_HTML if "franchise-registrations" in url else b"%PDF-fake"
    fdd.extract_text = lambda b: FDD_ITEM8
    try:
        fdd.collect_one(con, {"brand_id": "u", "franchisor": "TEST FRANCHISOR"},
                        now="2026-10-15T00:00:00Z", fetch_fn=fetch_i8)
    finally:
        fdd.extract_text = orig
    ij = con.execute("SELECT items_json FROM fdd_extracts WHERE brand_id='u'").fetchone()[0]
    check("item8: rebates flag in extract json", '"rebates": true' in ij, True)
    check("item8: franchisor_is_supplier in extract json", '"franchisor_is_supplier": true' in ij, True)
    check("item8: supply note in summary", "Item 8: " in con.execute("SELECT summary FROM pipeline_signals WHERE brand_id='u'").fetchone()[0], True)
    check("item8: rebates named in summary", "supplier rebates" in con.execute("SELECT summary FROM pipeline_signals WHERE brand_id='u'").fetchone()[0], True)

    # --- parse_item1/2/3/4: lineage, principals, risk flags ---
    i1 = fdd.parse_item1(fdd.item_section(FDD_ITEM1234, 1))
    check("item1 parent captured", (i1["parent"] or "").startswith("Test Global Holdings"), True)
    check("item1 state of organization", i1["incorporated_in"], "Delaware")
    i2 = fdd.parse_item2(fdd.item_section(FDD_ITEM1234, 2))
    names = [p["name"] for p in i2["principals"]]
    check("item2 CEO captured", "Wei Zhang" in names, True)
    check("item2 CFO captured", "John Smith" in names, True)
    check("item2 title captured", i2["principals"][0]["title"], "Chief Executive Officer")
    i3 = fdd.parse_item3(fdd.item_section(FDD_ITEM1234, 3))
    check("item3 no litigation disclosed", i3["has_litigation"], False)
    i4 = fdd.parse_item4(fdd.item_section(FDD_ITEM1234, 4))
    check("item4 no bankruptcy disclosed", i4["has_bankruptcy"], False)
    i3p = fdd.parse_item3(fdd.item_section(FDD_ITEM34_POS, 3))
    check("item3 litigation detected", i3p["has_litigation"], True)
    check("item3 case counted", i3p["case_count"] >= 1, True)
    i4p = fdd.parse_item4(fdd.item_section(FDD_ITEM34_POS, 4))
    check("item4 bankruptcy detected", i4p["has_bankruptcy"], True)

    # --- collect_one: Items 1-4 in the extract + new-entrant watch (recent vs old first filing) ---
    con = fresh()
    def fetch_1234(url, raw=False):
        return RESULTS_HTML if "franchise-registrations" in url else b"%PDF-fake"
    fdd.extract_text = lambda b: FDD_ITEM1234
    try:
        rnf = fdd.collect_one(con, {"brand_id": "nf", "franchisor": "TEST FRANCHISOR"},
                              now="2026-10-15T00:00:00Z", fetch_fn=fetch_1234)
    finally:
        fdd.extract_text = orig
    ij = con.execute("SELECT items_json FROM fdd_extracts WHERE brand_id='nf'").fetchone()[0]
    check("item1: parent in extract json", '"parent": "Test Global Holdings' in ij, True)
    check("item1: incorporated_in Delaware", '"incorporated_in": "Delaware"' in ij, True)
    check("item2: principal in extract json", '"Wei Zhang"' in ij, True)
    check("new-entrant: recent first filing flagged", rnf["first_filing"], True)
    check("new-entrant: marker in summary", "new US franchise entrant" in con.execute("SELECT summary FROM pipeline_signals WHERE brand_id='nf'").fetchone()[0], True)
    # an old filer must NOT be flagged as a new entrant
    con = fresh()
    def fetch_old(url, raw=False):
        return RESULTS_OLD if "franchise-registrations" in url else b"%PDF-fake"
    fdd.extract_text = lambda b: FDD_OPTOUT
    try:
        rold = fdd.collect_one(con, {"brand_id": "old", "franchisor": "OLD FRANCHISOR"},
                               now="2026-10-15T00:00:00Z", fetch_fn=fetch_old)
    finally:
        fdd.extract_text = orig
    check("new-entrant: old filer not flagged", rold["first_filing"], False)
    check("new-entrant: no marker for old filer", "new US franchise entrant" in con.execute("SELECT summary FROM pipeline_signals WHERE brand_id='old'").fetchone()[0], False)

    print("\n" + ("ALL PASS" if not fails else f"{len(fails)} FAIL: " + ", ".join(fails)))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())

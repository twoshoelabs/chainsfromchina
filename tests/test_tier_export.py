"""
The tier-gated exporter (docs/pro_spec.md build #5) is a PAYWALL GATE: a lower tier must never receive
Pro-only data. These tests pin the per-tier field allowlist and, critically, that the china_stores
split + source and the seeded economics anchor CANNOT appear in the public or observer bundles, while
pro gets them and intelligence adds the assembled dossier. Offline; the DB-backed economics is seeded,
the file-backed layers read live manual/ data for one real brand (chabaidao).

Run: .venv/bin/python tests/test_tier_export.py
"""
import json
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from chain_atlas import tier_export as T  # noqa: E402

BRAND = "chabaidao"        # real china_stores entry (china 8621 / overseas 38, HKEX:2555), has a dossier
SECRET = 99999123.0        # a distinctive seeded anchor value we track across the gate


def fresh():
    con = sqlite3.connect(":memory:")
    con.executescript("""
    CREATE TABLE financial_anchors(anchor_id INTEGER PRIMARY KEY AUTOINCREMENT, brand_id TEXT,
        period TEXT, metric TEXT, value REAL, unit TEXT, page_ref TEXT, source TEXT, source_url TEXT,
        retrieved_at TEXT, confidence TEXT);
    CREATE TABLE revenue_estimates(estimate_id INTEGER PRIMARY KEY AUTOINCREMENT, brand_id TEXT,
        scope TEXT, store_id INTEGER, period TEXT, low REAL, mid REAL, high REAL, unit TEXT,
        method_version TEXT, anchors_used TEXT, store_count_used INTEGER, store_count_as_of TEXT,
        modeled INTEGER, notes TEXT, generated_at TEXT);
    CREATE TABLE fdd_extracts(doc_number TEXT PRIMARY KEY, brand_id TEXT, franchisor TEXT, year INTEGER,
        state TEXT, items_json TEXT, needs_human_read INTEGER, source_url TEXT, retrieved_at TEXT);
    """)
    return con


def main():
    fails = []

    def check(label, got, want=True):
        ok = got == want
        print(("PASS" if ok else "FAIL"), label, "" if ok else f"(got {got!r}, want {want!r})")
        if not ok:
            fails.append(label)

    con = fresh()
    con.execute("INSERT INTO financial_anchors(brand_id,period,metric,value,confidence,source) "
                "VALUES(?,?,?,?,?,?)", (BRAND, "2025", "group_revenue", SECRET, "high", "FY2025 filing"))
    con.commit()

    pub = T.export(con, "public", brands=[BRAND])["brands"][BRAND]
    obs = T.export(con, "observer", brands=[BRAND])["brands"][BRAND]
    pro = T.export(con, "pro", brands=[BRAND])["brands"][BRAND]
    intel = T.export(con, "intelligence", brands=[BRAND])["brands"][BRAND]

    # --- field allowlist per tier ---
    check("public keys", set(pub), {"brand", "name", "name_zh", "presence", "worldwide_total"})
    check("observer adds abroad (not economics)", set(obs) - set(pub), {"abroad"})
    check("pro adds the analytics layers", {"scale", "economics", "structure", "narrative"} <= set(pro), True)
    check("intelligence adds the dossier report", "dossier_markdown" in intel, True)
    check("public still carries the public worldwide total", pub["worldwide_total"]["n"] is not None, True)

    # --- THE GATE: Pro-only data must be absent from public + observer ---
    for name, slc in (("public", pub), ("observer", obs)):
        raw = json.dumps(slc, ensure_ascii=False)
        check(f"{name}: no china split (8621)", "8621" not in raw, True)
        check(f"{name}: no china_stores source (HKEX:2555)", "2555" not in raw, True)
        check(f"{name}: no seeded economics anchor", str(int(SECRET)) not in raw, True)
        check(f"{name}: no economics/scale/narrative keys", not ({"scale", "economics", "narrative"} & set(slc)), True)
    # --- pro DOES contain them ---
    proraw = json.dumps(pro, ensure_ascii=False)
    check("pro: china split present", "8621" in proraw, True)
    check("pro: economics anchor present", str(int(SECRET)) in proraw, True)

    # --- write() round-trip; intelligence emits per-brand .md ---
    tmp = tempfile.mkdtemp()
    files = T.write(T.export(con, "intelligence", brands=[BRAND]), tmp)
    check("wrote bundle.json", any(f.endswith("bundle.json") for f in files), True)
    check("wrote per-brand dossier md", any(f.endswith(f"{BRAND}.md") for f in files), True)
    check("dossier md readable", "PRO dossier" in Path(os.path.join(tmp, "dossiers", f"{BRAND}.md")).read_text(), True)
    # a public write has no dossiers dir
    tmp2 = tempfile.mkdtemp()
    pubfiles = T.write(T.export(con, "public", brands=[BRAND]), tmp2)
    check("public write = bundle only", len(pubfiles), 1)

    # --- bad tier raises ---
    raised = False
    try:
        T.export(con, "enterprise", brands=[BRAND])
    except ValueError:
        raised = True
    check("unknown tier rejected", raised, True)

    # ========================= full dataset (build order #4) =========================
    pds = T.dataset(con, "public", brands=[BRAND])
    ods = T.dataset(con, "observer", brands=[BRAND])
    rds = T.dataset(con, "pro", brands=[BRAND])

    # --- table gating: a table appears only at/above its min tier ---
    check("public tables", set(pds["tables"]), {"brands", "outlets"})
    check("observer adds closings+abroad", set(ods["tables"]) - set(pds["tables"]), {"closings", "abroad"})
    check("pro adds the analytics + events tables",
          {"scale", "economics", "structure", "narrative", "events"} <= set(rds["tables"]), True)
    check("events table is pro-gated (absent public/observer)",
          "events" not in pds["tables"] and "events" not in ods["tables"], True)

    # --- THE GATE on the flat dataset: Pro-only values must not appear below pro ---
    for name, ds in (("public", pds), ("observer", ods)):
        raw = json.dumps(ds, ensure_ascii=False)
        check(f"dataset {name}: no economics anchor", str(int(SECRET)) not in raw, True)
        check(f"dataset {name}: no china split (8621)", "8621" not in raw, True)
    check("dataset pro: economics anchor present",
          str(int(SECRET)) in json.dumps(rds, ensure_ascii=False), True)

    # --- aggregates gate too ---
    check("public aggregates: core counts", {"brands_tracked", "us_outlets_total"} <= set(pds["aggregates"]), True)
    check("public aggregates: no event rollups", "new_us_entrants_90d" not in pds["aggregates"], True)
    check("pro aggregates: event rollups present", "new_us_entrants_90d" in rds["aggregates"], True)

    # --- manifest lists only emitted tables ---
    check("manifest tables match emitted", {t["name"] for t in pds["manifest"]["tables"]}, set(pds["tables"]))

    # --- write_dataset: CSVs + README + manifest; economics.csv is pro-only ---
    td = tempfile.mkdtemp()
    wf = T.write_dataset(rds, td)
    check("wrote bundle.json", any(f.endswith("bundle.json") for f in wf), True)
    check("wrote README.md", any(f.endswith("README.md") for f in wf), True)
    check("wrote outlets.csv", os.path.exists(os.path.join(td, "data", "outlets.csv")), True)
    check("pro wrote economics.csv", os.path.exists(os.path.join(td, "data", "economics.csv")), True)
    check("economics.csv carries the anchor", str(int(SECRET)) in
          Path(os.path.join(td, "data", "economics.csv")).read_text(), True)

    tp = tempfile.mkdtemp()
    T.write_dataset(pds, tp)
    check("public write has NO economics.csv", not os.path.exists(os.path.join(tp, "data", "economics.csv")), True)
    check("public economics value absent from every public file", all(
        str(int(SECRET)) not in Path(os.path.join(dp, f)).read_text()
        for dp, _, fs in os.walk(tp) for f in fs), True)

    print("\n" + ("ALL PASS" if not fails else f"{len(fails)} FAIL: " + ", ".join(fails)))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())

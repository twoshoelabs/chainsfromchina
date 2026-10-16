"""
The dossier-assembly command (docs/pro_spec.md build #2) pulls all five PRO layers for one chain into
one provenance-carrying document. These tests pin: the DB-backed economics/structure pulls (against a
seeded in-memory db), that the file-backed layers assemble for a real core brand (mixue), the Markdown
render, and that an unknown brand yields an empty-but-valid dossier (no crash, nothing fabricated).

Run: .venv/bin/python tests/test_dossier.py
"""
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from chain_atlas import dossier  # noqa: E402


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
    con.execute("INSERT INTO financial_anchors(brand_id,period,metric,value,unit,source,confidence) "
                "VALUES('mixue','2025','group_revenue',33559923.0,'RMB_thousands','FY2025 results','high')")
    con.execute("INSERT INTO revenue_estimates(brand_id,scope,period,low,mid,high,unit,method_version,generated_at) "
                "VALUES('mixue','us_total','2025',1000000,1500000,2000000,'USD','v3','2026-10-16T00:00:00Z')")
    con.execute("INSERT INTO fdd_extracts(doc_number,brand_id,year,items_json) VALUES('d1','mixue',2025,'"
                '{"item7":{"low":272000,"high":843000},"item8":{"rebates":true},'
                '"item20":{"projected":{"projected_new_franchised":11}},'
                '"item3":{"has_litigation":false},"item4":{"has_bankruptcy":false}}' "')")
    con.commit()

    d = dossier.assemble(con, "mixue")
    check("all 5 layers present", set(d) >= {"presence", "scale", "economics", "structure", "narrative"}, True)
    check("presence us_outlets is int", isinstance(d["presence"]["us_outlets"], int), True)
    check("presence tier = measured", d["presence"]["tier"], "measured")
    check("scale.home present (mixue in china_stores)", d["scale"]["home"] is not None, True)
    check("scale.abroad is a list", isinstance(d["scale"]["abroad"], list), True)
    check("narrative present (mixue has dossier)", d["narrative"] is not None, True)
    # DB-backed layers from the seeded connection
    check("economics anchor pulled", any(a["metric"] == "group_revenue" for a in d["economics"]["anchors"]), True)
    check("economics us estimate pulled", d["economics"]["us_revenue_estimate"]["mid"], 1500000)
    check("structure fdd investment", d["structure"]["fdd"]["initial_investment"], [272000, 843000])
    check("structure fdd supply flag", d["structure"]["fdd"]["supply_flags"], ["rebates"])
    check("structure fdd projected openings", d["structure"]["fdd"]["projected_openings"], 11)

    md = dossier.render_markdown(d)
    check("markdown has title", "PRO dossier" in md, True)
    check("markdown has all sections", all(
        h in md for h in ["## Presence", "## Scale", "## Economics", "## Structure", "## Narrative"]), True)
    check("markdown shows seeded investment", "$272,000" in md, True)

    # unknown brand -> empty-but-valid, nothing fabricated, no crash
    e = dossier.assemble(con, "no_such_brand_xyz")
    check("unknown brand -> 0 outlets", e["presence"]["us_outlets"], 0)
    check("unknown brand -> no home scale", e["scale"]["home"], None)
    check("unknown brand -> no narrative", e["narrative"], None)
    check("unknown brand markdown still renders", "PRO dossier" in dossier.render_markdown(e), True)

    print("\n" + ("ALL PASS" if not fails else f"{len(fails)} FAIL: " + ", ".join(fails)))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())

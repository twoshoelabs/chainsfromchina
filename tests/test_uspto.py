"""
USPTO trademark collector (docs/phase1_spec.md §5, deliverable 4). The network fetch is USPTO's to
answer; these tests hold the logic that turns a response into pipeline signals:

  a filing whose mark or applicant matches a tracked brand -> a linked signal (brand_id set)
  a China-applicant filing in a retail class that matches nothing -> an unlinked discovery lead
  a filing that is neither (foreign applicant, no match) -> dropped; this is a watch, not a firehose
  re-ingesting the same capture inserts nothing new -> idempotent (deduped on the serial)
  run() with no API key and no injected fetch SKIPS -> the manual fallback, no fabricated rows

Run: .venv/bin/python tests/test_uspto.py
"""
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from chain_atlas import db, uspto  # noqa: E402

REG = {"chains": {
    "anta": {"name": "Anta", "name_us": "Anta", "name_zh": "安踏",
             "parent": "Anta Sports Products (HKEX 2020)", "format": "apparel"},
    "jnby": {"name": "JNBY", "name_us": "AGoodFun", "name_zh": "江南布衣",
             "parent": "JNBY Design (HKEX 3306)", "format": "apparel"},
}, "markets": {}, "entries": []}

# A representative USPTO trademark-search response (shape isolated in parse()).
FIXTURE = {"results": [
    {"serialNumber": "97000001", "markText": "ANTA", "applicantName": "Anta Sports Products Limited",
     "applicantCountry": "CN", "filingDate": "2026-01-15", "internationalClasses": ["25", "35"]},
    {"serialNumber": "97000002", "markText": "AGOODFUN", "applicantName": "Sightclassic LLC",
     "applicantCountry": "US", "filingDate": "2026-02-01", "internationalClasses": ["25"]},
    {"serialNumber": "97000003", "markText": "SOME NEW BOBA BRAND", "applicantName": "Fuzhou Foo Bev Co Ltd",
     "applicantCountry": "CN", "filingDate": "2026-03-01", "internationalClasses": ["43", "30"]},
    {"serialNumber": "97000004", "markText": "RANDOM WIDGET", "applicantName": "Acme GmbH",
     "applicantCountry": "DE", "filingDate": "2026-03-02", "internationalClasses": ["7"]},
    {"serialNumber": "97000005", "markText": "PANDA SNACKS", "applicantName": "Shenzhen Panda Co",
     "applicantCountry": "CN", "filingDate": "2026-03-03", "internationalClasses": ["16"]},
]}


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

    # parse tolerates the envelope + field aliases
    marks = uspto.parse(json.dumps(FIXTURE))
    check("parse finds all 5 marks", len(marks), 5)
    check("parse normalises classes to ints", marks[0]["classes"], [25, 35])

    # classify
    ni, pi = uspto.build_index(REG)
    check("mark text match -> brand", uspto.classify(marks[0], ni, pi), ("anta", "brand_match"))
    check("applicant matches parent -> brand", uspto.classify(
        {"mark": "X", "applicant": "JNBY Design Ltd", "applicant_country": "CN", "classes": [25]}, ni, pi),
        ("jnby", "brand_match"))
    check("US applicant alias (AGoodFun) -> brand", uspto.classify(marks[1], ni, pi), ("jnby", "brand_match"))
    check("CN applicant, retail class, no match -> discovery lead", uspto.classify(marks[2], ni, pi),
          (None, "discovery_lead"))
    check("foreign applicant, non-retail -> dropped", uspto.classify(marks[3], ni, pi), None)
    check("CN applicant but non-retail class -> dropped", uspto.classify(marks[4], ni, pi), None)

    # ingest -> signals, with the right links
    s = uspto.ingest(con, FIXTURE, REG, raw_ref="raw/uspto/2026-09-30.json.gz@abc", now="2026-09-30T00:00:00Z")
    check("ingest inserts 3 relevant signals", s["inserted"], 3)
    check("two are brand matches", s["brand_matches"], 2)
    check("one is a discovery lead", s["discovery_leads"], 1)
    rows = con.execute("SELECT brand_id, confidence FROM pipeline_signals ORDER BY source_url").fetchall()
    check("linked signals carry a brand_id", sorted([r["brand_id"] for r in rows if r["brand_id"]]), ["anta", "jnby"])
    check("discovery lead is unlinked + low confidence",
          any(r["brand_id"] is None and r["confidence"] == "low" for r in rows), True)
    check("raw_ref recorded", con.execute(
        "SELECT raw_ref FROM pipeline_signals LIMIT 1").fetchone()["raw_ref"], "raw/uspto/2026-09-30.json.gz@abc")

    # idempotent
    s2 = uspto.ingest(con, FIXTURE, REG, now="2026-10-07T00:00:00Z")
    check("re-ingest inserts nothing", s2["inserted"], 0)
    check("re-ingest counts duplicates", s2["duplicates"], 3)
    check("still only 3 signals total", con.execute("SELECT COUNT(*) FROM pipeline_signals").fetchone()[0], 3)

    # run() manual-fallback when no key and no injected fetch
    out = uspto.run(con, d=REG, api_key="", fetch_fn=None)
    check("no-key run skips", "skipped" in out, True)

    # run() with an injected fetch (offline) wires fetch->save->ingest
    con2 = sqlite3.connect(":memory:"); con2.row_factory = sqlite3.Row
    con2.executescript(db.SCHEMA)
    out2 = uspto.run(con2, d=REG, terms=["Anta"], now="2026-09-30T00:00:00Z",
                     fetch_fn=lambda t: json.dumps(FIXTURE),
                     save_raw_fn=lambda payload: ("raw/uspto/x.json.gz", "deadbeef"))
    check("injected run inserts signals", out2["inserted"], 3)
    check("injected run recorded a raw_ref@sha", con2.execute(
        "SELECT raw_ref FROM pipeline_signals LIMIT 1").fetchone()["raw_ref"], "raw/uspto/x.json.gz@deadbeef")

    print("\n" + ("ALL PASS" if not fails else f"{len(fails)} FAILED: {fails}"))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())

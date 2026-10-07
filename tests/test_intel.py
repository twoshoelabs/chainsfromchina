"""
Two Pro-tier intelligence helpers added for the China-press research pipeline:

  dossiers.validate  Every qualitative item (history, popular item, flagship, note) must be dated and
                     sourced; an undated or unsourced claim is rejected. The real dossiers.json is valid.
  openings.pace      Opening pace is a DERIVATION of dated store counts: between two dated counts it
                     reports the net adds, the annualized rate and the % growth, inheriting the weaker
                     endpoint's confidence. One dated count yields no trend.

Run: CHAIN_ATLAS_DATA=$(mktemp -d) .venv/bin/python -m tests.test_intel
"""
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("CHAIN_ATLAS_DATA", tempfile.mkdtemp(prefix="uca_intel_"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from chain_atlas import db, dossiers, openings   # noqa: E402

fails = []


def check(label, got, want=True):
    ok = got == want
    print(f"  {'PASS' if ok else 'FAIL'}  {label}: {got}" + ("" if ok else f"  (want {want})"))
    if not ok:
        fails.append(label)


def test_dossiers_validate():
    check("real dossiers.json is valid", dossiers.validate(), [])
    bad = {"brands": {"x": {"history": {"text": "no date or source"}}}}
    errs = dossiers.validate(bad)
    check("undated/unsourced history is caught", len(errs) >= 2 and all("x.history" in e for e in errs))
    bad2 = {"brands": {"y": {"popular_items": [{"name": "Thing", "as_of": "2025"}]}}}  # no source
    check("item missing source is caught", any("missing source" in e for e in dossiers.validate(bad2)))


def _anchor(con, brand, period, value):
    con.execute("INSERT OR IGNORE INTO chains(chain_id,name,origin,format) VALUES(?,?, 'CN', 'tea')",
                (brand, brand))
    con.execute("INSERT INTO financial_anchors(brand_id,period,metric,value,unit,source,confidence)"
                " VALUES(?,?, 'store_count', ?, 'stores', 'test filing', 'high')", (brand, period, value))


def test_openings_pace():
    con = db.connect()
    _anchor(con, "testchain", "FY2024", 100)
    _anchor(con, "testchain", "FY2025", 150)
    con.commit()
    p = openings.pace(con, "testchain")
    check("one pace window between two dated counts", len(p), 1)
    w = p[0]
    check("net adds = 50", w["net"], 50)
    check("annualized ~50/yr", 49 <= w["per_year"] <= 51)
    check("growth ~50%/yr", w["pct_per_year"] is not None and 49 <= w["pct_per_year"] <= 51)
    check("confidence carried", w["confidence"], "high")
    # a single dated count yields no trend
    _anchor(con, "lonely", "FY2025", 10); con.commit()
    check("single count -> no pace", openings.pace(con, "lonely"), [])


def main():
    test_dossiers_validate()
    test_openings_pace()
    print("\n" + ("ALL PASS" if not fails else f"{len(fails)} FAILED: {fails}"))
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())

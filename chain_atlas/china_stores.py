"""
Reported CHINA store counts — a Pro-tier intelligence dimension. For each tracked chain, how big it is in
its HOME market (mainland China store count, and total/overseas where the split is reported), set beside
its US footprint from our own census. That home-market scale and the resulting US-penetration picture is
exactly what a Pro reader (landlord, broker, brand-expansion team, analyst) wants next to the US map.

PROVENANCE. Every figure is "reported": from a PRIMARY filing (HKEX/SEC/cninfo annual report —
confidence 'high', usually with a clean mainland/overseas split) or a company statement / reputable press
figure (confidence 'medium', often a worldwide total rather than a mainland-only count). Every entry
carries an `as_of` and a `source`. No third-party review/delivery/aggregator platforms (Dianping, Meituan,
窄门餐眼, …) — same posture as the rest of the project.

DATA: manual/china_stores.json (curated, version-controlled). The 'high' rows are refreshed when the
filings collector (chain_atlas/filings.py) flags a new annual report for that chain; the 'medium' rows are
curated from company/press. PRO ONLY — this is never written to the public map/data; it rides the Pro
export when that is built. `python -m chain_atlas china-stores` prints the China-vs-US view.
"""
import json
from pathlib import Path

PATH = Path(__file__).resolve().parents[1] / "manual" / "china_stores.json"


def load() -> dict:
    try:
        return json.loads(PATH.read_text(encoding="utf-8"))
    except Exception:                                            # noqa: BLE001
        return {"brands": {}}


def validate(d: dict | None = None) -> list:
    """Every entry needs a count (china or total), an as_of, and a source — an undated number is a rumour."""
    d = d if d is not None else load()
    errs = []
    for bid, v in d.get("brands", {}).items():
        if v.get("china") is None and v.get("total") is None:
            errs.append(f"{bid}: no china or total count")
        if not v.get("as_of"):
            errs.append(f"{bid}: a count needs as_of")
        if not v.get("source"):
            errs.append(f"{bid}: a count needs source")
    return errs


def best_count(v: dict):
    """The mainland count if reported, else the total — the single number to compare against US outlets."""
    return v.get("china") if v.get("china") is not None else v.get("total")


def rows(con) -> list:
    """Per-chain China scale joined to our US outlet count (site definition), newest-scale first."""
    brands = load().get("brands", {})
    from . import aggregate
    us = aggregate.us_outlets_by_chain(con)
    out = []
    for bid, v in brands.items():
        best = best_count(v)
        out.append({"brand": bid, "china": v.get("china"), "overseas": v.get("overseas"),
                    "total": v.get("total"), "best": best, "scope": "china" if v.get("china") is not None else "total",
                    "us": us.get(bid, 0), "as_of": v.get("as_of"), "confidence": v.get("confidence"),
                    "source": v.get("source"), "note": v.get("note", "")})
    out.sort(key=lambda r: -(r["best"] or 0))
    return out


def report(con) -> dict:
    r = rows(con)
    hi = sum(1 for x in r if x["confidence"] == "high")
    us_present = [x for x in r if x["us"] > 0]
    print(f"REPORTED CHINA STORE COUNTS — Pro intelligence ({len(r)} chains; {hi} filing-sourced, "
          f"{len(r)-hi} press/company)\n")
    print(f"  {'chain':14} {'China/total':>12} {'scope':6} {'as-of':10} {'cf':4} {'US':>4}  note")
    for x in r:
        print(f"  {x['brand']:14} {(x['best'] or 0):>12,} {x['scope']:6} {str(x['as_of']):10} "
              f"{(x['confidence'] or '')[:3]:4} {x['us']:>4}  {x['note'][:44]}")
    print(f"\n  {len(us_present)} of these have a US presence; the China:US gap is the Pro 'runway' signal.")
    return {"rows": r, "count": len(r), "filing_sourced": hi}

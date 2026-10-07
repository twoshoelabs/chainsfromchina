"""
Qualitative per-chain dossiers — the intelligence filings and store counts do not carry: a chain's
history, most popular items, flagship/best-known outlets, and loose notes. A Pro-tier dimension that
sits beside the measured numbers (china_stores, financial_anchors, opening pace).

PROVENANCE. Every item carries `as_of` + `source` (and a `source_url` where there is one) and a
`confidence` ('high' primary/filing, 'medium' reputable press, 'low' single weak mention). Nothing is
fabricated — an unknown field is absent. First-party / official / filings / reputable press /
licensed sources only, never review/delivery/aggregator platforms.

DATA: manual/dossiers.json (curated, version-controlled). PRO ONLY — never written to the public
map/data; it rides the Pro export. `python -m chain_atlas dossiers` validates and summarizes. See
china_stores.py (the sibling counts store) and [[cfc-analytics-paywall]].
"""
import json
from pathlib import Path

PATH = Path(__file__).resolve().parents[1] / "manual" / "dossiers.json"

LIST_FIELDS = ("popular_items", "flagship_outlets", "notes")


def load() -> dict:
    try:
        return json.loads(PATH.read_text(encoding="utf-8"))
    except Exception:                                            # noqa: BLE001
        return {"brands": {}}


def _check_item(errs: list, where: str, item: dict):
    """Every dossier item is dated and sourced — an undated or unsourced claim is a rumour."""
    if not isinstance(item, dict):
        errs.append(f"{where}: not an object"); return
    if not item.get("as_of"):
        errs.append(f"{where}: missing as_of")
    if not item.get("source"):
        errs.append(f"{where}: missing source")


def validate(d: dict | None = None) -> list:
    d = d if d is not None else load()
    errs: list = []
    for bid, v in d.get("brands", {}).items():
        if not isinstance(v, dict):
            errs.append(f"{bid}: not an object"); continue
        if "history" in v:
            if v["history"].get("text"):
                _check_item(errs, f"{bid}.history", v["history"])
            else:
                errs.append(f"{bid}.history: missing text")
        for f in LIST_FIELDS:
            for i, item in enumerate(v.get(f, [])):
                label = item.get("name") or item.get("text", "")[:20] if isinstance(item, dict) else ""
                _check_item(errs, f"{bid}.{f}[{i}] {label}".rstrip(), item)
    return errs


def summary(d: dict | None = None) -> dict:
    d = d if d is not None else load()
    brands = d.get("brands", {})
    filled = sum(1 for v in brands.values()
                 if v.get("history") or any(v.get(f) for f in LIST_FIELDS))
    return {"brands": len(brands), "with_content": filled, "as_of": d.get("as_of")}


def report(d: dict | None = None) -> dict:
    d = d if d is not None else load()
    brands = d.get("brands", {})
    s = summary(d)
    print(f"QUALITATIVE DOSSIERS — Pro intelligence ({s['brands']} chains, {s['with_content']} with "
          f"content; as_of {s['as_of']})\n")
    print(f"  {'chain':14} {'hist':5} {'items':6} {'flag':5} {'notes':6}")
    for bid in sorted(brands):
        v = brands[bid]
        print(f"  {bid:14} {('yes' if v.get('history') else '–'):5} "
              f"{len(v.get('popular_items', [])):>6} {len(v.get('flagship_outlets', [])):>5} "
              f"{len(v.get('notes', [])):>6}")
    return {"rows": len(brands), **s}

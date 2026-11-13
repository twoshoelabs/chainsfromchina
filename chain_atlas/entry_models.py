"""
US-entry / expansion model layer (Pro / intelligence).

Reads manual/us_entry_models.json (per-chain `us_entry_model` + the US operator/importer roster)
and reports how the US-present China chains entered and scale here. Keyed by chain_id, so it covers
every chain with US outlets, including those with no register.chains entry. Pro tier — not public.

    python -m chain_atlas entry-models            # summary + operator roster
    python -m chain_atlas entry-models --full      # + every chain, grouped by model
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "manual" / "us_entry_models.json"
GEOJSON = ROOT / "map" / "data" / "stores.geojson"

MODELS = ["direct_subsidiary", "us_franchise", "regional_operators",
          "importer_group", "authorized_partner", "distribution", "unknown"]


def _load():
    return json.loads(DATA.read_text())


def _us_counts():
    """Counted US outlets per chain from the exported geojson (0 if not yet exported)."""
    out = {}
    try:
        g = json.loads(GEOJSON.read_text())
    except FileNotFoundError:
        return out
    for f in g.get("features", []):
        c = f.get("properties", {}).get("chain")
        if c:
            out[c] = out.get(c, 0) + 1
    return out


def validate():
    """Return a list of problems (empty if clean)."""
    errs = []
    try:
        m = _load()
    except Exception as e:  # noqa: BLE001
        return [f"cannot parse us_entry_models.json: {e}"]
    chains = m.get("chains", {})
    ops = m.get("operators", {})
    for cid, v in chains.items():
        model = v.get("model")
        if model not in MODELS:
            errs.append(f"{cid}: unknown model {model!r}")
        op = v.get("operator")
        if op and op not in ops:
            errs.append(f"{cid}: operator {op!r} not in operators roster")
        if model != "unknown" and not v.get("basis"):
            errs.append(f"{cid}: missing basis")
    # every US-present chain should be classified
    us = _us_counts()
    missing = sorted(set(us) - set(chains))
    for c in missing:
        errs.append(f"{c}: US-present ({us[c]} outlets) but not classified")
    return errs


def report(full=False):
    m = _load()
    chains = m["chains"]
    ops = m.get("operators", {})
    us = _us_counts()

    by_model = {k: [] for k in MODELS}
    for cid, v in chains.items():
        by_model.setdefault(v["model"], []).append(cid)

    print(f"US-entry models  (as of {m.get('as_of', '?')})  — {len(chains)} US-present chains\n")
    print(f"  {'model':20} {'chains':>6} {'outlets':>8}")
    for k in MODELS:
        ids = by_model.get(k, [])
        if not ids:
            continue
        outlets = sum(us.get(c, 0) for c in ids)
        print(f"  {k:20} {len(ids):>6} {outlets:>8}")
    tot_c = len(chains)
    tot_o = sum(us.get(c, 0) for c in chains)
    print(f"  {'TOTAL':20} {tot_c:>6} {tot_o:>8}")

    print("\nOperators / importer groups:")
    for oid, o in ops.items():
        brands = o.get("china_brands_us", [])
        tag = o.get("type", "")
        print(f"  {o.get('name', oid)}  [{tag}]  — {len(brands)} China brand(s): {', '.join(brands)}")

    conf = {}
    for v in chains.values():
        conf[v.get("confidence", "?")] = conf.get(v.get("confidence", "?"), 0) + 1
    print("\nConfidence:", "  ".join(f"{k}={n}" for k, n in sorted(conf.items())))

    if full:
        for k in MODELS:
            ids = by_model.get(k, [])
            if not ids:
                continue
            print(f"\n[{k}]")
            for cid in sorted(ids, key=lambda c: -us.get(c, 0)):
                v = chains[cid]
                opname = ops.get(v.get("operator", ""), {}).get("name", "")
                opstr = f"  via {opname}" if opname else ""
                print(f"  {cid:20} {us.get(cid, 0):>4}  {v.get('confidence', ''):6}{opstr}  {v.get('basis', '')[:66]}")
    return 0

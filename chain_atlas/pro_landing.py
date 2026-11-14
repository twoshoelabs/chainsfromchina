"""
US LANDING intelligence (Pro / intelligence tier). Reads manual/pro_landing.json and reports:

  * landing-readiness scores — 7 weighted 0-5 dimensions roll up to a 0-100 score + A-F grade,
  * non-compete store-count caps — a realistic US ceiling vs the outlets that currently exist.

Keyed by chain_id, so it covers any brand (incl. ones with no register.chains entry). NOT public —
kept out of map/data; surfaced only via the CLI:

    python -m chain_atlas pro-landing            # readiness table + cap table
    python -m chain_atlas pro-landing --full      # + per-dimension detail and cap reasoning

The composite score is computed here (not stored) so the rubric weights stay the single source.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "manual" / "pro_landing.json"
GEOJSON = ROOT / "map" / "data" / "stores.geojson"

DIMS = ["entry_model", "fdd_discipline", "territory_protection", "supply_chain",
        "us_ops_team", "localization", "pace_discipline"]
STAGES = ["preparing", "trial", "expansion", "steady", "contracting", "exited"]
CHANNELS = ["a_malls", "strip_plazas", "street", "food_court", "campus", "grocery_anchored"]
ACCESS = {"blocked", "limited", "open"}


def _load():
    return json.loads(DATA.read_text())


def _us_counts():
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


def score(chain_rec, rubric):
    """Composite 0-100 from the 0-5 dimension scores, weighted by the rubric. Returns (score, grade)."""
    weights = {d: rubric["readiness_dimensions"][d]["weight"] for d in DIMS}
    total = 0.0
    wsum = 0.0
    for d in DIMS:
        dim = chain_rec.get("dimensions", {}).get(d)
        if not dim:
            continue
        s = dim.get("score")
        if s is None:
            continue
        total += (s / 5.0) * weights[d]
        wsum += weights[d]
    pct = round(100 * total / wsum) if wsum else 0
    bands = rubric["grade_bands"]
    grade = next((g for g in ["A", "B", "C", "D"] if pct >= bands[g]), "F")
    return pct, grade


def validate():
    """Return a list of problems (empty if clean)."""
    errs = []
    try:
        m = _load()
    except Exception as e:  # noqa: BLE001
        return [f"cannot parse pro_landing.json: {e}"]
    rubric = m.get("rubric", {})
    rdims = rubric.get("readiness_dimensions", {})
    if set(rdims) != set(DIMS):
        errs.append(f"rubric dimensions {sorted(rdims)} != expected {DIMS}")
    else:
        wsum = round(sum(rdims[d]["weight"] for d in DIMS), 6)
        if wsum != 1.0:
            errs.append(f"readiness weights sum to {wsum}, not 1.0")

    for cid, r in m.get("landing_readiness", {}).items():
        if r.get("stage") not in STAGES:
            errs.append(f"readiness {cid}: bad stage {r.get('stage')!r}")
        for d in DIMS:
            dim = r.get("dimensions", {}).get(d)
            if dim is None:
                errs.append(f"readiness {cid}: missing dimension {d}")
                continue
            s = dim.get("score")
            if not isinstance(s, int) or not (0 <= s <= 5):
                errs.append(f"readiness {cid}.{d}: score {s!r} not 0-5")

    for cid, c in m.get("noncompete_cap", {}).items():
        ch = c.get("channel_access", {})
        for k in CHANNELS:
            if k not in ch:
                errs.append(f"cap {cid}: missing channel_access.{k}")
            elif ch[k] not in ACCESS:
                errs.append(f"cap {cid}.{k}: {ch[k]!r} not in {sorted(ACCESS)}")
        ce = c.get("cap_estimate", {})
        if not (isinstance(ce.get("low"), int) and isinstance(ce.get("high"), int) and ce["low"] <= ce["high"]):
            errs.append(f"cap {cid}: bad cap_estimate {ce}")
    return errs


def report(full=False):
    m = _load()
    rubric = m["rubric"]
    us = _us_counts()

    rd = m.get("landing_readiness", {})
    print(f"US LANDING-READINESS  (as of {m.get('as_of','?')})  — {len(rd)} brand(s)\n")
    print(f"  {'chain':14} {'grade':5} {'score':>5} {'stage':11} {'US':>4}  flags")
    for cid in sorted(rd, key=lambda c: -score(rd[c], rubric)[0]):
        r = rd[cid]
        pct, grade = score(r, rubric)
        flags = ",".join(r.get("risk_flags", [])) or "-"
        print(f"  {cid:14} {grade:5} {pct:>5} {r.get('stage',''):11} {us.get(cid,0):>4}  {flags}")

    nc = m.get("noncompete_cap", {})
    print(f"\nNON-COMPETE STORE-COUNT CAPS  — {len(nc)} brand(s)  (current US vs realistic ceiling)\n")
    print(f"  {'chain':14} {'category':11} {'US now':>6} {'cap (low-high)':>16}  blockers")
    for cid in sorted(nc, key=lambda c: -nc[c]['cap_estimate']['high']):
        c = nc[cid]
        ce = c["cap_estimate"]
        blk = ", ".join(c.get("incumbent_blockers", []))
        rng = f"{ce['low']}-{ce['high']}"
        print(f"  {cid:14} {c.get('category',''):11} {us.get(cid,0):>6} {rng:>16}  {blk}")

    if full:
        print("\n— readiness detail —")
        for cid in sorted(rd):
            r = rd[cid]
            pct, grade = score(r, rubric)
            print(f"\n[{cid}]  {grade} ({pct})  stage={r.get('stage')}  conf={r.get('confidence')}")
            for d in DIMS:
                dim = r["dimensions"][d]
                print(f"    {d:22} {dim['score']}/5  {dim.get('value',''):12} {dim.get('note','')[:60]}")
        print("\n— cap reasoning —")
        for cid in sorted(nc):
            c = nc[cid]
            print(f"\n[{cid}]  {c['cap_estimate']['low']}-{c['cap_estimate']['high']}  ({c.get('confidence')})")
            print(f"    channels: " + "  ".join(f"{k}={c['channel_access'][k]}" for k in CHANNELS))
            print(f"    method: {c.get('cap_method','')}")
            print(f"    basis:  {c.get('basis','')}")
    return 0

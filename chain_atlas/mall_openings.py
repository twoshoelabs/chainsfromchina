"""
Mall-openings metric: the China-origin share of NEW store openings at 25 of the top US malls.

The numerator (China-origin new openings) comes from the register/sightings; the denominator
(ALL new openings) is captured by hand from each mall's own directory 'New'/'Coming Soon' tags,
because no public register of mall openings exists and the directories are JS/bot-walled. Source
file: manual/mall_openings.json. This module aggregates it into a public-facing metric.

The universe is deliberately '25 of the top US malls', not 'all US malls' — top malls skew
premium/Asian-metro, so the share runs higher than an all-US-mall average. We label it precisely.
"""
import json
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "manual" / "mall_openings.json"


def load(path: Path = SRC) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _latest_sweeps(doc: dict) -> dict:
    """The most recent sweep per mall id (by swept_on)."""
    latest: dict = {}
    for s in doc.get("sweeps", []):
        mk = s["mall"]
        if mk not in latest or s["swept_on"] > latest[mk]["swept_on"]:
            latest[mk] = s
    return latest


def compute(doc: dict | None = None) -> dict:
    """
    name:      compute
    purpose:   Reduce the mall-openings ledger to the headline metric + supporting detail.
    arguments: doc — parsed mall_openings.json (loaded if None)
    returns:   a metric dict safe to publish (no methodology-hiding).
    effects:   None.
    """
    doc = doc or load()
    malls = {m["id"]: m for m in doc.get("malls", [])}
    latest = _latest_sweeps(doc)

    complete = {mk: s for mk, s in latest.items() if s.get("complete")}
    total = sum(len(s["openings"]) for s in complete.values())
    china = sum(1 for s in complete.values() for o in s["openings"] if o.get("china_origin"))

    # Per-mall rows (latest sweep). The published China-origin openings list is drawn from COMPLETE
    # sweeps only, so it matches the headline share (partial sweeps contribute numerator detail to the
    # per-mall table but are not part of the published share or its opening list).
    per_mall, china_openings = [], []
    for mk, s in sorted(latest.items(), key=lambda kv: kv[0]):
        m = malls.get(mk, {"name": mk, "operator": None, "metro": None})
        n = len(s["openings"])
        c = sum(1 for o in s["openings"] if o.get("china_origin"))
        per_mall.append({"mall": m["name"], "operator": m.get("operator"), "metro": m.get("metro"),
                         "swept_on": s["swept_on"], "complete": bool(s.get("complete")),
                         "openings": n, "china_origin": c})
        if not s.get("complete"):
            continue
        for o in s["openings"]:
            if o.get("china_origin"):
                china_openings.append({"mall": m["name"], "metro": m.get("metro"),
                                       "name": o["name"], "chain": o.get("chain"),
                                       "status": o.get("status"), "swept_on": s["swept_on"]})

    # Per-operator share, complete sweeps only.
    by_op: dict = {}
    for mk, s in complete.items():
        op = malls.get(mk, {}).get("operator") or "Other"
        d = by_op.setdefault(op, {"openings": 0, "china_origin": 0, "malls": 0})
        d["openings"] += len(s["openings"])
        d["china_origin"] += sum(1 for o in s["openings"] if o.get("china_origin"))
        d["malls"] += 1

    return {
        "universe_label": doc.get("universe_label", "25 of the top US malls"),
        "as_of": doc.get("as_of"),
        "malls_tracked": len(malls),
        "malls_with_complete_sweep": len(complete),
        "openings_captured": total,          # denominator (complete sweeps)
        "china_origin_openings": china,       # numerator (complete sweeps)
        "china_origin_share": round(china / total, 4) if total else None,
        "by_operator": by_op,
        "china_origin_openings_list": sorted(china_openings, key=lambda o: (o["mall"], o["name"])),
        "per_mall": per_mall,
    }


def report(doc: dict | None = None) -> int:
    m = compute(doc)
    pct = f"{m['china_origin_share']*100:.0f}%" if m["china_origin_share"] is not None else "n/a"
    print(f"China-origin share of new openings — {m['universe_label']} (as of {m['as_of']})")
    print(f"  {m['china_origin_openings']} of {m['openings_captured']} captured openings are "
          f"China-origin  = {pct}")
    print(f"  (from {m['malls_with_complete_sweep']} of {m['malls_tracked']} malls with a complete sweep)")
    print("  per mall (latest sweep):")
    for r in m["per_mall"]:
        flag = "" if r["complete"] else "  [partial — numerator only]"
        print(f"    {r['mall']:34} {r['china_origin']}/{r['openings']} china  {r['swept_on']}{flag}")
    return 0


def export(out_dir: Path) -> str:
    """Write the public metric to map/data/mall_openings.json. Returns a one-line summary."""
    m = compute()
    (out_dir / "mall_openings.json").write_text(
        json.dumps(m, ensure_ascii=False, indent=1), encoding="utf-8")
    pct = f"{m['china_origin_share']*100:.0f}%" if m["china_origin_share"] is not None else "n/a"
    return (f"mall_openings: {m['china_origin_openings']}/{m['openings_captured']} china ({pct}) "
            f"across {m['malls_with_complete_sweep']}/{m['malls_tracked']} malls")

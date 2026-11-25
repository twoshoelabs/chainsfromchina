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
    """Write the public metric to map/data/mall_openings.json. Returns a one-line summary.

    The published metric is the SNAPSHOT comparison (mall_snapshots.compare): stores that opened
    since a dated baseline, and how many are China-origin. The older tag-based figure (compute())
    is carried alongside as `tagged`, clearly dated, until the first comparison exists."""
    from . import mall_snapshots
    doc = load()
    m = mall_snapshots.compare(doc)
    m["tagged"] = compute(doc)
    (out_dir / "mall_openings.json").write_text(
        json.dumps(m, ensure_ascii=False, indent=1), encoding="utf-8")
    if m["malls_compared"]:
        return (f"mall_openings: {m['opened_china_origin']}/{m['opened']} openings China-origin since "
                f"{m['tracking_since']} across {m['malls_compared']} compared malls")
    return (f"mall_openings: baseline {m['tracking_since']} — {m['stores_at_baseline']} stores at "
            f"{m['malls_baselined']}/{m['malls_tracked']} malls, no comparison yet")


def snapshot(mall_ids: list[str] | None = None, due_days: int | None = None) -> int:
    """Read every mall that has a scripted directory reader (or just `mall_ids`) and save today's
    snapshot. The first snapshot of a mall is its baseline; each later one is compared with it.
    `due_days`: skip a mall whose latest snapshot is younger than that many days — what lets the
    daily job call this every day and still read each mall only about once a month."""
    from datetime import date
    from . import mall_snapshots
    from .config import today_ny
    doc = load()
    today = date.fromisoformat(today_ny())
    n = skipped = 0
    for m in doc.get("malls", []):
        if not m.get("directory") or (mall_ids and m["id"] not in mall_ids):
            continue
        if due_days is not None:
            snaps = mall_snapshots.snapshots(m["id"])
            if snaps and (today - date.fromisoformat(snaps[-1]["captured_on"])).days < due_days:
                skipped += 1
                continue
        try:
            path = mall_snapshots.capture(m)
            tenants = json.loads(path.read_text(encoding="utf-8"))["tenants"]
            print(f"  {m['id']:22} {len(tenants):4} tenants -> {path.relative_to(path.parents[3])}")
            n += 1
        except Exception as e:                                # noqa: BLE001 — report, keep going
            print(f"  {m['id']:22} FAILED: {e}")
    print(f"mall-snapshot: {n} mall(s) read" + (f", {skipped} not yet due" if due_days is not None else "")
          + ". Malls without a scripted reader need a saved-page import (mall-snapshot --file).")
    return 0


def import_file(mall_id: str, path: str, on: str | None = None) -> int:
    """Save a snapshot for a mall whose directory cannot be read by script (it sits behind a
    human-verification check), from a copy of its stores page a person saved from their browser."""
    from . import mall_snapshots
    doc = load()
    mall = next((m for m in doc.get("malls", []) if m["id"] == mall_id), None)
    if not mall:
        print(f"unknown mall id: {mall_id}")
        return 2
    out = mall_snapshots.capture_saved(mall, Path(path), on)
    tenants = json.loads(out.read_text(encoding="utf-8"))["tenants"]
    print(f"  {mall_id:22} {len(tenants):4} tenants -> {out.relative_to(out.parents[3])}  (from saved page)")
    return 0

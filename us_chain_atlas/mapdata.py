"""
The map's data.

Two files, kept apart because they are different kinds of claim:

  stores.json   the current footprint: every store the collector can place, with its status,
                plus per-state totals. This is a snapshot and says so — it is true as of the
                last collected day.

THE STATE TOTALS ARE NOT THE DOTS. A state count includes stores that have no coordinates and
therefore cannot be drawn: Luckin publishes an address but no latitude for any of its New York
stores, so New York's total is right while New York's dots are missing twenty-two of them. The
state layer is the more complete of the two views, and the map says so where it matters.
  events.json   dated change: openings, announcements, closures, withdrawals. Only as old as
                the archive, which begins the day the collector first ran, and never
                backfilled from press reports or a chain's own history.

A store with no coordinate is NOT dropped. It is counted in `unlocated` per chain, so a reader
can see that Luckin's 22 New York stores are absent from the map for a reason that is about the
locator and not about Luckin.
"""
import json
from pathlib import Path

from . import db
from .adapters import REGISTRY
from .profiles import PROFILES, AS_OF as PROFILES_AS_OF


def export(out_dir: Path) -> dict:
    """
    name:      export
    purpose:   Write stores.json and events.json for the static map.
    arguments: out_dir (Path) — usually map/data
    returns:   dict summary of what was written
    effects:   Creates out_dir and overwrites the two files.
    other:     Derived output only: deleting these loses nothing the archive cannot rebuild.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    con = db.connect()

    chains, blocked = {}, []
    for a in REGISTRY:
        if a.ENABLED:
            chains[a.chain_id] = {"name": a.name, "name_zh": a.name_zh,
                                  "format": a.format, "parent": a.parent}
        else:
            blocked.append({"chain_id": a.chain_id, "name": a.name, "name_zh": a.name_zh,
                            "format": a.format, "reason": a.BLOCKED_REASON})

    # Per state, from the roster and NOT from the plotted dots, so a chain that publishes no
    # coordinates still counts. `chains` inside each state lets the map answer "who is in Utah".
    by_state, no_state = {}, 0
    for r in con.execute(
            "SELECT state, chain_id, status, COUNT(*) n FROM stores"
            " WHERE status!='withdrawn' GROUP BY state, chain_id, status"):
        if not r["state"]:
            no_state += r["n"]
            continue
        st = by_state.setdefault(r["state"], {"open": 0, "coming_soon": 0, "closed": 0, "chains": {}})
        key = {"active": "open", "pre_opening": "coming_soon"}.get(r["status"], "closed")
        st[key] += r["n"]
        c = st["chains"].setdefault(r["chain_id"], {"open": 0, "coming_soon": 0})
        if key in c:
            c[key] += r["n"]

    stores, unlocated = [], {}
    for r in con.execute(
            "SELECT chain_id,store_key,name,addr_raw,city,state,zip,lat,lon,status,"
            "first_seen,last_seen,opened_on FROM stores WHERE status!='withdrawn'"):
        if r["lat"] is None or r["lon"] is None:
            unlocated[r["chain_id"]] = unlocated.get(r["chain_id"], 0) + 1
            continue
        stores.append({
            "chain": r["chain_id"], "name": r["name"], "addr": r["addr_raw"],
            "city": r["city"], "state": r["state"],
            "lat": round(r["lat"], 6), "lon": round(r["lon"], 6),
            "status": r["status"], "first_seen": r["first_seen"],
            "opened_on": r["opened_on"],
        })

    events = [dict(chain=r["chain_id"], date=r["event_date"], type=r["event_type"],
                   name=r["name"], lat=r["lat"], lon=r["lon"], state=r["state"])
              for r in con.execute(
                  "SELECT e.event_date,e.event_type,e.chain_id,s.name,s.lat,s.lon,s.state"
                  " FROM events e JOIN stores s ON s.store_id=e.store_id"
                  " ORDER BY e.event_date")]

    cov = con.execute(
        "SELECT MIN(obs_date) a, MAX(obs_date) b, COUNT(DISTINCT obs_date) n"
        " FROM runs WHERE status='ok'").fetchone()
    meta = {
        "generated": con.execute("SELECT MAX(finished) f FROM runs").fetchone()["f"],
        "first_collected": cov["a"], "last_collected": cov["b"], "days_collected": cov["n"],
        "chains": chains, "blocked": blocked, "unlocated": unlocated,
        "by_state": by_state, "no_state": no_state,
        "profiles": PROFILES, "profiles_as_of": PROFILES_AS_OF,
        "counts": {
            "open": sum(1 for s in stores if s["status"] == "active"),
            "coming_soon": sum(1 for s in stores if s["status"] == "pre_opening"),
            "closed": sum(1 for s in stores if s["status"] == "closed"),
        },
    }
    (out_dir / "stores.json").write_text(
        json.dumps({"meta": meta, "stores": stores}, ensure_ascii=False, indent=1))
    (out_dir / "events.json").write_text(
        json.dumps({"meta": {"generated": meta["generated"]}, "events": events},
                   ensure_ascii=False, indent=1))
    return {"stores": len(stores), "events": len(events), "unlocated": unlocated,
            "states": len(by_state), "no_state": no_state}

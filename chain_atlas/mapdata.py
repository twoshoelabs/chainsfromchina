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

THIS FILE IS THE US MAP'S DATA, AND ONLY THAT. The archive now collects other markets — MINISO
UAE is the first — and they are deliberately excluded here rather than squeezed onto a map of
America. They are summarised in `meta.other_markets` so the page can say they exist and say
where to look, because a collected market that no page mentions is a collected market nobody
knows about.

COORDINATE PROVENANCE TRAVELS WITH THE POINT. `coord_src` says whether the chain published the
latitude or this project derived it from the address, and the page draws the two differently. A
derived point is a good guess about a street number, not a statement by the chain about its own
shop, and a map that blurs them is claiming precision it has not got.

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
        if a.country != "US":
            continue
        if a.ENABLED:
            chains[a.chain_id] = {"name": a.name, "name_zh": a.name_zh, "name_us": a.name_us,
                                  "format": a.format, "parent": a.parent,
                                  "provenance": a.PROVENANCE,
                                  "provenance_detail": (a.KNOWN_COUNT or {}).get("detail")
                                  if a.PROVENANCE != "collected" else None}
        else:
            blocked.append({"chain_id": a.chain_id, "name": a.name, "name_zh": a.name_zh,
                            "name_us": a.name_us,
                            "format": a.format, "reason": a.BLOCKED_REASON,
                            "known_count": a.KNOWN_COUNT})

    # Per state, from the roster and NOT from the plotted dots, so a chain that publishes no
    # coordinates still counts. `chains` inside each state lets the map answer "who is in Utah".
    by_state, no_state = {}, 0
    for r in con.execute(
            "SELECT state, chain_id, status, COUNT(*) n FROM stores"
            " WHERE status!='withdrawn' AND country='US' GROUP BY state, chain_id, status"):
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
            "SELECT chain_id,store_key,name,addr_raw,city,state,zip,lat,lon,coord_src,status,"
            "first_seen,last_seen,opened_on FROM stores"
            " WHERE status!='withdrawn' AND country='US'"):
        if r["lat"] is None or r["lon"] is None:
            unlocated[r["chain_id"]] = unlocated.get(r["chain_id"], 0) + 1
            continue
        stores.append({
            "chain": r["chain_id"], "name": r["name"], "addr": r["addr_raw"],
            "city": r["city"], "state": r["state"],
            "lat": round(r["lat"], 6), "lon": round(r["lon"], 6),
            "coord_src": r["coord_src"],
            "status": r["status"], "first_seen": r["first_seen"],
            "opened_on": r["opened_on"],
        })

    events = [dict(chain=r["chain_id"], date=r["event_date"], type=r["event_type"],
                   name=r["name"], lat=r["lat"], lon=r["lon"], state=r["state"])
              for r in con.execute(
                  "SELECT e.event_date,e.event_type,e.chain_id,s.name,s.lat,s.lon,s.state"
                  " FROM events e JOIN stores s ON s.store_id=e.store_id"
                  " WHERE s.country='US' ORDER BY e.event_date")]

    # Other markets the collector now covers, so the US page can point at them instead of
    # implying the archive stops at the border.
    other = {}
    for r in con.execute(
            "SELECT c.country, c.chain_id, c.name, COUNT(*) n,"
            " SUM(s.lat IS NOT NULL) located, MAX(s.last_seen) seen"
            " FROM stores s JOIN chains c ON c.chain_id=s.chain_id"
            " WHERE s.country!='US' AND s.status='active' GROUP BY c.chain_id"):
        other.setdefault(r["country"], []).append(
            {"chain": r["chain_id"], "name": r["name"], "stores": r["n"],
             "located": r["located"] or 0, "last_seen": r["seen"]})

    # Known locations of chains that are NOT counted. Excluded from every total above by
    # construction: they never touch stores, observations or events.
    try:
        from .sightings import geocoded as _sightings, rosters as _rosters
        sight = [r for r in _sightings(cache_only=True)]
        # Hand-assembled rosters with an explicit, dated completeness claim. They carry a
        # count — but a HAND count, kept in its own field and never folded into by_state
        # or meta.counts, which are the collector's and only the collector's.
        manual_rosters = _rosters()
    except Exception:                                           # noqa: BLE001
        sight, manual_rosters = [], []

    cov = con.execute(
        "SELECT MIN(obs_date) a, MAX(obs_date) b, COUNT(DISTINCT obs_date) n"
        " FROM runs WHERE status='ok'").fetchone()
    geocoded = {}
    for r in con.execute("SELECT chain_id, COUNT(*) n FROM stores WHERE coord_src='geocoded'"
                         " AND country='US' AND status!='withdrawn' GROUP BY chain_id"):
        geocoded[r["chain_id"]] = r["n"]

    meta = {
        "generated": con.execute("SELECT MAX(finished) f FROM runs").fetchone()["f"],
        "first_collected": cov["a"], "last_collected": cov["b"], "days_collected": cov["n"],
        "chains": chains, "blocked": blocked, "unlocated": unlocated,
        "other_markets": other,
        "geocoded": geocoded,
        "sightings": sight,
        "manual_rosters": manual_rosters,
        "by_state": by_state, "no_state": no_state,
        "profiles": PROFILES, "profiles_as_of": PROFILES_AS_OF,
        "counts": {
            "open": sum(1 for s in stores if s["status"] == "active"),
            "coming_soon": sum(1 for s in stores if s["status"] == "pre_opening"),
            "closed": sum(1 for s in stores if s["status"] == "closed"),
        },
    }
    meta["sighting_note"] = (
        "Known locations of chains this project does not count. They are not in any total on "
        "this page and never enter the archive: a partial roster in the census would turn every "
        "later discovery into an opening that never happened.")
    (out_dir / "stores.json").write_text(
        json.dumps({"meta": meta, "stores": stores}, ensure_ascii=False, indent=1))
    (out_dir / "events.json").write_text(
        json.dumps({"meta": {"generated": meta["generated"]}, "events": events},
                   ensure_ascii=False, indent=1))
    return {"stores": len(stores), "events": len(events), "unlocated": unlocated,
            "states": len(by_state), "no_state": no_state}

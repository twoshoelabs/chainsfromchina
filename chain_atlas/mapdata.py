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
import re
from pathlib import Path

from . import db
from .adapters import REGISTRY
from .profiles import PROFILES, AS_OF as PROFILES_AS_OF

# Collected store names come verbatim from each chain's own locator, which often repeats the brand
# and a format descriptor: "MIXUE-Union Square Store", "Haidilao Hot Pot Dallas", "CHAGEE Modern
# Teahouse- Orange". The map tooltip already leads with the chain, so that prefix is pure
# redundancy. Strip it for DISPLAY and keep the branch; the database keeps the verbatim name.
_NAME_LEAD = {
    "mixue": r"MIXUE",
    "haidilao": r"Haidilao\s+Hot\s*Pot",
    "chagee": r"CHAGEE\s+Modern\s+Teahouse",
    "miniso": r"Miniso",
    "aunteajenny": r"Auntea\s+Jenny",
    "mollytea": r"Molly\s*Tea",
}


def display_name(chain: str, name: str | None) -> str:
    """The store's branch label for the map: brand and format descriptor stripped, whitespace tidy."""
    n = (name or "").strip()
    lead = _NAME_LEAD.get(chain)
    if lead:
        n = re.sub(r"^\s*" + lead + r"\b\s*[-\u2013\u2014:]*\s*", "", n, flags=re.I).strip()
    if chain == "mixue":                                   # MIXUE names end " ... Store"
        n = re.sub(r"\s*Store\s*$", "", n, flags=re.I).strip()
    n = re.sub(r"\s+", " ", n).strip(" -\u2013\u2014:")
    return n or (name or "").strip()


# ---- Sighting graduation -------------------------------------------------------------------
# A hand-recorded sighting "graduates" the day the daily census starts covering the same spot:
# the census then owns that store's open/closed state, so the sighting is retired automatically \u2014
# suppressed from the map and the count \u2014 without editing sightings.json. Matching is by chain and
# proximity (a same-chain census store within ~180 m), because a mall sighting's address
# ("364 Maine Mall Rd") rarely matches the locator's unit string, but the coordinates line up.
_GRADUATE_M = 180.0


def census_points(con) -> dict:
    """{chain_id: [(lon, lat), ...]} for located, open or announced US census storefronts.
    Unstaffed machines (vending_robo) are excluded: a hand-verified storefront sighting must not
    be retired just because a ROBO SHOP machine sits at the same mall."""
    out = {}
    for r in con.execute(
            "SELECT chain_id, lon, lat FROM stores WHERE country='US'"
            " AND status IN ('active','pre_opening') AND lat IS NOT NULL AND lon IS NOT NULL"
            " AND COALESCE(format,'')<>'vending_robo'"):
        out.setdefault(r["chain_id"], []).append((r["lon"], r["lat"]))
    return out


def census_covers(points, lon, lat, meters: float = _GRADUATE_M) -> bool:
    """True when a same-chain census point lies within `meters` of (lon, lat) \u2014 the sighting has
    graduated to the census and should be retired from the hand record's drawing and count."""
    if lon is None or lat is None or not points:
        return False
    import math
    dlat = meters / 111_320.0
    dlon = meters / (111_320.0 * max(math.cos(math.radians(lat)), 0.01))
    return any(abs(plat - lat) <= dlat and abs(plon - lon) <= dlon for plon, plat in points)


def us_totals(con) -> dict:
    """
    name:      us_totals
    purpose:   The one canonical set of US outlet counts, so every page shows the SAME number.
    arguments: con
    returns:   {open, hand, announced, outlets, mapped, unmapped}
    effects:   None
    other:     `outlets` is what the project knows is open — collected census (active) plus
               hand-verified sightings — and is the single headline total. `mapped` is the geocoded
               subset actually drawn, so a page can note the few not yet placed. Low-confidence
               ('uncertain') sightings are held OUT: they wait in the submit-info queue until a
               human confirms them, so everything counted here is confirmed. Keep this the sole
               source of the total; pages read meta.totals rather than recomputing.
               Unstaffed machines (format='vending_robo', e.g. POP MART ROBO SHOPs) are NOT
               storefronts: they are kept in the data and reported as `roboshops`, but never added
               to `open`/`outlets`.
    """
    from .sightings import geocoded as _sightings
    r = con.execute(
        "SELECT SUM(status='active' AND COALESCE(format,'')<>'vending_robo') o,"
        " SUM(status='pre_opening' AND COALESCE(format,'')<>'vending_robo') p,"
        " SUM(status='active' AND lat IS NOT NULL AND COALESCE(format,'')<>'vending_robo') og,"
        " SUM(status='active' AND format='vending_robo') robo"
        " FROM stores WHERE country='US'").fetchone()
    open_, announced, open_mapped = r["o"] or 0, r["p"] or 0, r["og"] or 0
    roboshops = r["robo"] or 0
    hand = hand_mapped = 0
    cpts = census_points(con)
    for s in _sightings(cache_only=True):
        if s.get("confidence") == "uncertain" or not s.get("state"):
            continue
        if census_covers(cpts.get(s["chain"], []), s.get("lon"), s.get("lat")):
            continue                               # graduated to the census — retired here
        hand += 1
        if s.get("lat") is not None:
            hand_mapped += 1
    outlets, mapped = open_ + hand, open_mapped + hand_mapped
    return {"open": open_, "hand": hand, "announced": announced,
            "outlets": outlets, "mapped": mapped, "unmapped": outlets - mapped,
            "roboshops": roboshops}


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

    # A US store whose published address omits the state (some locators write a bare
    # "Las Vegas, 89102") gets one from its coordinate. This runs every export — after the daily
    # `run`, which re-parses and would otherwise leave such a store stateless again — so the
    # by-state tally stays complete. Only ever fills a blank; a chain-stated state is untouched.
    from .geo import state_from_point
    for r in con.execute("SELECT store_id, lat, lon FROM stores WHERE country='US'"
                         " AND (state IS NULL OR state='') AND lat IS NOT NULL"
                         " AND status!='withdrawn'").fetchall():
        st = state_from_point(r["lat"], r["lon"])
        if st:
            con.execute("UPDATE stores SET state=? WHERE store_id=?", (st, r["store_id"]))
    con.commit()

    chains, blocked = {}, []
    for a in REGISTRY:
        if a.country != "US":
            continue
        if a.ENABLED:
            chains[a.chain_id] = {"name": a.name, "name_zh": a.name_zh, "name_us": a.name_us,
                                  "aliases": list(a.aliases),
                                  "format": a.format, "parent": a.parent,
                                  "provenance": a.PROVENANCE,
                                  "provenance_detail": (a.KNOWN_COUNT or {}).get("detail")
                                  if a.PROVENANCE != "collected" else None}
        else:
            blocked.append({"chain_id": a.chain_id, "name": a.name, "name_zh": a.name_zh,
                            "name_us": a.name_us, "aliases": list(a.aliases),
                            "format": a.format, "reason": a.BLOCKED_REASON,
                            "known_count": a.KNOWN_COUNT})

    # Per state, from the roster and NOT from the plotted dots, so a chain that publishes no
    # coordinates still counts. `chains` inside each state lets the map answer "who is in Utah".
    by_state, no_state = {}, 0
    for r in con.execute(
            "SELECT state, chain_id, status, COUNT(*) n FROM stores"
            " WHERE status!='withdrawn' AND country='US'"
            " AND COALESCE(format,'')<>'vending_robo'"       # machines are not storefront counts
            " GROUP BY state, chain_id, status"):
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
            "format,first_seen,last_seen,opened_on FROM stores"
            " WHERE status!='withdrawn' AND country='US'"):
        if r["lat"] is None or r["lon"] is None:
            unlocated[r["chain_id"]] = unlocated.get(r["chain_id"], 0) + 1
            continue
        stores.append({
            "chain": r["chain_id"], "name": display_name(r["chain_id"], r["name"]), "addr": r["addr_raw"],
            "city": r["city"], "state": r["state"],
            "lat": round(r["lat"], 6), "lon": round(r["lon"], 6),
            "coord_src": r["coord_src"],
            # Machines stay in the data, tagged, so a consumer can tell a ROBO SHOP from a store.
            "format": r["format"],
            "status": r["status"], "first_seen": r["first_seen"],
            "opened_on": r["opened_on"],
        })

    events = [dict(chain=r["chain_id"], date=r["event_date"], type=r["event_type"],
                   name=display_name(r["chain_id"], r["name"]), lat=r["lat"], lon=r["lon"], state=r["state"])
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

    # Confirmed hand-verified locations per state, kept in their OWN structure so the census
    # `by_state` above stays the collector's alone (a hand count never merges into it). The
    # by-state table renders the two side by side, so a jurisdiction whose only outlet is a
    # sighting — Washington DC's Cotti, say — still appears, and the table reflects every located
    # outlet, not only the collected ones. Uncertain (unverified) sightings are excluded.
    by_state_hand: dict = {}
    for s in sight:
        if s.get("confidence") == "uncertain" or not s.get("state"):
            continue
        h = by_state_hand.setdefault(s["state"], {"count": 0, "chains": {}})
        h["count"] += 1
        h["chains"][s["chain"]] = h["chains"].get(s["chain"], 0) + 1
    try:
        from .coverage import scorecard
        _coverage = scorecard()
    except Exception:                                           # noqa: BLE001
        _coverage = {}
    try:
        import json as _json
        _companies = _json.loads((Path(__file__).resolve().parents[1] / "manual" / "companies.json").read_text(encoding="utf-8"))
    except Exception:                                           # noqa: BLE001
        _companies = {}
    # Per-brand stock-listing intelligence (exchange + ticker, listed parent, sister brands, mainland
    # A-share flag). Public-knowledge listing data, surfaced on the Chains tab. See manual/listings.json.
    try:
        import json as _json
        _listings = _json.loads((Path(__file__).resolve().parents[1] / "manual" / "listings.json").read_text(encoding="utf-8"))
    except Exception:                                           # noqa: BLE001
        _listings = {}

    # Fallback "Who they are" cards: every registered chain that lacks a hand-written profile gets a
    # lightweight card built from the register (its name, sector and `global` blurb), so no tracked
    # chain is missing a box. Hand-written profiles always win (skip a chain that already has one).
    try:
        from . import register as _reg
        _regd = _reg.load()
        _SECTOR_LABEL = {
            "food_drink": "Restaurant", "tea": "Bubble tea / tea", "coffee": "Coffee",
            "bakery": "Bakery", "grocery_convenience": "Grocery / convenience", "snacks": "Snacks",
            "apparel": "Apparel & accessories", "beauty": "Beauty",
            "lifestyle_variety": "Lifestyle / variety", "electronics": "Electronics", "home": "Home",
        }
        _MON = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

        def _fmt_since(s):
            # "2026-02-13"/"2026-02" -> "Feb 2026"; "2026" -> "2026"; else unchanged
            if not s:
                return None
            p = str(s).split("-")
            try:
                return f"{_MON[int(p[1])]} {p[0]}" if len(p) >= 2 else p[0]
            except (ValueError, IndexError):
                return str(s)

        comps = _companies.setdefault("companies", {})
        for _cid, _c in _regd.get("chains", {}).items():
            if _cid in comps:
                continue
            comps[_cid] = {
                "name": _c.get("name_us") or _c.get("name"),
                "name_zh": _c.get("name_zh") or "",
                "category": _SECTOR_LABEL.get(_reg.sector_of(_c)),
                "blurb": _c.get("global") or "",
                "us_since": _fmt_since(_c.get("us_entry_date")),
                "first_outlet": None,
                "site_cn": None, "site_us": None,
                "photo": None, "photo_credit": None,
                "auto": True,
            }
    except Exception:                                           # noqa: BLE001
        pass

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
        "coverage": _coverage,
        "companies": _companies,
        "listings": _listings,
        "by_state": by_state, "by_state_hand": by_state_hand, "no_state": no_state,
        "profiles": PROFILES, "profiles_as_of": PROFILES_AS_OF,
        "counts": {
            "open": sum(1 for s in stores if s["status"] == "active"),
            "coming_soon": sum(1 for s in stores if s["status"] == "pre_opening"),
            "closed": sum(1 for s in stores if s["status"] == "closed"),
        },
        "totals": us_totals(con),
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
    # A tiny file every page can fetch cheaply for the universal header's "Updated …" line and
    # shared totals, without pulling the full stores feed.
    (out_dir / "meta.json").write_text(json.dumps({
        "generated": meta["generated"], "last_collected": meta["last_collected"],
        "days_collected": meta["days_collected"], "totals": meta["totals"],
    }, ensure_ascii=False, indent=1))
    return {"stores": len(stores), "events": len(events), "unlocated": unlocated,
            "states": len(by_state), "no_state": no_state}

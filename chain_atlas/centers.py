"""
The shopping-center / co-tenancy view (docs/phase1_spec.md §4.5; the landlord/broker product).

The question a landlord or broker pays for: which centers and which owners have the most
China-origin tenants, and which brands cluster together. Answering it normally needs a mall
directory — which we cannot scrape. But this project already geocodes every store and sighting, so
co-location is computable from our own first-party data: stores that sit at the same coordinates are
in the same center or cluster. That is the engine here. A `shopping_centers` row, when we know the
mall's name / owner / REIT, attaches on top of a cluster; until then the cluster stands on its own
geographic footing, fully sourced by the stores that compose it.

Two ways a cluster is formed, authoritative first:
  * by `stores.center_id` — an explicit link to a named center (hand-curated, provenance-carrying);
  * else by a geographic bucket — coordinates rounded to `precision` decimals (~100 m), which puts
    stores in the same building/mall together.

CO-TENANCY is a cluster with two or more DISTINCT brands — the sellable signal. Everything carries
its members, so every count links back to the specific stores behind it.
"""
import json
import math
from collections import defaultdict
from pathlib import Path

from . import register
from .register import sector_of

CENTERS_PATH = Path(__file__).resolve().parents[1] / "manual" / "shopping_centers.json"
# How close a curated center must be to a cluster to be its name/owner (meters). A cluster is
# chains within ~100 m of each other; a named center within ~250 m of the cluster's centroid is it.
ATTACH_RADIUS_M = 250.0


def load_centers(path: Path | None = None) -> list[dict]:
    """
    name:      load_centers
    purpose:   Read the hand-curated shopping centers (names, owners/REITs, coordinates).
    arguments: path — defaults to manual/shopping_centers.json
    returns:   list of center dicts (empty if the file is absent — centers are optional)
    effects:   None
    other:     These are compiled from mall sites, REIT property lists and the trade press, each
               with a source; they attach a name/owner to a computed cluster but never create one.
    """
    p = path or CENTERS_PATH
    if not p.exists():
        return []
    return json.loads(p.read_text(encoding="utf-8")).get("centers", [])


def _dist_m(lat1, lon1, lat2, lon2) -> float:
    """name: _dist_m / purpose: quick planar distance in meters / arguments: two lat/lon pairs /
    returns: meters / effects: none / other: good enough at mall scale."""
    dlat = (lat2 - lat1) * 111320.0
    dlon = (lon2 - lon1) * 111320.0 * math.cos(math.radians((lat1 + lat2) / 2))
    return math.hypot(dlat, dlon)


def _nearest_center(lat, lon, centers: list[dict]) -> dict | None:
    """name: _nearest_center / purpose: the curated center within ATTACH_RADIUS_M of a point /
    arguments: lat, lon, centers / returns: a center dict or None / effects: none."""
    best, best_d = None, ATTACH_RADIUS_M
    for c in centers:
        if c.get("lat") is None or c.get("lon") is None:
            continue
        d = _dist_m(lat, lon, c["lat"], c["lon"])
        if d <= best_d:
            best, best_d = c, d
    return best


def _brand_meta(d: dict) -> dict:
    """
    name:      _brand_meta
    purpose:   Map every chain_id to a display name and sector, across the register and the adapters.
    arguments: d — a register dict
    returns:   {chain_id: {"name", "sector"}}
    effects:   None
    other:     Register brands use their US/English name and sector_of(); US-only adapter chains
               (not in the register) fall back to the adapter's US/English name and format-mapped
               sector.
    """
    meta = {}
    for cid, c in d.get("chains", {}).items():
        meta[cid] = {"name": c.get("name_us") or c.get("name") or cid, "sector": sector_of(c),
                     "franchise": c.get("franchise_available_us")}
    try:
        from .adapters import REGISTRY
        for a in REGISTRY:
            if a.chain_id == "fixture" or a.chain_id in meta:
                continue
            meta[a.chain_id] = {"name": getattr(a, "name_us", None) or a.name,
                                "sector": register.SECTOR_BY_FORMAT.get(getattr(a, "format", None))}
    except Exception:                                            # noqa: BLE001
        pass
    return meta


def _members(con, include_sightings: bool = True):
    """
    name:      _members
    purpose:   Every located US storefront that can join a cluster: census stores plus sightings.
    arguments: con; include_sightings
    returns:   list of {chain_id, lat, lon, city, state, status, center_id}
    effects:   Reads the DB and (optionally) the sightings file.
    other:     Census stores come from the stores table (active/pre_opening, US, located). Sightings
               are the present-not-collected chains' known outlets; only confirmed, located ones
               join (an `uncertain`/coming-soon sighting is not asserted as a tenant).
    """
    out = []
    for r in con.execute(
        "SELECT chain_id, lat, lon, city, state, status, center_id FROM stores "
        "WHERE country='US' AND lat IS NOT NULL AND status IN ('active','pre_opening')"
    ).fetchall():
        out.append({"chain_id": r["chain_id"], "lat": r["lat"], "lon": r["lon"],
                    "city": r["city"], "state": r["state"], "status": r["status"],
                    "center_id": r["center_id"]})
    if include_sightings:
        from . import sightings
        for s in sightings.geocoded(cache_only=True):
            if s.get("lat") is None or s.get("state") is None:
                continue
            if s.get("confidence") == "uncertain":
                continue
            out.append({"chain_id": s["chain"], "lat": s["lat"], "lon": s["lon"],
                        "city": s.get("city"), "state": s.get("state"), "status": "sighting",
                        "center_id": None})
    return out


def _center_rows(con) -> dict:
    """name: _center_rows / purpose: shopping_centers by id / arguments: con / returns: {id: row dict}
    / effects: reads DB / other: empty until centers are curated."""
    try:
        return {r["id"]: dict(r) for r in con.execute("SELECT * FROM shopping_centers").fetchall()}
    except Exception:                                            # noqa: BLE001
        return {}


def clusters(con, precision: int = 3, include_sightings: bool = True, d: dict | None = None,
             curated: list[dict] | None = None) -> list[dict]:
    """
    name:      clusters
    purpose:   Group located US storefronts into centers/clusters and describe the brands in each.
    arguments: con; precision — decimals to round coordinates to when there is no center_id
               (3 ≈ 100 m); include_sightings; d — register dict (defaults to load())
    returns:   list of cluster dicts, each with center meta (if linked), a representative
               location, the brands present, and the member stores behind them
    effects:   Reads the DB and sightings.
    other:     A cluster keyed by center_id is authoritative; the rest are geographic. `brand_count`
               is DISTINCT chains, `sector_count` distinct sectors — the numbers a landlord view sells.
    """
    d = d if d is not None else register.load()
    meta = _brand_meta(d)
    curated = curated if curated is not None else load_centers()
    center_rows = _center_rows(con)
    groups: dict = defaultdict(list)
    for m in _members(con, include_sightings):
        key = f"center:{m['center_id']}" if m["center_id"] else f"geo:{round(m['lat'], precision)},{round(m['lon'], precision)}"
        groups[key].append(m)

    out = []
    for key, members in groups.items():
        by_chain: dict = defaultdict(lambda: {"count": 0, "statuses": set()})
        for m in members:
            by_chain[m["chain_id"]]["count"] += 1
            by_chain[m["chain_id"]]["statuses"].add(m["status"])
        brands = []
        sectors = set()
        for cid, agg in by_chain.items():
            bm = meta.get(cid, {"name": cid, "sector": None})
            sectors.add(bm["sector"])
            brands.append({"chain_id": cid, "name": bm["name"], "sector": bm["sector"],
                           "count": agg["count"], "statuses": sorted(agg["statuses"])})
        brands.sort(key=lambda b: (-b["count"], b["name"]))
        rep = members[0]
        clat = round(sum(m["lat"] for m in members) / len(members), 5)
        clon = round(sum(m["lon"] for m in members) / len(members), 5)
        # An explicit center_id link is authoritative (its meta is the DB row); a geographic
        # cluster takes the nearest curated center within ATTACH_RADIUS_M, if any.
        center = (center_rows.get(key.split("center:", 1)[1]) if key.startswith("center:")
                  else _nearest_center(clat, clon, curated))
        out.append({
            "key": key,
            "center": center,
            "lat": clat,
            "lon": clon,
            "city": rep["city"], "state": rep["state"],
            "brands": brands,
            "brand_count": len(by_chain),
            "sector_count": len({s for s in sectors if s}),
            "store_count": len(members),
        })
    out.sort(key=lambda c: (-c["brand_count"], -c["store_count"], c["state"] or "", c["city"] or ""))
    return out


def places(con, min_brands: int = 2, **kw) -> list[dict]:
    """
    name:      places
    purpose:   The co-tenancy view as one row PER PLACE — a named center (all its clusters merged)
               or a single unnamed geographic cluster — which is what a landlord actually asks about.
    arguments: con; min_brands (default 2); passthrough kwargs to clusters()
    returns:   list of place dicts (center meta or None, merged brands, counts), most brands first
    effects:   Reads the DB and sightings.
    other:     A big mall spans several 100 m buckets, so its clusters are merged by center id; the
               brands are unioned, which also catches co-tenants that sit in different corners of the
               same center. Unnamed clusters (street corridors) pass through individually.
    """
    merged: dict = {}
    for c in clusters(con, **kw):
        gid = f"center:{c['center']['id']}" if c.get("center") else c["key"]
        p = merged.get(gid)
        if p is None:
            p = {"key": gid, "center": c.get("center"), "city": c["city"], "state": c["state"],
                 "lat": c["lat"], "lon": c["lon"], "_brands": {}, "store_count": 0, "cluster_count": 0}
            merged[gid] = p
        p["cluster_count"] += 1
        p["store_count"] += c["store_count"]
        if p["center"] and not p.get("city"):
            p["city"], p["state"] = c["city"], c["state"]
        for b in c["brands"]:
            e = p["_brands"].setdefault(b["chain_id"], {"chain_id": b["chain_id"], "name": b["name"],
                                        "sector": b["sector"], "count": 0, "statuses": set()})
            e["count"] += b["count"]
            e["statuses"].update(b["statuses"])
    out = []
    for p in merged.values():
        brands = sorted(p.pop("_brands").values(), key=lambda b: (-b["count"], b["name"]))
        for b in brands:
            b["statuses"] = sorted(b["statuses"])
        p["brands"] = brands
        p["brand_count"] = len(brands)
        p["sector_count"] = len({b["sector"] for b in brands if b["sector"]})
        if p["brand_count"] >= min_brands:
            out.append(p)
    out.sort(key=lambda p: (-p["brand_count"], -p["store_count"], p["state"] or "", p["city"] or ""))
    return out


# Back-compat name: co-tenancy is the per-place view.
co_tenancy = places


def reit_rollup(con, **kw) -> list[dict]:
    """
    name:      reit_rollup
    purpose:   Roll co-tenancy up by owner / REIT, for the landlord league table.
    arguments: con; passthrough kwargs
    returns:   list of {owner_reit, is_reit, centers, brands, brand_ids} sorted by centers then brands
    effects:   Reads the DB and sightings.
    other:     Counts DISTINCT named centers per owner (one row per mall, not per geo bucket) and
               unions the brands across them. Empty until centers are curated.
    """
    by_reit: dict = defaultdict(lambda: {"centers": 0, "is_reit": False, "brands": set()})
    for p in places(con, **kw):
        c = p["center"]
        if not c or not c.get("owner_reit"):
            continue
        r = by_reit[c["owner_reit"]]
        r["centers"] += 1
        r["is_reit"] = r["is_reit"] or bool(c.get("is_reit"))
        r["brands"].update(b["chain_id"] for b in p["brands"])
    out = [{"owner_reit": k, "is_reit": v["is_reit"], "centers": v["centers"],
            "brands": len(v["brands"]), "brand_ids": sorted(v["brands"])} for k, v in by_reit.items()]
    out.sort(key=lambda r: (-r["centers"], -r["brands"]))
    return out


def sync_centers_to_db(con, centers: list[dict] | None = None) -> int:
    """
    name:      sync_centers_to_db
    purpose:   Mirror the curated shopping centers into the DB shopping_centers table.
    arguments: con; centers — defaults to load_centers()
    returns:   number of centers upserted
    effects:   INSERT/UPDATE rows in shopping_centers.
    other:     The co-tenancy page reads the JSON directly; this keeps the DB table current for
               anything that queries it. Idempotent (keyed on id).
    """
    centers = centers if centers is not None else load_centers()
    n = 0
    for c in centers:
        con.execute(
            "INSERT INTO shopping_centers(id,name,owner_reit,class_tier,metro,anchors,source,"
            "source_url,retrieved_at,confidence) VALUES(?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(id) DO UPDATE SET name=excluded.name, owner_reit=excluded.owner_reit, "
            "class_tier=excluded.class_tier, metro=excluded.metro, anchors=excluded.anchors, "
            "source=excluded.source, source_url=excluded.source_url, "
            "retrieved_at=excluded.retrieved_at, confidence=excluded.confidence",
            (c["id"], c.get("name"), c.get("owner_reit"), c.get("class_tier"), c.get("metro"),
             json.dumps(c.get("anchors"), ensure_ascii=False) if c.get("anchors") else None,
             c.get("source"), c.get("source_url"), c.get("retrieved_at"), c.get("confidence")),
        )
        n += 1
    con.commit()
    return n


def export(con, out_dir, d: dict | None = None) -> dict:
    """
    name:      export
    purpose:   Write the co-tenancy view to the page's data directory.
    arguments: con; out_dir (usually map/data); d — register dict
    returns:   summary dict
    effects:   Writes centers.json.
    other:     Ships the co-tenancy clusters (>=2 brands) and the full cluster list, so the page can
               show "Chinese brands cluster here" without recomputing.
    """
    sync_centers_to_db(con)
    allc = clusters(con, d=d)
    cot = places(con, d=d)
    payload = {"co_tenancy": cot, "clusters": allc, "reit_rollup": reit_rollup(con, d=d)}
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    (Path(out_dir) / "centers.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1))
    return {"clusters": len(allc), "co_tenancy": len(cot)}


def report(con, min_brands: int = 2):
    """name: report / purpose: print the co-tenancy clusters / arguments: con, min_brands /
    returns: None / effects: prints."""
    cot = co_tenancy(con, min_brands=min_brands)
    print(f"{len(cot)} co-tenancy cluster(s) with >= {min_brands} China-origin brands:\n")
    for c in cot:
        where = (c["center"] or {}).get("name") or f"{c['city'] or '?'}, {c['state'] or '?'}"
        owner = (c["center"] or {}).get("owner_reit")
        head = f"  {c['brand_count']} brands / {c['sector_count']} sectors  {where}"
        print(head + (f"  [{owner}]" if owner else "") + f"  ({c['lat']},{c['lon']})")
        print("      " + ", ".join(f"{b['name']}×{b['count']}" for b in c["brands"]))

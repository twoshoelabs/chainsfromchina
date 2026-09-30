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
from collections import defaultdict

from . import register
from .register import sector_of


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
        meta[cid] = {"name": c.get("name_us") or c.get("name") or cid, "sector": sector_of(c)}
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


def clusters(con, precision: int = 3, include_sightings: bool = True, d: dict | None = None) -> list[dict]:
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
    centers = _center_rows(con)
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
        center = centers.get(key.split("center:", 1)[1]) if key.startswith("center:") else None
        out.append({
            "key": key,
            "center": center,
            "lat": round(sum(m["lat"] for m in members) / len(members), 5),
            "lon": round(sum(m["lon"] for m in members) / len(members), 5),
            "city": rep["city"], "state": rep["state"],
            "brands": brands,
            "brand_count": len(by_chain),
            "sector_count": len({s for s in sectors if s}),
            "store_count": len(members),
        })
    out.sort(key=lambda c: (-c["brand_count"], -c["store_count"], c["state"] or "", c["city"] or ""))
    return out


def co_tenancy(con, min_brands: int = 2, **kw) -> list[dict]:
    """
    name:      co_tenancy
    purpose:   The clusters that matter to a landlord: two or more distinct China-origin brands together.
    arguments: con; min_brands (default 2); passthrough kwargs to clusters()
    returns:   list of cluster dicts with brand_count >= min_brands, most brands first
    effects:   Reads the DB and sightings.
    """
    return [c for c in clusters(con, **kw) if c["brand_count"] >= min_brands]


def reit_rollup(con, **kw) -> list[dict]:
    """
    name:      reit_rollup
    purpose:   Roll co-tenancy up by owner / REIT, for the landlord league table.
    arguments: con; passthrough kwargs
    returns:   list of {owner_reit, centers, brand_instances, brands} sorted by brand_instances
    effects:   Reads the DB and sightings.
    other:     Only clusters attached to a named `shopping_centers` row carry an owner, so this is
               empty until centers are curated — the machinery, ready for the data.
    """
    by_reit: dict = defaultdict(lambda: {"centers": 0, "brand_instances": 0, "brands": set()})
    for c in clusters(con, **kw):
        owner = (c["center"] or {}).get("owner_reit")
        if not owner:
            continue
        r = by_reit[owner]
        r["centers"] += 1
        r["brand_instances"] += c["brand_count"]
        r["brands"].update(b["chain_id"] for b in c["brands"])
    out = [{"owner_reit": k, "centers": v["centers"], "brand_instances": v["brand_instances"],
            "brands": sorted(v["brands"])} for k, v in by_reit.items()]
    out.sort(key=lambda r: (-r["brand_instances"], -r["centers"]))
    return out


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
    import json
    from pathlib import Path
    allc = clusters(con, d=d)
    cot = [c for c in allc if c["brand_count"] >= 2]
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

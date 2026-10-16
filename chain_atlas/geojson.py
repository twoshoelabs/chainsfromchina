"""
Export the US footprint as GeoJSON, for a MapLibre GL (vector-basemap) map.

The current SVG map draws from stores.json and projects points itself. A MapLibre map instead wants
the pins as a GeoJSON FeatureCollection it can cluster and style with its own expressions. This
builds that file from the same two sources the project already trusts — the daily census (stores)
and the hand-verified sightings — so the new map shows exactly what the old one does, never more.

Each feature is a Point with:
  chain       chain_id
  name        the US/English display name
  sector      the retail sector (for per-sector icon/color)
  kind        'store'  (daily census) or 'sighting' (hand-verified, not collected)
  status      'open' | 'coming_soon' | 'sighting'
  confidence  for sightings: 'confirmed' | 'uncertain'
  address     the street line (e.g. '174 Smith St'), when known
  city, state
Counts are never baked in here; the map derives cluster counts from the features themselves.
"""
import json
import re
from pathlib import Path

from . import register, sightings
from .centers import _brand_meta


def _feature(lon, lat, props):
    return {"type": "Feature", "geometry": {"type": "Point", "coordinates": [lon, lat]},
            "properties": props}


_UNIT = (r"(?:suite|ste\.?|unit|apt\.?|apartment|space|spc\.?|room|rm\.?|bldg\.?|building|floor|"
         r"fl\.?|shop|store|kiosk|stall|booth|#|no\.?)")
_DANGLE = r"\b(the|at|of|on|and|&|shops?|near)$"


def _street(addr: str | None, city: str | None = None, state: str | None = None,
            zip_: str | None = None) -> str | None:
    """The street line of an address — the part before the city — so the popup can show it on its own
    line above the city/state it already displays.

    Raw locator addresses are messy, so this does more than split on the first comma:
      • it picks the first comma-field that begins with a street number (so a leading mall name or
        unit — 'Westfield Century City, 10250 Santa Monica Blvd' or 'Space#2020, 2601 Preston Rd' —
        falls through to the real street);
      • it re-joins a street name a stray comma split ('555 The' | 'Shops At Mission Viejo');
      • and it trims a city or 'ST 12345' tail that got smushed into the street field without a comma,
        unless doing so would leave a dangling connector (keeping mall names like 'Shops At Mission
        Viejo' intact).
    Directional suffixes (N/S/E/W) are preserved.
    """
    if not addr:
        return None
    parts = [p.strip() for p in addr.split(",") if p.strip()]
    if not parts:
        return None
    idx = next((i for i, p in enumerate(parts)
                if re.match(r"^\d|^one\b|^two\b|^three\b", p, re.I)), 0)
    s = parts[idx]
    while idx + 1 < len(parts) and re.search(r"\b(the|at|of|on|and|&)$", s, re.I):
        nxt = parts[idx + 1]
        if (re.match(rf"^{_UNIT}\b", nxt, re.I) or (city and nxt.lower() == city.lower())
                or re.search(r"\b[A-Z]{2}\s+\d{5}", nxt)):
            break
        idx += 1
        s = (s + " " + nxt).strip()
    s = re.sub(r"\s+[A-Z]{2}\s+\d{5}(-\d{4})?.*$", "", s)      # smushed 'ST 12345 ...' tail
    if city:
        trimmed = re.sub(rf"\s+{re.escape(city)}\s*$", "", s, flags=re.I).strip()
        if trimmed and not re.search(_DANGLE, trimmed, re.I):  # don't leave 'Shops At'
            s = trimmed
    s = re.sub(r"\s+", " ", s).strip().strip(",").strip()
    return s or None


def build(con, d: dict | None = None) -> dict:
    """
    name:      build
    purpose:   Assemble the US stores + sightings as a GeoJSON FeatureCollection.
    arguments: con — DB connection; d — register dict (defaults to load())
    returns:   a GeoJSON FeatureCollection dict
    effects:   Reads the DB and the sightings cache.
    other:     Census stores are 'open' or 'coming_soon' (pre_opening); sightings carry their
               confidence, and an 'uncertain'/coming-soon sighting is marked so the map can draw it
               as the dashed, held-out pin the legend describes.
    """
    d = d if d is not None else register.load()
    meta = _brand_meta(d)
    feats = []
    for r in con.execute(
        "SELECT chain_id, name, lat, lon, addr_norm, addr_raw, city, state, zip, status FROM stores "
        "WHERE country='US' AND lat IS NOT NULL AND status IN ('active','pre_opening') "
        # Unstaffed machines are not storefronts: kept in the data (stores.json), but off the map
        # and out of every count. POP MART ROBO SHOPs are the case this exists for.
        "AND COALESCE(format,'')<>'vending_robo'"
    ).fetchall():
        bm = meta.get(r["chain_id"], {})
        feats.append(_feature(r["lon"], r["lat"], {
            "chain": r["chain_id"],
            "name": bm.get("name") or r["name"] or r["chain_id"],
            "sector": bm.get("sector"),
            "fr": bm.get("franchise"),          # 1 = open to a US franchisee, 0 = not, null = unknown
            "fdd": bm.get("fdd"),           # 1 = registered US FDD on file, else 0/null
            "kind": "store",
            "status": "coming_soon" if r["status"] == "pre_opening" else "open",
            "address": _street(r["addr_raw"] or r["addr_norm"], r["city"], r["state"], r["zip"]),
            "city": r["city"], "state": r["state"],
        }))
    from .mapdata import census_points, census_covers
    cpts = census_points(con)
    for s in sightings.geocoded(cache_only=True):
        if s.get("lat") is None or not s.get("state"):
            continue
        # Low-confidence sightings are held out of the map and the count — they wait in the
        # submit-info queue until a human confirms them. Everything drawn here is confirmed, so
        # every sighting is a solid pin; the only not-yet-open marker is a census pre_opening.
        if s.get("confidence") == "uncertain":
            continue
        # A sighting graduates once the census covers the same spot (same chain, within ~180 m):
        # the census owns it, so the hand record is retired here automatically — no double count.
        if census_covers(cpts.get(s["chain"], []), s.get("lon"), s.get("lat")):
            continue
        bm = meta.get(s["chain"], {})
        feats.append(_feature(s["lon"], s["lat"], {
            "chain": s["chain"],
            "name": bm.get("name") or s["chain"],
            "sector": bm.get("sector"),
            "fr": bm.get("franchise"),          # 1 = open to a US franchisee, 0 = not, null = unknown
            "fdd": bm.get("fdd"),           # 1 = registered US FDD on file, else 0/null
            "kind": "sighting",
            "status": "sighting",
            "address": _street(s.get("address"), s.get("city"), s.get("state")),
            "city": s.get("city"), "state": s.get("state"),
        }))
    last = con.execute(
        "SELECT MAX(last_seen) AS d FROM stores WHERE country='US' AND status IN ('active','pre_opening')"
    ).fetchone()
    # `days` is how many distinct days the census has actually run — the homepage's "DAY N".
    days = con.execute("SELECT COUNT(DISTINCT obs_date) AS n FROM runs WHERE status='ok'").fetchone()
    gen = con.execute("SELECT MAX(finished) AS f FROM runs").fetchone()   # NY-time finish (run.py uses TZ)
    from .mapdata import us_totals, outlets_asof   # one canonical total, shared with stores.json
    totals = us_totals(con)
    prev = outlets_asof(con, 7)                  # ~a week ago, so the homepage counter can spin up to today
    totals["prev"] = prev["outlets"]
    totals["prev_as_of"] = prev["as_of"]
    # Extra search terms the map's hero search can match a chain by, beyond its display name: the
    # Chinese name, any in-market trading name, and explicit aliases (e.g. "Shanghai Auntie" for
    # 沪上阿姨 Auntea Jenny, or "Panda Hot Pot" for 熊猫烫火锅 Nanshan). Only for chains actually on
    # the map, and keyed to the register's own filter (register.js searchStr) so map and register
    # search match on the same terms. Terms come from BOTH the register chain record AND the adapter
    # stub, so US-only chains (not in register.json, e.g. feidachu/nonggengji/nanshan) are covered.
    reg_chains = d.get("chains", {})
    try:
        from .adapters import REGISTRY
        admap = {a.chain_id: a for a in REGISTRY}
    except Exception:                                            # noqa: BLE001
        admap = {}
    aliases = {}
    for cid in {f["properties"]["chain"] for f in feats}:
        c = reg_chains.get(cid) or {}
        display = (meta.get(cid) or {}).get("name")
        terms = [c.get("name_zh"), c.get("name_us"), c.get("name_intl")]
        if isinstance(c.get("aliases"), list):
            terms += c["aliases"]
        a = admap.get(cid)
        if a is not None:
            terms += [getattr(a, "name_zh", None), getattr(a, "name_us", None)]
            terms += list(getattr(a, "aliases", None) or ())
        terms = [t for t in dict.fromkeys(terms) if t and t != display]
        if terms:
            aliases[cid] = terms
    return {"type": "FeatureCollection", "features": feats,
            "meta": {"collected": last["d"] if last else None,
                     "days": days["n"] if days else None,
                     "generated": gen["f"] if gen else None,
                     "totals": totals,
                     "aliases": aliases}}


def export(con, out_dir, d: dict | None = None) -> dict:
    """
    name:      export
    purpose:   Write stores.geojson to the page's data directory.
    arguments: con; out_dir (usually map/data); d — register dict
    returns:   summary dict
    effects:   Writes stores.geojson.
    """
    fc = build(con, d=d)
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    (Path(out_dir) / "stores.geojson").write_text(json.dumps(fc, ensure_ascii=False))
    stores = sum(1 for f in fc["features"] if f["properties"]["kind"] == "store")
    return {"features": len(fc["features"]), "stores": stores,
            "sightings": len(fc["features"]) - stores}

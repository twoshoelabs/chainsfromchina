"""
Turning addresses this project already holds into coordinates it does not.

Luckin publishes 22 New York addresses and no latitudes; Haidilao's locator publishes both.
Rather than treat the first as unmappable forever, the addresses are geocoded — but a derived
coordinate is never allowed to look like a published one. `stores.coord_src` has carried the
distinction since the schema was written: 'published' means the chain said so, 'geocoded' means
we worked it out, and the map draws them differently.

THE GEOCODER IS THE US CENSUS BUREAU'S, deliberately. It is free, needs no key, imposes no terms
that conflict with republishing a derived point, and is the authoritative source for US street
addresses — the same data the decennial census is conducted against. Commercial geocoders are
better at messy international input and worse at every other property that matters here.

    GET https://geocoding.geo.census.gov/geocoder/locations/onelineaddress
        ?address=<one-line>&benchmark=Public_AR_Current&format=json

IT IS US-ONLY, which is a real limit and not a temporary one: MINISO's 46 UAE stores publish a
mall name and an emirate, and no US geocoder will place them. They stay unplaced, and the
unlocated count keeps saying so.

RESULTS ARE CACHED in the archive, keyed by the normalised address. A geocode is a derived fact
about a string, not an observation of the world — re-deriving it on every run would be pure
noise against the Census Bureau, and would let a service outage silently unplace a store that
was placed yesterday.
"""
import json
import urllib.parse
from pathlib import Path

from . import capture
from .config import DATA_DIR, today_ny
from .identity import norm_addr

ENDPOINT = "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress"
BENCHMARK = "Public_AR_Current"
CACHE_PATH = DATA_DIR / "geocode_cache.json"
# Hand-entered coordinates for collected US stores the Census geocoder cannot place. Kept in the
# repo (not the archive) because they are a curated editorial decision, not a fetched observation.
OVERRIDES_PATH = Path(__file__).resolve().parents[1] / "manual" / "geocode_overrides.json"


def _load_overrides() -> dict:
    """
    name:      _load_overrides
    purpose:   Manual coordinates for stores Census cannot place, keyed by normalised address.
    arguments: none
    returns:   {norm_addr: {"lat","lon","note"}}
    effects:   Reads manual/geocode_overrides.json if present.
    other:     A LAST RESORT, applied only where the Census geocoder returns no match — never to
               overrule a coordinate the Census (or the chain) did place. The point is marked
               coord_src='manual' so it is never mistaken for a Census-derived or published one.
    """
    if not OVERRIDES_PATH.exists():
        return {}
    try:
        doc = json.loads(OVERRIDES_PATH.read_text(encoding="utf-8"))
    except Exception:                                           # noqa: BLE001
        return {}
    out = {}
    for o in doc.get("overrides", []):
        if o.get("address") and o.get("lat") is not None and o.get("lon") is not None:
            out[norm_addr(o["address"])] = {"lat": o["lat"], "lon": o["lon"], "note": o.get("note")}
    return out


def _load_cache() -> dict:
    if CACHE_PATH.exists():
        try:
            return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        except Exception:                                       # noqa: BLE001
            return {}
    return {}


def _save_cache(c: dict):
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(c, ensure_ascii=False, indent=1), encoding="utf-8")


def geocode_one(addr: str, cache: dict | None = None) -> dict | None:
    """
    name:      geocode_one
    purpose:   Resolve one US address to a coordinate via the Census Bureau.
    arguments: addr — a one-line address; cache — optional dict, consulted and updated
    returns:   {"lat","lon","matched","as_of"} or None when the geocoder finds no match
    effects:   One HTTP request on a cache miss.
    other:     A miss is cached as None too. The Census Bureau will not learn to like an address
               it already rejected, and re-asking every night is just noise.
    """
    key = norm_addr(addr)
    if cache is not None and key in cache:
        return cache[key]
    url = f"{ENDPOINT}?" + urllib.parse.urlencode(
        {"address": addr, "benchmark": BENCHMARK, "format": "json"})
    out = None
    try:
        d = capture.fetch(url, tries=2).json()
        matches = (d.get("result") or {}).get("addressMatches") or []
        if matches:
            c = matches[0]["coordinates"]
            out = {"lat": round(float(c["y"]), 6), "lon": round(float(c["x"]), 6),
                   "matched": matches[0].get("matchedAddress"),
                   "as_of": today_ny()}
    except Exception:                                           # noqa: BLE001
        return None            # a failure is NOT cached: the address may be fine, the service not
    if cache is not None:
        cache[key] = out
    return out


def run(con, chain_id: str | None = None, limit: int = 500) -> dict:
    """
    name:      run
    purpose:   Geocode US stores that have an address and no coordinate.
    arguments: con; chain_id to restrict; limit as a safety stop
    returns:   summary dict
    effects:   HTTP requests, cache writes, UPDATEs to stores (lat, lon, cell100, coord_src).
    other:     Only ever fills a NULL coordinate. A published coordinate is never overwritten by
               a derived one, whatever the geocoder thinks — the chain is the authority on where
               its own shop is.
    """
    from .geo import cell100, state_from_point
    cache = _load_cache()
    overrides = _load_overrides()
    q = ("SELECT store_id, chain_id, addr_raw, country, state FROM stores"
         " WHERE lat IS NULL AND addr_raw IS NOT NULL AND addr_raw != ''"
         " AND country='US' AND status != 'withdrawn'")
    args: tuple = ()
    if chain_id:
        q += " AND chain_id=?"
        args = (chain_id,)
    rows = con.execute(q + " LIMIT ?", (*args, limit)).fetchall()

    placed = manual = failed = 0
    for r in rows:
        got = geocode_one(r["addr_raw"], cache)
        src = "geocoded"
        if not got:
            # Census could not place it — fall back to a hand-entered coordinate if one exists,
            # marked as manual so it is drawn as a derived point, not a published one.
            ov = overrides.get(norm_addr(r["addr_raw"]))
            if not ov:
                failed += 1
                continue
            got, src = {"lat": ov["lat"], "lon": ov["lon"]}, "manual"
            manual += 1
        # A store whose published address carried no state (some locators drop it, e.g. a bare
        # "Las Vegas, 89102") gets one from the coordinate we just derived — the same last-resort
        # rule run.normalise applies at parse time. Only ever fills a blank; a chain-stated state
        # is never overwritten.
        state = r["state"] or state_from_point(got["lat"], got["lon"])
        con.execute(
            "UPDATE stores SET lat=?, lon=?, coord_src=?, cell100=?, state=? "
            "WHERE store_id=?",
            (got["lat"], got["lon"], src, cell100(got["lat"], got["lon"], r["country"]),
             state, r["store_id"]))
        if src == "geocoded":
            placed += 1
    con.commit()
    _save_cache(cache)
    return {"candidates": len(rows), "placed": placed, "manual": manual, "unmatched": failed,
            "cache_entries": len(cache)}

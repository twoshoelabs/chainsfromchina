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
import time
import urllib.parse

from . import capture
from .config import DATA_DIR
from .identity import norm_addr

ENDPOINT = "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress"
BENCHMARK = "Public_AR_Current"
CACHE_PATH = DATA_DIR / "geocode_cache.json"


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
                   "as_of": time.strftime("%Y-%m-%d")}
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
    from .geo import cell100
    cache = _load_cache()
    q = ("SELECT store_id, chain_id, addr_raw, country FROM stores"
         " WHERE lat IS NULL AND addr_raw IS NOT NULL AND addr_raw != ''"
         " AND country='US' AND status != 'withdrawn'")
    args: tuple = ()
    if chain_id:
        q += " AND chain_id=?"
        args = (chain_id,)
    rows = con.execute(q + " LIMIT ?", (*args, limit)).fetchall()

    placed = failed = 0
    for r in rows:
        got = geocode_one(r["addr_raw"], cache)
        if not got:
            failed += 1
            continue
        con.execute(
            "UPDATE stores SET lat=?, lon=?, coord_src='geocoded', cell100=? WHERE store_id=?",
            (got["lat"], got["lon"], cell100(got["lat"], got["lon"], r["country"]), r["store_id"]))
        placed += 1
    con.commit()
    _save_cache(cache)
    return {"candidates": len(rows), "placed": placed, "unmatched": failed,
            "cache_entries": len(cache)}

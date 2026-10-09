"""
A DERIVED, MODELED read of where the measured outlets sit — never part of the measured count.

The daily census answers "how many, and where". This answers a different, softer question: what kind
of neighbourhood does a China-origin chain choose? It joins each located storefront to three public,
key-free sources and reports ONLY aggregates:

  • Asian-origin density of the host census tract   — US Census ACS table B03002, via CensusReporter
  • metro / urban setting                           — US Census geographies (tract, CSA, urban area)
  • nearest college campus                          — Urban Institute IPEDS directory

Everything here is modeled and lives behind the measured/modeled wall (docs/phase1_spec.md §"Measured
vs modeled"): the published snapshot (demographics.json) carries aggregates and a method note, NEVER a
per-outlet row, so no individual store is profiled. Roboshops are already absent — the pass reads
stores.geojson, which excludes them. The network pass is slow and is run on its own (`demographics`
CLI), not on every export; export merely copies the committed snapshot into the page's data dir.
"""
import json
import math
import ssl
import statistics as _stats
import time
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .config import today_ny

_CTX = ssl.create_default_context()

# State FIPS, for the IPEDS directory query (one call per state the outlets touch).
_FIPS = {
    "AL": "01", "AK": "02", "AZ": "04", "AR": "05", "CA": "06", "CO": "08", "CT": "09", "DE": "10",
    "DC": "11", "FL": "12", "GA": "13", "HI": "15", "ID": "16", "IL": "17", "IN": "18", "IA": "19",
    "KS": "20", "KY": "21", "LA": "22", "ME": "23", "MD": "24", "MA": "25", "MI": "26", "MN": "27",
    "MS": "28", "MO": "29", "MT": "30", "NE": "31", "NV": "32", "NH": "33", "NJ": "34", "NM": "35",
    "NY": "36", "NC": "37", "ND": "38", "OH": "39", "OK": "40", "OR": "41", "PA": "42", "RI": "44",
    "SC": "45", "SD": "46", "TN": "47", "TX": "48", "UT": "49", "VT": "50", "VA": "51", "WA": "53",
    "WV": "54", "WI": "55", "WY": "56",
}

_GEO_URL = ("https://geocoding.geo.census.gov/geocoder/geographies/coordinates"
            "?x={lon}&y={lat}&benchmark=Public_AR_Current&vintage=Census2020_Current&format=json")
_CR_URL = "https://api.censusreporter.org/1.0/data/show/latest?table_ids=B03002&geo_ids={ids}"
_IPEDS_URL = "https://educationdata.urban.org/api/v1/college-university/ipeds/directory/2022/?fips={fips}"


def _get(url, tries=3):
    """One GET, retried, with a timeout so a wedged endpoint can never hang the pass."""
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "cfc-research/1.0"})
            return urllib.request.urlopen(req, timeout=40, context=_CTX).read()
        except Exception:                                   # noqa: BLE001 — retried, then raised
            if i == tries - 1:
                raise
            time.sleep(0.6)


def _miles(a_lat, a_lon, b_lat, b_lon):
    """Flat-earth miles — fine at campus-proximity scale, and far cheaper than haversine per pair."""
    dy = (b_lat - a_lat) * 69.0
    dx = (b_lon - a_lon) * 69.0 * math.cos(math.radians(a_lat))
    return math.hypot(dx, dy)


def _outlets(geojson_path: Path):
    """The located storefronts to analyse: the OPEN outlets the site actually counts. stores.geojson
    already excludes roboshops and low-confidence sightings; we also drop `coming_soon` (announced,
    not yet open) here, so this set matches the governing open-outlet count the homepage shows rather
    than inflating the denominator with announced stores."""
    fc = json.loads(Path(geojson_path).read_text(encoding="utf-8"))
    out = []
    for f in fc.get("features", []):
        c = (f.get("geometry") or {}).get("coordinates")
        if not c:
            continue
        p = f.get("properties", {})
        if p.get("status") == "coming_soon":        # announced, not yet open — held out of every count
            continue
        out.append({"chain": p.get("chain"), "lon": round(c[0], 6), "lat": round(c[1], 6),
                    "state": p.get("state"), "sector": p.get("sector")})
    return out


# A lookup cache so the pass can run OFTEN (daily) without re-querying the Census for coordinates and
# tracts it already resolved. Coordinate->geography is effectively permanent and tract %Asian changes
# only with a new ACS vintage (~yearly), so cached hits stay valid for a long time; a daily run then
# only hits the network for the handful of NEW outlets. Only SUCCESSFUL lookups are cached — never a
# miss/None — so a transient empty response can't poison the cache (see the Census empty-200 gotcha).
# Local to the publish host; delete manual/demographics_cache.json to force a full re-fetch (e.g. for
# a new ACS vintage). The published snapshot still carries aggregates only — the cache is never shipped.
_CACHE_PATH = Path(__file__).resolve().parents[1] / "manual" / "demographics_cache.json"


def _load_cache() -> dict:
    try:
        return json.loads(_CACHE_PATH.read_text(encoding="utf-8"))
    except Exception:                                       # noqa: BLE001 — absent/corrupt → start fresh
        return {}


def _save_cache(cache: dict) -> None:
    try:
        _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        _CACHE_PATH.write_text(json.dumps(cache), encoding="utf-8")
    except Exception:                                       # noqa: BLE001 — caching is best-effort
        pass


def _geographies(uniq_keys, progress=None, geo_cache=None, save=None):
    """{(lon4,lat4): {tract, metro, urban, place}} from the Census geographies endpoint, one call per
    unique rounded coordinate (≈11 m), six at a time. Coordinates already in `geo_cache` are not
    re-fetched; new successful lookups are written back into it, and `save()` (if given) persists the
    cache every 120 new lookups — so even a slow run that is cut short leaves progress to resume from."""
    geo_cache = geo_cache if geo_cache is not None else {}
    ckey = lambda key: f"{key[0]},{key[1]}"
    out, todo = {}, []
    for key in uniq_keys:
        hit = geo_cache.get(ckey(key))
        if hit is not None:
            out[key] = hit
        else:
            todo.append(key)

    def one(key):
        lon, lat = key
        try:
            g = json.loads(_get(_GEO_URL.format(lon=lon, lat=lat)))["result"]["geographies"]
            tr = (g.get("Census Tracts") or [{}])[0]
            csa = (g.get("Combined Statistical Areas") or [{}])
            ua = [v for k, v in g.items() if "Urban Area" in k]
            place = (g.get("Incorporated Places") or [{}])
            return key, {"tract": tr.get("GEOID"),
                         "metro": (csa[0].get("NAME") if csa and csa[0] else None),
                         "urban": bool(ua and ua[0] and ua[0][0].get("NAME")),
                         "place": (place[0].get("NAME") if place and place[0] else None)}
        except Exception:                                   # noqa: BLE001 — a miss, not a failure
            return key, None
    done = 0
    # Three workers, not six: the Census geocoder rate-limits bursts, and a higher concurrency makes
    # requests stall into 40s timeouts (slower overall). With the cache, repeat runs query few coords.
    with ThreadPoolExecutor(max_workers=3) as ex:
        for key, val in ex.map(one, todo):
            out[key] = val
            if val is not None:                             # cache hits only, never a miss
                geo_cache[ckey(key)] = val
            done += 1
            if done % 120 == 0:
                if progress:
                    progress(f"  geo {done}/{len(todo)} (new)")
                if save:
                    save()                                  # persist partial progress for the next run
    if save and todo:
        save()
    if progress and not todo:
        progress(f"  geo: all {len(uniq_keys)} coords cached")
    return out


def _pct_asian(tracts, cache=None):
    """(%Asian by tract GEOID, national %Asian). B03002_006 (non-Hispanic Asian alone) over the
    tract total, from CensusReporter — the ACS without the api.census.gov key requirement. Tracts
    already in `cache` are served from it; new resolved values are written back."""
    cache = cache if cache is not None else {}
    nat_j = json.loads(_get(_CR_URL.format(ids="01000US")))
    e = nat_j["data"]["01000US"]["B03002"]["estimate"]
    nat = e["B03002006"] / e["B03002001"] * 100
    pct, todo = {}, []
    for t in tracts:
        if t in cache:
            pct[t] = cache[t]
        else:
            todo.append(t)
    geoids = ["14000US" + t for t in todo]
    for i in range(0, len(geoids), 40):
        batch = geoids[i:i + 40]
        try:
            d = json.loads(_get(_CR_URL.format(ids=",".join(batch))))["data"]
            for gid, tab in d.items():
                est = tab["B03002"]["estimate"]
                tot = est.get("B03002001") or 0
                v = (est.get("B03002006", 0) / tot * 100) if tot else None
                pct[gid[7:]] = v
                if v is not None:                           # cache resolved values only
                    cache[gid[7:]] = v
        except Exception:                                   # noqa: BLE001 — a dropped batch, noted by coverage
            pass
        time.sleep(0.2)
    return pct, nat


def _campuses(states):
    """[(lat, lon)] of every IPEDS college campus in the states the outlets touch."""
    pts = []
    for st in states:
        if st not in _FIPS:
            continue
        url = _IPEDS_URL.format(fips=_FIPS[st])
        while url:
            d = json.loads(_get(url))
            for r in d.get("results", []):
                if r.get("latitude") and r.get("longitude"):
                    pts.append((r["latitude"], r["longitude"]))
            url = d.get("next")
    return pts


def summarize(rows, national_pct):
    """
    name:      summarize
    purpose:   Reduce the per-outlet join to the aggregates the site is allowed to publish.
    arguments: rows — per-outlet dicts (tract pct_asian, ratio_vs_nat, metro, urban, univ_miles);
               national_pct — the national %Asian benchmark
    returns:   the snapshot dict (no per-outlet data)
    effects:   None
    other:     Aggregate only, by design: the published file names no store. Percentages are over
               the outlets for which that signal resolved, so each carries its own denominator.
    """
    def share(cond, base):
        return round(100 * sum(1 for r in base if cond(r)) / len(base), 1) if base else None

    has_a = [r for r in rows if r.get("pct_asian") is not None]
    urb = [r for r in rows if r.get("urban") is not None]
    with_m = [r for r in rows if r.get("metro")]
    has_u = [r for r in rows if r.get("univ_miles") is not None]
    top = Counter(r["metro"] for r in with_m).most_common(8)
    return {
        "outlets_analyzed": len(rows),
        "with_tract_asian": len(has_a),
        "national_pct_asian": round(national_pct, 1),
        "asian_density": {
            "median_tract_pct": round(_stats.median([r["pct_asian"] for r in has_a]), 1) if has_a else None,
            "ge_national": share(lambda r: r["pct_asian"] >= national_pct, has_a),
            "ge_2x": share(lambda r: r["ratio_vs_nat"] >= 2, has_a),
            "ge_5x": share(lambda r: r["ratio_vs_nat"] >= 5, has_a),
            "ge_10x": share(lambda r: r["ratio_vs_nat"] >= 10, has_a),
        },
        "metro": {
            "urban_pct": share(lambda r: r["urban"], urb),
            "in_csa_pct": round(100 * len(with_m) / len(rows), 1) if rows else None,
            "top": [{"name": nm, "n": ct} for nm, ct in top],
        },
        "university": {
            "within_half_mi": share(lambda r: r["univ_miles"] <= 0.5, has_u),
            "within_1mi": share(lambda r: r["univ_miles"] <= 1, has_u),
            "within_3mi": share(lambda r: r["univ_miles"] <= 3, has_u),
            "median_miles": round(_stats.median([r["univ_miles"] for r in has_u]), 1) if has_u else None,
        },
    }


def build(geojson_path: Path, progress=None) -> dict:
    """
    name:      build
    purpose:   Run the full derived pass and return the publishable snapshot.
    arguments: geojson_path — map/data/stores.geojson; progress — optional str callback
    returns:   the snapshot dict (metadata + aggregates, no per-outlet rows)
    effects:   Network I/O to the Census geocoder, CensusReporter and the IPEDS directory.
    """
    say = progress or (lambda _m: None)
    cache = _load_cache()
    outlets = _outlets(geojson_path)
    say(f"outlets with coords: {len(outlets)}")

    uniq = {(round(o["lon"], 4), round(o["lat"], 4)): None for o in outlets}
    say(f"unique coords (4dp): {len(uniq)} — fetching geographies "
        f"({len(cache.get('geo', {}))} cached)...")
    geo = _geographies(list(uniq), progress=progress, geo_cache=cache.setdefault("geo", {}),
                       save=lambda: _save_cache(cache))

    tracts = sorted({v["tract"] for v in geo.values() if v and v["tract"]})
    pct, nat = _pct_asian(tracts, cache=cache.setdefault("pct", {}))
    _save_cache(cache)
    say(f"national %Asian (NH alone): {nat:.2f}; tracts with %Asian: "
        f"{sum(1 for v in pct.values() if v is not None)}/{len(tracts)}")

    campuses = _campuses(sorted({o["state"] for o in outlets if o["state"]}))
    say(f"campuses loaded: {len(campuses)}")

    rows = []
    for o in outlets:
        gv = geo.get((round(o["lon"], 4), round(o["lat"], 4))) or {}
        tr = gv.get("tract")
        pa = pct.get(tr) if tr else None
        um = min((_miles(o["lat"], o["lon"], la, lo) for la, lo in campuses), default=None)
        rows.append({"metro": gv.get("metro"), "urban": gv.get("urban"),
                     "pct_asian": (round(pa, 1) if pa is not None else None),
                     "ratio_vs_nat": (round(pa / nat, 2) if pa is not None else None),
                     "univ_miles": (round(um, 1) if um is not None else None)})

    snap = summarize(rows, nat)
    snap["generated"] = today_ny()      # New York time — the site's zone, not the host's (Taipei)
    snap["source"] = ("stores.geojson (open storefronts the site counts; roboshops, "
                       "announced-not-yet-open and unconfirmed sightings excluded)")
    snap["method"] = ("Each located storefront joined to public, key-free sources: tract %Asian from "
                      "US Census ACS table B03002 (non-Hispanic Asian alone) via CensusReporter, "
                      "metro/urban from the US Census geographies endpoint, nearest campus from the "
                      "Urban Institute IPEDS directory. Aggregates only; modeled, not measured.")
    return snap


def export(out_dir: Path, src: Path | None = None) -> dict:
    """
    name:      export
    purpose:   Copy the committed snapshot into the page's data dir, so deploy ships it.
    arguments: out_dir — map/data; src — demographics.json (defaults to the repo root's)
    returns:   {"present": bool, "generated": str|None}
    effects:   Writes map/data/demographics.json when the committed snapshot exists.
    other:     The snapshot is NOT regenerated here — the network pass is the `demographics` CLI,
               run on its own cadence. A missing snapshot is not an error: the section hides itself.
    """
    src = src or (Path(__file__).resolve().parents[1] / "demographics.json")
    if not src.exists():
        return {"present": False, "generated": None}
    data = json.loads(src.read_text(encoding="utf-8"))
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    (Path(out_dir) / "demographics.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return {"present": True, "generated": data.get("generated")}


def run(out_path: Path | None = None, geojson_path: Path | None = None) -> int:
    """CLI entry: run the pass and write the committed snapshot at the repo root."""
    import sys
    root = Path(__file__).resolve().parents[1]
    out_path = out_path or (root / "demographics.json")
    geojson_path = geojson_path or (root / "map" / "data" / "stores.geojson")
    if not Path(geojson_path).exists():
        print(f"no {geojson_path}; run `export` first", file=sys.stderr)
        return 2
    snap = build(geojson_path, progress=lambda m: print(m, file=sys.stderr))
    Path(out_path).write_text(json.dumps(snap, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    d = snap["asian_density"]
    print(f"\nwrote {out_path}")
    print(f"  {snap['outlets_analyzed']} outlets | median tract {d['median_tract_pct']}% Asian "
          f"(nat {snap['national_pct_asian']}%) | {d['ge_2x']}% in a ≥2× tract")
    return 0

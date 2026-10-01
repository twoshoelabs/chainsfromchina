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
        "WHERE country='US' AND lat IS NOT NULL AND status IN ('active','pre_opening')"
    ).fetchall():
        bm = meta.get(r["chain_id"], {})
        feats.append(_feature(r["lon"], r["lat"], {
            "chain": r["chain_id"],
            "name": bm.get("name") or r["name"] or r["chain_id"],
            "sector": bm.get("sector"),
            "kind": "store",
            "status": "coming_soon" if r["status"] == "pre_opening" else "open",
            "address": _street(r["addr_raw"] or r["addr_norm"], r["city"], r["state"], r["zip"]),
            "city": r["city"], "state": r["state"],
        }))
    for s in sightings.geocoded(cache_only=True):
        if s.get("lat") is None or not s.get("state"):
            continue
        bm = meta.get(s["chain"], {})
        feats.append(_feature(s["lon"], s["lat"], {
            "chain": s["chain"],
            "name": bm.get("name") or s["chain"],
            "sector": bm.get("sector"),
            "kind": "sighting",
            "status": "coming_soon" if s.get("confidence") == "uncertain" else "sighting",
            "confidence": s.get("confidence"),
            "address": _street(s.get("address"), s.get("city"), s.get("state")),
            "city": s.get("city"), "state": s.get("state"),
        }))
    return {"type": "FeatureCollection", "features": feats}


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

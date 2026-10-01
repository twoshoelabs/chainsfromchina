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
  city, state
Counts are never baked in here; the map derives cluster counts from the features themselves.
"""
import json
from pathlib import Path

from . import register, sightings
from .centers import _brand_meta


def _feature(lon, lat, props):
    return {"type": "Feature", "geometry": {"type": "Point", "coordinates": [lon, lat]},
            "properties": props}


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
        "SELECT chain_id, name, lat, lon, city, state, status FROM stores "
        "WHERE country='US' AND lat IS NOT NULL AND status IN ('active','pre_opening')"
    ).fetchall():
        bm = meta.get(r["chain_id"], {})
        feats.append(_feature(r["lon"], r["lat"], {
            "chain": r["chain_id"],
            "name": bm.get("name") or r["name"] or r["chain_id"],
            "sector": bm.get("sector"),
            "kind": "store",
            "status": "coming_soon" if r["status"] == "pre_opening" else "open",
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

"""
Where a store is, in a form the map and any density series can use.

ONE SPATIAL KEY: a 100 m cell of the US National Atlas equal-area projection (EPSG:2163-style
Lambert azimuthal, centred on the lower 48). It is computed here from latitude and longitude
with no external data, so it is reproducible from the archive alone and cannot rot, disappear
behind a registration form, or change under us — the same reasoning that put TWD97 in the
Taiwan sibling rather than a lookup service.

Equal-area, not conformal, on purpose: the question this project asks is "how many stores per
unit of ground", and only an equal-area projection makes that comparable between Flushing and
Irvine. Alaska, Hawaii and Puerto Rico project fine on this centre — distorted in shape, but
uniquely and stably keyed, which is all a cell id has to be.

PROVENANCE IS RECORDED, NOT ASSUMED. A store's coordinates are either the chain's own
('published') or derived by us ('geocoded'). Stores whose chain publishes no coordinates stay
unlocated and are counted as unlocated rather than dropped: a footprint that quietly omits
what it could not place is a lie about its own coverage.
"""
import math

R = 6370997.0                     # sphere radius used by the US National Atlas projection, metres
CELL_M = 100

# One projection centre per market. A cell key is only comparable within its own market, which
# is the only comparison anyone makes: "how many stores per unit of ground in the UAE" is a
# question about the UAE. Keying the Gulf off a centre in Kansas would be arithmetically valid
# and cartographically absurd.
CENTRES = {
    "US": (45.0, -100.0),         # US National Atlas equal-area — matches map/app.js exactly
    "AE": (24.0, 54.0),
}
LAT0 = math.radians(CENTRES["US"][0])
LON0 = math.radians(CENTRES["US"][1])


def latlon_to_laea(lat: float, lon: float, country: str = "US") -> tuple[float, float]:
    """
    name:      latlon_to_laea
    purpose:   Project WGS84 degrees to Lambert azimuthal equal-area metres about (45N, 100W).
    arguments: lat, lon in degrees
    returns:   (x, y) in metres
    effects:   None
    other:     Spherical formulation — metre-level differences from the ellipsoidal form are far
               finer than a 100 m cell, and the sphere keeps this reproducible in 12 lines.
    """
    c0, l0 = CENTRES.get(country, CENTRES["US"])
    lat0, lon0 = math.radians(c0), math.radians(l0)
    phi, lam = math.radians(lat), math.radians(lon)
    cos_c = math.sin(lat0) * math.sin(phi) + math.cos(lat0) * math.cos(phi) * math.cos(lam - lon0)
    k = math.sqrt(max(0.0, 2.0 / (1.0 + cos_c)))
    x = R * k * math.cos(phi) * math.sin(lam - lon0)
    y = R * k * (math.cos(lat0) * math.sin(phi) - math.sin(lat0) * math.cos(phi) * math.cos(lam - lon0))
    return x, y


def cell100(lat, lon, country: str = "US") -> str | None:
    """
    name:      cell100
    purpose:   The 100 m cell key a coordinate falls in.
    arguments: lat, lon — degrees, or None
    returns:   'E<easting>N<northing>' in cell units, or None when either input is missing
    effects:   None
    other:     None in, None out: an unlocated store must stay unlocated rather than acquire a
               plausible-looking cell.
    """
    if lat is None or lon is None:
        return None
    x, y = latlon_to_laea(float(lat), float(lon), country)
    return f"{country}:E{int(math.floor(x / CELL_M))}N{int(math.floor(y / CELL_M))}"


def haversine_m(lat1, lon1, lat2, lon2) -> float | None:
    """
    name:      haversine_m
    purpose:   Great-circle distance between two coordinates, for the relocation test.
    arguments: two lat/lon pairs in degrees; any may be None
    returns:   metres, or None if a coordinate is missing
    effects:   None
    other:     —
    """
    if None in (lat1, lon1, lat2, lon2):
        return None
    p1, p2 = math.radians(float(lat1)), math.radians(float(lat2))
    dp = p2 - p1
    dl = math.radians(float(lon2) - float(lon1))
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6371008.8 * math.asin(math.sqrt(a))

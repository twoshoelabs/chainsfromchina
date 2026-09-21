"""
CHAGEE — https://www.chagee.us/stores

Next.js app; the complete US store list ships inside the server-rendered flight payload of the
stores page, so one request gets everything and no XHR endpoint has to be reverse-engineered.
Each store carries a stable UUID, a full address and a "lat, lon" string — published
coordinates, which makes CHAGEE the only chain here that needs no geocoding.

Observed 21 Sep 2026: 11 US stores, all in California.

LEGAL: no robots.txt is served (the path returns the app's 404 page), which is an allowance.
One request per day.

FRAGILITY: the payload is an implementation detail of the framework, not a published API, and
the escaping changes with Next.js versions. EXPECTED_MIN plus the count guard below turn a
silent parse failure into a loud refusal, which is the only safe behaviour: zero stores parsed
must never be recorded as eleven closures.
"""
import re

from .base import Adapter, StoreRecord
from .. import capture
from ..usaddr import split_tail

ENDPOINT = "https://www.chagee.us/stores"
EXPECTED_MIN = 3
_STORE = re.compile(
    r'\{"id":"([0-9a-fA-F-]{36})",'
    r'"name":"((?:[^"\\]|\\.)*)",'
    r'"address":"((?:[^"\\]|\\.)*)",'
    r'"location":"([^"]*)"\}')
_CARD = re.compile(r'CHAGEE Modern Teahouse')


def _stores(page: str) -> list[dict]:
    flat = page.replace('\\"', '"').replace("\\\\", "\\")
    out, seen = [], set()
    for sid, name, addr, loc in _STORE.findall(flat):
        if sid in seen:
            continue
        seen.add(sid)
        lat = lon = None
        parts = [p.strip() for p in loc.split(",")]
        if len(parts) == 2:
            try:
                lat, lon = float(parts[0]), float(parts[1])
            except ValueError:
                lat = lon = None
        out.append({"id": sid, "name": name.strip(), "addr": addr.strip(), "lat": lat, "lon": lon})
    return out


class ChageeAdapter(Adapter):
    chain_id, name, name_zh = "chagee", "CHAGEE", "霸王茶姬"
    parent, format = "CHAGEE Holding Ltd", "tea"
    closure_n_days = 5
    raw_ext = "html"
    ENABLED = True

    def fetch_raw(self):
        r = capture.fetch(ENDPOINT)
        r.encoding = "utf-8"
        page = r.text
        recs = _stores(page)
        if not recs:
            raise RuntimeError("CHAGEE page yielded no stores; the flight payload shape has"
                               " probably changed — refusing the pass")
        if len(recs) < EXPECTED_MIN:
            raise RuntimeError(f"only {len(recs)} CHAGEE stores (expected >= {EXPECTED_MIN});"
                               " refusing a partial footprint")
        return page

    def parse(self, raw) -> list[StoreRecord]:
        page = raw if isinstance(raw, str) else raw.decode("utf-8")
        out = []
        for s in _stores(page):
            city, st, zc = split_tail(s["addr"])
            out.append(StoreRecord(store_code=s["id"], name=s["name"], addr_raw=s["addr"],
                                   city=city, state=st, zip=zc, lat=s["lat"], lon=s["lon"],
                                   trading=True))
        return out


def probe():
    a = ChageeAdapter()
    for r in a.parse(a.fetch_raw()):
        print(f"  {r.name} | {r.addr_raw} | {r.lat},{r.lon}")

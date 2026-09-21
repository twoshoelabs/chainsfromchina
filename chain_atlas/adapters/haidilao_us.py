"""
Haidilao US (海底捞) — https://www.haidilao-inc.com/us/serve/storeSearch

The longest-established mainland chain in America: first restaurant Arcadia, Los Angeles, 2013.

ENDPOINT.

    GET https://www.haidilao-inc.com/us/eportal/store/listObjByPosition
        ?longitude=<lon>&latitude=<lat>&mapType=1&country=US&language=en-US

One request for the whole US estate, with coordinates, a stable per-store id, phone and hours.
The lat/lon are a SORT ORIGIN, not a filter: the same fifteen stores and the same id set come
back from Taiwan, Kansas or New York, only the `distance` field changes. Verified from three
origins before this adapter was written, because an endpoint that silently returned "nearest N"
would have quietly truncated the estate the day it grew past N.

WHY IT TOOK SO LONG TO FIND, recorded so the next hunt is shorter. The obvious hosts are all
decoys: haidilao.com serves only Greater China whatever country parameter is passed (1,493
stores, countryId CN/HK/MO/TW); superhiinternational.com, the listed overseas arm, publishes
country SUMMARIES at /eportal/earth/list and no store list at all; haidilao.us, hdlus.com and
haidilaousa.com do not resolve. The US estate lives on a third domain, haidilao-inc.com, under a
market path — and the same shape serves other markets (/sg/ returns 15 Singapore restaurants),
so this is a template for Haidilao's other countries whenever they are wanted.

WHAT IT CORRECTED. Super Hi's own country endpoint reports 13 US restaurants in 8 cities. This
locator lists 15, in 15 distinct cities. A company's published summary of itself was the less
accurate of its two first-party sources, which is worth remembering the next time a round number
in an annual report looks like corroboration.

LEGAL: robots.txt returns 404 on this host, i.e. no restriction. One request a day.
"""
import json

from .base import Adapter, StoreRecord
from .. import capture
from ..usaddr import split_tail

# A sort origin near the geographic centre of the US. Any origin returns the same set; this one
# at least makes the `distance` field mean something to a reader of the raw capture.
ENDPOINT = ("https://www.haidilao-inc.com/us/eportal/store/listObjByPosition"
            "?longitude=-98.6&latitude=39.8&mapType=1&country=US&language=en-US")
EXPECTED_MIN = 8


class HaidilaoUSAdapter(Adapter):
    chain_id, country = "haidilao", "US"
    name, name_zh = "Haidilao", "海底捞"
    parent, format = "Super Hi International (HKEX 9658 / Nasdaq HDL)", "restaurant"
    register_chain = "haidilao"
    closure_n_days = 7
    ENABLED = True

    def fetch_raw(self):
        r = capture.fetch(ENDPOINT)
        raw = r.text
        rows = (json.loads(raw) or {}).get("value") or []
        foreign = {s.get("countryId") for s in rows} - {"US"}
        if foreign:
            raise RuntimeError(f"Haidilao US returned non-US rows ({sorted(foreign)}); the market"
                               " path has changed — refusing rather than filing them as American")
        recs = self.parse(raw)
        if len(recs) < EXPECTED_MIN:
            raise RuntimeError(f"only {len(recs)} Haidilao US restaurants"
                               f" (expected >= {EXPECTED_MIN}); refusing a partial footprint")
        return raw

    def parse(self, raw) -> list[StoreRecord]:
        d = json.loads(raw) if isinstance(raw, (str, bytes)) else raw
        out = []
        for s in (d.get("value") or []):
            # isDisplay is the chain's own "show this on the locator" flag. A hidden row is not
            # evidence of a closure, so it is skipped rather than recorded as absent.
            if s.get("isDisplay") == 0:
                continue
            addr = (s.get("storeAddress") or "").strip()
            city, state, zc = split_tail(addr)
            lat, lon = s.get("latitude"), s.get("longitude")
            out.append(StoreRecord(
                store_code=s.get("storeId"), name=s.get("storeName"), addr_raw=addr,
                city=city, state=state, zip=zc,
                lat=float(lat) if lat not in (None, "") else None,
                lon=float(lon) if lon not in (None, "") else None,
                # openStatus 0 means the chain is not currently trading there.
                trading=(s.get("openStatus") != 0),
                flags={"phone": s.get("storeTelephone"), "hours": s.get("openTime"),
                       "open_status": s.get("openStatus")}))
        return out


def probe():
    a = HaidilaoUSAdapter()
    recs = a.parse(a.fetch_raw())
    print(f"  {len(recs)} restaurants")
    for r in recs:
        print(f"    {str(r.name)[:32]:34} {str(r.city):18} {str(r.state):3} {r.lat},{r.lon}")

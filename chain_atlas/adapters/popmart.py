"""
POP MART US (泡泡玛特) — blocked all day by Cloudflare, then collectable in one request.

HOW IT WAS FOUND, because the lesson is worth more than the adapter. This project spent hours
concluding Pop Mart was uncollectable: www.popmart.com/us/store-list returns a bot challenge to
any non-browser client, and so does the Hong Kong equivalent, so the block looked site-wide and
deliberate. The conclusion was recorded, dated, and wrong.

What broke it open was reading Overture's provenance. Its eight New York Pop Mart rows cited
`dataset=AllThePlaces` — an open-source project that scrapes brand store locators, exactly as
this project does. Its Pop Mart spider does not touch the website at all. It calls the app's API
host:

    POST https://prod-intl-api.popmart.com/shop/v1/store/mapStoreList
    {"latitudeCenter":"", ... all bounds empty ..., "query":" ", "country":"", "s":"", "t":<epoch>}

Empty bounds and a single-space query return the whole global estate — 384 stores, 182 of them
American — with coordinates, addresses, phone, hours and a stable `uniqCode`. No challenge, no
token, and robots.txt 404s on that host, so nothing is disallowed.

THE DEFENDED THING WAS THE WEBSITE, NOT THE DATA. A chain can protect its storefront and publish
the same records openly through the API its own app uses, and this project had no way to know
that from probing the website alone. Every other "no locator exists" verdict here deserves the
same suspicion: they describe where somebody looked, not what exists.

ITS COUNTRY LABEL IS NOT RELIABLE. The feed lists a roboshop at Square One Shopping Centre,
"100 City Centre Dr", as country "United States". The coordinate — 43.593, -79.642 — is
Mississauga, Ontario. The pipeline drops rows whose coordinates land in no US state and says how
many, rather than trusting a feed's own idea of where it is.

LEGAL: robots.txt returns 404 on prod-intl-api.popmart.com, i.e. no restriction. One request a
day for the entire global estate — lighter on their infrastructure than the seven the UAE site
costs, and far lighter than a browser session would have been.
"""
import json
import time

from .base import Adapter, StoreRecord
from .. import capture
from ..usaddr import split_tail

ENDPOINT = "https://prod-intl-api.popmart.com/shop/v1/store/mapStoreList"
EXPECTED_MIN = 60
COUNTRY = "United States"


class PopMartUSAdapter(Adapter):
    chain_id, country = "popmart", "US"
    name, name_zh = "POP MART", "泡泡玛特"
    parent, format = "Pop Mart International Group", "toys"
    register_chain = "popmart"
    closure_n_days = 7
    ENABLED = True

    def fetch_raw(self):
        body = {"latitudeCenter": "", "longitudeCenter": "", "latitudeSouthwest": "",
                "longitudeSouthwest": "", "latitudeNortheast": "", "longitudeNortheast": "",
                "query": " ", "country": "", "s": "", "t": int(time.time())}
        r = capture.fetch(ENDPOINT, method="POST",
                          headers={"Content-Type": "application/json"}, data=json.dumps(body))
        raw = r.text
        stores = (json.loads(raw).get("data") or {}).get("storeList") or []
        if not stores:
            raise RuntimeError("POP MART returned an empty storeList; refusing the pass")
        # The response is global. If the US disappears from it entirely, that is a change in the
        # endpoint rather than 182 simultaneous closures.
        if not [s for s in stores if s.get("country") == COUNTRY]:
            raise RuntimeError(f"POP MART returned {len(stores)} stores and none in {COUNTRY};"
                               " the country labelling has changed — refusing the pass")
        recs = self.parse(raw)
        if len(recs) < EXPECTED_MIN:
            raise RuntimeError(f"only {len(recs)} POP MART US stores (expected >= {EXPECTED_MIN});"
                               " refusing a partial footprint")
        return raw

    def parse(self, raw) -> list[StoreRecord]:
        d = json.loads(raw) if isinstance(raw, (str, bytes)) else raw
        out = []
        for s in ((d.get("data") or {}).get("storeList") or []):
            if s.get("country") != COUNTRY:
                continue
            addr = (s.get("addressLocal") or "").strip()
            city, state, zc = split_tail(addr)
            lat, lon = s.get("lat"), s.get("lon")
            out.append(StoreRecord(
                store_code=str(s.get("uniqCode") or s.get("id")),
                name=s.get("nameLocal") or s.get("nameCN"), addr_raw=addr,
                city=city, state=state, zip=zc,
                lat=float(lat) if lat not in (None, "") else None,
                lon=float(lon) if lon not in (None, "") else None,
                # Every US row carries status 1 today. A different value is not assumed to mean
                # "closed" — it means the field needs looking at before it is trusted.
                trading=(s.get("status") == 1),
                flags={"phone": s.get("storeTEL"), "hours": s.get("openingTimeDesc"),
                       "store_type": s.get("type"), "status": s.get("status")}))
        return out


def probe():
    a = PopMartUSAdapter()
    recs = a.parse(a.fetch_raw())
    from collections import Counter
    print(f"  {len(recs)} US stores; states: {len(set(r.state for r in recs if r.state))}")
    for st, n in Counter(r.state for r in recs).most_common(10):
        print(f"    {st}: {n}")

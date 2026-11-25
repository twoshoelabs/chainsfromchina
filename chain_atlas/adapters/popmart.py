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
import re
import time

from .base import Adapter, StoreRecord


def _dedup_key(addr_raw, city, state):
    """A coarse identity for a US storefront: leading street number + city + state. Lets a manual
    supplement entry self-remove once the live feed publishes a storefront at the same address,
    while keeping distinct stores apart — including two stores that share a street number in the
    same state but sit in different cities (e.g. 11401 NW 12th St Miami vs 11401 Pines Blvd
    Pembroke Pines)."""
    m = re.match(r"\s*(\d+)", addr_raw or "")
    num = m.group(1) if m else (addr_raw or "").strip().lower()
    return (num, (city or "").strip().lower(), (state or "").upper())
from .. import capture
from ..usaddr import split_tail

ENDPOINT = "https://prod-intl-api.popmart.com/shop/v1/store/mapStoreList"
EXPECTED_MIN = 60
COUNTRY = "United States"

# Stores confirmed open (mall directory / owner report) that the app API has not yet published.
# The API lags new openings, so a store can be trading for weeks before it appears in the feed.
# These are appended ONLY to a full live feed (see the EXPECTED_MIN guard in parse(), which keeps
# the test fixture untouched) and ONLY while the feed carries no store in that city — so the day
# the API finally lists it, the supplement drops out on its own and nothing is double-counted
# (there is no global dedup here, by design, because of the store/roboshop split). Re-check these
# against the API periodically and delete each once the feed catches up.
KNOWN_MISSING = [
    StoreRecord(
        store_code="manual-brea-mall", name="POP MART",
        addr_raw="1065 Brea Mall, Brea, CA 92821", city="Brea", state="CA", zip="92821",
        lat=33.9150, lon=-117.8864, trading=True, format="standard",
        flags={"source": "Brea Mall (Simon) directory 'Now Open' + owner-confirmed 2026-11-22",
               "manual_supplement": True}),
    # The three below are staffed stores the API mis-handles — it drops Ala Moana entirely and
    # tags Dolphin + Montgomery as type-2 roboshops — so a plain re-collect silently un-counts
    # them (the count fell 79->75 before this supplement was added). All re-verified OPEN via mall
    # directories + dated Google Maps "Store" listings on 2026-11-22. (Tysons VA is deliberately NOT
    # here: only a Robo Shop is live there; its staffed store is still "under development" for Q4
    # 2026 — add it once it actually opens.)
    StoreRecord(
        store_code="manual-ala-moana", name="POP MART",
        addr_raw="1450 Ala Moana Blvd, Honolulu, HI 96814", city="Honolulu", state="HI", zip="96814",
        lat=21.2911, lon=-157.8435, trading=True, format="standard",
        flags={"source": "Ala Moana Center directory 'Now Open' (Level 3, Ewa Wing; HI's first), "
                          "re-verified 2026-11-22", "manual_supplement": True}),
    StoreRecord(
        store_code="manual-dolphin-mall", name="POP MART",
        addr_raw="11401 NW 12th St #262, Miami, FL 33172", city="Miami", state="FL", zip="33172",
        lat=25.7884, lon=-80.3819, trading=True, format="standard",
        flags={"source": "Google Maps 'POPMART Dolphin Mall' (Store, 5.0*), opened 12 Sep 2026; "
                          "API mis-tags as roboshop. Re-verified 2026-11-22", "manual_supplement": True}),
    StoreRecord(
        store_code="manual-montgomery-mall", name="POP MART",
        addr_raw="7101 Democracy Blvd Unit 3316, Bethesda, MD 20817", city="Bethesda", state="MD",
        zip="20817", lat=39.0245, lon=-77.1464, trading=True, format="standard",
        flags={"source": "Google Maps 'POP MART' Westfield Montgomery (Store, 5.0*, staffed, recent "
                          "reviews); API mis-tags as roboshop. Re-verified 2026-11-22",
               "manual_supplement": True}),
]


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
                # One code ships as " R3S-E950" with a leading space. Stripping it here
                # keeps identity stable on the day they tidy it.
                store_code=str(s.get("uniqCode") or s.get("id")).strip(),
                name=s.get("nameLocal") or s.get("nameCN"), addr_raw=addr,
                city=city, state=state, zip=zc,
                lat=float(lat) if lat not in (None, "") else None,
                lon=float(lon) if lon not in (None, "") else None,
                # Every US row carries status 1 today. A different value is not assumed to mean
                # "closed" — it means the field needs looking at before it is trusted.
                trading=(s.get("status") == 1),
                # type 1 is a staffed store; type 2 is a ROBO SHOP — an unstaffed vending machine,
                # often two or three to a mall. Machines are tracked but not counted as storefronts,
                # so the format marks them for every downstream view.
                format=("vending_robo" if s.get("type") == 2 else "standard"),
                flags={"phone": s.get("storeTEL"), "hours": s.get("openingTimeDesc"),
                       "store_type": s.get("type"), "status": s.get("status")}))
        # Append confirmed-open storefronts the feed has not yet published — only on a full live
        # feed (never the small test fixture). Match by (street-number, state) against the feed's
        # STAFFED storefronts only: roboshop (vending_robo) rows do NOT count as coverage, because
        # the API routinely lists a mall's vending machines (or nothing) while omitting the staffed
        # store that is actually open, and it also mis-tags real stores as roboshops. Each entry
        # self-removes the day the API finally publishes a storefront at that address.
        if len(out) >= EXPECTED_MIN:
            have = {_dedup_key(r.addr_raw, r.city, r.state)
                    for r in out if r.state and r.format != "vending_robo"}
            for extra in KNOWN_MISSING:
                if _dedup_key(extra.addr_raw, extra.city, extra.state) not in have:
                    out.append(extra)
        return out


def probe():
    a = PopMartUSAdapter()
    recs = a.parse(a.fetch_raw())
    from collections import Counter
    print(f"  {len(recs)} US stores; states: {len(set(r.state for r in recs if r.state))}")
    for st, n in Counter(r.state for r in recs).most_common(10):
        print(f"    {st}: {n}")

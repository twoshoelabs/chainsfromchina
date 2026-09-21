"""
MINISO US — https://www.miniso-us.com/store-locator

The largest footprint in this project by an order of magnitude: 462 rows, ~425 real stores.

HOW IT IS COLLECTED. The locator is a Wix site whose store list is neither in the HTML nor in
any XHR the page itself makes — the fetch happens inside a Wix web worker, which is why an
ordinary network capture shows nothing. The page's own router config names the collection
backing /locations/<slug>:

    "prefix":"locations" ... "config":{"collection":"Locations", ...}

so the collector asks Wix Data for that collection directly, exactly as the site's own worker
does: GET /_api/v1/access-tokens for a session instance, then POST to the CMS query endpoint
with the site's gridAppId. Two requests a day for the whole estate.

WHAT THE DATA IS LIKE, which is the real work here. Miniso's CMS is a working business system,
not a published dataset, and taking its 462 rows at face value would overstate the chain by
about 9%:

  * `storeCode` is NOT unique. 33 codes appear on 67 rows because a bulk re-import on 1 July
    2026 re-added stores first entered on 8-9 June 2026. Same store, two rows, addresses written
    differently ("6191 S StateStreet, Ste. D311" and "6191 S State St #1195").
  * `storeCode` is also NOT unambiguous. Five codes cover genuinely different stores hundreds of
    kilometres apart, because America has more than one Southlake Mall, Columbia Mall, Northpark
    Mall and SouthPark Mall — and USFA covers two different Chinatown Centers, in Houston and in
    Austin, so the STATE does not separate them either. The city does.
  * Three rows carry `storeCode: "Closed"` with no address at all: stores Miniso has shut and
    kept in the CMS. They are excluded from the roster and reported, never counted as trading.
  * `stateTag` is unreliable — seven real stores carry the literal string "#N/A" — so the state
    is read from the address with this project's own parser instead, and the CMS field is
    ignored rather than trusted.

IDENTITY is therefore (storeCode, city), which merges the re-import duplicates and keeps the
same-name malls apart. Rows whose storeCode is not a real code ("#N/A", "Zootopia Pop-up") fall
back to the Wix item id, which is unique. A group whose members turn out to be more than
SPLIT_KM apart is split back to per-row identity rather than silently merged: the key failing to
discriminate must cost an unmerged duplicate, not a disappeared store.

LEGAL: robots.txt allows /store-locator (it disallows only *?lightbox= and, for other agents,
some internal paths). This is the site's own public store locator read through the site's own
public endpoint, once a day, with an identifying User-Agent.
"""
import json
import math
import re

from .base import Adapter, StoreRecord
from .. import capture
from ..usaddr import split_tail

TOKENS_URL = "https://www.miniso-us.com/_api/v1/access-tokens"
QUERY_URL = "https://www.miniso-us.com/_api/cloud-data/v1/wix-data/collections/query"
GRID_APP_ID = "4fdbf1a9-6e82-4028-b0b9-ef4bf6824697"
COLLECTION = "Locations"
# The Velo app, whose session instance the CMS query accepts. Unauthenticated queries are 400.
VELO_APP = "22bef345-3c5b-4c18-b782-74d4085112ff"
PAGE = 500
EXPECTED_MIN = 300
SPLIT_KM = 2.0
_REAL_CODE = re.compile(r"US[A-Z0-9]{2,4}\Z")
CLOSED_CODE = "Closed"


def _km(a, b):
    if not a or not b:
        return None
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    dp, dl = p2 - p1, math.radians(b[1] - a[1])
    x = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6371.0088 * math.asin(math.sqrt(x))


def _loc(item):
    l = (item.get("address") or {}).get("location") or {}
    lat, lon = l.get("latitude"), l.get("longitude")
    return (lat, lon) if lat is not None and lon is not None else None


def _type(item):
    r = item.get("reference")
    return r.get("title") if isinstance(r, dict) else None


def _created(item):
    return ((item.get("_createdDate") or {}).get("$date")) or ""


class MinisoAdapter(Adapter):
    chain_id, name, name_zh = "miniso", "MINISO", "名创优品"
    parent, format = "MINISO Group Holding", "lifestyle"
    closure_n_days = 7
    ENABLED = True

    def fetch_raw(self):
        tok = capture.fetch(TOKENS_URL).json()
        inst = (tok.get("apps") or {}).get(VELO_APP, {}).get("instance")
        if not inst:
            raise RuntimeError("MINISO: no Velo app instance in /_api/v1/access-tokens;"
                               " the site's app set has changed — refusing the pass")
        headers = {"Content-Type": "application/json", "Authorization": inst}
        items, total, offset = [], None, 0
        while True:
            body = {"collectionName": COLLECTION, "segment": "LIVE", "gridAppId": GRID_APP_ID,
                    "includeReferencedItems": ["reference"],
                    "query": {"paging": {"offset": offset, "limit": PAGE}}}
            page = capture.fetch(QUERY_URL, method="POST", headers=headers,
                                 data=json.dumps(body)).json()
            batch = page.get("items") or []
            items.extend(batch)
            total = page.get("totalCount") if total is None else total
            offset += len(batch)
            if not batch or total is None or offset >= total:
                break
            if offset > 5000:
                raise RuntimeError("MINISO: paging ran past 5000 rows; refusing to loop")
        if total is not None and len(items) != total:
            raise RuntimeError(f"MINISO: collected {len(items)} rows but the collection reports"
                               f" {total}; refusing a partial footprint")
        # Only the query result is archived. The access token is transient authentication, not
        # evidence, and a session identifier has no business sitting in a permanent archive.
        raw = {"collection": COLLECTION, "totalCount": total, "items": items}
        recs = self.parse(raw)
        if len(recs) < EXPECTED_MIN:
            raise RuntimeError(f"only {len(recs)} MINISO stores (expected >= {EXPECTED_MIN});"
                               " refusing a partial footprint")
        return raw

    def parse(self, raw) -> list[StoreRecord]:
        d = json.loads(raw) if isinstance(raw, (str, bytes)) else raw
        rows = [r for r in (d.get("items") or []) if (r.get("storeCode") or "") != CLOSED_CODE]

        # Group by the identity key, then split any group whose members are too far apart to be
        # the same shop.
        groups: dict[str, list] = {}
        for r in rows:
            code = (r.get("storeCode") or "").strip()
            city = ((r.get("address") or {}).get("city") or "").strip().lower()
            key = f"{code}:{city}" if _REAL_CODE.match(code) and city else f"wix:{r['_id']}"
            groups.setdefault(key, []).append(r)

        out = []
        for key, members in groups.items():
            for cluster in _split_far(members):
                out.append(self._record(key if len(members) == len(cluster) else
                                        f"wix:{cluster[0]['_id']}", cluster))
        return out

    def _record(self, key, cluster) -> StoreRecord:
        # Prefer the row that can be placed on a map, then the most recently created: the
        # 1 July 2026 re-import carries the tidier addresses.
        best = sorted(cluster, key=lambda r: (_loc(r) is not None, _created(r)))[-1]
        addr = (best.get("plainTextAddress") or
                (best.get("address") or {}).get("formatted") or "").strip()
        city, state, zc = split_tail(addr)
        a = best.get("address") or {}
        city = city or (a.get("city") or None)
        # stateTag holds "#N/A" for seven real stores, so the CMS field is a last resort only.
        state = state or (a.get("subdivision") or None)
        if state and len(state) != 2:
            state = None
        zc = zc or (a.get("postalCode") or None)
        loc = _loc(best)
        kind = _type(best)
        return StoreRecord(
            store_code=key, name=best.get("title_fld"), addr_raw=addr,
            city=city, state=state, zip=zc,
            lat=loc[0] if loc else None, lon=loc[1] if loc else None,
            trading=(kind != "Coming Soon"),
            flags={"store_type": kind, "code": best.get("storeCode"),
                   "merged_rows": len(cluster) if len(cluster) > 1 else None})


def _split_far(members):
    """
    name:      _split_far
    purpose:   Break a same-key group into clusters of rows that are plausibly one shop.
    arguments: members — rows sharing an identity key
    returns:   list of lists
    effects:   None
    other:     Single-linkage on SPLIT_KM. Rows with no coordinates cannot be shown to be far
               from anything, so they stay with the first cluster rather than becoming phantom
               extra stores.
    """
    if len(members) == 1:
        return [members]
    clusters: list[list] = []
    for r in sorted(members, key=_created, reverse=True):
        here = _loc(r)
        for c in clusters:
            if here is None or any((_km(here, _loc(x)) or 0) <= SPLIT_KM for x in c):
                c.append(r)
                break
        else:
            clusters.append([r])
    return clusters


def probe():
    a = MinisoAdapter()
    recs = a.parse(a.fetch_raw())
    from collections import Counter
    print(f"  {len(recs)} stores; states: {len(set(r.state for r in recs if r.state))}")
    for st, n in Counter(r.state for r in recs).most_common(8):
        print(f"    {st}: {n}")

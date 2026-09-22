"""
MIXUE USA — https://join.mixueusfranchise.com/stores

The best source in the project. The locator is a tRPC endpoint returning the whole US estate
in one request, with the chain's own integer id, coordinates, and — uniquely so far — a
`status` of `open` or `coming_soon` plus an `openingDate`. That means Mixue's pipeline is
visible weeks ahead, and an opening can be dated to the day the status flips rather than to
the day a new row appeared.

Observed 21 Sep 2026: 27 stores, 10 open and 17 coming_soon, in a single request.

LEGAL: robots.txt allows everything outside /private/, /admin/, /temp/, /cache/. This is the
franchisor's own public store locator, fetched once a day with an identifying User-Agent.

CAVEAT: this is the FRANCHISE site, not a consumer ordering app. It is first-party and it is
the only complete list published, but a store that opens without the franchise team updating
this page is invisible to us. Corroboration against a second source is future work.
"""
import json
from urllib.parse import quote

from .base import Adapter, StoreRecord
from .. import capture

_INPUT = quote(json.dumps({"0": {"json": None, "meta": {"values": ["undefined"]}}},
                          separators=(",", ":")), safe="")
ENDPOINT = f"https://join.mixueusfranchise.com/api/trpc/stores.getAll?batch=1&input={_INPUT}"
EXPECTED_MIN = 5


class MixueAdapter(Adapter):
    chain_id, name, name_zh = "mixue", "MIXUE", "蜜雪冰城"
    aliases = ("Mixue Ice Cream & Tea", "Mixue Bingcheng")
    parent, format = "Mixue Group", "tea"
    closure_n_days = 5
    ENABLED = True

    def fetch_raw(self):
        r = capture.fetch(ENDPOINT)
        raw = r.text
        recs = self.parse(raw)
        if len(recs) < EXPECTED_MIN:
            raise RuntimeError(f"only {len(recs)} MIXUE stores (expected >= {EXPECTED_MIN});"
                               " refusing a partial footprint")
        return raw

    def parse(self, raw) -> list[StoreRecord]:
        d = json.loads(raw) if isinstance(raw, (str, bytes)) else raw
        rows = d[0]["result"]["data"]["json"]
        out = []
        for s in rows:
            street = (s.get("address") or "").strip()
            city, st, zc = s.get("city"), s.get("state"), s.get("zipCode")
            full = ", ".join(x for x in (street, city, f"{st} {zc}".strip()) if x)
            lat, lon = s.get("latitude"), s.get("longitude")
            out.append(StoreRecord(
                store_code=str(s["id"]), name=s.get("name"), addr_raw=full,
                city=city, state=st, zip=zc,
                lat=float(lat) if lat not in (None, "") else None,
                lon=float(lon) if lon not in (None, "") else None,
                trading=(s.get("status") == "open"),
                flags={"status": s.get("status"), "openingDate": s.get("openingDate")}))
        return out


def probe():
    a = MixueAdapter()
    for r in a.parse(a.fetch_raw()):
        print(f"  {'OPEN ' if r.trading else 'SOON '} {r.name} | {r.addr_raw} | {r.lat},{r.lon}")

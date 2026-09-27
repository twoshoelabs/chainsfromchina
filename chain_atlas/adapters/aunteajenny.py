"""
Auntea Jenny — https://aunteajenny.us

沪上阿姨 (Auntea Jenny), a Shanghai bubble-tea chain founded 2013 and one of the mainland's largest,
trading in the US as "Auntea Jenny". Its US site renders the locator from a CMS list the page
itself reads: POST /api/cms/get_md with the site's own "All States" column returns every US outlet
as JSON — name in `title`, address in `desc` (with a <br>), "(Coming Soon)" marked in the title.
One request gets the whole footprint.

Observed 28 Sep 2026: 6 open (NY x2, CA x4) plus 11 coming soon (NY, IL, CA).

LEGAL: robots.txt is Allow: /; this is the same feed the public discover page reads, called the
same way, so it is what a visitor's browser fetches — not a private endpoint.

FRAGILITY: a CMS list, not a documented API. EXPECTED_MIN refuses an empty or partial pull rather
than record the open outlets as closures.
"""
import json
import re

from .base import Adapter, StoreRecord
from .. import capture
from ..usaddr import split_tail

ENDPOINT = "https://aunteajenny.us/api/cms/get_md"
ALL_STATES = "18"            # the "All States" column id in the site's own state selector
EXPECTED_MIN = 4
_SOON = re.compile(r"\(?（?\s*coming soon\s*）?\)?", re.I)
_TAG = re.compile(r"<[^>]+>")


def _clean_addr(desc: str) -> str:
    s = _TAG.sub(" ", desc or "")
    return re.sub(r"\s+", " ", s).strip().rstrip(",").strip()


def _stores(data) -> list[dict]:
    out = []
    for it in data or []:
        title = (it.get("title") or "").strip()
        addr = _clean_addr(it.get("desc"))
        if not title or not addr:
            continue
        out.append({"name": _SOON.sub("", title).strip(),
                    "addr": addr,
                    "trading": not bool(_SOON.search(title))})
    return out


class AunteaJennyAdapter(Adapter):
    chain_id, name, name_zh = "aunteajenny", "Auntea Jenny", "沪上阿姨"
    name_us = "Auntea Jenny"
    aliases = ("Hu Shang A Yi",)
    parent, format = "Auntea Jenny (沪上阿姨, Shanghai)", "tea"
    closure_n_days = 5
    raw_ext = "json"
    ENABLED = True

    def fetch_raw(self):
        r = capture.fetch(ENDPOINT, method="POST",
                          data={"lang": "en", "column_id": ALL_STATES, "keywords": ""})
        r.encoding = "utf-8"
        d = r.json()
        recs = _stores(d.get("data"))
        if len(recs) < EXPECTED_MIN:
            raise RuntimeError(f"only {len(recs)} Auntea Jenny stores (expected >= {EXPECTED_MIN});"
                               " the CMS feed shape has probably changed — refusing the pass")
        return d

    def parse(self, raw) -> list[StoreRecord]:
        d = json.loads(raw) if isinstance(raw, (str, bytes)) else raw
        out = []
        for s in _stores(d.get("data")):
            city, st, zc = split_tail(s["addr"])
            out.append(StoreRecord(store_code=None, name=s["name"], addr_raw=s["addr"],
                                   city=city, state=st, zip=zc, trading=s["trading"]))
        return out

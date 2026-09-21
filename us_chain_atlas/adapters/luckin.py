"""
Luckin Coffee US — https://www.luckincoffee.us/stores

Server-rendered list of store cards: a title (usually the street line) and a detail line with
the full address. No store id and no coordinates are published, so identity falls back to the
normalised address and the stores stay unlocated until geocoding is added.

Observed 21 Sep 2026: 22 US stores, all New York City.

LEGAL: robots.txt has a "User-agent: *" group whose Disallow lines are malformed (they contain
absolute off-site URLs) and therefore restrict nothing. One request per day.

FRAGILITY: the CSS-module class names carry a per-build hash (`_store-title_j9gxg_35`), so the
selectors below match the stable prefix and ignore the hash. If a rebuild renames the modules
entirely the count guard refuses the pass rather than reporting an empty estate.
"""
import re

from .base import Adapter, StoreRecord
from .. import capture

ENDPOINT = "https://www.luckincoffee.us/stores"
EXPECTED_MIN = 5
_TITLE = re.compile(r'class="_store-title_[^"]*"\s*>(.*?)</div>', re.S)
_DETAIL = re.compile(r'class="_detail_[^"]*"\s*>(.*?)</div>', re.S)
_TAG = re.compile(r"<[^>]+>")


def _text(s: str) -> str:
    return re.sub(r"\s+", " ", _TAG.sub("", s)).replace("&amp;", "&").strip()


def _stores(page: str) -> list[dict]:
    titles = [_text(t) for t in _TITLE.findall(page)]
    details = [_text(d) for d in _DETAIL.findall(page)]
    # The cards render title-then-detail in document order; pairing by index is only safe
    # while the counts agree, which fetch_raw checks before anything is recorded.
    out, seen = [], set()
    for name, addr in zip(titles, details):
        if not addr or addr in seen:
            continue
        seen.add(addr)
        out.append({"name": name or None, "addr": addr})
    return out


_TAIL = re.compile(r",\s*([A-Za-z .'-]+),\s*([A-Z]{2})\s*(\d{5})(?:-\d{4})?\s*$")


class LuckinAdapter(Adapter):
    chain_id, name, name_zh = "luckin", "Luckin Coffee", "瑞幸咖啡"
    parent, format = "Luckin Coffee Inc.", "coffee"
    closure_n_days = 5
    raw_ext = "html"
    ENABLED = True

    def fetch_raw(self):
        r = capture.fetch(ENDPOINT)
        r.encoding = "utf-8"
        page = r.text
        titles, details = _TITLE.findall(page), _DETAIL.findall(page)
        if not titles:
            raise RuntimeError("Luckin page listed no store cards; refusing the pass")
        if len(titles) != len(details):
            raise RuntimeError(f"Luckin: {len(titles)} titles but {len(details)} detail lines;"
                               " the card markup has changed — refusing to pair them")
        if len(_stores(page)) < EXPECTED_MIN:
            raise RuntimeError(f"only {len(_stores(page))} Luckin stores"
                               f" (expected >= {EXPECTED_MIN}); refusing a partial footprint")
        return page

    def parse(self, raw) -> list[StoreRecord]:
        page = raw if isinstance(raw, str) else raw.decode("utf-8")
        out = []
        for s in _stores(page):
            m = _TAIL.search(s["addr"])
            city, st, zc = (m.group(1).strip(), m.group(2), m.group(3)) if m else (None, None, None)
            out.append(StoreRecord(store_code=None, name=s["name"], addr_raw=s["addr"],
                                   city=city, state=st, zip=zc, trading=True))
        return out


def probe():
    a = LuckinAdapter()
    for r in a.parse(a.fetch_raw()):
        print(f"  {r.name} | {r.addr_raw}")

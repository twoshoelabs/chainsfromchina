"""
Möge Tee — https://www.mogeteeusa.com  (愿茶)

愿茶 "Möge Tee", a Chinese bubble-tea chain (founded 2012, franchised from 2018), trading in
the US as "Möge Tee". NOT 茉莉奶白 / Molly Tea — a different brand with a similar milk-tea line, tracked
separately (see mollytea.py).

Its US site is a Wix site whose store locator is one dynamic page per state
(/store-locations-1/<state>), linked from the /store-locations index. Each state page is a hand-built
text page, not a data feed: the stores are server-rendered into the page's `wix-warmup-data` JSON as
ordered rich-text components — the store name, then its address, then a phone number or a "COMING SOON"
marker, in that order. A plain fetch with the project User-Agent returns that JSON (robots allows /),
so no headless browser is needed.

`parse` walks the warmup JSON in document order: a "Moge Tee …" name opens a store, the next
address-shaped component is its address, and a "COMING SOON" marker before the next name flags a
not-yet-open store (trading=False, so it cannot inflate the count); a "Temporarily Closed" block is
dropped. States are read from the locator index, so a newly added state is picked up on its own.

FRAGILITY: a hand-built text page, not a structured feed — the name→address order is the contract, and
EXPECTED_MIN refuses a pull that comes back thin (a site redesign that broke parsing would otherwise
look like mass closures).
"""
import html as H
import json
import re

from .base import Adapter, StoreRecord
from .. import capture
from ..usaddr import split_tail

INDEX = "https://www.mogeteeusa.com/store-locations"
ORIGIN = "https://www.mogeteeusa.com"
EXPECTED_MIN = 45

# Stores Möge Tee's own locator still lists but that are permanently closed on the ground (verified
# by hand against Google's "Permanently closed" banner). We drop them rather than count a dead store
# until the brand updates its locator; the keys are the cleaned address lowercased. Prune an entry
# once the locator drops it.
PERMANENTLY_CLOSED = {
    "140 little cypress drive ste 102, st johns, fl 32259",   # St Johns FL — Google: permanently closed (5 Oct 2026)
    "678 market st, lynnfield, ma 01940",                     # Lynnfield MA — Google: permanently closed (5 Oct 2026)
}

_WARMUP = re.compile(r'id="wix-warmup-data"[^>]*>(.*?)</script>', re.S)
_STATE_LINK = re.compile(r'/store-locations-1/([a-z]{2})\b', re.I)
_ADDR = re.compile(r'^\d{1,6}\b.*,\s*[A-Za-z][A-Za-z .]*,\s*[A-Z]{2}(?:,|\s+\d{5})')


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", "", s or ""))).strip()


def _ordered_texts(doc: str) -> list[str]:
    """Every rich-text string in the page's warmup JSON, in document (render) order."""
    m = _WARMUP.search(doc or "")
    if not m:
        return []
    data = json.loads(m.group(1))
    out: list[str] = []

    def walk(o):
        if isinstance(o, str):
            out.append(_clean(o))
        elif isinstance(o, dict):
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(data)
    return out


def _stores_from_page(doc: str) -> list[dict]:
    """Walk the ordered components and group them into stores (name → address → status)."""
    stores: list[dict] = []
    cur = None
    for t in _ordered_texts(doc):
        if not t:
            continue
        low = t.lower()
        if low == "moge tee":                        # the bare brand name (nav/title), not a store
            continue
        if low.startswith("moge tee"):
            cur = {"name": t, "addr": None, "trading": True, "closed": False}
            stores.append(cur)
        elif cur is not None:
            if cur["addr"] is None and _ADDR.search(t):
                cur["addr"] = t
            elif t.upper() == "COMING SOON":
                cur["trading"] = False
            elif "temporarily closed" in low:
                cur["closed"] = True
    # Keep only real, open-or-coming-soon storefronts with an address; de-dup by address.
    seen, out = set(), []
    for s in stores:
        if not s["addr"] or s["closed"]:
            continue
        key = re.sub(r"\s+", " ", s["addr"]).lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(s)
    return out


def _state_pages(index_doc: str) -> list[str]:
    states = sorted({m.lower() for m in _STATE_LINK.findall(index_doc)})
    return [f"{ORIGIN}/store-locations-1/{st}" for st in states]


class MogeTeeAdapter(Adapter):
    chain_id, name, name_zh = "moge", "Möge Tee", "愿茶"
    name_us = "Möge Tee"
    aliases = ("Yuan Cha", "愿茶")
    parent, format = "Möge Tee (愿茶)", "tea"
    closure_n_days = 5
    raw_ext = "json"
    ENABLED = True

    def fetch_raw(self):
        index = capture.fetch(INDEX).text
        pages = {}
        for url in _state_pages(index):
            pages[url] = capture.fetch(url).text
        total = sum(len(_stores_from_page(h)) for h in pages.values())
        if total < EXPECTED_MIN:
            raise RuntimeError(f"only {total} Möge Tee US stores across {len(pages)} state pages "
                               f"(expected >= {EXPECTED_MIN}); the Wix page shape has probably "
                               "changed — refusing the pass")
        return pages

    def parse(self, raw) -> list[StoreRecord]:
        pages = json.loads(raw) if isinstance(raw, (str, bytes)) else raw
        out = []
        for doc in pages.values():
            for s in _stores_from_page(doc):
                addr = re.sub(r",?\s*USA\.?\s*$", "", s["addr"]).strip()
                if re.sub(r"\s+", " ", addr).lower() in PERMANENTLY_CLOSED:
                    continue                                  # listed on the locator but closed on the ground
                city, st, zc = split_tail(addr)
                out.append(StoreRecord(store_code=None, name=s["name"], addr_raw=addr,
                                       city=city, state=st, zip=zc, trading=s["trading"]))
        return out

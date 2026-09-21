"""
MINISO UAE — https://www.miniso-uae.com/our-stores/

The first non-US market in the archive, and it earns its place by being the same kind of thing:
a chain publishing its own estate on its own site, daily-collectable, with nobody else keeping
the series.

SHAPE. One page per emirate, linked from /our-stores/ — seven pages, seven requests. Each lists
its stores as Elementor <h2> headings. That is all: a name, and the emirate it is in. No address,
no coordinates, no store code. So these stores are counted and never mapped, exactly like
Luckin's New York estate, and `unlocated` says so rather than the map quietly omitting them.

ROBOTS, AND WHY THE OBVIOUS ROUTE IS NOT USED. The site runs WP Store Locator, whose usual
endpoint is /wp-admin/admin-ajax.php?action=store_search — and this site's robots.txt disallows
/wp-admin/. So that route is not used, though it would be one request instead of seven and would
almost certainly carry the coordinates this adapter lacks. The REST route the plugin registers,
/wp-json/wp/v2/wpsl_stores, is allowed but returns an empty array. The emirate pages are
first-party, explicitly allowed, and are what a reader of the site sees; seven polite requests a
day is the price of not going through a door marked shut.

IDENTITY. Name plus emirate, normalised. Watch for the zero-width space in
"AL GHURAIR CENTER​" — left in, it would rewrite the store's key the day someone edits it
out, and the archive would record a closure and an opening in the same mall.
"""
import html
import re

from .base import Adapter, StoreRecord
from .. import capture

BASE = "https://www.miniso-uae.com"
EMIRATES = {
    "dubai-stores": "Dubai",
    "abu-dhabi-stores": "Abu Dhabi",
    "sharjah-stores": "Sharjah",
    "ajman-stores": "Ajman",
    "fujairah-stores": "Fujairah",
    "ras-al-khaimah-stores": "Ras Al Khaimah",
    "umm-al-quwain-stores": "Umm Al Quwain",
}
EXPECTED_MIN = 20
_HEADING = re.compile(r"<h[2-5][^>]*elementor-heading-title[^>]*>(.*?)</h[2-5]>", re.S)
_TAG = re.compile(r"<[^>]+>")
# Headings on these pages are not all stores: the page furniture and the Instagram handle use
# the same widget. Anything matching these is not a shop.
_NOT_A_STORE = re.compile(r"^\s*(@|looking for|find (a )?store|our stores|follow)", re.I)


def _clean(s: str) -> str:
    s = html.unescape(_TAG.sub("", s))
    s = s.replace("​", "").replace(" ", " ")
    return re.sub(r"\s+", " ", s).strip()


def _stores(page: str, emirate: str) -> list[dict]:
    out, seen = [], set()
    for raw in _HEADING.findall(page):
        name = _clean(raw)
        if not name or len(name) < 3 or _NOT_A_STORE.match(name):
            continue
        key = name.upper()
        if key in seen:
            continue
        seen.add(key)
        out.append({"name": name, "emirate": emirate})
    return out


class MinisoUAEAdapter(Adapter):
    chain_id, country = "miniso_ae", "AE"
    name, name_zh = "MINISO (UAE)", "名创优品"
    parent, format = "MINISO Group Holding", "lifestyle"
    register_chain = "miniso"          # supersedes the hand-typed miniso/AE register row
    closure_n_days = 7
    raw_ext = "json"
    ENABLED = True

    def fetch_raw(self):
        pages = {}
        for slug, emirate in EMIRATES.items():
            r = capture.fetch(f"{BASE}/{slug}/")
            r.encoding = "utf-8"
            pages[slug] = r.text
            if not _stores(r.text, emirate):
                # An emirate with genuinely no store would also look like this, so this is a
                # warning in the raw file rather than a refusal — except for Dubai, below.
                pages.setdefault("_empty", []).append(slug)
        if not _stores(pages["dubai-stores"], "Dubai"):
            raise RuntimeError("MINISO UAE: the Dubai page listed no stores; the page markup has"
                               " probably changed — refusing the pass")
        raw = {"pages": {k: v for k, v in pages.items() if k != "_empty"},
               "empty": pages.get("_empty", [])}
        recs = self.parse(raw)
        if len(recs) < EXPECTED_MIN:
            raise RuntimeError(f"only {len(recs)} MINISO UAE stores (expected >= {EXPECTED_MIN});"
                               " refusing a partial footprint")
        return raw

    def parse(self, raw) -> list[StoreRecord]:
        import json
        d = json.loads(raw) if isinstance(raw, (str, bytes)) else raw
        out = []
        for slug, page in (d.get("pages") or {}).items():
            emirate = EMIRATES.get(slug)
            if not emirate:
                continue
            for s in _stores(page, emirate):
                # No street address is published, so the identity is the name and the emirate.
                # Written out as an address-shaped string because that is what the rest of the
                # project keys on, and because it is the most honest rendering of what is known.
                out.append(StoreRecord(
                    store_code=None, name=s["name"],
                    addr_raw=f"{s['name']}, {emirate}, United Arab Emirates",
                    city=emirate, state=None, zip=None, lat=None, lon=None,
                    trading=True, flags={"emirate": emirate}))
        return out


def probe():
    a = MinisoUAEAdapter()
    recs = a.parse(a.fetch_raw())
    from collections import Counter
    print(f"  {len(recs)} stores")
    for em, n in Counter(r.city for r in recs).most_common():
        print(f"    {em}: {n}")

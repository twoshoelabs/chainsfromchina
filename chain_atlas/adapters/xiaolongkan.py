"""
Xiaolongkan / Shoo Loong Kan Hotpot — https://shooloongkan.us/locations/

A Sichuan hotpot chain from Chengdu, one of mainland China's largest, trading in the US as
"Shoo Loong Kan Hotpot". Unusually for the mainland restaurant chains tracked here, it publishes
its own US locator: a Bricks-builder page whose location cards each carry a city heading, the
address in the first <p>, and a "Coming Soon" ribbon on the ones not yet trading. One request
gets the whole US footprint; no coordinates are published, so addresses are geocoded.

Observed 28 Sep 2026: 8 open (NY x2, NJ x2, TX x2, Chicago, Las Vegas) plus 4 coming soon
(Houston, Bellevue, Costa Mesa, San Diego).

LEGAL: one request per day against the chain's own public page.

FRAGILITY: the card markup is a page-builder's output, not a published API. EXPECTED_MIN turns a
silent parse failure into a loud refusal — zero stores parsed must never be recorded as eight
closures.
"""
import re

from .base import Adapter, StoreRecord
from .. import capture
from ..usaddr import split_tail

ENDPOINT = "https://shooloongkan.us/locations/"
EXPECTED_MIN = 4

# Each location is a <li class="... location__card ...">: an <h3> city heading, the address in
# the first <p> that starts with a house number and contains a 5-digit ZIP, and — only on the
# not-yet-open ones — a "Coming Soon" ribbon div.
_CARD = re.compile(r'location__card(.*?)(?=location__card|</ul>|$)', re.S)
_H3 = re.compile(r'<h3[^>]*>(.*?)</h3>', re.S)
_ADDR = re.compile(r'<p>\s*(\d[^<]*?\d{5}[^<]*?)</p>')
_RIBBON = re.compile(r'ribbon[^>]*>\s*Coming Soon', re.I)


def _stores(page: str) -> list[dict]:
    out = []
    for seg in _CARD.findall(page):
        m = _ADDR.search(seg)
        if not m:
            continue                       # a template/placeholder card carries no address
        addr = re.sub(r'\s+', ' ', m.group(1)).strip().rstrip(',')
        h = _H3.search(seg)
        name = re.sub(r'<[^>]+>', '', h.group(1)).strip() if h else None
        out.append({"name": name, "addr": addr, "trading": not bool(_RIBBON.search(seg))})
    return out


class XiaolongkanAdapter(Adapter):
    chain_id, name, name_zh = "xiaolongkan", "Xiaolongkan", "小龙坎"
    name_us = "Shoo Loong Kan Hotpot"
    aliases = ("Xiao Long Kan", "Shoo Loong Kan")
    parent, format = "Xiaolongkan (小龙坎, Chengdu)", "hotpot"
    closure_n_days = 5
    raw_ext = "html"
    ENABLED = True

    def fetch_raw(self):
        r = capture.fetch(ENDPOINT)
        r.encoding = "utf-8"
        page = r.text
        recs = _stores(page)
        if not recs:
            raise RuntimeError("Shoo Loong Kan locator yielded no stores; the card markup has"
                               " probably changed — refusing the pass")
        if len(recs) < EXPECTED_MIN:
            raise RuntimeError(f"only {len(recs)} Shoo Loong Kan stores (expected >= "
                               f"{EXPECTED_MIN}); refusing a partial footprint")
        return page

    def parse(self, raw) -> list[StoreRecord]:
        page = raw if isinstance(raw, str) else raw.decode("utf-8")
        out = []
        for s in _stores(page):
            city, st, zc = split_tail(s["addr"])
            out.append(StoreRecord(store_code=None, name=s["name"], addr_raw=s["addr"],
                                   city=city, state=st, zip=zc, trading=s["trading"]))
        return out

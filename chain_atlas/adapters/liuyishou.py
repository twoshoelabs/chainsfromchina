"""
Liuyishou Hot Pot — https://www.liuyishouna.com

刘一手火锅 (Liuyishou), a Chongqing hotpot chain founded 2000 and one of the mainland's largest,
trading in North America as "Liuyishou Hot Pot". Its NA site is a Wix build with one page per
city; the address sits in the page hero as "A  <address>". The sitemap (pages-sitemap.xml) lists
both the US cities and the Canadian ones (Toronto, Burnaby, Richmond, Montreal, Ottawa,
Edmonton...), and this adapter is the US market only — the Canadian estate is a separate market
this project does not yet collect, so the US city slugs are listed explicitly rather than crawled
blind. The site's own banner claims ~20 North America outlets, of which the US is the ten below.

Observed 28 Sep 2026: 10 US outlets (MA, CA x3, TX x2, WA, IL, NJ, NY). The /austin page is a
placeholder still showing the Plano TX address, so it is not listed; a real Austin opening will
surface through the lead-discovery routine and get a slug added here.

LEGAL: robots.txt is Allow: /. One request per city page per day.

FRAGILITY: this is Wix hero markup, not an API. Each page must yield exactly one US-state address;
too few and the pass refuses (EXPECTED_MIN) rather than record phantom closures.
"""
import json
import re

from .base import Adapter, StoreRecord
from .. import capture
from ..usaddr import split_tail

BASE = "https://www.liuyishouna.com"
# US city pages from pages-sitemap.xml (28 Sep 2026). Canadian pages are a separate market and
# are deliberately not listed here.
US_SLUGS = ["boston", "sandiego", "sanjose", "houston", "seattle",
            "chicago", "princeton", "dallas", "flushing", "sanmateo"]
EXPECTED_MIN = 6

# An address line in the page hero: a street number, then text, then ", <City>, XX 12345".
# Requiring a US two-letter state and a 5-digit ZIP both filters the JSON/asset noise elsewhere on
# the page and drops any Canadian address (alphanumeric postcode) a page might carry.
_ADDR = re.compile(r"\d{1,6}[^<>{}\"]{3,70}?,\s*[A-Za-z][A-Za-z .'-]+,\s*[A-Z]{2}\s+\d{5}(?:-\d{4})?")


def _address(page: str) -> str | None:
    for cand in _ADDR.findall(page):
        cand = re.sub(r"\s+", " ", cand).strip()
        _, st, _z = split_tail(cand)
        if st:                        # split_tail validates the state against the USPS list
            return cand
    return None


class LiuyishouAdapter(Adapter):
    chain_id, name, name_zh = "liuyishou", "Liuyishou Hot Pot", "刘一手火锅"
    name_us = "Liuyishou Hot Pot"
    aliases = ("Liuyishou", "Liu Yi Shou")
    parent, format = "Liuyishou (刘一手, Chongqing)", "hotpot"
    closure_n_days = 5
    raw_ext = "json"
    ENABLED = True

    def fetch_raw(self):
        found = {}
        for slug in US_SLUGS:
            r = capture.fetch(f"{BASE}/{slug}")
            r.encoding = "utf-8"
            addr = _address(r.text)
            if addr:
                found[slug] = addr
        if len(found) < EXPECTED_MIN:
            raise RuntimeError(f"only {len(found)} Liuyishou US pages yielded an address (expected"
                               f" >= {EXPECTED_MIN}); the Wix hero markup has probably changed —"
                               " refusing the pass")
        return found

    def parse(self, raw) -> list[StoreRecord]:
        d = json.loads(raw) if isinstance(raw, (str, bytes)) else raw
        out, seen = [], set()
        for _slug, addr in d.items():
            city, st, zc = split_tail(addr)
            key = re.sub(r"[^a-z0-9]", "", addr.lower())
            if key in seen:           # e.g. /austin reuses the Plano hero — dedup on the address
                continue
            seen.add(key)
            out.append(StoreRecord(store_code=None, name=city, addr_raw=addr,
                                   city=city, state=st, zip=zc, trading=True))
        return out

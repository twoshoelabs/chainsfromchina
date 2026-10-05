"""
Happy Lamb Hot Pot — https://happylambhotpot.com/locations/

快乐小羊 (Happy Lamb), an Inner-Mongolian-style hot pot chain re-founded in 2017 by Zhang Gang
(张钢), the founder of Little Sheep (小肥羊) — he started over after Yum! Brands acquired Little
Sheep. The first store opened in Baotou, Inner Mongolia in December 2017; it now runs ~100+
restaurants across roughly 11 countries, with North American operations run from a Houston, TX
base. Chinese-origin brand, so in scope; the US estate is what this adapter collects (the Canadian
estate is a separate market at happylambhotpotca.com and is not collected here — one adapter, one
market). The brand's overseas spread (HK, Canada, UK, Australia, Singapore, Japan, …) is carried by
hand in the international register.

SHAPE. The US locations page is a WordPress (Oxygen builder) page whose store list is plain-text
addresses pasted from a Google Sheet, grouped under US state headings. There are no coordinates, so
rows geocode downstream like Luckin's. Addresses read "<street>, <City>, ST ZIP"; two states
(Nevada, Utah) omit the comma before the state, so the address regex tolerates that.

LEGAL: robots.txt disallows only /wp-admin/; /locations/ is allowed. One request per day.

FRAGILITY: this is pasted-sheet HTML, not an API. Each row must parse to a real USPS state + ZIP
(split_tail validates), and the pass refuses below EXPECTED_MIN rather than record phantom closures.
"""
import json
import re

from .base import Adapter, StoreRecord
from .. import capture
from ..usaddr import split_tail

URL = "https://happylambhotpot.com/locations/"
EXPECTED_MIN = 20

# A US street address: number, text, ", City", an OPTIONAL comma, a USPS state, a 5-digit ZIP.
# The optional comma before the state catches the NV/UT rows ("Las Vegas NV 89119"). Requiring the
# two-letter state + ZIP filters the page's CSS/asset noise and drops any non-US (alphanumeric) line.
_ADDR = re.compile(
    r"\d{1,6}[^<>{}\"]{3,70}?,\s*[A-Za-z][A-Za-z .'-]+,?\s*[A-Z]{2}\s+\d{5}(?:-\d{4})?"
)


def _addresses(page: str) -> list[str]:
    import html as _html
    text = _html.unescape(page)
    out, seen = [], set()
    for cand in _ADDR.findall(text):
        cand = re.sub(r"\s+", " ", cand).strip()
        key = re.sub(r"[^a-z0-9]", "", cand.lower())
        if key in seen:
            continue
        _city, st, _zip = split_tail(cand)
        if not st:                     # split_tail validates the state against the USPS list
            continue
        seen.add(key)
        out.append(cand)
    return out


class HappyLambAdapter(Adapter):
    chain_id, name, name_zh = "happylamb", "Happy Lamb Hot Pot", "快乐小羊"
    name_us = "Happy Lamb Hot Pot"
    aliases = ("Happy Lamb", "快樂小羊")
    parent = "Happy Lamb (快乐小羊; founded by Little Sheep's Zhang Gang, Inner Mongolia)"
    format = "hotpot"
    closure_n_days = 5
    raw_ext = "json"
    ENABLED = True

    def fetch_raw(self):
        r = capture.fetch(URL)
        r.encoding = "utf-8"
        addrs = _addresses(r.text)
        if len(addrs) < EXPECTED_MIN:
            raise RuntimeError(
                f"only {len(addrs)} Happy Lamb US addresses parsed (expected >= {EXPECTED_MIN}); "
                "the locations page markup has probably changed — refusing the pass"
            )
        return sorted(addrs)

    def parse(self, raw) -> list[StoreRecord]:
        addrs = json.loads(raw) if isinstance(raw, (str, bytes)) else raw
        out = []
        for addr in addrs:
            city, st, zc = split_tail(addr)
            out.append(StoreRecord(store_code=None, name=city, addr_raw=addr,
                                   city=city, state=st, zip=zc, trading=True))
        return out

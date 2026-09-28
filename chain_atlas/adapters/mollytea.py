"""
Molly Tea — https://usa.mollytea.com

茉莉奶白 (Molly Tea), a mainland Chinese premium milk-tea chain founded in 2021, known for
jasmine-tea-forward "milk white" drinks, trading in the US as "Molly Tea". Its US site runs the
Advanced Store Locator (ASL) WordPress plugin, whose admin-ajax feed returns every store as JSON —
and the site's robots.txt explicitly allows /wp-admin/admin-ajax.php. The feed is GLOBAL (Thailand,
Australia, Indonesia, Singapore, the UK, Canada and the US in one list), so this US adapter keeps
only the rows whose address ends in a US state and a 5-digit ZIP; a store's own `state` field is
blank and its `city` field is unreliable (one US row lists its city as another town), so the
address tail is the single trustworthy signal.

Observed 28 Sep 2026: 17 US outlets (CA, WA, MA, UT, GA x2, TX, NV, NJ x2, IL, PA). A Rockville MD
row carries no state (only a ZIP) and is left out rather than guessed at; a real confirmation will
come through a permit or the lead-discovery routine.

FRAGILITY: a plugin feed, hand-entered and messy (run-together text, full-width punctuation, the
odd typo). The address is tidied for spacing only — never rewritten — and EXPECTED_MIN refuses a
pull that yields too few US rows.
"""
import json
import re

from .base import Adapter, StoreRecord
from .. import capture
from ..usaddr import split_tail

ENDPOINT = ("https://usa.mollytea.com/wp-admin/admin-ajax.php"
            "?action=asl_load_stores&load_all=1&layout=1")
EXPECTED_MIN = 8
_TAG = re.compile(r"<[^>]+>")


# A short list of verified one-off typos in the source feed, corrected so the store can be placed.
# Each is a specific fix confirmed against the real address, not a blanket rewrite.
_FIX = {"E1 Camino Real": "El Camino Real"}   # 605 E El Camino Real, Sunnyvale


def _norm(s: str) -> str:
    """Tidy a feed address enough to parse and geocode: full-width punctuation to ASCII, spaces
    after commas, run-together words split (the feed sometimes drops all spaces, e.g.
    "318UniversityAve, PaloAlto"), a run-together STATE+ZIP separated, and a short list of verified
    source typos corrected. Wording is otherwise preserved."""
    s = _TAG.sub(" ", s or "")
    s = s.replace("，", ", ").replace("　", " ").replace("．", ".").replace("　", " ")
    for bad, good in _FIX.items():
        s = s.replace(bad, good)
    s = re.sub(r",(\S)", r", \1", s)                       # a space after every comma
    s = re.sub(r"([a-z])([A-Z])", r"\1 \2", s)             # "UniversityAve" -> "University Ave"
    s = re.sub(r"(\d)([A-Z][a-z])", r"\1 \2", s)           # "318University" -> "318 University"
    s = re.sub(r"\b([A-Za-z]{2})(\d{5})\b", r"\1 \2", s)   # "CA94301" -> "CA 94301"
    return re.sub(r"\s+", " ", s).strip().strip(".").strip().rstrip(",").strip()


def _us_stores(data) -> list[dict]:
    out = []
    for it in data or []:
        addr = _norm(it.get("street") or "")
        _c, st, _z = split_tail(addr)
        if not st:                        # not a US state+ZIP tail -> a foreign row, or no state
            joined = _norm(", ".join(p for p in (it.get("street"), it.get("city"),
                                                 it.get("state"), it.get("postal_code")) if p))
            _c, st, _z = split_tail(joined)
            if not st:
                continue
            addr = joined
        out.append({"name": (it.get("title") or "").strip(), "addr": addr})
    return out


class MollyTeaAdapter(Adapter):
    chain_id, name, name_zh = "mollytea", "Molly Tea", "茉莉奶白"
    name_us = "Molly Tea"
    aliases = ("Moli Naibai",)
    parent, format = "Molly Tea (茉莉奶白)", "tea"
    closure_n_days = 5
    raw_ext = "json"
    ENABLED = True

    def fetch_raw(self):
        r = capture.fetch(ENDPOINT)
        r.encoding = "utf-8"
        d = r.json()
        if len(_us_stores(d)) < EXPECTED_MIN:
            raise RuntimeError(f"only {len(_us_stores(d))} US Molly Tea rows (expected >= "
                               f"{EXPECTED_MIN}); the ASL feed shape has probably changed —"
                               " refusing the pass")
        return d

    def parse(self, raw) -> list[StoreRecord]:
        d = json.loads(raw) if isinstance(raw, (str, bytes)) else raw
        out = []
        for s in _us_stores(d):
            city, st, zc = split_tail(s["addr"])
            out.append(StoreRecord(store_code=None, name=s["name"], addr_raw=s["addr"],
                                   city=city, state=st, zip=zc, trading=True))
        return out

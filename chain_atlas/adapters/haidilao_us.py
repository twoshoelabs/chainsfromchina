"""
Haidilao US (海底捞) — SUPPLIED, NOT COLLECTED.

Fifteen US restaurants, handed over by the project operator on 21 Sep 2026 from a Haidilao US
store list whose URL was not recorded. Everything else in this archive can show you a gzipped
capture of the page it came from. This cannot, and the distinction is carried in the data rather
than left to a reader's memory: `PROVENANCE = "supplied"`, surfaced by `status`, by the chip on
the map, and in the chain metadata the pages read.

WHY IT IS HERE ANYWAY. Haidilao is the longest-established mainland chain in America — Arcadia,
Los Angeles, 2013 — and the alternative was a greyed-out chip reading "13, no locations
published". Fifteen dated, attributed, address-level records beat that, provided nobody is
allowed to mistake them for a daily series.

WHAT IT ALREADY PROVED. Super Hi International's own country endpoint says 13 US restaurants in
8 cities. This list has 15, across 15 distinct cities. The company's published summary understates
its own estate — which is the first hard corroboration result this project has produced, and it
points the opposite way to the usual worry: the risk was never only that a locator overcounts.

WHAT IT CANNOT DO. It cannot be re-fetched, so it cannot be diffed tomorrow. Re-running writes
identical rows; the diff engine will report no change, and that silence means "nobody looked",
not "nothing moved". The moment the source URL is known this file should be replaced by a real
adapter against it, and this one deleted.

No coordinates are published in the source, so these restaurants are counted and state-mapped —
WA 3, CA 7, AZ 1, IL 1, TX 2, NY 1 — but not drawn, exactly like Luckin's New York estate.
"""
import json
from pathlib import Path

from .base import Adapter, StoreRecord
from ..usaddr import split_tail

DATA = Path(__file__).resolve().parents[2] / "manual" / "haidilao_us.json"
EXPECTED_MIN = 10


class HaidilaoUSAdapter(Adapter):
    chain_id, country = "haidilao", "US"
    name, name_zh = "Haidilao", "海底捞"
    parent, format = "Super Hi International (HKEX 9658 / Nasdaq HDL)", "restaurant"
    register_chain = "haidilao"
    closure_n_days = 7
    ENABLED = True
    PROVENANCE = "supplied"
    KNOWN_COUNT = {"stores": 15, "detail": "supplied 2026-09-21, not re-collected",
                   "as_of": "2026-09-21", "source": "handed over by the project operator"}

    def fetch_raw(self):
        """Reads the supplied file. No network: there is nothing to ask."""
        raw = json.loads(DATA.read_text(encoding="utf-8"))
        recs = self.parse(raw)
        if len(recs) < EXPECTED_MIN:
            raise RuntimeError(f"only {len(recs)} supplied Haidilao US rows"
                               f" (expected >= {EXPECTED_MIN}); refusing a truncated file")
        return raw

    def parse(self, raw) -> list[StoreRecord]:
        d = json.loads(raw) if isinstance(raw, (str, bytes)) else raw
        out = []
        for r in d.get("stores", []):
            addr = (r.get("address") or "").strip()
            city, state, zc = split_tail(addr)
            out.append(StoreRecord(
                store_code=None, name=r.get("name"), addr_raw=addr,
                city=city, state=state, zip=zc, lat=None, lon=None, trading=True,
                flags={"phone": r.get("phone"), "hours": r.get("hours"),
                       "provenance": "supplied"}))
        return out


def probe():
    a = HaidilaoUSAdapter()
    for r in a.parse(a.fetch_raw()):
        print(f"  {r.name[:34]:36} {str(r.city):18} {str(r.state)}")

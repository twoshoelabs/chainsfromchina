"""
Which observations are the same store.

A store's key is the chain's own id when it publishes one — Mixue's integer, Chagee's UUID —
because that survives an address being reworded, a suite number appearing, or a name changing
from "MIXUE-Allston Store" to "MIXUE Brookline". When no id is published (Luckin), the key is
the normalised address, and the normaliser below is therefore load-bearing: every difference
it fails to erase invents a closure and an opening on the same corner.
"""
import re

_SUFFIX = {
    "STREET": "ST", "AVENUE": "AVE", "BOULEVARD": "BLVD", "ROAD": "RD", "DRIVE": "DR",
    "LANE": "LN", "PLACE": "PL", "COURT": "CT", "PARKWAY": "PKWY", "HIGHWAY": "HWY",
    "SQUARE": "SQ", "TERRACE": "TER", "CIRCLE": "CIR", "TURNPIKE": "TPKE", "EXPRESSWAY": "EXPY",
    "SUITE": "STE", "UNIT": "UNIT", "SPACE": "SPC", "BUILDING": "BLDG", "FLOOR": "FL",
    "NORTH": "N", "SOUTH": "S", "EAST": "E", "WEST": "W",
    "NORTHEAST": "NE", "NORTHWEST": "NW", "SOUTHEAST": "SE", "SOUTHWEST": "SW",
}
_ORDINAL = re.compile(r"\b(\d+)(ST|ND|RD|TH)\b")


def norm_addr(addr: str | None) -> str:
    """
    name:      norm_addr
    purpose:   Reduce a US street address to a comparable form.
    arguments: addr — the chain's own string, or None
    returns:   normalised uppercase string ('' for None)
    effects:   None
    other:     Suite and space numbers are KEPT. Two Mixue counters in one mall are two stores,
               and collapsing them would hide exactly the density this project exists to measure.
               '#' becomes 'STE' so that '#249A' and 'Suite 249A' agree.
    """
    if not addr:
        return ""
    s = addr.upper().replace("&", " AND ")
    s = s.replace("#", " STE ")
    s = re.sub(r"[.,;:()]", " ", s)
    s = re.sub(r"[^A-Z0-9\- ]", " ", s)
    s = _ORDINAL.sub(r"\1\2", s)
    out = []
    for w in s.split():
        out.append(_SUFFIX.get(w, w))
    return " ".join(out)


def store_key(rec) -> str:
    """
    name:      store_key
    purpose:   The identity a StoreRecord is filed under.
    arguments: rec (StoreRecord)
    returns:   str
    effects:   None
    other:     Prefixed so a chain that starts publishing ids mid-life does not silently
               re-key its whole estate into what looks like a mass closure and reopening;
               the prefix change is visible in the diff and can be migrated deliberately.
    """
    if rec.store_code:
        return f"id:{rec.store_code}"
    return f"addr:{norm_addr(rec.addr_raw)}"

"""
Shared machinery for the permit watchers, one per jurisdiction.

A watcher reads a city or county's own food-establishment records and produces OPENING (and, where
the data supports it, CLOSING) candidates for a human to verify. It never writes to the archive —
it feeds the review queue, exactly as the Overture pass does, because a machine-found location is a
lead and the base rate of leads in this subject does not earn trust unseen.

WHAT IS SHARED lives here: the brand-name map, whole-term matching (so BISCOTTI is never Cotti),
the street-level cross-reference against what the archive already holds, and the review-CSV shape.
WHAT DIFFERS stays in each source's own file, because jurisdictions do not agree on anything:

  New York   a live Socrata query, a "Pre-permit (Non-operational)" inspection that precedes an
             opening, and coordinates on every row.
  Los Angeles a 24 MB CSV export covering whole years, no pre-permit inspection and no
             coordinates, but a PROGRAM STATUS of ACTIVE/INACTIVE that New York does not publish —
             so LA can suggest a CLOSING and New York cannot.

The signals are therefore not symmetric, and the watchers do not pretend they are. Each reports
the strongest opening signal its source actually carries, and a closing only where the source
states one; absence is never read as a closure, here or anywhere in this project.
"""
import math
import os
import re
import sqlite3
import sys

sys.path.insert(0, os.path.expanduser("~/Projects/chain_atlas"))
from chain_atlas.identity import norm_addr  # noqa: E402

DB = os.path.expanduser("~/chain_atlas_data/chain_atlas.sqlite")

# The trading name as a health department is likely to record it, upper-cased, mapped to the chain
# we would file it under. US aliases matter: a county files the operator's DBA, so TeaByDo not
# ChaPanda, NaiSnow not Nayuki. Matched on whole terms, never as substrings.
TERMS = {
    "MIXUE": "mixue",
    "CHAGEE": "chagee",
    "LUCKIN": "luckin",
    "MINISO": "miniso",
    "HAIDILAO": "haidilao", "HAI DI LAO": "haidilao",
    "POP MART": "popmart", "POPMART": "popmart",
    "HEYTEA": "heytea", "HEY TEA": "heytea",
    "COTTI": "cotti",
    "YANG'S BRAISED": "yangs", "YANGS BRAISED": "yangs", "YANG'S CHICKEN": "yangs",
    "TAI ER": "taier", "TAIER": "taier",
    "TEABYDO": "chabaidao", "TEA BY DO": "chabaidao", "CHAPANDA": "chabaidao", "CHA PANDA": "chabaidao",
    "NAISNOW": "nayuki", "NAIXUE": "nayuki", "NAYUKI": "nayuki",
    "JUEWEI": "juewei",
    "YANGGUOFU": "yangguofu", "YGF": "yangguofu",
    "FISH WITH YOU": "fishwithyou", "YONNY": "fishwithyou",
    "WEI'S FISH": "fishwithyou", "WEIS FISH": "fishwithyou",
}


def classify(name):
    """
    The chains a facility name matches, on WHOLE terms. "COTTI" must not fire on "BISCOTTI" and
    "HEY TEA" must not fire on "THEY TEACH" — the false positive the Overture pass was built to
    reject, in a different dataset.
    """
    up = (name or "").upper()
    return sorted({chain for term, chain in TERMS.items()
                   if re.search(rf"(?<![A-Z]){re.escape(term)}(?![A-Z])", up)})


def street_key(addr):
    """
    A house-number-plus-street fingerprint, with unit and everything after the street dropped, for
    matching across sources that format addresses differently. LA's facility address is
    "227 W VALLEY BLVD" while a sighting reads "227 W Valley Blvd #198C, San Gabriel, CA 91776";
    both reduce to "227 W VALLEY BLVD". Returns "" when there is no leading house number to anchor
    on, so a keyless address never matches another keyless one by accident.
    """
    n = norm_addr((addr or "").split(",")[0]).strip()
    # Cut at the street-type suffix: everything after it is a unit, however it is written
    # ("WAY E-16", "BLVD #2020", "AVE 118B"). This is what makes a mall address from one
    # source line up with the same address from another.
    m = re.search(r"^(.*?\b(?:ST|AVE|BLVD|RD|DR|WAY|LN|PKWY|CT|PL|CIR|HWY|TER|SQ|PLZ|ALY|LOOP|WALK|ROW|PATH|RUN|TRL|XING|CTR)\b)", n)
    if m:
        n = m.group(1)
    else:
        # No recognisable suffix (mall names, plazas): drop a keyword unit or a trailing code.
        n = re.split(r"\b(?:STE|SUITE|UNIT|APT|#|SPC|FL|FLOOR|RM|BLDG)\b", n)[0]
        n = re.sub(r"\s+#?[A-Z]?-?\d+[A-Z]?$", "", n.strip())
    return n.strip() if re.match(r"^\d+[A-Z]?(?:-\d+)?\s+\S", n) else ""


def hav(a, b, c, d):
    if None in (a, b, c, d):
        return 9e9
    R = 6371000
    p1, p2 = math.radians(a), math.radians(c)
    x = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(d - b) / 2) ** 2
    return 2 * R * math.asin(math.sqrt(x))


def known_locations(states):
    """
    Everything the archive already holds or has sighted in the given states, so a watcher can tell
    a new lead from a store we already have. Returns tuples
    (chain, kind, norm_addr, street_key, lat, lon, label).
    """
    where = "(" + " OR ".join("state=?" for _ in states) + ")"
    known = []
    c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    for r in c.execute(f"SELECT chain_id,name,addr_raw,lat,lon FROM stores"
                       f" WHERE {where} AND status!='withdrawn'", tuple(states)):
        known.append((r["chain_id"], "census", norm_addr(r["addr_raw"] or ""),
                      street_key(r["addr_raw"] or ""), r["lat"], r["lon"], r["name"]))
    c.close()
    try:
        from chain_atlas.sightings import geocoded
        from chain_atlas.usaddr import split_tail
        for s in geocoded(cache_only=True):
            _, st, _ = split_tail(s.get("address") or "")
            if st in states:
                known.append((s["chain"], "sighting", norm_addr(s.get("address") or ""),
                              street_key(s.get("address") or ""), s.get("lat"), s.get("lon"),
                              s.get("name")))
    except Exception:                                        # noqa: BLE001
        pass
    return known


def match_known(chain, naddr, skey, lat, lon, known):
    """Same normalised address, same street fingerprint, or within 75 m of a known store."""
    for kchain, kind, kaddr, kkey, klat, klon, label in known:
        if kchain != chain:
            continue
        if naddr and kaddr == naddr:
            return kind, label, 0.0
        if skey and kkey and skey == kkey:
            return kind, label, 0.0
        d = hav(lat, lon, klat, klon)
        if d < 75:
            return kind, label, round(d, 1)
    return None, None, None

"""
Known locations for chains whose complete roster this project cannot get.

THE THIRD SHAPE OF PARTIAL KNOWLEDGE. The archive already distinguishes two:

  a census    a complete roster, re-read daily, which can therefore produce openings and
              closures because absence from it means something.
  a count     Haidilao's parent stating "13 US restaurants in 8 cities" and naming none of
              them (Adapter.KNOWN_COUNT). A number without addresses.

Sightings are the inverse of the second: addresses without completeness. Six Cotti shops are
known; Cotti's US estate is larger and unenumerated.

THEY NEVER ENTER stores, observations or events, and that restriction is the reason the file
exists rather than a limitation of it. Put a partial roster in the census and the day a complete
source is finally read, every store beyond the partial list is recorded as an OPENING that never
happened — growth invented by the act of learning more. `Adapter.fetch_raw` refuses partial
footprints for exactly this reason; a partial footprint arriving by hand is no different.

So they are drawn on the map as open squares, excluded from every count, and labelled as known
locations of a chain that is not counted. A sighting graduates by being deleted: when the real
locator is found, its adapter supersedes this file.
"""
import json
from datetime import date, datetime, timedelta
from pathlib import Path

from .config import TZ

SIGHTINGS_PATH = Path(__file__).resolve().parents[1] / "manual" / "sightings.json"

# Sightings are hand-assembled facts, not a locator, so they cannot go stale on their own — a shop
# in the list can close and nothing here will move. The counterpart to a daily census is a periodic
# human re-check: every group carries a `reviewed` date, and a group not looked at within this many
# days is due for one. Ninety days matches the international register's cadence, for the same reason
# — facts from press and field notes, re-verified on a schedule rather than crawled.
REVIEW_STALE_DAYS = 90


def reviewed_on(group: dict) -> str:
    """The date a group was last re-verified: explicit `reviewed`, else the newest claim it carries."""
    return group.get("reviewed") or group.get("complete_as_of") or group.get("supplied_on")


def stale(d: dict | None = None, days: int = REVIEW_STALE_DAYS) -> list[tuple[str, str, int]]:
    """
    name:      stale
    purpose:   List sighting groups not re-verified within `days`.
    arguments: d (loaded sightings, or None to load), days
    returns:   list of (chain, scope-or-reviewed-date, age_days), oldest first
    effects:   None
    other:     This is the sightings file's only scheduled obligation, and the reason it is safe for
               these locations to sit outside the daily machinery: a human re-reads them on a cadence
               instead. A group with no reviewable date at all is returned with age -1 so it sorts to
               the top and cannot hide.
    """
    d = d or load()
    today = datetime.now(TZ).date()     # NY day (site-wide zone)
    cutoff = today - timedelta(days=days)
    out = []
    for g in d.get("sightings", []):
        r = reviewed_on(g)
        if r is None:
            out.append((g["chain"], "no reviewed date", -1))
            continue
        rd = date.fromisoformat(r)
        if rd < cutoff:
            out.append((g["chain"], g.get("complete_scope") or g.get("scope") or r,
                        (today - rd).days))
    # Undated groups (age -1) are the most urgent — we cannot know when they were last checked —
    # so they sort to the top; the rest follow by descending age (longest overdue first).
    return sorted(out, key=lambda t: (t[2] >= 0, -t[2] if t[2] >= 0 else 0))


def load(path: Path | None = None) -> dict:
    """
    name:      load
    purpose:   Read sightings.json, or return an empty set if there is none.
    arguments: path
    returns:   dict with a "sightings" list
    effects:   None
    other:     Absence is normal and not an error — most chains have no sightings.
    """
    p = path or SIGHTINGS_PATH
    if not p.exists():
        return {"sightings": []}
    return json.loads(p.read_text(encoding="utf-8"))


def geocoded(cache_only: bool = False) -> list[dict]:
    """
    name:      geocoded
    purpose:   Sightings with coordinates attached, ready for the map.
    arguments: cache_only — if True, read coordinates from the cache and never call the geocoder
    returns:   list of {chain, name, address, lat, lon, city, state, source, scope, supplied_on}
    effects:   May geocode uncached US addresses (one request each, cached thereafter).
    other:     An address that will not geocode is still returned, without coordinates, so the
               page can say how many known locations it could not place.
    """
    from .geocode import geocode_one, _load_cache, _save_cache
    from .identity import norm_addr
    from .usaddr import split_tail

    cache = _load_cache()
    out = []
    for group in load().get("sightings", []):
        for loc in group.get("locations", []):
            addr = loc.get("address") or ""
            city, state, _ = split_tail(addr)
            # cache_only means "do not call the geocoder", NOT "pretend nothing is known":
            # export runs in this mode and must still read what was already resolved.
            got = cache.get(norm_addr(addr)) if cache_only else geocode_one(addr, cache)
            lat, lon = (got or {}).get("lat"), (got or {}).get("lon")
            # Narrow public-records exception to Census-only: when the Census geocoder cannot place
            # a permit-sourced address (a redeveloped block, a mall unit), fall back to the
            # coordinates the health-department permit itself carries. Census is still preferred
            # whenever it succeeds; the permit's own lat/lon is government data, not a commercial
            # geocoder, and is the actual inspected location.
            if lat is None and loc.get("lat") is not None and loc.get("lon") is not None:
                lat, lon = loc["lat"], loc["lon"]
            out.append({
                "chain": group["chain"], "name": loc.get("name"), "address": addr,
                "city": city, "state": state,
                "lat": lat, "lon": lon,
                "source": group.get("source"), "scope": group.get("scope"),
                "supplied_on": group.get("supplied_on"),
                # A sighting the operator flagged "maybe" is not the same claim as one they
                # confirmed, and the map should not draw them identically.
                "confidence": loc.get("confidence"), "verified_by": loc.get("verified_by"),
            })
    _save_cache(cache)
    return out


def rosters(path: Path | None = None) -> list[dict]:
    """
    name:      rosters
    purpose:   The sighting groups that carry an explicit, dated completeness claim, turned into
               countable hand-assembled rosters.
    arguments: path
    returns:   list of {chain, complete_as_of, complete_scope, source, count, unconfirmed,
               by_state}
    effects:   None
    other:     THE COMPLETENESS FLAG IS A CLAIM SOMEONE MAKES, NOT ONE THE CODE INFERS. A group
               becomes a count only when a human writes `complete_as_of` into it, taking
               responsibility for the claim that "these are all of them, within this scope, as of
               this date". A group without that field stays a sighting: known locations, no
               total. Only `confirmed` locations are counted; anything flagged `uncertain` is
               reported alongside but never in the number. These counts are HAND-ASSEMBLED and
               NOT MONITORED — they never touch stores/observations/events, so they can never
               produce an opening or a closure. That is the whole point: a dated snapshot the
               reader can see is a snapshot, kept out of the machinery that manufactures change.
    """
    from .usaddr import split_tail

    out = []
    for g in load(path).get("sightings", []):
        if not g.get("complete_as_of"):
            continue
        by_state, count, unconfirmed = {}, 0, 0
        for loc in g.get("locations", []):
            if loc.get("confidence") == "uncertain":
                unconfirmed += 1
                continue
            count += 1
            _, state, _ = split_tail(loc.get("address") or "")
            if state:
                by_state[state] = by_state.get(state, 0) + 1
        out.append({
            "chain": g["chain"], "complete_as_of": g["complete_as_of"],
            "complete_scope": g.get("complete_scope"), "source": g.get("source"),
            "count": count, "unconfirmed": unconfirmed, "by_state": by_state,
        })
    return out

"""
Turn the permit watchers' candidates into recorded sightings — for the BLOCKED chains only, whose
count is otherwise TBD. A municipal health department licensing a food business of a given name at
a given address is real, dated evidence a shop exists there; it is stronger than an aggregator
(a government record, not a crowd guess) and weaker than the chain's own page (which we prefer
when we have it). So these enter as sightings, clearly marked permit-sourced, never as the census.

CONFIDENCE mirrors what the permit says:
  confirmed   the establishment has a routine health inspection — it is operating
  uncertain   only a pre-permit / not-yet-inspected record — licensed, maybe not yet trading
  closing     an INACTIVE / closing candidate — retires the matching sighting if we hold one

It MERGES; it does NOT rebuild from scratch. The permit sightings already in manual/sightings.json
are the accumulated result of every past run and the source of truth. Each CSV only carries the
candidates the watcher currently flags NEW — so replacing the held set with "whatever the CSV lists
today" silently deletes every store that was new on an earlier day (a bug that once wiped 33 real
sightings). Instead this run keeps what is held, ADDS genuinely-new rows, and REMOVES a sighting
only on a positive signal: a closing permit, or a first-party/hand sighting (or a FALSE_MATCHES /
CONFIRMED_ELSEWHERE entry) that supersedes it. A missing or shrunken CSV can no longer erase data.
It still DEDUPES against everything held from first-party sites or filings, so a shop we confirmed
by hand is never demoted to a permit guess. Collected chains are skipped entirely — they have a
census.

Run: .venv/bin/python scripts/permit_sightings.py     (after the watchers have written their CSVs)
"""
import csv
import json
import os
import re
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from permit_common import street_key  # noqa: E402
from chain_atlas.identity import norm_addr  # noqa: E402
sys.path.insert(0, os.path.expanduser("~/Projects/chain_atlas"))
from chain_atlas.adapters import REGISTRY  # noqa: E402
from chain_atlas.usaddr import split_tail  # noqa: E402

DATA = os.path.expanduser("~/chain_atlas_data")
SIGHTINGS = os.path.expanduser("~/Projects/chain_atlas/manual/sightings.json")
# Every review_<id>_permits.csv a watcher has written, so a new metro flows through the moment
# its watcher runs — no list to keep in sync. Friendly names for the ones worth naming; the rest
# fall back to the id.
NAMES = {"nyc": "NYC", "chicago": "Chicago", "seattle": "Seattle/King County",
         "bayarea": "Santa Clara County", "la": "LA County", "austin": "Austin",
         "montgomery": "Montgomery County MD"}
TODAY = "2026-09-23"
MARKER = "permit"   # provenance flag on the groups this script owns

# The chain's US trading name, used to label a permit sighting instead of the raw facility name a
# health department happens to record ("TAIER FISH", "STARLIGHT BILLIARDS / HEY HEY TEA"). The
# chain is already identified by the group; the location just needs a clean, human branch label.
BRAND = {a.chain_id: (getattr(a, "name_us", None) or getattr(a, "name", a.chain_id)) for a in REGISTRY}

# Permit rows that matched a chain's term but are NOT that chain, verified by hand against the
# source. Keyed by (chain, street fingerprint) so a real store is never dropped by accident.
#   heytea @ 6019 4th Ave, Brooklyn — "STARLIGHT BILLIARDS / HEY HEY TEA" (DOHMH CAMIS 50174572),
#   a billiards hall that matched on the words "HEY TEA"; not 喜茶.
#   nayuki @ 233 W 42nd St, Manhattan — a NaiSnow-named health permit with NO operating store:
#   web-verified 29 Sep 2026 (no Google Business listing, no reviews, no press; 234 W 42nd is an
#   unrelated bubble-tea shop). A permit that never became a shop; kept out of the sightings.
FALSE_MATCHES = {("heytea", street_key("6019 4 AVENUE, Brooklyn, NY 11220")),
                 ("nayuki", street_key("233 WEST   42 STREET, Manhattan, NY 10036"))}

# Permit rows confirmed BY HAND under a CORRECTED address (the store is real and open, but the
# permit's street address differs from the one it actually trades at), so the permit candidate is
# dropped in favour of the hand sighting instead of re-appearing as an uncertain duplicate. The
# matching-address confirmations need nothing here — they dedupe on street_key against the hand
# group automatically; only an address the permit got wrong needs listing.
#   heytea @ 2813 Broadway   -> confirmed open at 2815 Broadway (Yelp)
#   heytea @ 42-17 Crescent  -> confirmed open at 42-20 27th St, Long Island City (Yelp/Corner)
CONFIRMED_ELSEWHERE = {("heytea", street_key("2813 BROADWAY, Manhattan, NY 10025")),
                       ("heytea", street_key("42-17 CRESCENT STREET, Queens, NY 11101"))}

_ORD = re.compile(r"(\d)(Th|St|Nd|Rd)\b")


def _city(addr):
    return (split_tail(addr)[0] or "").strip().title()


def _street(addr):
    """A clean, house-number-bearing street label for disambiguating two shops in one city."""
    seg = addr.split(",")[0]
    # Drop a unit tail — but \b so "STE" does not eat the start of "STEVENS", and "#" separately.
    seg = re.sub(r"\s+(?:STE|SUITE|UNIT|RM|FL|APT)\b.*$", "", seg, flags=re.I)
    seg = re.sub(r"\s*#.*$", "", seg)
    seg = re.sub(r"\s+", " ", seg).strip()
    return _ORD.sub(lambda m: m.group(1) + m.group(2).lower(), seg.title())


def branch_name(chain, addr, city_counts):
    """Brand (Locality): the city when a chain has one shop there, else the street."""
    brand = BRAND.get(chain, chain)
    city = _city(addr)
    branch = city if (city and city_counts.get(city, 0) == 1) else (_street(addr) or city)
    return (f"{brand} ({branch})" if branch else brand)[:60]


def blocked_chains():
    return {a.chain_id for a in REGISTRY if a.country == "US" and not a.ENABLED}


def _flt(v):
    try:
        return round(float(v), 6)
    except (TypeError, ValueError):
        return None


def read_candidates():
    """Yield one dict per blocked-chain permit row across every present CSV, carrying the flags the
    merge needs: `is_new` (the watcher had not seen it before) and `is_closing` (the permit is
    going inactive). lat/lon are the health department's OWN coordinates when the source carries
    them, used only as a fallback where the Census geocoder cannot place the address. Unlike the
    old version this does NOT pre-filter to new-and-open rows — the merge in main() needs to see
    known and closing rows too, so it can retire a closed store without discarding the rest."""
    import glob
    blocked = blocked_chains()
    for path in sorted(glob.glob(os.path.join(DATA, "review_*_permits.csv"))):
        jid = os.path.basename(path)[len("review_"):-len("_permits.csv")]
        metro = NAMES.get(jid, jid)
        for r in csv.DictReader(open(path)):
            if r["chain"] not in blocked:
                continue
            name = r.get("name") or r.get("facility_name") or ""
            pre = (r.get("pre_opening") or "").upper() == "YES"
            # Bay Area has no pre-opening field; treat a facility with no real inspection date as
            # pre-opening too (its "first_inspection" is blank or a placeholder).
            fi = r.get("first_inspection") or ""
            not_inspected = fi in ("", "not yet inspected")
            yield {"chain": r["chain"], "metro": metro, "name": name.strip(),
                   "address": r["address"].strip(),
                   "conf": "uncertain" if (pre or not_inspected) else "confirmed", "fi": fi,
                   "lat": _flt(r.get("lat")), "lon": _flt(r.get("lon")),
                   "is_new": r.get("already_known") == "NEW CANDIDATE",
                   "is_closing": (r.get("closing_candidate") or "").upper() == "YES"}


def existing_keys(sightings, chain):
    """Street fingerprints we ALREADY hold for a chain from non-permit sources — never re-add."""
    keys = set()
    for g in sightings["sightings"]:
        if g["chain"] != chain or g.get("provenance") == MARKER:
            continue                                       # skip our own permit groups
        for loc in g.get("locations", []):
            keys.add(street_key(loc.get("address") or "") or norm_addr(loc.get("address") or ""))
    return keys


def main():
    doc = json.load(open(SIGHTINGS, encoding="utf-8"))

    # MERGE, never rebuild-from-scratch. The permit sightings already in the file are the
    # accumulated result of every past run and the SOURCE OF TRUTH — the CSVs only carry whichever
    # candidates the watcher currently flags NEW, so rebuilding from them alone silently deletes
    # every store that was flagged new on some earlier day (the bug that once wiped 33 real
    # sightings). Instead: start from what is held, ADD genuinely-new rows, and REMOVE a sighting
    # only on a positive signal — a closing permit, a first-party/hand sighting that supersedes it,
    # or an explicit FALSE_MATCHES / CONFIRMED_ELSEWHERE entry. Anything the CSVs don't mention is
    # left exactly as it was.
    held: dict = {}                       # (chain, street_key) -> location dict (the live objects)
    for g in doc["sightings"]:
        if g.get("provenance") != MARKER:
            continue
        for loc in g.get("locations", []):
            k = street_key(loc.get("address") or "") or norm_addr(loc.get("address") or "")
            held[(g["chain"], k)] = loc

    hand_cache: dict = {}
    def hand_keys(chain):                 # street fingerprints held from NON-permit sources
        if chain not in hand_cache:
            hand_cache[chain] = existing_keys(doc, chain)
        return hand_cache[chain]

    # Aggregate the CSV rows per (chain, street fingerprint) FIRST. One address can carry several
    # permit records — a stale INACTIVE one beside a fresh ACTIVE one when a shop re-permits — so a
    # closure must not win while an open record for the same address exists. An address is OPEN if
    # ANY record is non-closing; it is closing-only when every record for it is a closure.
    sig: dict = {}
    for r in read_candidates():
        key = (r["chain"], street_key(r["address"]) or norm_addr(r["address"]))
        e = sig.setdefault(key, {"open": False, "closing": False, "new": False, "conf": None,
                                 "address": r["address"], "metro": r["metro"], "name": r["name"],
                                 "fi": "", "lat": None, "lon": None})
        e["new"] = e["new"] or r["is_new"]
        if r["is_closing"]:
            e["closing"] = True
            continue
        e["open"] = True
        if e["conf"] != "confirmed":      # take details from the best (a confirmed) open record
            e.update(conf=r["conf"], address=r["address"], metro=r["metro"], name=r["name"],
                     fi=r["fi"], lat=r["lat"], lon=r["lon"])

    added = removed = upgraded = 0
    for key, e in sig.items():
        chain, k = key
        if key in FALSE_MATCHES or key in CONFIRMED_ELSEWHERE or k in hand_keys(chain):
            if held.pop(key, None):       # not-this-chain, a corrected address, or a first-party /
                removed += 1              # hand sighting — each supersedes the permit one
        elif e["open"]:
            if key in held:
                loc = held[key]           # already ours: keep it, but let a real inspection promote
                if loc.get("confidence") == "uncertain" and e["conf"] == "confirmed":
                    loc["confidence"] = "confirmed"
                    loc["verified_by"] = (f"{e['metro']} health-department permit"
                                          + (f", first inspected {e['fi']}" if e["fi"] else "")
                                          + f" (confirmed {TODAY})")
                    upgraded += 1
            elif e["new"]:                # a genuinely new, open candidate — add it
                loc = {"name": e["name"][:60] or "(permit)", "address": e["address"],
                       "confidence": e["conf"],
                       "verified_by": f"{e['metro']} health-department permit"
                       + (f", first inspected {e['fi']}" if e["fi"] and e["conf"] == "confirmed" else "")
                       + f" ({TODAY})"}
                # Carry the permit's own coordinates as a fallback where Census can't place it.
                if e["lat"] is not None and e["lon"] is not None:
                    loc["lat"], loc["lon"] = e["lat"], e["lon"]
                held[key] = loc
                added += 1
            # open but neither held nor new → a known store we don't carry; leave it alone
        elif e["closing"]:                # closing-only (no open record anywhere for this address)
            if held.pop(key, None):
                removed += 1

    # Rebuild the permit groups FROM `held` (the merged set), one per chain, with names and scope
    # regenerated from the addresses so they stay consistent.
    doc["sightings"] = [g for g in doc["sightings"] if g.get("provenance") != MARKER]
    by_chain: dict = {}
    for (chain, _k), loc in held.items():
        by_chain.setdefault(chain, []).append(loc)

    total = 0
    for chain, locs in sorted(by_chain.items()):
        counts = Counter(c for c in (_city(l["address"]) for l in locs) if c)
        for l in locs:
            l["name"] = branch_name(chain, l["address"], counts)
        c = sum(1 for l in locs if l["confidence"] == "confirmed")
        u = len(locs) - c
        doc["sightings"].append({
            "chain": chain, "supplied_on": TODAY, "provenance": MARKER,
            "source": ("Municipal health-department food-establishment permit records, matched by "
                       "the chain's trading name or a recorded alias, deduped against everything "
                       "already held from first-party sites or filings."),
            "scope": (f"{len(locs)} permit-sourced location(s) ({c} operating, {u} pre-opening "
                      "or not-yet-inspected) for a chain with no first-party US roster. A permit is a "
                      "government record that a food business of this name is licensed at this "
                      "address — stronger than an aggregator, weaker than the chain's own page. Not "
                      "a complete roster; not the census."),
            "locations": locs})
        total += len(locs)
        print(f"  {chain:12} {len(locs):>2} permit sighting(s)  ({c} confirmed, {u} uncertain)")

    json.dump(doc, open(SIGHTINGS, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\nmerge complete: +{added} added, -{removed} removed, {upgraded} promoted; "
          f"{total} permit sighting(s) held across {len(by_chain)} chain(s).")


if __name__ == "__main__":
    main()

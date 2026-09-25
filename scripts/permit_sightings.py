"""
Turn the permit watchers' candidates into recorded sightings — for the BLOCKED chains only, whose
count is otherwise TBD. A municipal health department licensing a food business of a given name at
a given address is real, dated evidence a shop exists there; it is stronger than an aggregator
(a government record, not a crowd guess) and weaker than the chain's own page (which we prefer
when we have it). So these enter as sightings, clearly marked permit-sourced, never as the census.

CONFIDENCE mirrors what the permit says:
  confirmed   the establishment has a routine health inspection — it is operating
  uncertain   only a pre-permit / not-yet-inspected record — licensed, maybe not yet trading
  (skipped)   an INACTIVE / closing candidate — not added; a closure is a lead, not a sighting

It is IDEMPOTENT and self-correcting: it rebuilds the permit-sourced groups from the current CSVs
each run (replacing the previous ones), and it DEDUPES every candidate against the sightings we
already hold from first-party sites or filings, so a shop we confirmed by hand is never demoted to
a permit guess. Collected chains are skipped entirely — they have a census.

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
FALSE_MATCHES = {("heytea", street_key("6019 4 AVENUE, Brooklyn, NY 11220"))}

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


def read_candidates():
    """Yield (chain, metro, name, address, confidence) for every NEW blocked-chain permit row."""
    import glob
    blocked = blocked_chains()
    for path in sorted(glob.glob(os.path.join(DATA, "review_*_permits.csv"))):
        jid = os.path.basename(path)[len("review_"):-len("_permits.csv")]
        metro = NAMES.get(jid, jid)
        for r in csv.DictReader(open(path)):
            if r["chain"] not in blocked or r.get("already_known") != "NEW CANDIDATE":
                continue
            if (r.get("closing_candidate") or "").upper() == "YES":
                continue                                   # a closure is a lead, not a sighting
            name = r.get("name") or r.get("facility_name") or ""
            pre = (r.get("pre_opening") or "").upper() == "YES"
            # Bay Area has no pre-opening field; treat a facility with no real inspection date as
            # pre-opening too (its "first_inspection" is blank or a placeholder).
            fi = r.get("first_inspection") or ""
            not_inspected = fi in ("", "not yet inspected")
            conf = "uncertain" if (pre or not_inspected) else "confirmed"
            yield r["chain"], metro, name.strip(), r["address"].strip(), conf, fi


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
    # Drop the permit groups from a previous run; we are about to rebuild them.
    doc["sightings"] = [g for g in doc["sightings"] if g.get("provenance") != MARKER]

    by_chain = {}
    for chain, metro, name, addr, conf, fi in read_candidates():
        by_chain.setdefault(chain, {"locs": [], "seen": set(), "held": existing_keys(doc, chain)})
        rec = by_chain[chain]
        k = street_key(addr) or norm_addr(addr)
        if (chain, k) in FALSE_MATCHES:
            continue                                       # a verified not-this-chain permit row
        if k in rec["held"] or k in rec["seen"]:
            continue                                       # already ours, or a dupe across metros
        rec["seen"].add(k)
        rec["locs"].append({
            "_chain": chain, "name": name[:60] or "(permit)", "address": addr, "confidence": conf,
            "verified_by": f"{metro} health-department permit"
            + (f", first inspected {fi}" if fi and conf == "confirmed" else "") + f" ({TODAY})"})

    # Name every permit location Brand (Locality), disambiguating same-city shops by street.
    for rec in by_chain.values():
        counts = Counter(c for c in (_city(l["address"]) for l in rec["locs"]) if c)
        for l in rec["locs"]:
            l["name"] = branch_name(l["_chain"], l["address"], counts)

    added = 0
    for chain, rec in sorted(by_chain.items()):
        if not rec["locs"]:
            continue
        c = sum(1 for l in rec["locs"] if l["confidence"] == "confirmed")
        u = len(rec["locs"]) - c
        doc["sightings"].append({
            "chain": chain, "supplied_on": TODAY, "provenance": MARKER,
            "source": ("Municipal health-department food-establishment permit records, matched by "
                       "the chain's trading name or a recorded alias, deduped against everything "
                       "already held from first-party sites or filings."),
            "scope": (f"{len(rec['locs'])} permit-sourced location(s) ({c} operating, {u} pre-opening "
                      "or not-yet-inspected) for a chain with no first-party US roster. A permit is a "
                      "government record that a food business of this name is licensed at this "
                      "address — stronger than an aggregator, weaker than the chain's own page. Not "
                      "a complete roster; not the census."),
            "locations": rec["locs"]})
        added += len(rec["locs"])
        print(f"  {chain:12} +{len(rec['locs']):>2} permit sighting(s)  ({c} confirmed, {u} uncertain)")

    for g in doc["sightings"]:
        for l in g.get("locations", []):
            l.pop("_chain", None)
    json.dump(doc, open(SIGHTINGS, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\n{added} permit-sourced sighting(s) written across {sum(1 for r in by_chain.values() if r['locs'])} chain(s).")


if __name__ == "__main__":
    main()

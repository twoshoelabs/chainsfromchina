"""
A watcher, not a source. Reads NYC's open restaurant-inspection data for the chains this project
follows, and produces a list of OPENING and change CANDIDATES for a human to verify. Nothing it
finds enters stores, observations or events — it feeds the same review queue the Overture pass
does, and for the same reason: a machine-found location is a lead, and the base rate of leads in
this subject is not high enough to trust one unseen.

WHY THIS SOURCE, FOR THESE CHAINS. Four of them (Cotti, HEYTEA, Tai Er, Yang's) publish no US
roster this project can read, so the archive cannot see them open or close a store. A city health
department can. Every food business in New York is inspected, and a NEW one is given a
"Pre-permit (Non-operational) / Initial Inspection" BEFORE it opens — which is the closest thing
to an authoritative opening signal this project has found for a chain it cannot scrape. The date
comes with it. New York is one jurisdiction of thousands, but this expansion is concentrated: the
metros where these chains cluster are countable on two hands, and each is one dataset like this.

WHAT IT CANNOT DO is tell you a store CLOSED. Absence from an inspection feed is not a closure any
more than absence from Overture is — a restaurant between inspections looks identical to one that
shut. The only clean closing signal here is a permit that lapses or is revoked, and that needs the
licensing dataset, not this one. So this watcher reports openings well and says nothing it cannot
back about closings, which is the same discipline the census applies to itself.

Usage: .venv/bin/python scripts/nyc_permits.py            (writes a CSV to the data directory)
       SOCRATA_APP_TOKEN=... raises the rate limit; it runs fine without one.
"""
import csv
import math
import os
import sys
import urllib.parse
import urllib.request
import re
from collections import defaultdict

sys.path.insert(0, os.path.expanduser("~/Projects/chain_atlas"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from permit_common import TERMS, classify, street_key, known_locations, match_known  # noqa: E402
from chain_atlas.identity import norm_addr  # noqa: E402

ENDPOINT = "https://data.cityofnewyork.us/resource/43nn-pn8j.json"
OUT = os.path.expanduser("~/chain_atlas_data/review_nyc_permits.csv")
DB = os.path.expanduser("~/chain_atlas_data/chain_atlas.sqlite")

# NYC files the trading name in `dba`; the shared brand map covers the US aliases.
DBA_TERMS = TERMS
PREOPEN = "pre-permit (non-operational)"     # the inspection type that precedes an opening


def _get(where):
    q = urllib.parse.urlencode({
        "$select": "camis,dba,boro,building,street,zipcode,cuisine_description,"
                   "latitude,longitude,inspection_date,inspection_type,record_date",
        "$where": where, "$limit": "5000", "$order": "inspection_date DESC"})
    req = urllib.request.Request(f"{ENDPOINT}?{q}")
    tok = os.environ.get("SOCRATA_APP_TOKEN")
    if tok:
        req.add_header("X-App-Token", tok)
    import json
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode())








def main():
    esc = lambda t: t.replace("'", "''")
    where = " OR ".join(f"upper(dba) like '%{esc(t)}%'" for t in DBA_TERMS)
    rows = _get(where)
    print(f"raw inspection rows returned: {len(rows)}")

    # Reduce many inspection rows to one record per establishment (camis).
    est = {}
    for r in rows:
        cam = r.get("camis")
        if not cam:
            continue
        e = est.setdefault(cam, {"insp_types": set(), "insp_dates": [], "record_dates": []})
        e.update({k: r.get(k) for k in ("dba", "boro", "building", "street", "zipcode",
                                        "cuisine_description", "latitude", "longitude")})
        if r.get("inspection_type"):
            e["insp_types"].add(r["inspection_type"])
        if r.get("inspection_date"):
            e["insp_dates"].append(r["inspection_date"][:10])
        if r.get("record_date"):
            e["record_dates"].append(r["record_date"][:10])


    known = known_locations(("NY",))
    out = []
    for cam, e in est.items():
        chains = classify(e.get("dba"))
        if not chains:
            continue                              # DBA matched the LIKE but not a whole term
        chain = chains[0]
        addr = f"{e.get('building','')} {e.get('street','')}, {e.get('boro','')}, NY {e.get('zipcode','')}".strip()
        lat = float(e["latitude"]) if e.get("latitude") else None
        lon = float(e["longitude"]) if e.get("longitude") else None
        kind, label, dist = match_known(chain, norm_addr(addr), street_key(addr), lat, lon, known)
        real = sorted(d for d in e["insp_dates"] if d != "1900-01-01")
        not_yet_inspected = bool(e["insp_dates"]) and not real
        # A pre-permit inspection type, OR an establishment in the register with no
        # real inspection yet, both mean the same thing: not open yet.
        pre = any(PREOPEN in t.lower() for t in e["insp_types"]) or not_yet_inspected
        first_seen = real[0] if real else ("not yet inspected" if not_yet_inspected else "")
        last_seen = real[-1] if real else ""
        out.append({
            "chain": chain, "camis": cam, "dba": e.get("dba"), "address": addr,
            "lat": lat, "lon": lon, "cuisine": e.get("cuisine_description"),
            "first_inspection": first_seen, "last_inspection": last_seen,
            "pre_opening_inspection": "YES" if pre else "",
            "inspection_types": " | ".join(sorted(e["insp_types"])),
            "already_known": kind or "NEW CANDIDATE",
            "matches": label or "", "metres_from_known": dist if dist is not None else "",
        })

    out.sort(key=lambda r: (r["already_known"] != "NEW CANDIDATE", r["chain"], r["first_inspection"]))
    if out:
        with open(OUT, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
            w.writeheader()
            w.writerows(out)

    new = [r for r in out if r["already_known"] == "NEW CANDIDATE"]
    preo = [r for r in new if r["pre_opening_inspection"]]
    print(f"{len(est)} establishments matched; {len(out)} filed to chains")
    print(f"  {len(out) - len(new)} already in our census/sightings")
    print(f"  {len(new)} NEW candidate(s) to verify — of which {len(preo)} carry a pre-opening inspection")
    for r in new:
        flag = " [PRE-OPENING]" if r["pre_opening_inspection"] else ""
        print(f"    {r['chain']:<9} {r['dba'][:26]:<28} {r['address'][:42]:<44} first seen {r['first_inspection']}{flag}")
    print(f"-> {OUT}" if out else "(nothing matched; no file written)")


if __name__ == "__main__":
    main()

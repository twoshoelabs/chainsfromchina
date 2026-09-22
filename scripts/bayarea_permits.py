"""
Bay Area permit watcher — built to catch Tai Er, and it does: TAIER FISH, 2855 Stevens Creek Blvd,
San Jose, one inspection dated 9 Apr 2026. The Bay Area is the fragmented case. There is no county
that covers it the way LA County covers the San Gabriel Valley; each county runs its own health
department, and their open data is wildly uneven:

  * Santa Clara County (data.sccgov.org) is LIVE — inspections current to within days — and
    GEOCODED. It covers San Jose, Milpitas, Cupertino, Sunnyvale, Santa Clara and Mountain View,
    which is where nearly all of the Bay Area's mainland-chain density actually is. This is the
    source the watcher reads.
  * San Mateo County's food-inspection feed is frozen at January 2022 — it predates this whole
    wave of expansion and is useless for it. The Peninsula is therefore a KNOWN GAP, named here so
    it is not mistaken for an absence of stores.
  * San Francisco's LIVES feed currently lists none of these chains.

So "the Bay Area" here means the South Bay, honestly scoped. Santa Clara's schema is two tables
joined on a business id: a business list with coordinates, and an inspection log. There is no
pre-permit inspection and no program status, so the opening proxy is the earliest inspection date
and there is NO closing signal — absence is not a closure, exactly as everywhere else. Coordinates
are present, so cross-reference is by proximity as well as street fingerprint.

Like every watcher, it produces CANDIDATES for a human and never writes to the archive.

Usage: .venv/bin/python scripts/bayarea_permits.py       (writes a CSV to the data directory)
"""
import csv
import json
import os
import sys
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from permit_common import TERMS, classify, street_key, known_locations, match_known  # noqa: E402
sys.path.insert(0, os.path.expanduser("~/Projects/chain_atlas"))
from chain_atlas.identity import norm_addr  # noqa: E402

BIZ = "https://data.sccgov.org/resource/vuw7-jmjk.json"      # business list, with coordinates
INSP = "https://data.sccgov.org/resource/2u2d-8jej.json"     # inspection log, by business_id
OUT = os.path.expanduser("~/chain_atlas_data/review_bayarea_permits.csv")


def _get(url, params):
    q = urllib.parse.urlencode(params)
    req = urllib.request.Request(f"{url}?{q}")
    tok = os.environ.get("SOCRATA_APP_TOKEN")
    if tok:
        req.add_header("X-App-Token", tok)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode())


def parse_date(s):
    """YYYYMMDD -> ISO."""
    s = (s or "").strip()
    return f"{s[0:4]}-{s[4:6]}-{s[6:8]}" if len(s) == 8 and s.isdigit() else ""


def main():
    # One query for the business list: every chain term OR'd together, then tightened by
    # whole-term matching so BISCOTTI and CHUN YANG TEA fall out.
    esc = lambda t: t.replace("'", "''")
    where = " OR ".join(f"upper(name) like '%{esc(t)}%'" for t in TERMS)
    biz = _get(BIZ, {"$where": where, "$limit": "500"})
    biz = [b for b in biz if classify(b.get("name"))]
    print(f"{len(biz)} Santa Clara business(es) matched a chain")

    # One query for all their inspections, to date each opening.
    ids = [b["business_id"] for b in biz if b.get("business_id")]
    insp = {}
    if ids:
        inlist = ",".join(f"'{esc(i)}'" for i in ids)
        for r in _get(INSP, {"$where": f"business_id in ({inlist})", "$limit": "5000",
                             "$order": "date"}):
            insp.setdefault(r["business_id"], []).append(parse_date(r.get("date")))

    known = known_locations(("CA",))
    out = []
    for b in biz:
        chain = classify(b["name"])[0]
        addr = f"{(b.get('address') or '').strip()}, {(b.get('city') or '').title()}, CA {b.get('postal_code') or ''}".strip()
        lat = float(b["latitude"]) if b.get("latitude") else None
        lon = float(b["longitude"]) if b.get("longitude") else None
        kind, label, dist = match_known(chain, norm_addr(addr), street_key(b.get("address") or ""),
                                        lat, lon, known)
        ds = sorted(d for d in insp.get(b["business_id"], []) if d)
        out.append({
            "chain": chain, "business_id": b["business_id"], "name": b.get("name"),
            "address": addr, "city": b.get("city"), "lat": lat, "lon": lon,
            "first_inspection": ds[0] if ds else "", "last_inspection": ds[-1] if ds else "",
            "inspections": len(ds),
            "already_known": kind or "NEW CANDIDATE", "matches": label or "",
            "metres_from_known": dist if dist is not None else "",
        })

    out.sort(key=lambda r: (r["already_known"] != "NEW CANDIDATE", r["chain"], r["first_inspection"]))
    if out:
        with open(OUT, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(out[0].keys()))
            w.writeheader()
            w.writerows(out)

    new = [r for r in out if r["already_known"] == "NEW CANDIDATE"]
    print(f"  {len(out) - len(new)} already in our census/sightings")
    print(f"  {len(new)} NEW candidate(s) to verify")
    for r in new:
        print(f"    {r['chain']:<9} {(r['name'] or '')[:24]:<26} {r['address'][:44]:<46} first {r['first_inspection']}")
    print(f"-> {OUT}" if out else "(nothing matched; no file written)")


if __name__ == "__main__":
    main()

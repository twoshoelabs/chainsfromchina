"""
LA County permit watcher — the San Gabriel Valley is to this project what Flushing is: the densest
concentration of these chains in America, and Cotti, HEYTEA, NaiSnow and Yang's all trade there
without a roster this project can read.

THE SOURCE IS A BULK CSV, NOT A QUERY. LA County publishes "Environmental Health Restaurant and
Market Inspections" as a whole-years CSV export on its ArcGIS hub, ~24 MB, no coordinates. It is
downloaded once and filtered locally. It differs from New York's feed in three ways that change
what the watcher can honestly say:

  * NO PRE-PERMIT INSPECTION. LA records only ROUTINE and OWNER INITIATED inspections, so there is
    no signal that precedes an opening. The opening proxy is the EARLIEST inspection date on a
    facility — later than a true opening, but the best the data carries.
  * NO COORDINATES. Cross-referencing is by street fingerprint (house number + street, unit
    dropped), which is why 227 W Valley Blvd matches our San Gabriel Cotti sighting despite the
    suite differing.
  * IT HAS PROGRAM STATUS. Every facility is ACTIVE or INACTIVE — a CLOSING signal New York does
    not publish. An INACTIVE record for a chain we hold is a closing CANDIDATE, still for a human
    to confirm, never an automatic closure.

FRESHNESS IS THE CATCH. The export covers whole calendar years and lags the present by months, so
this watcher is for reconstructing a region's footprint and its recent closings, not for catching
an opening the week it happens the way New York's live feed can. The coverage window is printed
every run so the staleness is never hidden.

Usage: .venv/bin/python scripts/la_permits.py            (downloads once to the data dir, caches)
       Delete the cached CSV to force a fresh download.
"""
import csv
import os
import sys
import urllib.request
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from permit_common import classify, street_key, known_locations, match_known  # noqa: E402
sys.path.insert(0, os.path.expanduser("~/Projects/chain_atlas"))
from chain_atlas.identity import norm_addr  # noqa: E402

# The CSV export item on LA County's ArcGIS hub. `/data` streams the file itself.
ITEM = "19b6607ac82c4512b10811870975dbdc"
SRC = f"https://www.arcgis.com/sharing/rest/content/items/{ITEM}/data"
CACHE = os.path.expanduser("~/chain_atlas_data/la_county_inspections.csv")
OUT = os.path.expanduser("~/chain_atlas_data/review_la_permits.csv")

# The San Gabriel Valley and the rest of LA County are one dataset; there is no need to filter by
# city, but naming the SGV cities lets the summary say how much of the yield is from there.
SGV = {"SAN GABRIEL", "ALHAMBRA", "MONTEREY PARK", "ARCADIA", "ROWLAND HEIGHTS", "SAN MARINO",
       "TEMPLE CITY", "ROSEMEAD", "EL MONTE", "HACIENDA HEIGHTS", "WALNUT", "DIAMOND BAR",
       "WEST COVINA", "COVINA", "CITY OF INDUSTRY", "DUARTE", "MONROVIA", "SIERRA MADRE"}


def ensure_csv():
    if not os.path.exists(CACHE):
        print(f"downloading LA County inspections CSV -> {CACHE} (~24 MB, once)")
        urllib.request.urlretrieve(SRC, CACHE)
    return CACHE


def parse_date(s):
    """MM/DD/YYYY -> ISO, so dates sort. Returns '' on anything unexpected."""
    p = [x.strip() for x in (s or "").strip().split("/")]
    if len(p) == 3 and all(x.isdigit() for x in p):
        return f"{p[2]}-{int(p[0]):02d}-{int(p[1]):02d}"
    return ""


def main():
    path = ensure_csv()
    rows = list(csv.DictReader(open(path, encoding="utf-8", errors="replace")))
    all_dates = sorted(parse_date(r["ACTIVITY DATE"]) for r in rows if parse_date(r["ACTIVITY DATE"]))
    window = f"{all_dates[0]} to {all_dates[-1]}" if all_dates else "unknown"
    print(f"{len(rows)} inspection rows; coverage window {window}")

    # One record per facility, keeping the earliest/latest inspection and the last program status.
    fac = {}
    for r in rows:
        chains = classify(r.get("FACILITY NAME"))
        if not chains:
            continue
        fid = r.get("FACILITY ID") or r.get("RECORD ID")
        f = fac.setdefault(fid, {"dates": [], "status": ""})
        f.update({k: r.get(k) for k in ("FACILITY NAME", "FACILITY ADDRESS", "FACILITY CITY",
                                        "FACILITY ZIP", "PROGRAM STATUS", "PE DESCRIPTION")})
        d = parse_date(r["ACTIVITY DATE"])
        if d:
            f["dates"].append(d)
        f["chain"] = chains[0]

    known = known_locations(("CA",))
    out = []
    for fid, f in fac.items():
        chain = f["chain"]
        addr = f"{f.get('FACILITY ADDRESS','').strip()}, {f.get('FACILITY CITY','').title()}, CA {f.get('FACILITY ZIP','')}".strip()
        skey = street_key(f.get("FACILITY ADDRESS", ""))
        kind, label, dist = match_known(chain, norm_addr(addr), skey, None, None, known)
        ds = sorted(f["dates"])
        status = (f.get("PROGRAM STATUS") or "").upper()
        out.append({
            "chain": chain, "facility_id": fid, "facility_name": f.get("FACILITY NAME"),
            "address": addr, "city": f.get("FACILITY CITY"),
            "in_sgv": "YES" if (f.get("FACILITY CITY") or "").upper() in SGV else "",
            "program_status": status,
            "first_inspection": ds[0] if ds else "", "last_inspection": ds[-1] if ds else "",
            "closing_candidate": "YES" if status == "INACTIVE" else "",
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
    closing = [r for r in out if r["closing_candidate"]]
    sgv = [r for r in new if r["in_sgv"]]
    print(f"{len(fac)} facilities matched to chains; {len(out)} filed")
    print(f"  {len(out) - len(new)} already in our census/sightings")
    print(f"  {len(new)} NEW candidate(s) to verify — {len(sgv)} in the San Gabriel Valley")
    print(f"  {len(closing)} INACTIVE record(s) — closing candidate(s) for a human to confirm")
    for r in new:
        tags = (" [SGV]" if r["in_sgv"] else "") + (" [INACTIVE]" if r["closing_candidate"] else "")
        print(f"    {r['chain']:<9} {(r['facility_name'] or '')[:26]:<28} {r['address'][:46]:<48} {r['first_inspection']}{tags}")
    print(f"-> {OUT}" if out else "(nothing matched; no file written)")


if __name__ == "__main__":
    main()

"""
The national permit watcher. It reads scripts/jurisdictions.json and runs every Socrata source in
it — New York, Chicago, Seattle today, and whatever else is added as a row tomorrow. This is the
answer to chasing metros one at a time: a new city is a registry entry with its column names, not
a new program.

It works because most US city and county open data is Socrata, and the columns differ only in
name. The registry maps each source's columns to the same handful of roles (name, address, date,
inspection type, a closing signal where one exists), and this driver does the rest: the whole-term
name match that keeps BISCOTTI from being Cotti, the reduction to one record per establishment, the
opening proxy (earliest inspection, flagged pre-opening when the type says so), the closing
candidate (only where the source states one — never inferred from absence), and the cross-reference
against what the archive already holds. Every row is a CANDIDATE for a human; nothing is written to
the archive.

Sources whose shape does not fit one Socrata query keep their own scripts: Santa Clara (a two-table
join) and LA County (a bulk CSV). Honolulu is robots-excluded. All are documented in the README.

Usage: .venv/bin/python scripts/watch.py [jurisdiction_id ...]   (default: all in the registry)
       SOCRATA_APP_TOKEN=... raises the rate limit; runs fine without one.
"""
import csv
import json
import os
import re
import sys
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from permit_common import classify, street_key, known_locations, match_known  # noqa: E402
sys.path.insert(0, os.path.expanduser("~/Projects/chain_atlas"))
from chain_atlas.identity import norm_addr  # noqa: E402

REGISTRY = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jurisdictions.json")
OUT_DIR = os.path.expanduser("~/chain_atlas_data")
PREOPEN_RE = re.compile(r"pre-permit|pre-opening|non-operational", re.I)


def socrata(domain, resource, params):
    q = urllib.parse.urlencode(params)
    req = urllib.request.Request(f"https://{domain}/resource/{resource}.json?{q}")
    tok = os.environ.get("SOCRATA_APP_TOKEN")
    if tok:
        req.add_header("X-App-Token", tok)
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.loads(r.read().decode())


def iso(s):
    """Accept ISO timestamps and YYYYMMDD; return YYYY-MM-DD or ''."""
    s = (s or "").strip()
    if "T" in s or "-" in s:
        return s[:10]
    return f"{s[0:4]}-{s[4:6]}-{s[6:8]}" if len(s) == 8 and s.isdigit() else ""


def run_socrata(j):
    from permit_common import TERMS
    esc = lambda t: t.replace("'", "''")
    nf = j["name_field"]
    where = " OR ".join(f"upper({nf}) like '%{esc(t)}%'" for t in TERMS)
    rows = socrata(j["domain"], j["resource"], {"$where": where, "$limit": "10000"})

    # Reduce to one record per establishment.
    est = {}
    for r in rows:
        if not classify(r.get(nf)):
            continue
        key = r.get(j.get("id_field")) or "|".join(str(r.get(f, "")) for f in j["addr_fields"])
        e = est.setdefault(key, {"dates": [], "types": set(), "closed": False, "row": r})
        d = iso(r.get(j["date_field"]))
        if d:
            e["dates"].append(d)
        if j.get("type_field") and r.get(j["type_field"]):
            e["types"].add(r[j["type_field"]])
        if j.get("closed_bool_field") and str(r.get(j["closed_bool_field"])).lower() in ("true", "1", "yes"):
            e["closed"] = True
        if j.get("closed_field") and j.get("closed_re") and re.search(j["closed_re"], r.get(j["closed_field"]) or "", re.I):
            e["closed"] = True

    known = known_locations(tuple(j["states"]))
    out = []
    for key, e in est.items():
        r = e["row"]
        chain = classify(r.get(nf))[0]
        street = " ".join(str(r.get(f, "")).strip() for f in j["addr_fields"]).strip()
        # Some feeds (Austin) put the whole address — city, state, ZIP — in one field.
        addr = street if j.get("addr_full") else \
            f"{street}, {r.get(j.get('city_field'), '')}, {j['state']} {r.get(j.get('zip_field'), '')}".strip()
        lat = float(r[j["lat_field"]]) if j.get("lat_field") and r.get(j["lat_field"]) else None
        lon = float(r[j["lon_field"]]) if j.get("lon_field") and r.get(j["lon_field"]) else None
        kind, label, dist = match_known(chain, norm_addr(addr), street_key(street), lat, lon, known)
        real = sorted(d for d in e["dates"] if d and d != "1900-01-01")
        not_yet = bool(e["dates"]) and not real
        # "Pre-opening" means still pre-opening NOW, not "ever had a pre-permit inspection":
        # every restaurant gets a pre-permit inspection when it opens, so that alone flags
        # everything. The real signal is an establishment with no operating inspection yet —
        # every type it has is a pre-permit/non-operational one, or it is not inspected yet.
        operating = [t for t in e["types"] if not PREOPEN_RE.search(t)]
        pre = not_yet or (bool(e["types"]) and not operating)
        out.append({
            "jurisdiction": j["id"], "chain": chain, "name": r.get(nf), "address": addr,
            "lat": lat, "lon": lon,
            "first_inspection": real[0] if real else ("not yet inspected" if not_yet else ""),
            "last_inspection": real[-1] if real else "",
            "pre_opening": "YES" if pre else "",
            "closing_candidate": "YES" if e["closed"] else "",
            "already_known": kind or "NEW CANDIDATE", "matches": label or "",
            "metres_from_known": dist if dist is not None else "",
        })
    return out


def main(which):
    reg = json.load(open(REGISTRY))["jurisdictions"]
    if which:
        reg = [j for j in reg if j["id"] in which]
    grand_new = 0
    for j in reg:
        if j["platform"] != "socrata":
            continue
        try:
            out = run_socrata(j)
        except Exception as ex:                                  # noqa: BLE001
            print(f"{j['id']:<9} FAILED: {type(ex).__name__}: {str(ex)[:80]}")
            continue
        out.sort(key=lambda r: (r["already_known"] != "NEW CANDIDATE", r["chain"], r["first_inspection"]))
        new = [r for r in out if r["already_known"] == "NEW CANDIDATE"]
        pre = [r for r in new if r["pre_opening"]]
        clo = [r for r in out if r["closing_candidate"]]
        grand_new += len(new)
        path = os.path.join(OUT_DIR, f"review_{j['id']}_permits.csv")
        if out:
            with open(path, "w", newline="") as fh:
                w = csv.DictWriter(fh, fieldnames=list(out[0].keys()))
                w.writeheader(); w.writerows(out)
        print(f"{j['id']:<9} {j['name']:<22} {len(out):>3} filed  {len(out)-len(new):>3} known  "
              f"{len(new):>3} new ({len(pre)} pre-opening, {len(clo)} closing)  -> {os.path.basename(path)}")
    print(f"\n{grand_new} new candidate(s) across {len(reg)} jurisdiction(s) to verify.")


if __name__ == "__main__":
    main(sys.argv[1:])

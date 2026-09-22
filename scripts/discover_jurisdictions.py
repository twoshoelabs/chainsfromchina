"""
Find the metros, instead of chasing them. Most US city and county open data is Socrata, and
Socrata runs one national catalog across every domain. This asks it for food-inspection datasets
everywhere at once and prints a worklist: what exists, where, how fresh, and whether it is already
in scripts/jurisdictions.json. Promoting a metro is then a matter of confirming its columns and
adding a registry row — the discovery is done for you.

It does not touch the archive and it does not add anything to the registry; a human reads the
worklist and decides. Coverage note: this sees Socrata (the majority), not ArcGIS hubs, bulk-CSV
counties like LA, or vendor portals like Hawaii's — those still need finding by hand, and the
README records the ones already found.

Usage: .venv/bin/python scripts/discover_jurisdictions.py     (writes a CSV to the data directory)
"""
import csv
import json
import os
import sys
import urllib.parse
import urllib.request

CATALOG = "http://api.us.socrata.com/api/catalog/v1"
QUERIES = ["restaurant inspection", "food establishment inspection", "food facility inspection"]
OUT = os.path.expanduser("~/chain_atlas_data/discovered_jurisdictions.csv")
REGISTRY = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jurisdictions.json")

# Domains that are not US local health departments, so a "food inspection" hit there is noise.
SKIP = ("demo.socrata.com", "lehman.cuny.edu")


def catalog(q):
    params = {"q": q, "only": "dataset", "limit": "200"}
    req = urllib.request.Request(f"{CATALOG}?{urllib.parse.urlencode(params)}")
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode()).get("results", [])


def main():
    have = {(j["domain"], j["resource"]) for j in json.load(open(REGISTRY))["jurisdictions"]}
    seen, rows = set(), []
    for q in QUERIES:
        for r in catalog(q):
            res, md = r.get("resource", {}), r.get("metadata", {})
            dom, rid = md.get("domain", ""), res.get("id", "")
            if not dom or (dom, rid) in seen or any(s in dom for s in SKIP):
                continue
            seen.add((dom, rid))
            name = (res.get("name") or "")
            # Keep the ones that look like an establishment-level inspection dataset, not a
            # violations lookup, a summary or a rodent log.
            low = name.lower()
            if "inspection" not in low and "food" not in low:
                continue
            # Not an establishment-level opening signal: violations-only lookups, school
            # cafeterias, mobile/temporary vendors, and non-restaurant inspections.
            NOISE = ("violation", "school", "tobacco", "mobile", "temporary", "truck",
                     "residence", "home park", "handwash", "farmers", "feed_info", "pool")
            if any(w in low for w in NOISE):
                continue
            rows.append({
                "domain": dom, "resource": rid, "name": name,
                "updated": (res.get("data_updated_at") or "")[:10],
                "rows": res.get("columns_name") and res.get("rowCount") or (res.get("rowCount") or ""),
                "in_registry": "YES" if (dom, rid) in have else "",
                "link": r.get("link", ""),
            })

    rows.sort(key=lambda r: (r["in_registry"] == "YES", r["updated"]), reverse=True)
    with open(OUT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["domain", "resource", "name", "updated", "rows",
                                          "in_registry", "link"])
        w.writeheader(); w.writerows(rows)

    fresh = [r for r in rows if r["updated"] >= "2026-01-01"]
    print(f"{len(rows)} candidate inspection dataset(s) across Socrata nationally; "
          f"{len(fresh)} updated in 2026; {sum(1 for r in rows if r['in_registry'])} already registered.")
    print("\nFresh and NOT yet in the registry (the worklist):")
    for r in fresh:
        if not r["in_registry"]:
            print(f"  {r['updated']}  {r['domain']:<28} {r['resource']:<12} {r['name'][:44]}")
    print(f"\n-> {OUT}")


if __name__ == "__main__":
    main()

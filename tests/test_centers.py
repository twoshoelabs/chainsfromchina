"""
Shopping-center / co-tenancy view (docs/phase1_spec.md §4.5). Co-location is computed from the
project's own geocoded stores; these tests hold the grouping and the landlord-facing counts:

  stores at the same coordinates form one cluster; distant ones do not
  co_tenancy() keeps only clusters with >= 2 DISTINCT brands (the sellable signal)
  an explicit center_id groups authoritatively, overriding geography, and attaches the center's meta
  brand_count / sector_count are distinct brands / sectors, and every cluster carries its members

Run: .venv/bin/python tests/test_centers.py
"""
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from chain_atlas import db, centers  # noqa: E402

REG = {"chains": {
    "miniso": {"name": "MINISO", "format": "lifestyle"},
    "popmart": {"name": "POP MART", "format": "toys"},
    "mixue": {"name": "MIXUE", "format": "tea"},
    "haidilao": {"name": "Haidilao", "format": "hotpot"},
}, "markets": {}, "entries": []}


def seed(con, rows):
    for chain, key, lat, lon, city, state, center_id in rows:
        con.execute("INSERT OR IGNORE INTO chains(chain_id,name,origin,format) VALUES(?,?,'CN','x')",
                    (chain, chain))
        con.execute("INSERT INTO stores(chain_id,country,store_key,lat,lon,city,state,first_seen,"
                    "last_seen,status,center_id) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                    (chain, "US", key, lat, lon, city, state, "2026-01-01", "2026-09-30",
                     "active", center_id))
    con.commit()


def main():
    fails = []

    def check(label, got, want=True):
        ok = got == want
        print(f"  {'PASS' if ok else 'FAIL'}  {label}" + ("" if ok else f"  (got {got!r}, want {want!r})"))
        if not ok:
            fails.append(label)

    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row
    con.executescript(db.SCHEMA)
    con.execute("INSERT INTO shopping_centers(id,name,owner_reit,class_tier,metro,source,retrieved_at,"
                "confidence) VALUES('sc1','Trophy Mall','GiantREIT','A','SEA-CBSA','manual',"
                "'2026-09-30T00:00:00Z','high')")
    seed(con, [
        # two brands of DIFFERENT sectors at the same coordinates -> a co-tenancy cluster
        ("miniso",  "m1", 40.7602, -73.8340, "Queens", "NY", None),  # lifestyle_variety
        ("mixue",   "x1", 40.7603, -73.8341, "Queens", "NY", None),  # tea
        # a lone brand far away -> its own single-brand cluster
        ("popmart", "p1", 34.0588, -118.4189, "Los Angeles", "CA", None),
        # two brands linked to the SAME named center though ~a mile apart -> grouped by center_id
        ("miniso",  "m2", 47.6100, -122.3300, "Seattle", "WA", "sc1"),
        ("haidilao","h2", 47.6200, -122.3500, "Seattle", "WA", "sc1"),
    ])

    cl = centers.clusters(con, include_sightings=False, d=REG, curated=[])
    by_where = {(c["city"], c["state"], c["key"].startswith("center:")): c for c in cl}
    # Queens geo cluster: 2 brands
    q = next(c for c in cl if c["city"] == "Queens")
    check("Queens cluster has 2 distinct brands", q["brand_count"], 2)
    check("Queens cluster has 2 sectors", q["sector_count"], 2)
    check("Queens cluster names resolve", sorted(b["name"] for b in q["brands"]), ["MINISO", "MIXUE"])
    check("cluster carries its store members", q["store_count"], 2)

    # LA lone brand: single-brand cluster, excluded from co-tenancy
    la = next(c for c in cl if c["city"] == "Los Angeles")
    check("LA cluster is single-brand", la["brand_count"], 1)

    # center_id grouping overrides geography and attaches center meta
    sc = next(c for c in cl if c["key"] == "center:sc1")
    check("center_id groups the two Seattle stores despite distance", sc["brand_count"], 2)
    check("center meta attached (name)", sc["center"]["name"], "Trophy Mall")
    check("center meta attached (owner)", sc["center"]["owner_reit"], "GiantREIT")

    cot = centers.co_tenancy(con, include_sightings=False, d=REG, curated=[])
    check("co_tenancy keeps only 2+ brand clusters", sorted(c["key"] for c in cot),
          sorted(["geo:40.76,-73.834", "center:sc1"]))
    check("co_tenancy excludes the lone LA brand", all(c["city"] != "Los Angeles" for c in cot), True)

    # REIT rollup only counts centers with a known owner
    roll = centers.reit_rollup(con, include_sightings=False, d=REG, curated=[])
    check("REIT rollup surfaces GiantREIT", roll[0]["owner_reit"], "GiantREIT")
    check("REIT rollup counts one distinct center", roll[0]["centers"], 1)
    check("REIT rollup unions its brands", roll[0]["brands"], 2)

    print("\n" + ("ALL PASS" if not fails else f"{len(fails)} FAILED: {fails}"))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())

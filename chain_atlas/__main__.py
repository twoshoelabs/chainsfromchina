"""
CLI. `python -m chain_atlas <command>`
"""
import sys
from pathlib import Path


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd = argv[0] if argv else "help"

    def opt(name, default=None):
        return argv[argv.index(name) + 1] if name in argv else default

    if cmd == "run":
        from .run import run
        return run(chain_id=opt("--chain"), obs_date=opt("--date"), force="--force" in argv)

    if cmd == "reparse":
        from .run import reparse
        return reparse(chain_id=opt("--chain"), obs_date=opt("--date"))

    if cmd == "recheck":
        from .run import recheck
        return recheck(chain_id=opt("--chain"))

    if cmd == "watch":
        from .run import watch_launches
        return 0 if watch_launches(chain_id=opt("--chain")) == 0 else 0

    if cmd == "status":
        from .run import status
        status()
        return 0

    if cmd == "register":
        from . import register
        d = register.load()
        if "--stale" in argv:
            days = int(opt("--stale-days", register.STALE_DAYS))
            rows = register.stale(d, days)
            print(f"{len(rows)} entr(y/ies) not reviewed in {days} days")
            for c, m, age in rows:
                print(f"  {c:9} {m}  {age} days")
            return 0
        if "--gaps" in argv:
            g = register.gaps(d)
            print(f"{len(g)} chain/market pairs never looked at:")
            for c, m in g:
                print(f"  {c:9} {m}")
            return 0
        register.report(d, chain=opt("--chain"), market=opt("--market"))
        return 0

    if cmd == "sightings":
        from . import sightings
        d = sightings.load()
        if "--stale" in argv:
            days = int(opt("--stale-days", sightings.REVIEW_STALE_DAYS))
            rows = sightings.stale(d, days)
            print(f"{len(rows)} sighting group(s) not re-verified in {days} days:")
            for chain, scope, age in rows:
                when = f"{age} days" if age >= 0 else "NEVER (no reviewed date)"
                print(f"  {chain:12} {when:>24}  {str(scope)[:70]}")
            return 0
        groups = d.get("sightings", [])
        locs = sum(len(g.get("locations", [])) for g in groups)
        print(f"{len(groups)} sighting groups, {locs} locations. "
              f"Use --stale [--stale-days N] to list groups due for re-verification.")
        return 0

    if cmd == "closings":
        from . import closings
        rows = closings.load().get("closings", [])
        cs = closings.summary()
        print(f"{cs['total']} hand-recorded closings "
              f"({cs['confirmed']} confirmed, {cs['uncertain']} uncertain), "
              f"{len(cs['chains'])} chains:")
        for r in sorted(rows, key=lambda r: (r["chain"], r.get("city") or "")):
            where = r.get("address") or f"{r.get('city','')}, {r.get('state','')}".strip(", ")
            when = r.get("closed_on") or (r.get("closed_note") or "")
            mark = "" if r.get("confidence") == "confirmed" else " (uncertain)"
            print(f"  {r['chain']:13} {where:40}  {when}{mark}")
        return 0

    if cmd == "geocode":
        from . import db, geocode
        con = db.connect()
        print(geocode.run(con, chain_id=opt("--chain"), limit=int(opt("--limit", 500))))
        return 0

    if cmd == "sync-brands":
        from . import db, register
        con = db.connect()
        n = register.sync_brands_to_db(con)
        print(f"synced brand fields into {n} chains")
        return 0

    if cmd == "uspto":
        from . import db, uspto
        con = db.connect()
        print(uspto.run(con))
        return 0

    if cmd == "centers":
        from . import db, centers
        con = db.connect()
        centers.report(con, min_brands=int(opt("--min", 2)))
        return 0

    if cmd == "export":
        from .mapdata import export
        from . import register, geojson, db, demographics
        out = Path(opt("--out", str(Path(__file__).resolve().parents[1] / "map" / "data")))
        con = db.connect()
        print(export(out), "->", out)
        print(register.export(out), "-> register.json")
        # NOTE: co-tenancy (centers.json) is a PAID/Pro tier — deliberately NOT written to the public
        # data dir. The generator stays available via `python -m chain_atlas centers` and will feed the
        # access-controlled Pro export; it must never be emitted here. See cfc-analytics-paywall.
        print(geojson.export(con, out), "-> stores.geojson")
        print(demographics.export(out), "-> demographics.json")
        return 0

    if cmd == "demographics":
        from . import demographics
        return demographics.run()

    if cmd == "revenue":
        from . import db, revenue
        con = db.connect()
        print(revenue.run(con))
        return 0

    if cmd == "capacity":
        from . import db, capacity
        con = db.connect()
        import json as _json
        print(_json.dumps(capacity.run(con, brand_id=opt("--chain", "haidilao")), indent=2))
        return 0

    if cmd == "fdd":
        from . import db, fdd
        con = db.connect()
        import json as _json
        print(_json.dumps(fdd.run(con), indent=2, default=str))
        return 0

    if cmd == "aggregate":
        from . import db, aggregate
        con = db.connect()
        aggregate.report(con)
        return 0

    if cmd == "probe":
        from .adapters import by_id
        from . import capture
        capture.set_delay(1, 2)
        a = by_id(opt("--chain", ""))
        if a is None:
            print("usage: probe --chain <id>")
            return 2
        mod = sys.modules[a.__class__.__module__]
        if not hasattr(mod, "probe"):
            print(f"{a.chain_id}: no probe (blocked: {a.BLOCKED_REASON})")
            return 2
        mod.probe()
        return 0

    print(__doc__.strip())
    print("  run [--chain X] [--date YYYY-MM-DD] [--force]   daily pass")
    print("  reparse [--chain X] [--date YYYY-MM-DD]                re-derive a day from raw, no network")
    print("  status                                          stock, pipeline, blocked chains")
    print("  geocode [--chain X] [--limit N]                  derive coordinates from US addresses")
    print("  sync-brands                                     push register brand fields into the DB")
    print("  uspto                                           weekly USPTO trademark pipeline signals")
    print("  centers [--min N]                               co-tenancy clusters (>=N China brands)")
    print("  export [--out DIR]                              write map/data/*.json")
    print("  demographics                                    DERIVED/MODELED: tract %Asian, metro, campus aggregates")
    print("  revenue                                         MODELED: per-outlet + US-total revenue from filing anchors x store count")
    print("  capacity [--chain X]                             official occupant-load + TX alcohol receipts; reality-checks the revenue AUV")
    print("  fdd                                              FDD Item 19 (US per-outlet AUV) + Item 20 outlet counts, from MN franchise registry")
    print("  aggregate                                        MODELED grand total: banded US revenue across all chains (anchored + benchmark)")
    print("  recheck [--chain X]                              re-probe why a chain is still blocked")
    print("  watch [--chain X]                                launch-watch: alert when a blocked chain's page changes")
    print("  register [--chain X] [--market XX] [--stale] [--gaps]   international register")
    print("  sightings [--stale] [--stale-days N]            hand-verified locations; review cadence")
    print("  closings                                        hand-recorded historical closings")
    print("  probe --chain X                                 print one chain's live locator")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

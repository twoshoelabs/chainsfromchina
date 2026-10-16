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

    if cmd == "provenance":
        from . import provenance
        s = provenance.summary()
        state = "intact" if s["ok"] else "BROKEN"
        print(f"{s['entries']} provenance entr(y/ies) — hash chain {state}. "
              f"head={s['head'][:16]}…")
        if not s["ok"]:
            for prob in s["problems"]:
                print("  !", prob)
            return 1
        if "--show" in argv:
            for e in provenance.load():
                print(f"  #{e['seq']:>3} {e['ts']}  {e['record_id']}  [{e['event']}]")
                print(f"       {e['statement']}")
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

    if cmd == "china-stores":
        from . import db, china_stores
        con = db.connect()
        errs = china_stores.validate()
        if errs:
            print("china_stores.json invalid:")
            for e in errs:
                print("  " + e)
            return 2
        china_stores.report(con)
        return 0

    if cmd == "openings":
        from . import db, openings
        con = db.connect()
        openings.report(con)
        return 0

    if cmd == "dossier":
        from . import db, dossier
        brand = next((a for a in argv[1:] if not a.startswith("-")), None)
        if not brand:
            print("usage: python -m chain_atlas dossier <chain_id> [--md]")
            return 2
        con = db.connect()
        print(dossier.run(con, brand, as_markdown=("--md" in argv)))
        return 0

    if cmd == "console":
        from . import console
        return console.serve(port=int(opt("--port", "8787")), open_browser="--no-open" not in argv) or 0

    if cmd == "export-tier":
        from . import db, tier_export
        tier = next((a for a in argv[1:] if not a.startswith("-")), None)
        if tier not in tier_export.TIERS:
            print(f"usage: python -m chain_atlas export-tier <{'|'.join(tier_export.TIERS)}> [--brand X] [--out DIR]")
            return 2
        con = db.connect()
        brands = [opt("--brand")] if opt("--brand") else None
        out = opt("--out")
        if "--dataset" in argv:                        # the full tabular dataset product
            ds = tier_export.dataset(con, tier, brands=brands)
            if out:
                files = tier_export.write_dataset(ds, out)
                print(f"{tier} dataset: {ds['brand_count']} brands, "
                      f"{len(ds['tables'])} table(s) -> {len(files)} file(s) in {out}")
            else:
                import json as _json
                print(_json.dumps(ds, ensure_ascii=False, indent=1))
            return 0
        bundle = tier_export.export(con, tier, brands=brands)
        if out:
            files = tier_export.write(bundle, out)
            print(f"{tier}: {bundle['brand_count']} brands -> {len(files)} file(s) in {out}")
        else:
            import json as _json
            print(_json.dumps(bundle, ensure_ascii=False, indent=1))
        return 0

    if cmd == "verify":
        from . import db, verify
        con = db.connect()
        rid = opt("--resolve")
        if rid:
            vd = opt("--verdict")
            if vd not in ("verified", "rejected"):
                print("usage: … verify --resolve <id> --verdict verified|rejected [--by W] [--note …] [--confidence high]")
                return 2
            r = verify.record_verdict(rid, vd, by=opt("--by", "owner"), note=opt("--note"),
                                      new_confidence=opt("--confidence"))
            print(f"recorded: {r['verdict']} {rid} by {r['by']}")
            return 0
        items = verify.queue(con)
        if opt("--reason"):
            items = [i for i in items if i["reason"] == opt("--reason")]
        if opt("--brand"):
            items = [i for i in items if i["brand"] == opt("--brand")]
        print(verify.render(items, limit=int(opt("--limit", "40"))))
        return 0

    if cmd == "alerts":
        from . import alerts
        sub = argv[1] if len(argv) > 1 and not argv[1].startswith("-") else "digest"
        con = None
        if "--with-filings" in argv:
            from . import db
            con = db.connect()
        if sub == "detect":
            seeded = not Path(alerts.BASELINE).exists()
            new = alerts.run_detect(con)
            print(f"detected {len(new)} new event(s)"
                  + ("  (baseline seeded — first run emits nothing)" if seeded
                     else "  (no changes)" if not new else ""))
            if new and "--digest" in argv:
                print("\n" + alerts.digest(new, title="New alerts"))
            return 0
        if sub == "notify":
            r = alerts.notify(con, macos="--no-macos" not in argv)
            if r["undelivered"]:
                print(r["digest"])
                print(f"\n-- {r['undelivered']} new alert(s) written to {r['digest_path']} --")
            else:
                print(f"no new alerts (detected {r['detected']} this run)")
            return 0
        if sub in ("digest", "log"):
            events = alerts.load()
            lens = {}
            if opt("--kind"):
                lens["kinds"] = [opt("--kind")]
            if opt("--brand"):
                lens["brands"] = [opt("--brand")]
            if opt("--sector"):
                lens["sectors"] = [opt("--sector")]
            if opt("--min-confidence"):
                lens["min_confidence"] = opt("--min-confidence")
            since = alerts.read_cursor() if "--undelivered" in argv else opt("--since")
            if sub == "log":
                rows = alerts.filter_events(events, lens, since)[-int(opt("--limit", "40")):]
                for e in rows:
                    print(f"  [{e['kind']}] {e['brand']}: {e['headline']}  "
                          f"({e['confidence']}, {e['as_of']})")
                print(f"-- {len(rows)} event(s) of {len(events)} in log --")
                return 0
            out = alerts.digest(events, lens, since)
            print(out or "(no alerts match)")
            if "--deliver" in argv and out:
                cur = alerts.mark_delivered(events)
                print(f"\n-- delivery cursor advanced to {cur} --")
            return 0
        print("usage: python -m chain_atlas alerts detect [--digest] [--with-filings]")
        print("       python -m chain_atlas alerts notify [--with-filings] [--no-macos]  (daily hook)")
        print("       python -m chain_atlas alerts digest|log [--since ISO | --undelivered]"
              " [--kind K] [--brand B] [--sector S] [--min-confidence high] [--deliver]")
        return 2

    if cmd == "apps":
        from . import apps
        sub = argv[1] if len(argv) > 1 and not argv[1].startswith("-") else "report"
        if sub == "validate":
            probs = apps.validate()
            if probs:
                print("apps.json invalid:")
                for p in probs:
                    print("  " + p)
                return 2
            print(f"apps.json valid ({len(apps.verified())} verified US apps)")
            return 0
        if sub == "lookup":
            i = opt("--id")
            if not i:
                print("usage: python -m chain_atlas apps lookup --id <app_id_or_url>")
                return 2
            for aid, m in apps.lookup(i).items():
                print(f"  {m['app']}  [{m['genre']}]  langs: {','.join(m['languages'][:8])}")
                print(f"  seller: {m['seller']}  | {m['ios_url']}")
                if m.get("seller_url"):
                    print(f"  seller_url: {m['seller_url']}")
                print(f"  desc: {m['desc'][:400]}")
            return 0
        if sub == "probe":
            bl = [opt("--brand")] if opt("--brand") else None
            detail = "--details" in argv
            hits = apps.probe(brands=bl, detail=detail)
            for b, rows in sorted(hits.items()):
                for c in rows:
                    print(f"  {b:16} [{c['score']:6}] {str(c['app'])[:34]:34} by "
                          f"{str(c['seller'])[:24]:24} ({c.get('ratings_n') or '-'})  {c['ios_url']}")
                    if detail and c.get("desc") is not None:
                        print(f"        {c.get('genre','?')} · {','.join((c.get('languages') or [])[:6])}"
                              f" · {c.get('desc','')[:150]}")
            print(f"-- {len(hits)} brand(s) with candidate US app(s); VERIFY before adding to "
                  "manual/apps.json (name collisions are common) --")
            return 0
        apps.report()
        return 0

    if cmd == "dossiers":
        from . import dossiers
        errs = dossiers.validate()
        if errs:
            print("dossiers.json invalid:")
            for e in errs:
                print("  " + e)
            return 2
        dossiers.report()
        return 0

    if cmd == "filings":
        from . import db, filings
        con = db.connect()
        s = filings.run(con)
        print(f"checked {s['checked']} filers — {s['new']} new, {s['duplicate']} current, "
              f"{s['manual']} check-link, {s['skipped']} unavailable")
        for r in s["rows"]:
            tag = r["status"]
            extra = r.get("title") or r.get("url") or ""
            print(f"  {r['brand']:12} {r['venue']:7} {tag:10} {str(r.get('date') or ''):12} {extra[:70]}")
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
    print("  filings                                          watch SEC/HKEX/cninfo filings of US-present listed chains; signal new annual reports")
    print("  china-stores                                     Pro: reported China store counts vs US footprint (home-market scale / runway)")
    print("  openings                                         Pro: opening pace (net stores/year, %) derived from dated store counts")
    print("  console [--port N] [--no-open]                   Pro: PRIVATE owner console (localhost) — submit data points + work the queue")
    print("  export-tier <public|observer|pro|intelligence> [--brand X] [--out DIR]   tier-gated export (pro/ = access-controlled)")
    print("  verify [--reason R|--brand B|--limit N]          Pro: the verification queue — records awaiting a human verdict")
    print("  verify --resolve <id> --verdict verified|rejected   …record a verdict (append-only verifications.jsonl)")
    print("  dossier <chain_id> [--md]                        Pro: assemble ONE chain's full dossier (all 5 layers) as JSON or Markdown")
    print("  dossiers                                         Pro: qualitative per-chain dossiers (history, popular items, flagships)")
    print("  recheck [--chain X]                              re-probe why a chain is still blocked")
    print("  watch [--chain X]                                launch-watch: alert when a blocked chain's page changes")
    print("  register [--chain X] [--market XX] [--stale] [--gaps]   international register")
    print("  sightings [--stale] [--stale-days N]            hand-verified locations; review cadence")
    print("  closings                                        hand-recorded historical closings")
    print("  probe --chain X                                 print one chain's live locator")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

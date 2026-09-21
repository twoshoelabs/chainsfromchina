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

    if cmd == "export":
        from .mapdata import export
        from . import register
        out = Path(opt("--out", str(Path(__file__).resolve().parents[1] / "map" / "data")))
        print(export(out), "->", out)
        print(register.export(out), "-> register.json")
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
    print("  export [--out DIR]                              write map/data/*.json")
    print("  recheck [--chain X]                              re-probe why a chain is still blocked")
    print("  register [--chain X] [--market XX] [--stale] [--gaps]   international register")
    print("  probe --chain X                                 print one chain's live locator")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

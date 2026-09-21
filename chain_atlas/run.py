"""
The daily pass: for each enabled chain, capture, record, diff.

Idempotent per (chain, day). A chain already `ok` for the date is skipped unless --force, so a
retry costs the sites nothing for work already done.
"""
import json
import re
from datetime import datetime
from pathlib import Path

from . import capture, db
from .adapters import REGISTRY, by_id
from .config import TZ
from .events import diff
from .identity import store_key, norm_addr

# A day's count that moves by more than this fraction is not trusted without a second look:
# the usual cause is a partial page, and a partial page looks exactly like a wave of closures.
SUSPICIOUS_DELTA = 0.30


def today() -> str:
    return datetime.now(TZ).date().isoformat()


def run(chain_id: str | None = None, obs_date: str | None = None, force: bool = False) -> int:
    """
    name:      run
    purpose:   Collect every enabled chain (or one) for a date and derive its events.
    arguments: chain_id — restrict to one chain; obs_date — defaults to today in US/Eastern;
               force — re-run chains already recorded ok for the date
    returns:   process exit code (0 all ok, 1 if any chain failed)
    effects:   Network I/O, raw files, database writes.
    other:     Each chain is independent: one chain's failure never aborts the pass, because a
               day with three chains collected and one missing is far more useful than no day.
    """
    obs_date = obs_date or today()
    con = db.connect()
    failed = 0

    targets = [by_id(chain_id)] if chain_id else list(REGISTRY)
    if chain_id and targets[0] is None:
        print(f"no such chain: {chain_id}")
        return 2

    for a in targets:
        if not a.ENABLED:
            print(f"{a.chain_id:9} skipped — {a.BLOCKED_REASON or 'not enabled'}")
            continue
        prev_ok = con.execute(
            "SELECT 1 FROM runs WHERE chain_id=? AND obs_date=? AND status='ok'",
            (a.chain_id, obs_date)).fetchone()
        if prev_ok and not force:
            print(f"{a.chain_id:9} already ok for {obs_date}; skipping")
            continue

        db.upsert_chain(con, a)
        started = datetime.now(TZ).isoformat()
        cur = con.execute("INSERT INTO runs (obs_date,chain_id,started,status) VALUES (?,?,?,?)",
                          (obs_date, a.chain_id, started, "failed"))
        run_id = cur.lastrowid
        con.commit()

        try:
            raw = a.fetch_raw()
            raw_path, raw_sha = capture.save_raw(a.chain_id, obs_date, raw, a.raw_ext)
            recs = a.parse(raw)

            prev_n = con.execute(
                "SELECT n_records FROM runs WHERE chain_id=? AND status='ok' AND obs_date<?"
                " ORDER BY obs_date DESC LIMIT 1", (a.chain_id, obs_date)).fetchone()
            prev_n = prev_n["n_records"] if prev_n else None
            delta = (len(recs) - prev_n) if prev_n is not None else None

            if prev_n and abs(delta) / max(prev_n, 1) > SUSPICIOUS_DELTA:
                con.execute("UPDATE runs SET finished=?,status='suppressed',n_records=?,delta=?,"
                            "raw_path=?,raw_sha256=?,error=? WHERE run_id=?",
                            (datetime.now(TZ).isoformat(), len(recs), delta, raw_path, raw_sha,
                             f"delta {delta} on {prev_n} exceeds {SUSPICIOUS_DELTA:.0%}", run_id))
                con.commit()
                print(f"{a.chain_id:9} SUPPRESSED {len(recs)} records (was {prev_n}); raw kept,"
                      " nothing derived — inspect before forcing")
                failed += 1
                continue

            baseline = con.execute(
                "SELECT 1 FROM runs WHERE chain_id=? AND status='ok' AND obs_date<? LIMIT 1",
                (a.chain_id, obs_date)).fetchone() is None

            con.execute("DELETE FROM observations WHERE chain_id=? AND obs_date=?",
                        (a.chain_id, obs_date))
            for r in recs:
                con.execute(
                    "INSERT OR IGNORE INTO observations (obs_date,chain_id,store_key,store_code,"
                    "name,addr_raw,addr_norm,city,state,zip,lat,lon,trading,temp_closed,run_id)"
                    " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (obs_date, a.chain_id, store_key(r), r.store_code, r.name, r.addr_raw,
                     norm_addr(r.addr_raw), r.city, r.state, r.zip, r.lat, r.lon,
                     int(r.trading), int(r.temp_closed), run_id))

            counts = diff(con, a.chain_id, obs_date, a.closure_n_days, baseline)
            con.execute("UPDATE runs SET finished=?,status='ok',n_records=?,delta=?,raw_path=?,"
                        "raw_sha256=? WHERE run_id=?",
                        (datetime.now(TZ).isoformat(), len(recs), delta, raw_path, raw_sha, run_id))
            con.commit()
            tail = " ".join(f"{k}={v}" for k, v in sorted(counts.items())) or "no changes"
            print(f"{a.chain_id:9} ok  {len(recs):4} records  {'(baseline) ' if baseline else ''}{tail}")
        except Exception as e:                                  # noqa: BLE001 — recorded, not raised
            con.execute("UPDATE runs SET finished=?,status='failed',error=? WHERE run_id=?",
                        (datetime.now(TZ).isoformat(), f"{type(e).__name__}: {e}", run_id))
            con.commit()
            print(f"{a.chain_id:9} FAILED  {type(e).__name__}: {e}")
            failed += 1

    return 1 if failed else 0


def reparse(chain_id: str | None = None, obs_date: str | None = None) -> int:
    """
    name:      reparse
    purpose:   Re-derive a day's observations and events from the archived raw capture,
               without touching the network.
    arguments: chain_id — restrict to one chain; obs_date — defaults to today
    returns:   exit code
    effects:   Rewrites observations and events for that (chain, date). Raw files are untouched.
    other:     This is what makes "the raw capture is the primary evidence" a fact rather than a
               claim: a parser fix is applied to history by re-reading the archive, and the
               numbers move without anyone re-asking the chain for them. It re-derives ONE day;
               replaying a whole archive after a parser change means walking the dates in order.
    """
    obs_date = obs_date or today()
    con = db.connect()
    rows = con.execute(
        "SELECT chain_id, raw_path FROM runs WHERE obs_date=? AND status='ok' AND raw_path IS NOT NULL"
        + (" AND chain_id=?" if chain_id else "") + " ORDER BY run_id",
        (obs_date, chain_id) if chain_id else (obs_date,)).fetchall()
    if not rows:
        print(f"no successful captures stored for {obs_date}")
        return 2
    for r in rows:
        a = by_id(r["chain_id"])
        try:
            recs = a.parse(capture.read_raw(r["raw_path"]))
        except Exception as e:                                  # noqa: BLE001
            print(f"{a.chain_id:9} reparse FAILED  {type(e).__name__}: {e}")
            continue
        con.execute("DELETE FROM observations WHERE chain_id=? AND obs_date=?", (a.chain_id, obs_date))
        for rec in recs:
            con.execute(
                "INSERT OR IGNORE INTO observations (obs_date,chain_id,store_key,store_code,"
                "name,addr_raw,addr_norm,city,state,zip,lat,lon,trading,temp_closed)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (obs_date, a.chain_id, store_key(rec), rec.store_code, rec.name, rec.addr_raw,
                 norm_addr(rec.addr_raw), rec.city, rec.state, rec.zip, rec.lat, rec.lon,
                 int(rec.trading), int(rec.temp_closed)))
        # The roster carries fields derived from the observations, so it is rebuilt too. A
        # reparse of the baseline day stays a baseline: it must not invent openings.
        baseline = con.execute(
            "SELECT 1 FROM runs WHERE chain_id=? AND status='ok' AND obs_date<? LIMIT 1",
            (a.chain_id, obs_date)).fetchone() is None
        con.execute("DELETE FROM stores WHERE chain_id=? AND first_seen=? AND last_seen=?",
                    (a.chain_id, obs_date, obs_date))
        counts = diff(con, a.chain_id, obs_date, a.closure_n_days, baseline)
        con.commit()
        print(f"{a.chain_id:9} reparsed {len(recs):4} records from {Path(r['raw_path']).name}"
              f"  {' '.join(f'{k}={v}' for k, v in sorted(counts.items())) or 'no changes'}")
    return 0


def recheck(chain_id: str | None = None) -> int:
    """
    name:      recheck
    purpose:   Re-probe the URLs behind each blocked chain and report what they answer now.
    arguments: chain_id — restrict to one chain
    returns:   exit code (0 always; this reports, it never decides)
    effects:   One polite request per URL. Touches nothing in the archive.
    other:     A BLOCKED_REASON is a fact about a date, not a permanent verdict. ChaPanda has no
               locator because it has two American shops; Pop Mart's challenge could be relaxed;
               Tai Er's endpoint could be fixed. Without this, the roster would keep quoting the
               day somebody gave up. Deliberately dumb: it prints status, size and a guess at
               whether the response is a bot challenge, and leaves the judgement to a person.
    """
    from . import capture
    # A probe, not a census: short delays, and a dead domain should cost one attempt rather than
    # three. The nightly pass keeps its own politeness settings; this is a person waiting.
    capture.set_delay(1, 2)
    targets = [a for a in REGISTRY
               if not a.ENABLED and a.RECHECK and (not chain_id or a.chain_id == chain_id)]
    if not targets:
        print("nothing to recheck" + (f" for {chain_id}" if chain_id else ""))
        return 0
    print(f"re-probing {sum(len(a.RECHECK) for a in targets)} URL(s) for "
          f"{len(targets)} blocked chain(s)\n")
    for a in targets:
        print(f"{a.name} ({a.chain_id})", flush=True)
        print(f"  was: {a.BLOCKED_REASON}", flush=True)
        for url in a.RECHECK:
            try:
                r = capture.fetch(url, tries=1)
                body = r.text or ""
                challenge = bool(re.search(r"challenge-platform|cf-browser-verification|"
                                           r"just a moment|enable javascript and cookies",
                                           body, re.I))
                note = " [bot challenge]" if challenge else ""
                print(f"  now: {r.status_code} {len(body):>7}B{note}  {url}", flush=True)
            except Exception as e:                              # noqa: BLE001
                print(f"  now: FAILED {type(e).__name__}: {str(e)[:70]}  {url}", flush=True)
        print()
    print("Nothing here changes the archive. If a page has started publishing stores,"
          " write the adapter.")
    return 0


def status():
    """
    name:      status
    purpose:   Print stock, pipeline and last run per chain, including why a chain is missing.
    arguments: none
    returns:   None
    effects:   Reads the database.
    other:     Blocked chains are listed with their reason. A tracker must show its own holes.
    """
    con = db.connect()
    print(f"{'chain':10} {'open':>5} {'soon':>5} {'closed':>6} {'located':>8}  last run")
    for a in REGISTRY:
        row = con.execute(
            "SELECT SUM(status='active') o, SUM(status='pre_opening') p, SUM(status='closed') c,"
            " SUM(lat IS NOT NULL AND status='active') loc FROM stores WHERE chain_id=?",
            (a.chain_id,)).fetchone()
        last = con.execute(
            "SELECT obs_date,status,n_records FROM runs WHERE chain_id=? ORDER BY run_id DESC LIMIT 1",
            (a.chain_id,)).fetchone()
        if not a.ENABLED and not last:
            print(f"{a.chain_id:10} {'—':>5} {'—':>5} {'—':>6} {'—':>8}  BLOCKED: {a.BLOCKED_REASON}")
            continue
        o, p, c, loc = (row["o"] or 0, row["p"] or 0, row["c"] or 0, row["loc"] or 0)
        lastdesc = f"{last['obs_date']} {last['status']} ({last['n_records']})" if last else "never"
        print(f"{a.chain_id:10} {o:5} {p:5} {c:6} {loc:8}  {lastdesc}")
    ev = con.execute("SELECT event_type, COUNT(*) n FROM events GROUP BY 1 ORDER BY 2 DESC").fetchall()
    if ev:
        print("\nevents: " + ", ".join(f"{r['event_type']}={r['n']}" for r in ev))

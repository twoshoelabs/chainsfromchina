"""
The diff engine is the whole product: a baseline day is just a list, and every number this
project will ever publish is a difference between two days. These tests drive synthetic days
through it because the interesting cases — a coming_soon flipping to open, a store vanishing
for exactly N collected days, a cancelled plan — cannot be waited for.

Run: US_CHAIN_ATLAS_DATA=$(mktemp -d) .venv/bin/python -m tests.test_events
"""
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("US_CHAIN_ATLAS_DATA", tempfile.mkdtemp(prefix="uca_test_"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from us_chain_atlas import db                       # noqa: E402
from us_chain_atlas.events import diff              # noqa: E402
from us_chain_atlas.adapters.base import StoreRecord  # noqa: E402
from us_chain_atlas.identity import store_key, norm_addr  # noqa: E402

CHAIN = "t"
N_DAYS = 3


def _record_day(con, date, recs):
    con.execute("INSERT INTO runs (obs_date,chain_id,started,status,n_records)"
                " VALUES (?,?,?, 'ok', ?)", (date, CHAIN, date, len(recs)))
    con.execute("DELETE FROM observations WHERE chain_id=? AND obs_date=?", (CHAIN, date))
    for r in recs:
        con.execute(
            "INSERT INTO observations (obs_date,chain_id,store_key,store_code,name,addr_raw,"
            "addr_norm,city,state,zip,lat,lon,trading,temp_closed)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (date, CHAIN, store_key(r), r.store_code, r.name, r.addr_raw, norm_addr(r.addr_raw),
             r.city, r.state, r.zip, r.lat, r.lon, int(r.trading), int(r.temp_closed)))


def s(code, trading=True, lat=40.75, lon=-73.99, addr="1 Main St, New York, NY 10001"):
    return StoreRecord(store_code=code, name=f"store {code}", addr_raw=addr,
                       city="New York", state="NY", zip="10001", lat=lat, lon=lon, trading=trading)


def kinds(con, date):
    return sorted(r["event_type"] for r in con.execute(
        "SELECT event_type FROM events WHERE detected_date=?", (date,)))


def main():
    con = db.connect()
    con.execute("INSERT OR REPLACE INTO chains (chain_id,name,origin,format,closure_n_days)"
                " VALUES (?,?,?,?,?)", (CHAIN, "Test", "CN", "tea", N_DAYS))
    fails = []

    def check(label, got, want):
        ok = got == want
        print(f"  {'PASS' if ok else 'FAIL'}  {label}: {got}" + ("" if ok else f"  (want {want})"))
        if not ok:
            fails.append(label)

    # Day 1 — baseline. Everything pre-exists; nothing is an opening.
    _record_day(con, "2026-09-01", [s("A"), s("B"), s("C", trading=False)])
    c1 = diff(con, CHAIN, "2026-09-01", N_DAYS, baseline=True)
    check("day 1 emits no events", kinds(con, "2026-09-01"), [])
    check("day 1 counts as baseline", c1.get("baseline"), 3)

    # Day 2 — C starts trading (the precise opening), D appears already trading,
    # E appears announced.
    _record_day(con, "2026-09-02", [s("A"), s("B"), s("C"), s("D"), s("E", trading=False)])
    diff(con, CHAIN, "2026-09-02", N_DAYS, baseline=False)
    check("day 2 events", kinds(con, "2026-09-02"), ["announced", "opening", "opening"])
    row = con.execute("SELECT status,opened_on FROM stores WHERE store_key='id:C'").fetchone()
    check("C is open, dated to the flip", (row["status"], row["opened_on"]), ("active", "2026-09-02"))

    # Days 3-4 — B and E gone. Not yet N=3 collected days of absence, so nothing is declared.
    _record_day(con, "2026-09-03", [s("A"), s("C"), s("D")])
    diff(con, CHAIN, "2026-09-03", N_DAYS, baseline=False)
    check("day 3 declares nothing yet", kinds(con, "2026-09-03"), [])

    _record_day(con, "2026-09-04", [s("A"), s("C"), s("D")])
    diff(con, CHAIN, "2026-09-04", N_DAYS, baseline=False)
    check("day 4 still nothing", kinds(con, "2026-09-04"), [])

    # Day 5 — three collected days of absence: B closed, E withdrawn (announced, never traded).
    _record_day(con, "2026-09-05", [s("A"), s("C"), s("D")])
    diff(con, CHAIN, "2026-09-05", N_DAYS, baseline=False)
    check("day 5 closure + withdrawal", kinds(con, "2026-09-05"), ["closure", "withdrawn"])
    ev = con.execute("SELECT event_date FROM events WHERE event_type='closure'").fetchone()
    check("closure dated day after last seen", ev["event_date"], "2026-09-03")

    # Day 6 — B trades again.
    _record_day(con, "2026-09-06", [s("A"), s("B"), s("C"), s("D")])
    diff(con, CHAIN, "2026-09-06", N_DAYS, baseline=False)
    check("day 6 reopen", kinds(con, "2026-09-06"), ["reopen"])

    # Day 7 — F opens 120 m from where B sits: same chain, close, recent. Advisory relocation
    # rides along with the opening, and the opening still stands on its own.
    _record_day(con, "2026-09-07", [s("A"), s("B"), s("C"), s("D"),
                                    s("F", lat=40.7511, lon=-73.9900)])
    diff(con, CHAIN, "2026-09-07", N_DAYS, baseline=False)
    check("day 7 opening recorded", "opening" in kinds(con, "2026-09-07"), True)

    # A collector outage must never look like closures.
    _record_day(con, "2026-09-08", [s("A"), s("B"), s("C"), s("D"), s("F", lat=40.7511, lon=-73.99)])
    con.execute("UPDATE runs SET status='failed' WHERE obs_date='2026-09-08'")
    con.execute("DELETE FROM observations WHERE obs_date='2026-09-08'")
    diff(con, CHAIN, "2026-09-08", N_DAYS, baseline=False)
    still_open = con.execute("SELECT COUNT(*) n FROM stores WHERE status='active'").fetchone()["n"]
    check("failed day closes nothing", still_open, 5)

    # Address identity: the same shop written three ways is one store, not three.
    keys = {norm_addr("133 4th Avenue, Manhattan, NY 10003"),
            norm_addr("133 4TH AVE., Manhattan, NY 10003"),
            norm_addr("133 4th Ave, Manhattan NY 10003")}
    check("address normalisation collapses variants", len(keys), 1)
    check("suite numbers are kept apart",
          norm_addr("1 Mall Rd #249A") == norm_addr("1 Mall Rd #250"), False)

    print(f"\n{'ALL PASS' if not fails else 'FAILURES: ' + ', '.join(fails)}")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())

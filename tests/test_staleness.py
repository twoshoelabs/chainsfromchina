"""
Two guards against a closing we fail to notice, and the hand record of the ones that predate us:

  feed_staleness   A collected feed whose captured bytes have not moved in a long time can no
                   longer be showing us a closing. The age must count from the last BYTE change,
                   and only successful captures count, so a frozen feed is visible while collector
                   downtime is not mistaken for one.
  sightings.stale  Hand-verified locations are never monitored, so they get a periodic human
                   re-check instead; a group past its review window must surface, and one with no
                   reviewable date at all must surface first, never hide.
  closings.summary The hand-recorded historical closings load and count, confirmed apart from
                   uncertain.

Run: CHAIN_ATLAS_DATA=$(mktemp -d) .venv/bin/python -m tests.test_staleness
"""
import os
import sys
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path

os.environ.setdefault("CHAIN_ATLAS_DATA", tempfile.mkdtemp(prefix="uca_stale_"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from chain_atlas import db, sightings, closings   # noqa: E402
from chain_atlas.config import TZ                  # noqa: E402  (feed_staleness measures in NY time)
from chain_atlas.run import feed_staleness         # noqa: E402

fails = []


def check(label, got, want):
    ok = got == want
    print(f"  {'PASS' if ok else 'FAIL'}  {label}: {got}" + ("" if ok else f"  (want {want})"))
    if not ok:
        fails.append(label)


def _run(con, chain, d, sha):
    con.execute("INSERT INTO runs (obs_date,chain_id,started,status,n_records,raw_sha256)"
                " VALUES (?,?,?, 'ok', 1, ?)", (d, chain, d, sha))


def test_feed_staleness():
    con = db.connect()
    today = datetime.now(TZ).date()
    # FROZEN: byte-identical for 30 collected days.
    for i in range(30, -1, -1):
        _run(con, "frozen", (today - timedelta(days=i)).isoformat(), "AAAA")
    # LIVE: bytes change every day.
    for i in range(30, -1, -1):
        d = (today - timedelta(days=i)).isoformat()
        _run(con, "live", d, f"sha-{d}")
    # RECENTLY MOVED: identical for a fortnight, but changed 2 days ago.
    for i in range(30, 2, -1):
        _run(con, "moved", (today - timedelta(days=i)).isoformat(), "OLD")
    for i in range(2, -1, -1):
        _run(con, "moved", (today - timedelta(days=i)).isoformat(), "NEW")
    # A GAP: same bytes 30 calendar days apart, but only two captures — not evidence of a live feed
    # sitting still, so days is large while the run count is small.
    _run(con, "gappy", (today - timedelta(days=30)).isoformat(), "G")
    _run(con, "gappy", today.isoformat(), "G")
    con.commit()

    st = feed_staleness(con)
    check("frozen feed age counts ~30 days unchanged", st["frozen"][0] in (30, 31), True)
    check("frozen feed counted every collected run", st["frozen"][2] == 31, True)
    check("live feed is 0 days since last byte change", st["live"][0], 0)
    check("recently-moved feed is 2 days, not a fortnight", st["moved"][0], 2)
    check("gappy feed: 30 days but only 2 collected runs", st["gappy"], (30, (datetime.now(TZ).date()-timedelta(days=30)).isoformat(), 2))


def test_sightings_stale():
    today = datetime.now(TZ).date()
    d = {"sightings": [
        {"chain": "fresh", "reviewed": today.isoformat()},
        {"chain": "old", "reviewed": (today - timedelta(days=200)).isoformat()},
        {"chain": "nodate"},                       # no reviewable date at all
        {"chain": "fallback", "supplied_on": (today - timedelta(days=200)).isoformat()},
    ]}
    rows = sightings.stale(d, days=90)
    chains = [r[0] for r in rows]
    check("fresh group is not stale", "fresh" in chains, False)
    check("old group is stale", "old" in chains, True)
    check("group with no reviewed date surfaces", "nodate" in chains, True)
    check("reviewed falls back to supplied_on", "fallback" in chains, True)
    check("undated group sorts first (age -1 sentinel)", rows[0][0], "nodate")


def test_closings_summary():
    cs = closings.summary()               # the real manual/closings.json
    check("closings load and total is positive", cs["total"] > 0, True)
    check("confirmed + uncertain == total", cs["confirmed"] + cs["uncertain"], cs["total"])
    check("at least one chain recorded", len(cs["chains"]) > 0, True)


def main():
    test_feed_staleness()
    test_sightings_stale()
    test_closings_summary()
    print("\n" + ("ALL PASS" if not fails else f"{len(fails)} FAILED: {fails}"))
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())

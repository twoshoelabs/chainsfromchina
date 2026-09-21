"""
The manual roster is the one place hand-entered data is allowed to become a COUNT, and the entire
value of the distinction is that the count never leaks into the collected census. These tests
hold that line:

  a group with no `complete_as_of` produces no count       — it stays a sighting
  a group WITH it counts only `confirmed` locations         — `uncertain` is reported, not counted
  the manual count never appears in by_state or meta.counts  — those are the collector's alone

Run: .venv/bin/python tests/test_sightings.py
"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from chain_atlas.sightings import rosters  # noqa: E402

FIXTURE = {
    "sightings": [
        {   # complete, dated -> a count of the confirmed, NY only
            "chain": "cotti", "complete_as_of": "2026-09-22",
            "complete_scope": "New York City",
            "locations": [
                {"address": "174 Smith St, Brooklyn, NY 11201", "confidence": "confirmed"},
                {"address": "482 3rd Ave, New York, NY 10016", "confidence": "confirmed"},
                {"address": "65 Nassau St, New York, NY 10038", "confidence": "uncertain"},
            ],
        },
        {   # same chain, no completeness claim -> contributes NOTHING to the count
            "chain": "cotti",
            "locations": [{"address": "227 W Valley Blvd, San Gabriel, CA 91776"}],
        },
        {   # a different chain, no claim -> not a roster
            "chain": "yangs",
            "locations": [{"address": "13824 Red Hill Ave, Tustin, CA 92780"}],
        },
    ]
}


def main():
    d = tempfile.mkdtemp()
    p = Path(d) / "s.json"
    p.write_text(json.dumps(FIXTURE))
    rs = rosters(p)
    fails = []

    def check(label, got, want):
        ok = got == want
        print(f"  {'PASS' if ok else 'FAIL'}  {label}: {got}" + ("" if ok else f"  (want {want})"))
        if not ok:
            fails.append(label)

    check("only the dated group becomes a roster", len(rs), 1)
    r = rs[0]
    check("it is the cotti one", r["chain"], "cotti")
    check("confirmed are counted, uncertain is not", r["count"], 2)
    check("the uncertain one is reported separately", r["unconfirmed"], 1)
    check("state breakdown counts only confirmed", r["by_state"], {"NY": 2})
    check("the scope claim travels with it", r["complete_scope"], "New York City")

    # The no-leak guarantee, at the export layer.
    from chain_atlas import mapdata
    src = "\n".join(Path(mapdata.__file__).read_text().splitlines())
    check("manual_rosters is its own meta field", '"manual_rosters"' in src, True)
    # by_state is built purely from the stores table; assert the export never adds sightings to it.
    check("by_state is fed only by the stores query",
          "for r in con.execute(" in src and "sightings" not in src.split("by_state, no_state")[1].split("stores, unlocated")[0],
          True)

    print("\n" + ("ALL PASS" if not fails else f"{len(fails)} FAILED: {fails}"))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())

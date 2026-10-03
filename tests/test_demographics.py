"""
The demographic pass is modeled, and the one thing that must never slip is the wall: the published
snapshot carries aggregates and nothing that identifies a store. These checks pin the summary maths
and that shape — denominators per signal, ratios, and no per-outlet data leaking into the snapshot.

Run: .venv/bin/python tests/test_demographics.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from chain_atlas.demographics import summarize  # noqa: E402


def main():
    fails = []

    def check(label, got, want):
        ok = got == want
        print(f"  {'PASS' if ok else 'FAIL'}  {label}: {got}" + ("" if ok else f"  (want {want})"))
        if not ok:
            fails.append(label)

    nat = 10.0
    rows = [
        # tract %Asian, ratio vs national, metro, urban, nearest-campus miles
        {"pct_asian": 50.0, "ratio_vs_nat": 5.0, "metro": "A CSA", "urban": True, "univ_miles": 0.3},
        {"pct_asian": 20.0, "ratio_vs_nat": 2.0, "metro": "A CSA", "urban": True, "univ_miles": 0.9},
        {"pct_asian": 10.0, "ratio_vs_nat": 1.0, "metro": "B CSA", "urban": True, "univ_miles": 2.0},
        {"pct_asian": 5.0, "ratio_vs_nat": 0.5, "metro": None, "urban": False, "univ_miles": 7.0},
        # an outlet the Asian-share join missed: it must not count in that denominator, but still
        # counts for metro/urban/campus where those resolved.
        {"pct_asian": None, "ratio_vs_nat": None, "metro": "A CSA", "urban": True, "univ_miles": 1.0},
    ]
    s = summarize(rows, nat)

    check("every outlet is analyzed", s["outlets_analyzed"], 5)
    check("only resolved tracts enter the Asian denominator", s["with_tract_asian"], 4)
    check("median tract share (of the 4 resolved)", s["asian_density"]["median_tract_pct"], 15.0)
    check("share >= 2x national (2 of 4)", s["asian_density"]["ge_2x"], 50.0)
    check("share >= 5x national (1 of 4)", s["asian_density"]["ge_5x"], 25.0)
    check("share >= national (3 of 4)", s["asian_density"]["ge_national"], 75.0)
    # metro share is over ALL outlets (4 of 5 carry a CSA); urban over the 5 with a urban flag.
    check("in a metro (4 of 5)", s["metro"]["in_csa_pct"], 80.0)
    check("urban (4 of 5)", s["metro"]["urban_pct"], 80.0)
    check("top metro is the most common CSA", s["metro"]["top"][0]["name"], "A CSA")
    check("...with its count", s["metro"]["top"][0]["n"], 3)
    # campus proximity over the 5 with a distance.
    check("within 1 mi (3 of 5)", s["university"]["within_1mi"], 60.0)
    check("within 1/2 mi (1 of 5)", s["university"]["within_half_mi"], 20.0)

    # The wall: the snapshot must not carry any per-outlet record.
    flat = str(s)
    check("snapshot exposes no per-outlet rows key", "rows" in s, False)
    check("snapshot is aggregate-shaped (dict of stats)", set(s) >= {
        "asian_density", "metro", "university", "outlets_analyzed"}, True)

    print(f"\n{'ALL PASS' if not fails else 'FAILURES: ' + ', '.join(fails)}")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())

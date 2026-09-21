"""
POP MART's feed is global, and three of its habits can each cost a store silently:

  country "United States" on a Mississauga roboshop   -> the label is not evidence of a country
  " R3S-E950"  a store code shipped with a leading space -> identity must not depend on typing
  "Rosemont, Illinois 60018"  full state names          -> the tail parser must not rewrite cities

The fixture is a real slice of the 21 Sep 2026 capture. Its New York row is the one that caught
the first attempt at full-state-name support, which turned "New York, NY 10007" into "NY, NY".

Run: .venv/bin/python tests/test_popmart.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from chain_atlas.adapters.popmart import PopMartUSAdapter  # noqa: E402
from chain_atlas.geo import state_from_point  # noqa: E402

RAW = json.loads((Path(__file__).parent / "fixtures" / "popmart_sample.json").read_text())


def main():
    recs = PopMartUSAdapter().parse(RAW)
    by_code = {r.store_code: r for r in recs}
    fails = []

    def check(label, got, want):
        ok = got == want
        print(f"  {'PASS' if ok else 'FAIL'}  {label}: {got}" + ("" if ok else f"  (want {want})"))
        if not ok:
            fails.append(label)

    # 7 rows in, the United Kingdom one filtered out by country.
    check("non-US rows are filtered by country", len(recs), 6)
    check("no UK store survives", "POSUK14" in by_code, False)

    check("full state name -> abbreviation", by_code["POSUS25"].state, "IL")
    check("...and the city is not rewritten", by_code["POSUS25"].city, "Rosemont")
    check("full state name -> TX", by_code["POSUS32"].state, "TX")

    # The regression that full-state-name support introduced and the tests caught.
    check("a city named after a state survives", by_code["POSUS33"].city, "New York")
    check("...with its own state intact", by_code["POSUS33"].state, "NY")

    check("store codes are stripped", "R3S-E950" in by_code, True)
    check("two roboshops at one address stay apart",
          len({by_code["R3S-E950"].store_code, by_code["R3S-E850"].store_code}), 2)

    # The feed calls this one American. The coordinate is Mississauga, Ontario. parse() keeps it —
    # filtering by geography is normalise()'s job — but no US state may be invented for it.
    mi = by_code["R2Y-C712"]
    check("the Mississauga row claims no US state", mi.state, None)
    check("...and point-in-polygon agrees it is not in one",
          state_from_point(mi.lat, mi.lon), None)

    check("every store has a code", all(r.store_code for r in recs), True)
    check("every store has a coordinate", all(r.lat and r.lon for r in recs), True)

    print("\n" + ("ALL PASS" if not fails else f"{len(fails)} FAILED: {fails}"))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())

"""
normalise() is the one gate every US record passes, and its job is to refuse foreign stores that a
feed mislabels as American. Two ways that happens, both seen live:

  a coordinate in no US state, state blank   POP MART's Mississauga, Ontario roboshop
  a non-US state in the state field          MIXUE's "Richmond, BC" (British Columbia, Canada)

A state field is not proof of country. These tests hold the line.

Run: .venv/bin/python tests/test_normalise.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from chain_atlas.adapters.base import StoreRecord  # noqa: E402
from chain_atlas.geo import US_STATES  # noqa: E402
from chain_atlas.run import normalise  # noqa: E402


class A:
    country = "US"


def rec(state=None, lat=None, lon=None, city=None):
    return StoreRecord(store_code="x", name="n", addr_raw="a", city=city, state=state,
                       zip=None, lat=lat, lon=lon, trading=True, temp_closed=False, flags={})


def main():
    fails = []

    def check(label, got, want):
        ok = got == want
        print(f"  {'PASS' if ok else 'FAIL'}  {label}: {got}" + ("" if ok else f"  (want {want})"))
        if not ok:
            fails.append(label)

    check("BC is not a US state", "BC" in US_STATES, False)
    check("PR and GU are", "PR" in US_STATES and "GU" in US_STATES, True)

    # Richmond, BC: a Canadian point with a foreign state — must be dropped as outside the US.
    keep, outside = normalise(A(), [rec(state="BC", lat=49.187, lon=-123.130)])
    check("a BC store is dropped", len(keep), 0)
    check("...and counted as outside", len(outside), 1)

    # A real US store with a valid state and a US point survives untouched.
    keep, outside = normalise(A(), [rec(state="NY", lat=40.71, lon=-74.01)])
    check("a NY store is kept", len(keep), 1)
    check("...and its state stands", keep[0].state, "NY")

    # A blank state with a US coordinate is rescued by the point (existing behaviour, still holds).
    keep, _ = normalise(A(), [rec(state=None, lat=40.71, lon=-74.01)])
    check("blank state rescued from the point", keep[0].state, "NY")

    print("\n" + ("ALL PASS" if not fails else f"{len(fails)} FAILED: {fails}"))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())

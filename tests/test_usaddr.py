"""
The state map is only as good as this parser, so every real-world variant that has actually
appeared in a capture gets a case here. The four at the top are the ones that silently dropped
stores from the state totals on 21 Sep 2026 before the parser was rewritten.

Run: .venv/bin/python tests/test_usaddr.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from us_chain_atlas.usaddr import split_tail  # noqa: E402

CASES = [
    # (address, expected city, state, zip)
    ("20 City Boulevard West Suite 916, Orange CA 92868", "Orange", "CA", "92868"),
    ("14006 Riverside Dr Space 249A  San Fernando Valley, CA 91423",
     "San Fernando Valley", "CA", "91423"),
    ("Westfield Century City, 10250 Santa Monica Blvd, Los Angeles, CA-90067, USA",
     "Los Angeles", "CA", "90067"),
    ("555 6th Ave, New York, NY 10011, United States", "New York", "NY", "10011"),
    ("1065 Brea Mall, Brea, CA 92821", "Brea", "CA", "92821"),
    ("133 4th Avenue, Manhattan, NY 10003", "Manhattan", "NY", "10003"),
    ("81-18 Roosevelt Avenue, Queens, NY 11372", "Queens", "NY", "11372"),
    ("3390 South State Street, South Salt Lake, UT 84115", "South Salt Lake", "UT", "84115"),
    ("178 Harvard Street, Brookline, MA 02446", "Brookline", "MA", "02446"),
    ("1 Main St, Washington, DC 20001", "Washington", "DC", "20001"),
    ("500 Ala Moana Blvd, Honolulu, HI 96813-1234", "Honolulu", "HI", "96813"),
    # A ZIP+4 keeps only the five-digit ZIP, above. Below: nothing to read.
    ("no address at all", None, None, None),
    ("", None, None, None),
    (None, None, None, None),
]

# A two-letter token that is not a state must not become one, or a street called "1 Mall Dr"
# starts contributing to Massachusetts.
NEGATIVE = [
    "100 Broadway, Somewhere, ZZ 12345",
    "42 High St, Anytown, QQ 99999",
]


def main():
    fails = []
    for addr, city, st, zc in CASES:
        got = split_tail(addr)
        ok = got == (city, st, zc)
        print(f"  {'PASS' if ok else 'FAIL'}  {got}" + ("" if ok else f" want {(city, st, zc)}") +
              f"   <- {addr!r}")
        if not ok:
            fails.append(addr)
    for addr in NEGATIVE:
        got = split_tail(addr)
        ok = got[1] is None
        print(f"  {'PASS' if ok else 'FAIL'}  rejects non-state {got}   <- {addr!r}")
        if not ok:
            fails.append(addr)
    print(f"\n{'ALL PASS' if not fails else 'FAILURES: ' + str(len(fails))}")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())

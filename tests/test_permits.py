"""
The permit watchers share two functions that carry the whole burden of not embarrassing the
project: the name matcher that must not turn BISCOTTI into Cotti, and the street fingerprint that
must make one source's address line up with another's despite every formatting difference. Both
are pure, so both are tested here even though the watchers themselves talk to live data.

Run: .venv/bin/python tests/test_permits.py
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from permit_common import classify, street_key  # noqa: E402


def main():
    fails = []

    def check(label, got, want):
        ok = got == want
        print(f"  {'PASS' if ok else 'FAIL'}  {label}: {got!r}" + ("" if ok else f"  (want {want!r})"))
        if not ok:
            fails.append(label)

    # Whole-term matching, the Overture lesson in a new dataset.
    check("BISCOTTI is not Cotti", classify("BISCOTTI"), [])
    check("COTTI COFFEE is Cotti", classify("COTTI COFFEE"), ["cotti"])
    check("HEY TEA matches heytea", classify("HEY TEA @ NYU"), ["heytea"])
    check("a US alias resolves", classify("NAISNOW TEA & BAKERY"), ["nayuki"])
    check("Tai Er without a space still resolves", classify("TAIER FISH"), ["taier"])
    check("a tea shop that merely contains YANG is not Yang's",
          classify("CHUN YANG TEA"), [])
    check("plain word does not match", classify("YANG'S KITCHEN"), [])  # not the braised-chicken brand

    # Street fingerprints must survive unit codes, mall suites and city/state tails so the same
    # store from two sources matches.
    pairs = [
        ("227 W VALLEY BLVD 118B", "227 W Valley Blvd #198C, San Gabriel, CA 91776"),
        ("775 AMERICANA WAY E-16", "775 Americana Way, Space E-16, Glendale, CA 91210"),
        ("3525 W CARSON ST # 239B", "3525 W Carson St, Torrance, CA 90503"),
        ("1600 S AZUSA AVE #174 & 178", "1600 S Azusa Ave Unit 178, City of Industry, CA"),
    ]
    for a, b in pairs:
        ka, kb = street_key(a), street_key(b)
        check(f"same building matches: {a[:20]}", ka == kb and ka != "", True)

    # Different buildings must NOT collide, and an address with no house number anchors nothing.
    check("different streets stay apart",
          street_key("100 MAIN ST") == street_key("200 MAIN ST"), False)
    check("no house number -> no key", street_key("Westfield Century City"), "")

    print("\n" + ("ALL PASS" if not fails else f"{len(fails)} FAILED: {fails}"))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())

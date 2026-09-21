"""
register.json is hand-edited, which makes its validator the only thing standing between a
careful record and a pile of half-remembered claims. These tests check that the validator
actually refuses the mistakes a person makes while typing at midnight — an undated count, a
presence with no source, a duplicated pair — and that the real file passes.

Run: .venv/bin/python tests/test_register.py
"""
import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from chain_atlas import register  # noqa: E402

GOOD = {
    "as_of": "2026-09-21",
    "markets": {"SG": {"name": "Singapore", "region": "Southeast Asia"}},
    "chains": {"luckin": {"name": "Luckin", "name_zh": "瑞幸", "format": "coffee", "global": "x"}},
    "entries": [{"chain": "luckin", "market": "SG", "status": "present", "locations": 82,
                 "locations_as_of": "2026-03-31", "first_opened": "2023-03-31",
                 "precision": "day", "confidence": "high", "reviewed": "2026-09-21",
                 "sources": ["https://example.invalid/"]}],
}


def main():
    fails = []

    def check(label, got, want=True):
        ok = got == want
        print(f"  {'PASS' if ok else 'FAIL'}  {label}" + ("" if ok else f"  (got {got})"))
        if not ok:
            fails.append(label)

    def broken(mutate):
        d = copy.deepcopy(GOOD)
        mutate(d)
        return register.validate(d)

    check("a well-formed entry validates", register.validate(GOOD), [])

    # The rule that matters most: a number with no date attached is a rumour.
    p = broken(lambda d: d["entries"][0].pop("locations_as_of"))
    check("undated count is rejected", any("locations_as_of" in x for x in p))

    p = broken(lambda d: (d["entries"][0].pop("sources"), d["entries"][0].pop("note", None)))
    check("presence with no source and no note is rejected", any("source" in x for x in p))

    p = broken(lambda d: d["entries"].append(copy.deepcopy(d["entries"][0])))
    check("duplicate chain/market pair is rejected", any("duplicate" in x for x in p))

    p = broken(lambda d: d["entries"][0].update(status="maybe"))
    check("unknown status is rejected", any("status" in x for x in p))

    p = broken(lambda d: d["entries"][0].update(confidence="prettysure"))
    check("unknown confidence is rejected", any("confidence" in x for x in p))

    p = broken(lambda d: d["entries"][0].update(chain="nosuchchain"))
    check("unknown chain is rejected", any("unknown chain" in x for x in p))

    p = broken(lambda d: d["entries"][0].update(market="ZZ"))
    check("unknown market is rejected", any("unknown market" in x for x in p))

    p = broken(lambda d: d["entries"][0].pop("precision"))
    check("a date with no stated precision is rejected", any("precision" in x for x in p))

    p = broken(lambda d: d["entries"][0].pop("reviewed"))
    check("missing review date is rejected", any("reviewed" in x for x in p))

    p = broken(lambda d: d["entries"][0].update(locations=-1))
    check("negative count is rejected", any("locations" in x for x in p))

    # 'no_evidence' is a statement about the search, so it is allowed to carry no sources.
    d = copy.deepcopy(GOOD)
    d["entries"][0] = {"chain": "luckin", "market": "SG", "status": "no_evidence",
                       "locations": None, "first_opened": None, "precision": None,
                       "confidence": "medium", "reviewed": "2026-09-21", "sources": []}
    check("no_evidence needs no source", register.validate(d), [])

    # And the real file.
    real = register.load()
    check("the shipped register.json validates", register.validate(real), [])
    present = [e for e in real["entries"] if e["status"] == "present"]
    check("every 'present' row cites a source or explains itself",
          all(e.get("sources") or e.get("note") for e in present))
    counted = [e for e in real["entries"] if e.get("locations") is not None]
    check("every count carries an as-of date", all(e.get("locations_as_of") for e in counted))
    check("every count that is not high confidence says so in a note",
          all(e.get("note") for e in counted if e["confidence"] != "high"))

    print(f"\n{'ALL PASS' if not fails else 'FAILURES: ' + ', '.join(fails)}")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())

"""
MINISO's CMS is a working business system, not a dataset, and the parser that turns 462 rows
into a store count is the most intricate thing in this project. The fixture is a real slice of
the 21 Sep 2026 capture, chosen to carry every shape that matters:

  USBS, USFK, USL8   the same store entered twice by the 1 July 2026 re-import  -> must merge
  USCL, USFA         one code covering two genuinely different stores           -> must NOT merge
                     (Southlake Mall IN vs GA; Chinatown Center Houston vs Austin — same state,
                      so only distance and city separate them)
  storeCode Closed   three shut stores kept in the CMS, no address              -> must be dropped
  storeCode #N/A     real stores whose stateTag literally reads "#N/A"          -> state from address

Run: .venv/bin/python tests/test_miniso.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from chain_atlas.adapters.miniso import MinisoAdapter  # noqa: E402

RAW = json.loads((Path(__file__).parent / "fixtures" / "miniso_sample.json").read_text())


def main():
    recs = MinisoAdapter().parse(RAW)
    by_code = {}
    for r in recs:
        by_code.setdefault(r.flags.get("code"), []).append(r)
    fails = []

    def check(label, got, want):
        ok = got == want
        print(f"  {'PASS' if ok else 'FAIL'}  {label}: {got}" + ("" if ok else f"  (want {want})"))
        if not ok:
            fails.append(label)

    # 16 rows - 3 closed = 13; USBS, USFK and USL8 each merge two rows into one = 10 stores.
    check("16 rows collapse to 10 stores", len(recs), 10)
    check("re-import duplicates merge (USBS)", len(by_code.get("USBS", [])), 1)
    check("re-import duplicates merge (USFK)", len(by_code.get("USFK", [])), 1)
    check("near-identical rows merge (USL8)", len(by_code.get("USL8", [])), 1)
    check("same code, different states stays two (USCL)", len(by_code.get("USCL", [])), 2)
    check("same code, same state, 219km apart stays two (USFA)", len(by_code.get("USFA", [])), 2)
    check("closed rows are dropped", any(r.flags.get("code") == "Closed" for r in recs), False)

    # The merged row must be the usable one, not whichever happened to sort first.
    usfk = by_code["USFK"][0]
    check("merge keeps a placeable record", usfk.lat is not None, True)
    check("merge records how many rows it stood for", usfk.flags.get("merged_rows"), 2)

    # The two USCL stores are the two different Southlake Malls, and must not have the same key.
    keys = {r.store_code for r in by_code["USCL"]}
    check("distinct stores get distinct keys", len(keys), 2)
    check("USCL states", sorted(r.state for r in by_code["USCL"]), ["GA", "IN"])
    check("USFA cities differ", sorted(r.city.lower() for r in by_code["USFA"]), ["austin", "houston"])

    # stateTag is "#N/A" on these; the state has to come from the address instead.
    na = by_code.get("#N/A", [])
    check("#N/A rows are kept as real stores", len(na), 2)
    check("#N/A rows still get a state", all(r.state and len(r.state) == 2 for r in na), True)

    check("every store has a key", all(r.store_code for r in recs), True)
    check("keys are unique", len({r.store_code for r in recs}), len(recs))
    check("all trading (no Coming Soon in fixture)", all(r.trading for r in recs), True)

    # Cross-key de-duplication: the CMS carries a few shops as two rows the identity key cannot
    # join — two different real codes, or one coded and one bare wix row — at one address. These
    # are the real double-counts the site showed; _merge_same_store folds them, but must never
    # merge two genuinely distinct counters that differ by suite.
    from chain_atlas.adapters.base import StoreRecord
    from chain_atlas.adapters.miniso import _merge_same_store

    def R(code, addr, lat, lon):
        return StoreRecord(store_code=code, name="MINISO", addr_raw=addr, lat=lat, lon=lon)

    two_codes = _merge_same_store([
        R("USY5:davenport", "320 W Kimberly Rd, Davenport, IA 52806 USA", 41.56088, -90.57361),
        R("USM1:davenport", "320 W Kimberly Rd, Davenport, IA 52806", 41.56088, -90.57361)])
    check("two codes at one address merge", len(two_codes), 1)
    check("...keeping a single coded record", two_codes[0].store_code, "USY5:davenport")

    coded_and_wix = _merge_same_store([
        R("US65:new york", "490 Broadway, New York, NY 10012", 40.72193, -73.99957),
        R("wix:abc", "490 Broadway, New York, NY 10012", 40.72193, -73.99957)])
    check("coded + bare wix row at one address merge", len(coded_and_wix), 1)
    check("...preferring the coded record", coded_and_wix[0].store_code, "US65:new york")

    two_suites = _merge_same_store([
        R("USAA:mall", "100 Mall Dr Ste 100, Anytown, CA 90000", 34.0, -118.0),
        R("USBB:mall", "100 Mall Dr Ste 200, Anytown, CA 90000", 34.00005, -118.00005)])
    check("two suites at one mall stay two stores", len(two_suites), 2)

    print(f"\n{'ALL PASS' if not fails else 'FAILURES: ' + ', '.join(fails)}")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())

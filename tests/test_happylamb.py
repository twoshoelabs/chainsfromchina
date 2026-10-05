"""
Happy Lamb's US list is plain-text addresses pasted from a Google Sheet, and three of its habits
can each cost or invent a store silently:

  the Google-Sheets span repeats each address in a data-sheets-value attribute  -> must dedup to one
  "Las Vegas NV 89119" / "Murray UT 84107" omit the comma before the state      -> must still parse
  a CSS "rgba(0,0,0,0.1) 12px 34px" tuple sits in the page                       -> must NOT parse

The fixture is a trimmed real slice of the 5 Oct 2026 locations page.

Run: .venv/bin/python tests/test_happylamb.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from chain_atlas.adapters.happylamb import HappyLambAdapter, _addresses  # noqa: E402

HTML = (Path(__file__).parent / "fixtures" / "happylamb_sample.html").read_text(encoding="utf-8")


def main():
    addrs = _addresses(HTML)
    recs = HappyLambAdapter().parse(sorted(addrs))
    by_state = {r.state: r for r in recs}
    fails = []

    def check(label, got, want):
        ok = got == want
        print(f"  {'PASS' if ok else 'FAIL'}  {label}: {got}" + ("" if ok else f"  (want {want})"))
        if not ok:
            fails.append(label)

    # six real rows; the duplicated Cupertino span collapses to one, and the CSS tuple is not a store
    check("exactly the six real addresses parse", len(recs), 6)
    check("the repeated Cupertino span dedups to one",
          sum(1 for r in recs if r.city == "Cupertino"), 1)

    # the comma-less NV/UT rows still resolve to the right state + city
    check("no-comma Nevada row parses its state", by_state["NV"].state, "NV")
    check("...and its city", by_state["NV"].city, "Las Vegas")
    check("no-comma Utah row parses its state", by_state["UT"].state, "UT")
    check("...and its city", by_state["UT"].city, "Murray")

    # a city named 37th Ave in Flushing keeps NY (the hyphenated house number must survive)
    check("Flushing NY row intact", by_state["NY"].city, "Flushing")

    check("every row carries a state", all(r.state for r in recs), True)
    check("every row carries a ZIP", all(r.zip for r in recs), True)
    check("every row is trading", all(r.trading for r in recs), True)

    print("\n" + ("ALL PASS" if not fails else f"{len(fails)} FAILED: {fails}"))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())

"""
The China-store-count dataset is Pro intelligence a reader may lean on, so every entry must carry a count,
an as_of and a source (an undated number is a rumour), and best_count must prefer the mainland figure over
a worldwide total. These tests validate the shipped dataset and pin the helpers.

Run: .venv/bin/python tests/test_china_stores.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from chain_atlas import china_stores  # noqa: E402


def main():
    fails = []

    def check(label, got, want=True):
        ok = got == want
        print(("PASS" if ok else "FAIL"), label, "" if ok else f"(got {got!r}, want {want!r})")
        if not ok:
            fails.append(label)

    # the shipped dataset is valid (every count dated + sourced)
    errs = china_stores.validate()
    check("shipped china_stores.json validates (0 errors)", errs, [])

    d = china_stores.load()
    brands = d.get("brands", {})
    check("has a meaningful seed (>=30 chains)", len(brands) >= 30, True)
    check("filing-sourced rows carry mainland/overseas where split", brands["mixue"].get("china"), 55356)
    check("filing-sourced Mixue total", brands["mixue"].get("total"), 59823)
    check("Mixue is high confidence", brands["mixue"].get("confidence"), "high")

    # best_count prefers china over total
    check("best_count prefers mainland", china_stores.best_count({"china": 100, "total": 500}), 100)
    check("best_count falls back to total", china_stores.best_count({"total": 500}), 500)

    # validate catches a bad entry
    bad = {"brands": {"x": {"china": 10}, "y": {"total": 5, "as_of": "2025", "source": "s"},
                      "z": {"as_of": "2025", "source": "s"}}}
    be = china_stores.validate(bad)
    check("flags missing as_of/source", any("x:" in e for e in be), True)
    check("flags no count", any("z:" in e for e in be), True)
    check("accepts a complete entry (y not flagged)", any("y:" in e for e in be), False)

    print("\n" + ("ALL PASS" if not fails else f"{len(fails)} FAIL: " + ", ".join(fails)))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())

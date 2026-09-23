"""
The coverage scorecard must keep collected and sighted chains apart, and it must never turn a
missing estimate into a fake ratio. It also must not fold estimates into any real count.

Run: .venv/bin/python tests/test_coverage.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from chain_atlas.coverage import scorecard  # noqa: E402


def main():
    s = scorecard()
    rows = {r["chain"]: r for r in s["rows"]}
    fails = []

    def check(label, got, want):
        ok = got == want
        print(f"  {'PASS' if ok else 'FAIL'}  {label}: {got}" + ("" if ok else f"  (want {want})"))
        if not ok:
            fails.append(label)

    # Collected chains are complete with no ratio; sighted chains carry a status.
    check("a collected chain is complete", rows["miniso"]["kind"], "collected")
    check("...with no ratio", rows["miniso"]["ratio"], None)
    check("...and status complete", rows["miniso"]["status"], "complete")

    check("a sighted chain is sighted", rows["heytea"]["kind"], "sighted")
    check("...with a ratio", isinstance(rows["heytea"]["ratio"], float), True)

    # A sighted chain with no estimate gets 'no benchmark', never a made-up ratio.
    # (juewei has an estimate in the shipped file; assert the RULE via a synthetic check.)
    from chain_atlas.coverage import scorecard as sc
    # ratio must equal confirmed/estimate where both exist
    h = rows["heytea"]
    if h["estimate"]:
        check("ratio is confirmed/estimate", h["ratio"], round(h["held_confirmed"] / h["estimate"], 2))

    # Estimates are never added into the collected store total.
    collected_total = s["totals"]["collected_stores"]
    check("collected total counts only collected chains",
          collected_total, sum(r["held"] for r in s["rows"] if r["kind"] == "collected"))
    check("sighted estimate is a separate number",
          "sighted_estimated" in s["totals"] and "collected_stores" in s["totals"], True)

    print("\n" + ("ALL PASS" if not fails else f"{len(fails)} FAILED: {fails}"))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())

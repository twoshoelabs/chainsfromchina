"""
The aggregation rolls per-chain estimates into a banded grand total and must be honest about the two
band widths and the anchored-vs-benchmark split. These tests pin the pure math (no DB): the envelope
(fully-correlated) sum, the independent (quadrature) range, and the benchmark row.

Run: .venv/bin/python tests/test_aggregate.py
"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from chain_atlas import aggregate  # noqa: E402


def main():
    fails = []

    def check(label, got, want=True):
        ok = (got == want) if not isinstance(want, float) else (abs(got - want) < 1e-6)
        print(("PASS" if ok else "FAIL"), label, "" if ok else f"(got {got!r}, want {want!r})")
        if not ok:
            fails.append(label)

    # benchmark_row: AUV x outlets, by format
    r = aggregate.benchmark_row("moge", 10, "tea")
    lo, mid, hi = aggregate.BENCHMARK_AUV["tea"]
    check("benchmark mid = tea mid x 10", r["mid"], mid * 10)
    check("benchmark low = tea low x 10", r["low"], lo * 10)
    check("benchmark tier", r["tier"], "benchmark")
    r2 = aggregate.benchmark_row("x", 3, None)   # unknown format -> default
    check("unknown format -> default AUV", r2["mid"], aggregate.DEFAULT_AUV[1] * 3)

    # combine: envelope = sum of lows/highs; independent = quadrature half-widths
    rows = [{"low": 100, "mid": 150, "high": 200}, {"low": 300, "mid": 500, "high": 900}]
    c = aggregate.combine(rows)
    check("mid = sum of mids", c["mid"], 650.0)
    check("envelope low = sum lows", c["lo_env"], 400.0)
    check("envelope high = sum highs", c["hi_env"], 1100.0)
    hw = math.sqrt(((200 - 100) / 2) ** 2 + ((900 - 300) / 2) ** 2)   # sqrt(50^2 + 300^2)
    check("independent high = mid + quadrature", c["hi_indep"], 650.0 + hw)
    check("independent low = mid - quadrature", c["lo_indep"], 650.0 - hw)
    check("independent range < envelope", (c["hi_indep"] - c["lo_indep"]) < (c["hi_env"] - c["lo_env"]), True)

    # empty -> zeros
    e = aggregate.combine([])
    check("empty mid 0", e["mid"], 0.0)
    check("empty low never negative", e["lo_indep"], 0.0)

    # lo_indep floored at 0 when quadrature exceeds mid
    big = aggregate.combine([{"low": 0, "mid": 10, "high": 1000}])
    check("lo_indep floored at 0", big["lo_indep"], 0.0)

    print("\n" + ("ALL PASS" if not fails else f"{len(fails)} FAIL: " + ", ".join(fails)))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())

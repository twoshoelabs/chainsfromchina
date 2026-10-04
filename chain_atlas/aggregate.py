"""
Site-wide US revenue aggregation — the banded grand total across every chain and outlet on the map.
This is the top of the revenue stack (docs/phase2_revenue_spec.md): it rolls the per-chain estimates into
one modeled figure for "US revenue of all China-origin chains tracked here", and is scrupulously honest
about how much of that figure rests on filings vs a rough benchmark.

TIERS. Each chain's US revenue comes from the best source it has:
  * ANCHORED — a filing-derived estimate already in `revenue_estimates` (restaurant-AUV, channel-retail,
    or regional-apportionment). High/medium confidence, the tight core of the total.
  * BENCHMARK — for a chain with no filing anchor, a rough US-industry revenue-per-store for its format
    x its US outlet count. SECONDARY and low-confidence, with wide bands; the long tail of small chains.

GRAND TOTAL, two honest widths:
  * `indep` range = mid +/- sqrt(sum of per-chain half-widths^2) — the realistic range if chains' errors
    are largely independent (they mostly are: different brands, sectors, data sources). This is the
    headline range.
  * `envelope` = [sum of lows, sum of highs] — the conservative width if every chain erred the same way
    at once (fully correlated). Reported as the outer bound.

MEASURED/MODELED WALL. Every number here is MODELED and a RANGE. The report states what share of the
total is filing-anchored vs benchmark, and the per-chain tier, so a reader never mistakes the benchmark
tail for measured fact. Outlet counts are the site's own count (census 'open' stores + confirmed
sightings), roboshops excluded. DB-only / Pro tier — never written to the public site.
"""
import math
from datetime import datetime, timezone

# US-industry annual revenue per storefront (USD) by format, for chains with NO filing anchor. (low, mid,
# high). Still SECONDARY/estimated, but REFINED 2026-10-04 using disclosed home-market per-store economics
# as a comparator instead of pure guesswork, so the bands are tighter than before.
#
# METHOD: US per-store ~ China per-store GMV x a US premium. US menu prices run ~2.5-4x China, partly
# offset by lower US store volumes (less footfall density), so net ~2-3.5x; cross-checked against US
# industry norms. LIMITATIONS (why bands stay meaningfully wide): format/volume/maturity differ, US stores
# are often larger, and a franchisor's *reported* revenue is not the same as store GMV. The anchored US
# outliers (Haidilao ~US$8M, Pop Mart ~US$4.4M) are NOT used to set these.
# Disclosed comparators (China unless noted): tea mass ~RMB1.37M/store (Auntea Jenny) ~US$190k; tea premium
# ~US$390k (Nayuki self-op) / ~US$645k (Chagee); hotpot/full-service ~US$1.08M blended (Tai Er; overseas
# ~2x higher); coffee US ~US$0.40-0.45M (Luckin US, new/ramping).
BENCHMARK_AUV = {
    "tea":          (440_000,   580_000,   820_000),   # 190k China x ~3 (premium tails higher); was 350-950
    "coffee":       (400_000,   600_000,   850_000),   # Luckin US ~0.45M (ramping); was 450-1150
    "hotpot":     (1_500_000, 2_600_000, 4_000_000),   # Tai Er overseas ~2x blended; was 1.2-4.5M
    "restaurant": (1_000_000, 1_600_000, 2_400_000),   # Tai Er blended ~US$1.08M, US higher; was 900k-2.8M
    "fastfood":     (600_000,   950_000, 1_400_000),   # QSR (Wallace/Zhengxin)
    "bakery":       (400_000,   650_000,   950_000),
    "snack":        (350_000,   550_000,   850_000),
    "toys":         (800_000, 1_500_000, 2_800_000),
    "lifestyle":    (800_000, 1_500_000, 2_800_000),
    "apparel":    (1_200_000, 2_200_000, 4_000_000),   # flagship SoHo-type stores run high
    "beauty":       (600_000, 1_200_000, 2_000_000),
    "convenience":(1_000_000, 2_500_000, 4_500_000),
    "supermarket":(2_000_000, 4_000_000, 7_000_000),
    "grocery":    (1_000_000, 2_500_000, 4_500_000),
    "electronics":(1_000_000, 2_500_000, 4_500_000),
}
DEFAULT_AUV = (500_000, 1_000_000, 1_800_000)   # unknown/other format
BENCHMARK_METHODS = {"v1-benchmark"}            # method_versions that are NOT filing-anchored


def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def benchmark_row(brand: str, n: int, fmt: str | None) -> dict:
    """A benchmark estimate: US-industry revenue-per-store for the format x outlet count."""
    lo, mid, hi = BENCHMARK_AUV.get(fmt or "", DEFAULT_AUV)
    return {"brand": brand, "outlets": n, "tier": "benchmark", "method": "sector-benchmark",
            "format": fmt, "low": lo * n, "mid": mid * n, "high": hi * n}


def combine(rows: list[dict]) -> dict:
    """
    name:      combine
    purpose:   Roll a set of per-chain {low,mid,high} into a banded subtotal (pure; no DB).
    returns:   {mid, lo_env, hi_env, lo_indep, hi_indep} — the envelope (fully-correlated) and the
               independent (quadrature) ranges.
    """
    if not rows:
        return {"mid": 0.0, "lo_env": 0.0, "hi_env": 0.0, "lo_indep": 0.0, "hi_indep": 0.0}
    mid = sum(r["mid"] for r in rows)
    lo_env = sum(r["low"] for r in rows)
    hi_env = sum(r["high"] for r in rows)
    hw = math.sqrt(sum(((r["high"] - r["low"]) / 2.0) ** 2 for r in rows))
    return {"mid": mid, "lo_env": lo_env, "hi_env": hi_env,
            "lo_indep": max(0.0, mid - hw), "hi_indep": mid + hw}


def us_outlets_by_chain(con) -> dict:
    """Per-chain US outlet count on the SITE's definition: census 'open' stores + confirmed (non
    'coming_soon') sightings. Reuses geojson.build so it matches the map exactly; roboshops are already
    excluded there (vending_robo is not an 'open' storefront feature)."""
    from . import geojson
    fc = geojson.build(con)
    out: dict = {}
    for f in fc["features"]:
        p = f.get("properties", {})
        ch, st, kd = p.get("chain"), p.get("status"), p.get("kind")
        is_outlet = (kd == "store" and st == "open") or (kd == "sighting" and st != "coming_soon")
        if ch and is_outlet:
            out[ch] = out.get(ch, 0) + 1
    return out


def _anchored(con) -> dict:
    """brand -> the best filing-anchored us_total estimate {low,mid,high,method}. Filing methods win
    over any 'v1-benchmark' row; ties keep the first."""
    rows: dict = {}
    for r in con.execute(
            "SELECT brand_id,method_version,low,mid,high FROM revenue_estimates WHERE scope='us_total'"):
        rows.setdefault(r[0], []).append({"method": r[1], "low": r[2], "mid": r[3], "high": r[4]})
    best = {}
    for b, rs in rows.items():
        filing = [x for x in rs if x["method"] not in BENCHMARK_METHODS]
        best[b] = (filing or rs)[0]
    return best


def _formats(con) -> dict:
    from . import register
    try:
        us = register.us_status()
    except Exception:                                            # noqa: BLE001
        return {}
    return {b: info.get("format") for b, info in us.items()}


def grand_total(con) -> dict:
    """
    name:      grand_total
    purpose:   The banded US-revenue grand total across every tracked chain with US outlets.
    returns:   {rows, total, anchored, benchmark, coverage, generated}. Each row carries its tier so the
               report can show what rests on filings vs benchmark. Read-only.
    """
    outlets = us_outlets_by_chain(con)
    anchored = _anchored(con)
    fmt = _formats(con)
    rows = []
    for brand, n in outlets.items():
        a = anchored.get(brand)
        if a and a["method"] not in BENCHMARK_METHODS:
            rows.append({"brand": brand, "outlets": n, "tier": "anchored", "method": a["method"],
                         "format": fmt.get(brand), "low": a["low"], "mid": a["mid"], "high": a["high"]})
        else:
            rows.append(benchmark_row(brand, n, fmt.get(brand)))
    rows.sort(key=lambda r: -r["mid"])
    anc = [r for r in rows if r["tier"] == "anchored"]
    ben = [r for r in rows if r["tier"] == "benchmark"]
    total = combine(rows)
    return {
        "rows": rows, "total": total, "anchored": combine(anc), "benchmark": combine(ben),
        "coverage": {
            "chains": len(rows), "outlets": sum(r["outlets"] for r in rows),
            "anchored_chains": len(anc), "anchored_outlets": sum(r["outlets"] for r in anc),
            "benchmark_chains": len(ben), "benchmark_outlets": sum(r["outlets"] for r in ben),
            "anchored_share_of_mid": (combine(anc)["mid"] / total["mid"]) if total["mid"] else 0.0,
        },
        "generated": _utcnow(),
    }


def _m(x: float) -> str:
    return f"${x/1e9:.2f}B" if abs(x) >= 1e9 else f"${x/1e6:.0f}M"


def report(con) -> dict:
    """Print a readable grand-total report and return the structure."""
    g = grand_total(con)
    t, cov = g["total"], g["coverage"]
    print("US REVENUE — modeled grand total across China-origin chains (ALL figures MODELED, ranges)\n")
    print(f"  GRAND TOTAL (mid):  {_m(t['mid'])}")
    print(f"    likely range:     {_m(t['lo_indep'])} – {_m(t['hi_indep'])}   (independent combination)")
    print(f"    outer envelope:   {_m(t['lo_env'])} – {_m(t['hi_env'])}   (fully-correlated bound)\n")
    print(f"  Anchored (filings): {_m(g['anchored']['mid'])}  "
          f"({cov['anchored_chains']} chains / {cov['anchored_outlets']} outlets; "
          f"{cov['anchored_share_of_mid']*100:.0f}% of the total)")
    print(f"  Benchmark (tail):   {_m(g['benchmark']['mid'])}  "
          f"({cov['benchmark_chains']} chains / {cov['benchmark_outlets']} outlets; low confidence)\n")
    print(f"  Coverage: {cov['chains']} chains, {cov['outlets']} US outlets.\n")
    print("  Top chains:")
    for r in g["rows"][:12]:
        tag = "anchor" if r["tier"] == "anchored" else "bench "
        print(f"    {r['brand']:14} {r['outlets']:4}  [{tag}] {_m(r['mid']):>7}  "
              f"({_m(r['low'])}–{_m(r['high'])})")
    return g

"""
Opening pace — how fast a chain is adding stores, derived from its DATED store counts rather than
typed by hand. A Pro-tier intelligence dimension: "net +N stores/year (+X%)" is the momentum signal
that sits beside a chain's current size and its US footprint.

SOURCE OF THE COUNTS. Every dated count comes from somewhere already measured and cited: a
`store_count` row in `financial_anchors` (filing-sourced), and the current snapshot in
`manual/china_stores.json` (filing 'high' / press 'medium'). Pace is computed between consecutive
dated points — it is a DERIVATION of measured numbers, never an estimate, and it inherits the
weakest confidence of the two endpoints. With fewer than two dated counts it reports "insufficient
history" rather than inventing a trend.

PRO ONLY — like china_stores, this rides the Pro export, never the public map/data. See
docs/phase2_revenue_spec.md and [[cfc-analytics-paywall]]. `python -m chain_atlas openings`.
"""
from datetime import date

from . import china_stores


def _period_date(p) -> date | None:
    """Best-effort end-date for a period string: ISO date, 'FY2025', 'H1 2025'/'1H2025', 'Q3 2025'."""
    if not p:
        return None
    s = str(p).strip()
    try:
        return date.fromisoformat(s[:10])
    except ValueError:
        pass
    import re
    m = re.search(r"(20\d{2})", s)
    if not m:
        return None
    y = int(m.group(1))
    low = s.lower()
    if "h1" in low or "1h" in low or "q2" in low:
        return date(y, 6, 30)
    if "q1" in low:
        return date(y, 3, 31)
    if "q3" in low or "9m" in low:
        return date(y, 9, 30)
    return date(y, 12, 31)              # FY / H2 / Q4 / bare year -> year end


def series(con, brand: str) -> list[dict]:
    """Every dated store count we hold for a brand, oldest first, deduped by date (filing wins)."""
    pts: dict[str, dict] = {}
    # china_stores snapshot (one dated point)
    v = china_stores.load().get("brands", {}).get(brand)
    if v and china_stores.best_count(v) is not None and v.get("as_of"):
        d = _period_date(v["as_of"])
        if d:
            pts[d.isoformat()] = {"date": d.isoformat(), "count": china_stores.best_count(v),
                                  "source": v.get("source"), "confidence": v.get("confidence")}
    # filing anchors (store_count rows across periods) — these take precedence on a shared date
    if con is not None:
        for r in con.execute(
                "SELECT period, value, source, confidence FROM financial_anchors"
                " WHERE brand_id=? AND metric='store_count' AND value IS NOT NULL", (brand,)):
            d = _period_date(r["period"])
            if d:
                pts[d.isoformat()] = {"date": d.isoformat(), "count": r["value"],
                                      "source": r["source"], "confidence": r["confidence"]}
    return [pts[k] for k in sorted(pts)]


_WEAKEST = {"high": 0, "medium": 1, "low": 2, None: 2}


def pace(con, brand: str) -> list[dict]:
    """Net adds between consecutive dated counts, with an annualized rate and % growth."""
    pts = series(con, brand)
    out = []
    for a, b in zip(pts, pts[1:]):
        d0, d1 = date.fromisoformat(a["date"]), date.fromisoformat(b["date"])
        days = (d1 - d0).days
        if days <= 0:
            continue
        net = (b["count"] or 0) - (a["count"] or 0)
        yrs = days / 365.25
        conf = max((a["confidence"], b["confidence"]), key=lambda c: _WEAKEST.get(c, 2))
        out.append({
            "from": a["date"], "to": b["date"], "days": days,
            "from_count": a["count"], "to_count": b["count"], "net": net,
            "per_year": round(net / yrs, 1),
            "pct_per_year": (round((net / a["count"]) / yrs * 100, 1) if a["count"] else None),
            "confidence": conf})
    return out


def report(con) -> dict:
    brands = china_stores.load().get("brands", {})
    # include any brand that has >=1 china_stores snapshot or filing store_count row
    cand = set(brands)
    if con is not None:
        cand |= {r[0] for r in con.execute(
            "SELECT DISTINCT brand_id FROM financial_anchors WHERE metric='store_count'")}
    rows, thin = [], []
    for b in sorted(cand):
        p = pace(con, b)
        (rows if p else thin).append(b)
    print(f"OPENING PACE — Pro intelligence (derived from dated store counts)\n")
    print(f"  {'chain':14} {'window':23} {'from→to':>16} {'net/yr':>8} {'%/yr':>7} cf")
    n = 0
    for b in rows:
        last = pace(con, b)[-1]
        n += 1
        pct = f"{last['pct_per_year']:+.1f}%" if last["pct_per_year"] is not None else "   –"
        print(f"  {b:14} {last['from']}→{last['to']:10} "
              f"{int(last['from_count']):>7,}→{int(last['to_count']):<7,} {last['per_year']:>+8,.0f} "
              f"{pct:>7} {(last['confidence'] or '')[:3]}")
    print(f"\n  {n} chain(s) with a computable pace; {len(thin)} with only one dated count "
          f"(insufficient history — need a second dated filing/snapshot).")
    return {"with_pace": n, "insufficient": len(thin)}

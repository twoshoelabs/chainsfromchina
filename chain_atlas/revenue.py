"""
Revenue model (Phase 2). Turns officially-disclosed financial ANCHORS (SEC/EDGAR, HKEX, FDD Item 19)
plus our US store count into MODELED per-outlet and chain-US-total revenue RANGES. Everything written
here is modeled, carries a low/mid/high band, and traces back to the financial_anchors it used.

See docs/phase2_revenue_spec.md. The pilot is Super Hi / Haidilao — the one case whose filing lets
the per-outlet figure be cross-checked two independent ways (daily-rate x days vs segment-rev / stores),
which validates the whole pipeline before it fans out to chains that only disclose a segment total.
"""
import json
from datetime import datetime, timezone

METHOD_VERSION = "v1-auv-flat"      # flat per-chain AUV; format/metro/maturity modifiers are v2
OPERATING_DAYS = 365                # restaurants trade ~year-round; the disclosed daily average is
                                    # revenue / (restaurants x calendar days), confirmed by the cross-check


def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# --- Pilot anchors: Super Hi International (Haidilao's overseas operator; Nasdaq HDL / HKEX 9658) ---
# FY2025 results, announced 31 Mar 2026. Figures hand-read from the cited filing per the spec's manual
# fallback (§4.1); each carries its page reference. A later EDGAR/HKEX parser replaces the hardcoded
# values without any schema change.
SUPERHI_FY2025 = {
    "brand_id": "haidilao",
    "period": "2025",
    "source": "SEC/EDGAR — Super Hi International Holding Ltd, FY2025 results (6-K) + 20-F",
    "source_url": "https://www.sec.gov/Archives/edgar/data/1995306/000110465926042370/hdl-20251231x20f.htm",
    # (metric, value, unit, page_ref, confidence)
    "anchors": [
        ("overseas_segment", 840800.0, "USD_thousands", "FY2025 total revenue US$840.8M (+8.0% YoY)", "high"),
        ("americas_revenue", 164695.0, "USD_thousands", "FY2025 revenue by geographical region — North America (20.8% of total)", "high"),
        ("auv",                  22.6, "USD_thousands_per_day", "FY2025 North America average daily revenue per restaurant (US$22.6k)", "high"),
        ("store_count",          20.0, "restaurants", "North America Haidilao restaurants (~20, as of 30 Jun 2025)", "medium"),
    ],
}


def collect_superhi(con, now: str | None = None) -> int:
    """
    name:      collect_superhi
    purpose:   Record Super Hi / Haidilao's disclosed FY2025 financial anchors.
    arguments: con — DB connection; now — UTC stamp (defaults to real now).
    returns:   number of NEW anchor rows written.
    effects:   INSERTs into financial_anchors. Never updates or deletes. Idempotent: dedupe on
               (brand_id, period, metric), so re-running adds nothing.
    other:     Values are hand-read from the cited filing (manual fallback); the EDGAR/HKEX auto-parser
               is the next step and will reuse this exact table + metrics.
    """
    now = now or _utcnow()
    a = SUPERHI_FY2025
    have = {r[0] for r in con.execute(
        "SELECT metric FROM financial_anchors WHERE brand_id=? AND period=?",
        (a["brand_id"], a["period"]))}
    n = 0
    for metric, value, unit, page_ref, conf in a["anchors"]:
        if metric in have:
            continue
        con.execute(
            "INSERT INTO financial_anchors(brand_id,period,metric,value,unit,page_ref,source,"
            "source_url,retrieved_at,confidence) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (a["brand_id"], a["period"], metric, value, unit, page_ref, a["source"], a["source_url"], now, conf))
        n += 1
    con.commit()
    return n


def us_store_count(con, brand_id: str) -> int:
    """Our census count of open ('active') US outlets for a brand — the model's denominator."""
    return con.execute(
        "SELECT COUNT(*) FROM stores WHERE chain_id=? AND country='US' AND status='active'",
        (brand_id,)).fetchone()[0]


def _anchors(con, brand_id: str, period: str) -> dict:
    rows = con.execute(
        "SELECT anchor_id,metric,value,unit FROM financial_anchors WHERE brand_id=? AND period=?",
        (brand_id, period)).fetchall()
    return {r[1]: {"id": r[0], "value": r[2], "unit": r[3]} for r in rows}


def estimate(con, brand_id: str, period: str = "2025", now: str | None = None) -> dict:
    """
    name:      estimate
    purpose:   Compute MODELED per-outlet and US-total revenue for a brand from its anchors x our US
               store count, as a low/mid/high range, and write them to revenue_estimates.
    arguments: con; brand_id; period; now.
    returns:   a summary dict (per-outlet + US-total mid, store count, band, cross-check disagreement).
    effects:   Replaces this brand/period/method's prior estimate rows, then INSERTs fresh ones.
               Modeled only — never writes an observed figure.
    other:     v1 is a flat per-chain AUV. The chain US total uses OUR current store count (the census),
               not the filing's, because ours is more current; the segment-revenue figure is kept as a
               cross-check. See docs/phase2_revenue_spec.md §5.
    """
    now = now or _utcnow()
    anc = _anchors(con, brand_id, period)
    has_derivable = "americas_revenue" in anc and "store_count" in anc and anc["store_count"]["value"]
    if "auv" not in anc and not has_derivable:
        return {"brand": brand_id, "period": period, "skipped": "no AUV anchor and none derivable"}

    used, band, auv_annual, xcheck = [], 0.25, None, None

    # 1) AUV (annual, USD). Prefer a directly-disclosed daily rate (tighter band); else derive it.
    if "auv" in anc and anc["auv"]["unit"] == "USD_thousands_per_day":
        auv_annual = anc["auv"]["value"] * 1000 * OPERATING_DAYS
        used.append(anc["auv"]["id"]); band = 0.12
    if has_derivable:
        derived = anc["americas_revenue"]["value"] * 1000 / anc["store_count"]["value"]
        used += [anc["americas_revenue"]["id"], anc["store_count"]["id"]]
        if auv_annual is None:
            auv_annual = derived
        else:
            xcheck = round(abs(derived - auv_annual) / auv_annual, 4)   # agreement of the two methods

    n = us_store_count(con, brand_id)
    as_of = con.execute(
        "SELECT MAX(last_seen) FROM stores WHERE chain_id=? AND country='US' AND status='active'",
        (brand_id,)).fetchone()[0]
    per_mid, tot_mid = auv_annual, auv_annual * n

    meta = {"anchors": used, "fx": "disclosed in USD", "operating_days": OPERATING_DAYS,
            "crosscheck_disagreement": xcheck, "method": METHOD_VERSION}
    note = f"Modeled v1: AUV US${per_mid/1e6:.2f}M x {n} US outlets = US${tot_mid/1e6:.1f}M."
    if xcheck is not None:
        note += f" Two-method cross-check agrees to {xcheck*100:.1f}%."

    con.execute("DELETE FROM revenue_estimates WHERE brand_id=? AND period=? AND method_version=?",
                (brand_id, period, METHOD_VERSION))

    def _ins(scope, store_id, mid):
        con.execute(
            "INSERT INTO revenue_estimates(brand_id,scope,store_id,period,low,mid,high,unit,"
            "method_version,anchors_used,store_count_used,store_count_as_of,modeled,notes,generated_at)"
            " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,1,?,?)",
            (brand_id, scope, store_id, period, mid * (1 - band), mid, mid * (1 + band), "USD",
             METHOD_VERSION, json.dumps(meta), n, as_of, note, now))

    _ins("us_total", None, tot_mid)
    for (sid,) in con.execute(
            "SELECT store_id FROM stores WHERE chain_id=? AND country='US' AND status='active'", (brand_id,)):
        _ins("outlet", sid, per_mid)
    con.commit()
    return {"brand": brand_id, "period": period, "us_outlets": n, "band": band,
            "per_outlet_usd_mid": round(per_mid), "us_total_usd_mid": round(tot_mid),
            "crosscheck_disagreement": xcheck}


def run(con, now: str | None = None) -> dict:
    """
    name:      run
    purpose:   The revenue pass: collect the pilot anchors (Super Hi) and compute Haidilao's US
               revenue estimate end to end.
    arguments: con; now.
    returns:   a dict summary.
    effects:   INSERTs into financial_anchors + revenue_estimates (both idempotent).
    """
    now = now or _utcnow()
    wrote = collect_superhi(con, now)
    est = estimate(con, "haidilao", "2025", now)
    return {"anchors_written": wrote, "estimate": est}

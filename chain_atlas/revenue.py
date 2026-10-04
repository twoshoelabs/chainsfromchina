"""
Revenue model (Phase 2). Turns officially-disclosed financial ANCHORS (SEC/EDGAR, HKEX, FDD Item 19)
plus our US store count into MODELED per-outlet and chain-US-total revenue RANGES. Everything written
here is modeled, carries a low/mid/high band, traces back to the financial_anchors it used, and must
pass a unit-economics reality check before it is written.

See docs/phase2_revenue_spec.md. The pilot is Super Hi / Haidilao.

The reality check (the real one, not a circular arithmetic restatement): from the chain's own disclosed
`spend_per_guest` and `table_turnover`, the modeled AUV implies a daily customer count and a peak
simultaneous-seated count. That peak must fit inside a plausible restaurant's seating — ideally under
the fire-code occupant load once we have it. If the implied house is absurd, the AUV is wrong and the
estimate is flagged, not published.

Capacity data (a TODO, not built here): the hard cap is a store's **occupant load**, set by the fire
marshal on its Certificate of Occupancy under the fire code, and often its health-permit **seating
capacity**. These are official/first-party (city building & fire departments, county health open-data,
records requests) and fit the project's legal posture — but they are per-city and uneven, so they are a
Phase-2/3 **permit/CO collector** (the `stores.square_footage` column already exists to receive size,
and `pipeline_signals` already has a `permit` signal type). Until then the check uses turnover x a
plausible seating envelope, and `square_footage` when a store happens to carry it.
"""
import json
from datetime import datetime, timezone

METHOD_VERSION = "v1-auv-flat"      # flat per-chain AUV; format/metro/maturity modifiers are v2
OPERATING_DAYS = 365                # the disclosed daily average is revenue / (restaurants x calendar days)

# Unit-economics reality-check envelope.
PARTY_SIZE  = 3.5                   # assumed average party; informational only — peak-seated is party-free
SEATS_MIN, SEATS_MAX = 15, 800      # a sit-down restaurant's plausible simultaneous-seating range
SQFT_PER_SEAT = 15                  # ~IBC net dining area per person, for an optional square-footage cross-check


def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# --- Pilot anchors: Super Hi International (Haidilao's overseas operator; Nasdaq HDL / HKEX 9658) ---
# FY2025 results, announced 31 Mar 2026, VERIFIED against the primary results release (not a search
# summary). Only figures that actually appear in that release are recorded. Note what is NOT here: a
# North-America *revenue* total — the release discloses per-restaurant operating metrics by region, not
# a regional revenue breakdown, so NA revenue is derived from the daily rate, never asserted as fact.
SUPERHI_FY2025 = {
    "brand_id": "haidilao",
    "period": "2025",
    "source": "Super Hi International FY2025 results (SEC Form 6-K / press release, 31 Mar 2026)",
    "source_url": "https://www.globenewswire.com/news-release/2026/03/31/3265236/0/en/super-hi-reports-unaudited-financial-results-for-the-fourth-quarter-and-full-year-2025.html",
    # (metric, value, unit, page_ref, confidence)
    "anchors": [
        ("overseas_segment", 840800.0, "USD_thousands", "FY2025 total (overseas) revenue US$840.8M (+8.0% YoY)", "high"),
        ("auv",                  22.6, "USD_thousands_per_day", "Operating data — North America average daily revenue per restaurant, US$22.6k (FY2025)", "high"),
        ("spend_per_guest",      39.9, "USD", "Operating data — North America average spending per guest, US$39.9 (FY2025)", "high"),
        ("table_turnover",        4.0, "turns_per_day", "Operating data — North America average table turnover, 4.0x/day (FY2025)", "high"),
        ("store_count",          22.0, "restaurants", "Number of restaurants — North America, 22 as of 31 Dec 2025", "high"),
    ],
}


def collect_superhi(con, now: str | None = None) -> int:
    """
    name:      collect_superhi
    purpose:   Record Super Hi / Haidilao's disclosed, primary-verified FY2025 anchors.
    arguments: con — DB connection; now — UTC stamp (defaults to real now).
    returns:   number of NEW anchor rows written.
    effects:   INSERTs into financial_anchors. Idempotent: dedupe on (brand_id, period, metric).
    other:     Hand-read from the cited release (manual fallback); the EDGAR/HKEX auto-parser is next.
    """
    now = now or _utcnow()
    a = SUPERHI_FY2025
    have = {r[0] for r in con.execute(
        "SELECT metric FROM financial_anchors WHERE brand_id=? AND period=?", (a["brand_id"], a["period"]))}
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


def _median_sqft(con, brand_id: str):
    vals = [r[0] for r in con.execute(
        "SELECT square_footage FROM stores WHERE chain_id=? AND country='US' AND status='active' "
        "AND square_footage IS NOT NULL AND square_footage>0", (brand_id,))]
    if not vals:
        return None
    vals.sort(); n = len(vals)
    return vals[n // 2] if n % 2 else (vals[n // 2 - 1] + vals[n // 2]) / 2


def _anchors(con, brand_id: str, period: str) -> dict:
    rows = con.execute(
        "SELECT anchor_id,metric,value,unit FROM financial_anchors WHERE brand_id=? AND period=?",
        (brand_id, period)).fetchall()
    return {r[1]: {"id": r[0], "value": r[2], "unit": r[3]} for r in rows}


def unit_economics(auv_daily_usd: float, anc: dict, sqft=None):
    """
    name:      unit_economics
    purpose:   The reality check. From the disclosed spend-per-guest and table-turnover, work out the
               customer volume a modeled AUV implies and test it against a plausible seated house.
    returns:   (status, detail). status True = reconciles; False = implausible (caller must FLAG and
               NOT write); None = cannot check (no spend/turnover anchor) — caller writes but marks it.
    other:     peak_seated = guests/day / turnover is a full-house snapshot and is party-size-free; it
               is what must sit under real seating / the fire-code occupant load. When a store carries
               square_footage, also require peak_seated <= ~ occupant load (sqft / SQFT_PER_SEAT).
    """
    if "spend_per_guest" not in anc or "table_turnover" not in anc:
        return None, {"reason": "no spend/guest or turnover anchor; unit economics unchecked"}
    spend = anc["spend_per_guest"]["value"]; turns = anc["table_turnover"]["value"]
    if not spend or not turns or spend <= 0 or turns <= 0:
        return None, {"reason": "non-positive spend/turnover anchor"}
    guests_day = auv_daily_usd / spend
    peak_seated = guests_day / turns
    detail = {"guests_per_day": round(guests_day), "peak_seated": round(peak_seated),
              "implied_tables": round(peak_seated / PARTY_SIZE), "seats_envelope": [SEATS_MIN, SEATS_MAX]}
    ok = SEATS_MIN <= peak_seated <= SEATS_MAX
    if sqft:
        occ = sqft / SQFT_PER_SEAT
        detail["occupant_load_est"] = round(occ)
        ok = ok and peak_seated <= occ * 1.1
    return ok, detail


def estimate(con, brand_id: str, period: str = "2025", now: str | None = None) -> dict:
    """
    name:      estimate
    purpose:   Compute MODELED per-outlet + US-total revenue = AUV x our US store count, as a low/mid/
               high range — but only AFTER the unit-economics check passes.
    arguments: con; brand_id; period; now.
    returns:   a summary dict. If the reality check fails, returns {flagged: ...} and writes NOTHING.
    effects:   Replaces this brand/period/method's prior estimate rows, then INSERTs fresh ones.
    other:     v1 = flat per-chain AUV. US total uses OUR current store count. See the Phase-2 spec §5.
    """
    now = now or _utcnow()
    anc = _anchors(con, brand_id, period)

    # 1) AUV (annual, USD): prefer a disclosed daily rate (tighter band); else derive from a disclosed
    #    segment revenue / segment store count. No AUV -> can't model.
    band, auv_annual = 0.25, None
    if "auv" in anc and anc["auv"]["unit"] == "USD_thousands_per_day":
        auv_annual = anc["auv"]["value"] * 1000 * OPERATING_DAYS; band = 0.12
    elif "americas_revenue" in anc and "store_count" in anc and anc["store_count"]["value"]:
        auv_annual = anc["americas_revenue"]["value"] * 1000 / anc["store_count"]["value"]
    if auv_annual is None:
        return {"brand": brand_id, "period": period, "skipped": "no AUV anchor and none derivable"}

    # 2) Reality check — implied customers must fit a plausible house. Flag (don't publish) if not.
    sqft = _median_sqft(con, brand_id)
    status, econ = unit_economics(auv_annual / OPERATING_DAYS, anc, sqft)
    if status is False:
        return {"brand": brand_id, "period": period, "flagged": "unit economics implausible — not written",
                "auv_usd": round(auv_annual), "unit_economics": econ}

    # 3) Totals.
    n = us_store_count(con, brand_id)
    as_of = con.execute(
        "SELECT MAX(last_seen) FROM stores WHERE chain_id=? AND country='US' AND status='active'",
        (brand_id,)).fetchone()[0]
    per_mid, tot_mid = auv_annual, auv_annual * n

    used = [v["id"] for k, v in anc.items() if k in ("auv", "americas_revenue", "store_count",
                                                     "spend_per_guest", "table_turnover")]
    meta = {"anchors": used, "fx": "disclosed in USD", "operating_days": OPERATING_DAYS,
            "unit_economics": econ, "method": METHOD_VERSION}
    note = f"Modeled v1: AUV US${per_mid/1e6:.2f}M x {n} US outlets = US${tot_mid/1e6:.1f}M."
    note += (f" Reality check: ~{econ['guests_per_day']} guests/day, ~{econ['peak_seated']} seated at peak." if status
             else f" Reality check {econ.get('reason', 'unavailable')}.")

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
            "unit_economics": econ, "checked": status}


def run(con, now: str | None = None) -> dict:
    """The revenue pass: collect the pilot anchors (Super Hi) and model Haidilao's US revenue."""
    now = now or _utcnow()
    wrote = collect_superhi(con, now)
    return {"anchors_written": wrote, "estimate": estimate(con, "haidilao", "2025", now)}

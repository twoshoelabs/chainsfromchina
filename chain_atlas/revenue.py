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
RETAIL_METHOD_VERSION = "v1-retail-channel"   # channel-isolated store AUV x our store count
REGION_METHOD_VERSION = "v1-region-apportion"  # disclosed regional revenue / region stores, US by share
OPERATING_DAYS = 365                # the disclosed daily average is revenue / (restaurants x calendar days)

# Unit-economics reality-check envelope (restaurant model).
PARTY_SIZE  = 3.5                   # assumed average party; informational only — peak-seated is party-free
SEATS_MIN, SEATS_MAX = 15, 800      # a sit-down restaurant's plausible simultaneous-seating range
SQFT_PER_SEAT = 15                  # ~IBC net dining area per person, for an optional square-footage cross-check

# Retail model reality-check envelope: a plausible annual per-store sales range (USD) for a mall/
# flagship specialty retailer. Pop Mart's modeled AUV must land inside this or the estimate is flagged.
RETAIL_AUV_MIN_USD, RETAIL_AUV_MAX_USD = 300_000, 25_000_000
REGION_BAND = 0.30                  # regional revenue disclosed, but US apportioned by store share +
                                    # US/Canada mix + period-vs-count mismatch -> wider than channel
RETAIL_BAND = 0.25                  # channel rev + store count both disclosed, but a regional average
                                    # applied to US + FX + store-maturity mix -> wider than a direct AUV

# RMB -> USD. Pop Mart reports only in RMB and states no translation rate, so we apply an external
# period-average and record it in `anchors_used` for reproducibility. 2025 average per FRED AEXCHUS
# (annual average 7.1875); the IRS yearly average agrees to ~7.19.
FX_RMB_PER_USD = {"2025": 7.187}
FX_SOURCE = "FRED AEXCHUS 2025 annual average (7.1875); company states no rate"


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
    "model": "restaurant_auv",   # store revenue == restaurant sales; AUV x count is clean
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

# Pop Mart (HKEX 9992). RETAIL and multi-channel — and the channel mix is the whole point: dividing
# ALL Americas revenue by stores implied ~US$14M/store, nonsense, because in the Americas ONLINE is
# 64% of revenue and offline retail stores are only 29.4%. The FY2025 announcement discloses the
# Americas channel split verbatim (p.31), so we isolate the offline retail-store channel and divide
# by the disclosed Americas store count to get a real per-store AUV (~US$4.4M), then apply it to our
# own US standard-store census (roboshops excluded, matching the filing's "retail stores"). All
# figures are primary from the HKEXnews announcement (text-extracted from the PDF), so confidence is
# high; the only modeled inputs are the RMB->USD rate and the Americas-average-applied-to-US step.
POPMART_FY2025 = {
    "brand_id": "popmart",
    "period": "2025",
    "model": "retail_channel",
    "source": "Pop Mart FY2025 annual results announcement (HKEXnews, 25 Mar 2026; year ended 31 Dec 2025)",
    "source_url": "https://www1.hkexnews.hk/listedco/listconews/sehk/2026/0325/2026032500285.pdf",
    # Revenue figures are RMB '000 exactly as the filing reports them; FX is applied in the model.
    "anchors": [
        ("group_revenue",               37120052.0, "RMB_thousands", "Revenue by regions, p.27 (= Note 3/4 group total); +184.7% YoY", "high"),
        ("americas_revenue",             6806189.0, "RMB_thousands", "Revenue by regions — Americas, p.27 (18.3% of group, +748.4% YoY; ALL channels)", "high"),
        ("americas_retail_store_rev",    2003799.0, "RMB_thousands", "Americas channel split — offline retail stores, p.31 (29.4% of Americas)", "high"),
        ("americas_roboshop_rev",         231730.0, "RMB_thousands", "Americas channel split — roboshops, p.31 (3.4%)", "high"),
        ("americas_online_rev",          4353581.0, "RMB_thousands", "Americas channel split — online, p.31 (64.0%)", "high"),
        ("group_retail_store_rev",      17254326.0, "RMB_thousands", "Note 4 business lines — retail store sales, PRC+Overseas summed, p.10-11", "high"),
        ("americas_retail_store_count",       64.0, "retail_stores", "Offline channels store count @31 Dec 2025, p.24/p.31 (US not split out)", "high"),
    ],
}

# Fan-out order; add more parents here as data, not code.
# MINISO (NYSE 9896-equivalent; NYSE:MNSO / HKEX:9896). RETAIL, part-franchised. Its FY2025 20-F
# discloses a NORTH AMERICA region revenue (US+Canada) but NO US-only figure and NO NA channel split, so
# the channel-isolation retail model (Pop Mart's) does not apply; we use regional apportionment instead.
# Important: MINISO's reported revenue books FULL sales only for directly-operated stores and WHOLESALE
# for its "Retail Partner" (franchised) stores, so revenue-per-store here is the chain's REPORTED revenue
# per outlet, not gross consumer retail sales (which the filing does not disclose). All figures primary.
MINISO_FY2025 = {
    "brand_id": "miniso",
    "period": "2025",
    "model": "retail_region",
    "source": "MINISO Group FY2025 Form 20-F (SEC EDGAR, filed 24 Apr 2026; acc 0001104659-26-048172)",
    "source_url": "https://www.sec.gov/Archives/edgar/data/1815846/000110465926048172/mnso-20251231x20f.htm",
    "anchors": [
        ("group_revenue",            21443827.0, "RMB_thousands", "Consolidated revenue FY2025 (income statement / revenue note)", "high"),
        ("north_america_revenue",     3342918.0, "RMB_thousands", "Segment geographic note — North America (US+Canada) revenue FY2025 (R86)", "high"),
        ("north_america_store_count",     461.0, "stores", "MINISO FY2025 results release (ir.miniso.com, 31 Mar 2026) — North America stores at 31 Dec 2025 (up from 350); period-consistent with FY2025 revenue", "high"),
        ("miniso_brand_revenue",     19524901.0, "RMB_thousands", "Segment note — MINISO brand external revenue FY2025 (R84)", "high"),
        ("toptoy_revenue",            1915618.0, "RMB_thousands", "Segment note — TOP TOY brand external revenue FY2025 (R84)", "high"),
    ],
}

# Chagee (NASDAQ:CHA). SINGLE reportable segment — the FY2025 20-F states "no geographical revenue
# information is presented", so there is NO US/North America revenue to model. US appears only as a store
# count (3 teahouses at 31 Dec 2025; our census now ~11) and the one per-store metric (avg monthly GMV)
# is explicitly CHINA-ONLY. Anchors captured for the record; the US estimate is deferred — applying a
# China GMV to US stores would be a Tier-5 benchmark at best, not written here.
CHAGEE_FY2025 = {
    "brand_id": "chagee",
    "period": "2025",
    "model": "single_segment_no_us",
    "source": "Chagee Holdings FY2025 Form 20-F (SEC EDGAR, filed 29 Apr 2026; acc 0001104659-26-050766)",
    "source_url": "https://www.sec.gov/Archives/edgar/data/2013649/000110465926050766/cha-20251231x20f.htm",
    "anchors": [
        ("group_revenue",             12907407.0, "RMB_thousands", "Total net revenues FY2025 (Results of Operations, Item 5.A)", "high"),
        ("company_owned_rev",          1490316.0, "RMB_thousands", "Net revenues — company-owned teahouses FY2025 (11.5%)", "high"),
        ("franchised_rev",            11417091.0, "RMB_thousands", "Net revenues — franchised teahouses FY2025 (88.5%; mostly product sales to franchisees)", "high"),
        ("total_gmv",                    31582.3, "RMB_millions", "Total GMV (China + overseas) FY2025 (Item 4.B)", "high"),
        ("store_count_total",             7453.0, "stores", "Total teahouses at 31 Dec 2025 (Item 4.B)", "high"),
        ("us_store_count",                   3.0, "stores", "US teahouses at 31 Dec 2025 (Item 4.B geographic table; 0 in 2023/2024)", "high"),
        ("china_monthly_gmv_per_store",    387.0, "RMB_thousands_per_month", "Avg monthly GMV per teahouse — China only (Key Operating Data, Item 5.A)", "high"),
    ],
}

PARENTS = [SUPERHI_FY2025, POPMART_FY2025, MINISO_FY2025, CHAGEE_FY2025]


def collect(con, parent: dict, now: str | None = None) -> int:
    """
    name:      collect
    purpose:   Record one parent's disclosed, primary-verified financial anchors.
    arguments: con; parent — a PARENTS entry; now — UTC stamp.
    returns:   number of NEW anchor rows written.
    effects:   INSERTs into financial_anchors. Idempotent: dedupe on (brand_id, period, metric).
    """
    now = now or _utcnow()
    have = {r[0] for r in con.execute(
        "SELECT metric FROM financial_anchors WHERE brand_id=? AND period=?",
        (parent["brand_id"], parent["period"]))}
    n = 0
    for metric, value, unit, page_ref, conf in parent["anchors"]:
        if metric in have:
            continue
        con.execute(
            "INSERT INTO financial_anchors(brand_id,period,metric,value,unit,page_ref,source,"
            "source_url,retrieved_at,confidence) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (parent["brand_id"], parent["period"], metric, value, unit, page_ref,
             parent["source"], parent["source_url"], now, conf))
        n += 1
    con.commit()
    return n


def collect_all(con, now: str | None = None) -> int:
    """Ingest every PARENTS entry's anchors. Returns total new rows written."""
    now = now or _utcnow()
    return sum(collect(con, p, now) for p in PARENTS)


def us_store_count(con, brand_id: str, exclude_formats: tuple = ()) -> int:
    """Our census count of open ('active') US outlets for a brand — the model's denominator.
    `exclude_formats` drops formats that are not storefronts for this model: the retail model passes
    ('vending_robo',) so Pop Mart roboshops are not counted as stores (they are a separate channel,
    and the filing's 'retail stores' count excludes them too)."""
    q = "SELECT COUNT(*) FROM stores WHERE chain_id=? AND country='US' AND status='active'"
    args = [brand_id]
    for fmt in exclude_formats:
        q += " AND COALESCE(format,'')!=?"; args.append(fmt)
    return con.execute(q, args).fetchone()[0]


def _us_store_ids(con, brand_id: str, exclude_formats: tuple = ()):
    q = "SELECT store_id FROM stores WHERE chain_id=? AND country='US' AND status='active'"
    args = [brand_id]
    for fmt in exclude_formats:
        q += " AND COALESCE(format,'')!=?"; args.append(fmt)
    return [r[0] for r in con.execute(q, args)]


def _median_sqft(con, brand_id: str):
    vals = [r[0] for r in con.execute(
        "SELECT square_footage FROM stores WHERE chain_id=? AND country='US' AND status='active' "
        "AND square_footage IS NOT NULL AND square_footage>0", (brand_id,))]
    if not vals:
        return None
    vals.sort(); n = len(vals)
    return vals[n // 2] if n % 2 else (vals[n // 2 - 1] + vals[n // 2]) / 2


def _median_occupant_load(con, brand_id: str):
    """Median OFFICIAL occupant load across active US stores that carry one (the capacity probe fills
    it). None when no store has an official number yet — the check then falls back to square footage."""
    vals = [r[0] for r in con.execute(
        "SELECT occupant_load FROM stores WHERE chain_id=? AND country='US' AND status='active' "
        "AND occupant_load IS NOT NULL AND occupant_load>0", (brand_id,))]
    if not vals:
        return None
    vals.sort(); n = len(vals)
    return vals[n // 2] if n % 2 else (vals[n // 2 - 1] + vals[n // 2]) / 2


def _anchors(con, brand_id: str, period: str) -> dict:
    rows = con.execute(
        "SELECT anchor_id,metric,value,unit FROM financial_anchors WHERE brand_id=? AND period=?",
        (brand_id, period)).fetchall()
    return {r[1]: {"id": r[0], "value": r[2], "unit": r[3]} for r in rows}


def unit_economics(auv_daily_usd: float, anc: dict, sqft=None, occupant_load=None):
    """
    name:      unit_economics
    purpose:   The reality check. From the disclosed spend-per-guest and table-turnover, work out the
               customer volume a modeled AUV implies and test it against a plausible seated house.
    returns:   (status, detail). status True = reconciles; False = implausible (caller must FLAG and
               NOT write); None = cannot check (no spend/turnover anchor) — caller writes but marks it.
    other:     peak_seated = guests/day / turnover is a full-house snapshot and is party-size-free; it
               is what must sit under real seating / the fire-code occupant load. The occupant-load cap
               is applied in priority order: an OFFICIAL occupant_load (from the capacity probe's CO /
               assembly permit) when we have one, else a square-footage estimate (sqft / SQFT_PER_SEAT).
               The official number is a hard cap (no slack); the sqft estimate keeps a 10% cushion since
               it is itself modeled.
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
    if occupant_load:
        detail["occupant_load"] = int(occupant_load)
        detail["occupant_load_src"] = "official"
        ok = ok and peak_seated <= occupant_load
    elif sqft:
        occ = sqft / SQFT_PER_SEAT
        detail["occupant_load_est"] = round(occ)
        detail["occupant_load_src"] = "sqft_estimate"
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
    #    Prefer an official occupant load (capacity probe) over the square-footage estimate.
    sqft = _median_sqft(con, brand_id)
    occ = _median_occupant_load(con, brand_id)
    status, econ = unit_economics(auv_annual / OPERATING_DAYS, anc, sqft, occupant_load=occ)
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


# Formats in our census that are NOT storefronts for the retail revenue model. Pop Mart roboshops
# (vending_robo) are a separate disclosed channel and are excluded from the filing's store count too.
RETAIL_STORE_FORMATS_EXCLUDED = ("vending_robo",)


def retail_estimate(con, brand_id: str, period: str = "2025", now: str | None = None) -> dict:
    """
    name:      retail_estimate
    purpose:   MODELED per-outlet + US-total revenue for a multi-channel RETAIL chain, by ISOLATING the
               offline retail-store channel from a disclosed regional channel split and dividing by the
               disclosed regional store count to get a real per-store AUV — then applying it to our own
               US standard-store census. This is the channel-aware answer to "dividing all Americas
               revenue by stores is nonsense" (online is most of it).
    arguments: con; brand_id; period; now.
    returns:   a summary dict. Flags (and writes NOTHING) if the per-store AUV is implausible for the
               format, or if the modeled US total would exceed disclosed GROUP retail-store revenue.
    effects:   Replaces this brand/period/method's estimate rows, then INSERTs fresh ones.
    other:     Needs the channel split (americas_retail_store_rev + americas_retail_store_count) and an
               FX rate; without them it SKIPS, never guessing. Roboshops are excluded from both the
               numerator (channel) and the denominator (store count).
    """
    now = now or _utcnow()
    anc = _anchors(con, brand_id, period)
    fx = FX_RMB_PER_USD.get(period)
    need = ("americas_retail_store_rev", "americas_retail_store_count")
    if not all(k in anc for k in need) or not fx:
        return {"brand": brand_id, "period": period,
                "skipped": "need Americas retail-store channel revenue + store count and an FX rate"}
    count = anc["americas_retail_store_count"]["value"]
    if not count or count <= 0:
        return {"brand": brand_id, "period": period, "skipped": "no disclosed store count to divide by"}

    # 1) Channel-isolated regional retail-store revenue in USD, and the Americas-average per-store AUV.
    region_store_rev_usd = anc["americas_retail_store_rev"]["value"] * 1000 / fx
    auv_usd = region_store_rev_usd / count

    # 2) Reality check — the per-store number must be plausible for a retail storefront. Flag if not.
    if not (RETAIL_AUV_MIN_USD <= auv_usd <= RETAIL_AUV_MAX_USD):
        return {"brand": brand_id, "period": period,
                "flagged": "per-store AUV implausible for retail format — not written",
                "auv_usd": round(auv_usd), "envelope": [RETAIL_AUV_MIN_USD, RETAIL_AUV_MAX_USD]}

    # 3) Our US storefront census (roboshops excluded, matching the filing's 'retail stores').
    n = us_store_count(con, brand_id, exclude_formats=RETAIL_STORE_FORMATS_EXCLUDED)
    as_of = con.execute(
        "SELECT MAX(last_seen) FROM stores WHERE chain_id=? AND country='US' AND status='active'",
        (brand_id,)).fetchone()[0]
    per_mid, tot_mid = auv_usd, auv_usd * n

    # 4) Hard guardrail — a US store-channel total above GROUP (worldwide) retail-store revenue is
    #    impossible, so flag and write nothing.
    if "group_retail_store_rev" in anc:
        group_cap_usd = anc["group_retail_store_rev"]["value"] * 1000 / fx
        if tot_mid > group_cap_usd:
            return {"brand": brand_id, "period": period,
                    "flagged": "modeled US total exceeds disclosed GROUP retail-store revenue — not written",
                    "us_total_usd": round(tot_mid), "group_cap_usd": round(group_cap_usd)}

    # Our current US count will usually exceed the filing's 31 Dec 2025 Americas count: the footprint
    # grew. That makes the US total a current-footprint annualized RUN-RATE, not a FY2025 actual.
    run_rate = n > count

    used = [v["id"] for k, v in anc.items()
            if k in ("americas_retail_store_rev", "americas_retail_store_count",
                     "americas_revenue", "group_retail_store_rev")]
    meta = {"anchors": used, "fx_rmb_per_usd": fx, "fx_source": FX_SOURCE,
            "channel": "offline retail stores (online/roboshop/wholesale excluded)",
            "region_basis": "Americas", "method": RETAIL_METHOD_VERSION,
            "auv_usd": round(auv_usd), "region_store_rev_usd": round(region_store_rev_usd)}
    note = (f"Modeled v1 (retail, channel-isolated): Americas offline retail-store revenue "
            f"US${region_store_rev_usd/1e6:.1f}M / {int(count)} disclosed Americas stores = AUV "
            f"US${auv_usd/1e6:.2f}M; x {n} US standard stores (roboshops excluded) = US${tot_mid/1e6:.0f}M.")
    if run_rate:
        note += (f" Our US count ({n}) exceeds the filing's Americas count ({int(count)}, 31 Dec 2025), "
                 f"so the total is a current-footprint annualized run-rate, not a FY2025 actual.")

    con.execute("DELETE FROM revenue_estimates WHERE brand_id=? AND period=? AND method_version=?",
                (brand_id, period, RETAIL_METHOD_VERSION))

    def _ins(scope, store_id, mid):
        con.execute(
            "INSERT INTO revenue_estimates(brand_id,scope,store_id,period,low,mid,high,unit,"
            "method_version,anchors_used,store_count_used,store_count_as_of,modeled,notes,generated_at)"
            " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,1,?,?)",
            (brand_id, scope, store_id, period, mid * (1 - RETAIL_BAND), mid, mid * (1 + RETAIL_BAND),
             "USD", RETAIL_METHOD_VERSION, json.dumps(meta), n, as_of, note, now))

    _ins("us_total", None, tot_mid)
    for sid in _us_store_ids(con, brand_id, exclude_formats=RETAIL_STORE_FORMATS_EXCLUDED):
        _ins("outlet", sid, per_mid)
    con.commit()
    return {"brand": brand_id, "period": period, "us_outlets": n, "band": RETAIL_BAND,
            "per_outlet_usd_mid": round(per_mid), "us_total_usd_mid": round(tot_mid),
            "auv_usd": round(auv_usd), "channel": "offline_retail_stores",
            "footprint_run_rate": run_rate, "fx_rmb_per_usd": fx}


def region_estimate(con, brand_id: str, period: str = "2025", now: str | None = None) -> dict:
    """
    name:      region_estimate
    purpose:   MODELED US revenue for a chain that discloses a REGIONAL revenue (e.g. North America, which
               includes the US) but NO US-only figure and NO channel split. Per-outlet = region revenue
               (FX->USD) / region store count = the chain's REPORTED revenue per store; US total = that x
               our US store count, which apportions the region to the US by store share (so the US total
               stays within the disclosed region revenue).
    arguments: con; brand_id; period; now.
    returns:   a summary dict; flags (writes nothing) if the per-store figure is implausible.
    effects:   Replaces this brand/period/method's estimate rows, then INSERTs fresh ones.
    other:     CAVEAT (in notes): for a part-franchised retailer this is the chain's reported revenue per
               outlet — FULL sales for directly-operated stores, WHOLESALE for franchised ("Retail
               Partner") stores — NOT gross consumer retail sales, which the filing does not disclose. The
               region (e.g. US+Canada) is apportioned to the US by store share; the region store count may
               be a slightly different date than the revenue, which the band absorbs.
    """
    now = now or _utcnow()
    anc = _anchors(con, brand_id, period)
    fx = FX_RMB_PER_USD.get(period)
    need = ("north_america_revenue", "north_america_store_count")
    if not all(k in anc for k in need) or not fx:
        return {"brand": brand_id, "period": period,
                "skipped": "need north_america_revenue + north_america_store_count and an FX rate"}
    region_count = anc["north_america_store_count"]["value"]
    if not region_count or region_count <= 0:
        return {"brand": brand_id, "period": period, "skipped": "no region store count"}

    region_rev_usd = anc["north_america_revenue"]["value"] * 1000 / fx
    auv_usd = region_rev_usd / region_count          # region revenue per store (company-reported basis)
    if not (RETAIL_AUV_MIN_USD <= auv_usd <= RETAIL_AUV_MAX_USD):
        return {"brand": brand_id, "period": period,
                "flagged": "per-store revenue implausible for a retail storefront — not written",
                "auv_usd": round(auv_usd), "envelope": [RETAIL_AUV_MIN_USD, RETAIL_AUV_MAX_USD]}

    n = us_store_count(con, brand_id, exclude_formats=RETAIL_STORE_FORMATS_EXCLUDED)
    as_of = con.execute(
        "SELECT MAX(last_seen) FROM stores WHERE chain_id=? AND country='US' AND status='active'",
        (brand_id,)).fetchone()[0]
    # US is a subset of the region: cap the apportioned count at the region's store count.
    n_eff = min(n, int(region_count))
    capped = n > region_count
    per_mid, tot_mid = auv_usd, auv_usd * n_eff

    used = [v["id"] for k, v in anc.items()
            if k in ("north_america_revenue", "north_america_store_count", "group_revenue")]
    meta = {"anchors": used, "fx_rmb_per_usd": fx, "fx_source": FX_SOURCE,
            "basis": "North America region revenue apportioned to US by store share",
            "region_store_count": region_count, "method": REGION_METHOD_VERSION,
            "auv_usd": round(auv_usd), "region_rev_usd": round(region_rev_usd)}
    note = (f"Modeled v1 (regional apportionment): North America revenue US${region_rev_usd/1e6:.0f}M / "
            f"{int(region_count)} NA stores = US${auv_usd/1e6:.2f}M per store; x {n_eff} US stores = "
            f"US${tot_mid/1e6:.0f}M. This is the chain's REPORTED revenue per store (full sales for "
            f"directly-operated stores, wholesale for franchised 'Retail Partner' stores), NOT gross "
            f"consumer retail sales; North America includes Canada, apportioned by store share.")
    if capped:
        note += f" NOTE: our US count ({n}) exceeds the region's store count ({int(region_count)}); capped."

    con.execute("DELETE FROM revenue_estimates WHERE brand_id=? AND period=? AND method_version=?",
                (brand_id, period, REGION_METHOD_VERSION))

    def _ins(scope, store_id, mid):
        con.execute(
            "INSERT INTO revenue_estimates(brand_id,scope,store_id,period,low,mid,high,unit,"
            "method_version,anchors_used,store_count_used,store_count_as_of,modeled,notes,generated_at)"
            " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,1,?,?)",
            (brand_id, scope, store_id, period, mid * (1 - REGION_BAND), mid, mid * (1 + REGION_BAND),
             "USD", REGION_METHOD_VERSION, json.dumps(meta), n, as_of, note, now))

    _ins("us_total", None, tot_mid)
    for sid in _us_store_ids(con, brand_id, exclude_formats=RETAIL_STORE_FORMATS_EXCLUDED):
        _ins("outlet", sid, per_mid)
    con.commit()
    return {"brand": brand_id, "period": period, "us_outlets": n, "band": REGION_BAND,
            "per_outlet_usd_mid": round(per_mid), "us_total_usd_mid": round(tot_mid),
            "auv_usd": round(auv_usd), "basis": "na_region_apportioned", "fx_rmb_per_usd": fx}


def run(con, now: str | None = None) -> dict:
    """
    name:      run
    purpose:   The revenue pass. Collect every parent's anchors, then compute each parent's estimate
               with the engine its model names: restaurant-AUV for Super Hi, channel-isolated retail
               for Pop Mart. A parent whose model has no engine yet is reported as pending.
    returns:   a dict summary.
    effects:   INSERTs into financial_anchors + revenue_estimates (both idempotent).
    """
    now = now or _utcnow()
    wrote = collect_all(con, now)
    estimates, pending = {}, {}
    for p in PARENTS:
        if p["model"] == "restaurant_auv":
            estimates[p["brand_id"]] = estimate(con, p["brand_id"], p["period"], now)
        elif p["model"] == "retail_channel":
            estimates[p["brand_id"]] = retail_estimate(con, p["brand_id"], p["period"], now)
        elif p["model"] == "retail_region":
            estimates[p["brand_id"]] = region_estimate(con, p["brand_id"], p["period"], now)
        else:
            pending[p["brand_id"]] = f"anchors captured; estimate pending the {p['model']} model"
    return {"anchors_written": wrote, "estimates": estimates, "pending": pending}

"""
Capacity & official-receipts probe — the revenue model's reality check, sourced from official records
(docs/phase2_revenue_spec.md §5, the unit-economics check). The revenue model turns a disclosed AUV into
a modeled per-outlet number; this module pulls *independent, official, per-store* facts that bound or
corroborate that number, so an implausible estimate is caught against the real world, not just against an
envelope of assumptions.

TWO KINDS OF OFFICIAL FACT, both first-party / open-data (no third-party scraping, per the legal posture):

  1. OCCUPANT LOAD — a store's fire-code maximum occupancy, set by the fire marshal on its Certificate of
     Occupancy / Place-of-Assembly permit. It is the hard cap the reality check wants: the modeled AUV
     implies a peak simultaneous-seated count (revenue.unit_economics), and that peak cannot exceed the
     occupant load. Stored on `stores.occupant_load`; revenue.unit_economics prefers it over the
     square-footage estimate once present.

     Reality, found by probing: occupant load is mostly NOT in city open-data APIs. NYC's CO datasets
     (DOB `bs8b-p36w`, DOB NOW `pkdm-hqz6`) carry only residential dwelling-unit counts, and "place of
     assembly" in the NYC catalog returns political districts — the real assembly occupant load lives on
     the CO PDF, behind a records request. So the OCC_SOURCES registry is honest about coverage: a
     jurisdiction with no machine-readable feed is reported as UNAVAILABLE and SKIPPED, never guessed.

  2. ALCOHOL RECEIPTS — Texas publishes every mixed-beverage permittee's monthly beer/wine/liquor sales
     (TX Comptroller, Socrata `naix-2893`). For a licensed restaurant this is a hard, official revenue
     floor. It does not give total revenue (alcohol is a fraction of the check), but it proves the outlet
     is trading at scale and lets `reconcile()` test the modeled AUV's implied alcohol share for sanity.
     Verified live against our Frisco and Katy Haidilao stores — names, addresses and permits all match.

TERMS / VOLUME / FALLBACK (stated before building, per the project's rule):
  * Sources: TX Comptroller open data; city building/fire open data. Public records, official APIs.
  * Terms: clean. A Socrata app token (SOCRATA_APP_TOKEN) only lifts the anonymous rate limit; optional.
  * Volume: tiny. A handful of stores per brand, a dozen monthly rows each. Diffed against what is stored.
  * Manual fallback: no network, or a source with no feed, SKIPS cleanly and records nothing fabricated.

WHERE IT WRITES. Occupant load -> `stores.occupant_load` (the revenue check reads it there). Receipts and
every probe outcome -> `pipeline_signals` as `signal_type='capacity'`, `location_id`=store_id, idempotent
on `source_url` (a stable per-store-per-period key), so a monthly refresh appends one row and re-running a
month adds nothing. These are append-only facts with provenance, exactly like the USPTO signals.
"""
import json
from datetime import datetime, timezone

from .config import SOCRATA_APP_TOKEN

# TX Comptroller — Mixed Beverage Gross Receipts (monthly, per permitted location).
TX_RECEIPTS = ("data.texas.gov", "naix-2893")

# Occupant-load feeds, keyed by the jurisdiction that issues the CO / assembly permit. Each entry is
# a callable(store, now)->record|None. Honesty over coverage: a jurisdiction with no machine-readable
# occupant-load feed is simply ABSENT here, and the probe reports those stores as unavailable rather
# than inventing a number. Add a city only once its official feed is confirmed to expose occupancy.
OCC_SOURCES: dict = {}   # e.g. ("NY", "New York"): nyc_occupant_load  -- none confirmed yet (see docstring)


def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _num(x) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


def soql(domain: str, resource: str, params: dict, fetch_fn=None) -> list:
    """
    name:      soql
    purpose:   Run one Socrata SoQL query against an official open-data portal.
    arguments: domain (e.g. 'data.texas.gov'); resource (dataset id); params (SoQL $where/$order/...);
               fetch_fn — injectable IO for tests (defaults to the shared polite, robots-checked session).
    returns:   list of row dicts (empty on any failure — the caller then skips, never guesses).
    effects:   One network request. Sends the app token header when SOCRATA_APP_TOKEN is set.
    other:     This is the ONLY function tied to Socrata's wire shape; sources below stay transport-free.
    """
    url = f"https://{domain}/resource/{resource}.json"
    if fetch_fn is None:
        from . import capture
        headers = {"Accept": "application/json"}
        if SOCRATA_APP_TOKEN:
            headers["X-App-Token"] = SOCRATA_APP_TOKEN
        try:
            resp = capture.fetch(url, method="GET", params=params, headers=headers)  # capture sets timeout
            return json.loads(resp.text)
        except Exception:                                            # noqa: BLE001
            return []
    rows = fetch_fn(url, params)
    return json.loads(rows) if isinstance(rows, (str, bytes)) else (rows or [])


def brand_tokens(con, brand_id: str) -> list:
    """
    name:      brand_tokens
    purpose:   The uppercased name tokens an official record would carry for this brand.
    arguments: con; brand_id.
    returns:   list of tokens (>=4 letters), longest first; [] if the brand is unknown.
    other:     A permittee is listed under a trading name ('HAIDILAO HOT POT'), so matching on the
               brand's distinctive word plus the store's own city/zip is specific enough to avoid
               false positives without hard-coding every permit's exact spelling.
    """
    row = con.execute("SELECT name FROM chains WHERE chain_id=?", (brand_id,)).fetchone()
    name = (row[0] if row else brand_id) or brand_id
    toks = sorted({w for w in "".join(c if c.isalpha() else " " for w in [name] for c in w).split()
                   if len(w) >= 4}, key=len, reverse=True)
    return [t.upper() for t in toks] or [brand_id.upper()]


def us_stores(con, brand_id: str, state: str | None = None) -> list:
    """Open US outlets for a brand (optionally one state), as dict rows the sources can read."""
    q = ("SELECT store_id,chain_id,addr_raw,addr_norm,city,state,zip,occupant_load FROM stores "
         "WHERE chain_id=? AND country='US' AND status='active'")
    args = [brand_id]
    if state:
        q += " AND state=?"; args.append(state)
    return [dict(r) for r in con.execute(q, args).fetchall()]


# --- Source: Texas mixed-beverage receipts -------------------------------------------------------

def tx_receipts(store: dict, tokens: list, fetch_fn=None) -> dict | None:
    """
    name:      tx_receipts
    purpose:   Pull a TX store's recent monthly alcohol receipts and summarise the trailing window.
    arguments: store (a us_stores row, must be state='TX'); tokens (brand_tokens); fetch_fn (test IO).
    returns:   a record {kind:'alcohol_receipts', period, trailing_12_usd, latest_month_usd, months,
               permit, matched_name, address, source_url} or None when nothing matches.
    effects:   Network via soql(). No DB writes (collect() persists).
    other:     Matches on brand token in location_name AND the store's own zip, so it cannot pick up a
               different permittee. 'period' is the latest reported obligation month (YYYY-MM): a new
               month yields a new signal, re-running a month is idempotent.
    """
    if (store.get("state") or "").upper() != "TX" or not store.get("zip"):
        return None
    zp = str(store["zip"]).split("-")[0].strip()
    tok = tokens[0] if tokens else ""
    where = f"upper(location_name) like '%{tok}%' and location_zip='{zp}'"
    rows = soql(*TX_RECEIPTS, {"$where": where, "$order": "obligation_end_date_yyyymmdd DESC",
                               "$limit": "24"}, fetch_fn=fetch_fn)
    if not rows:
        return None
    months = [r.get("obligation_end_date_yyyymmdd", "")[:7] for r in rows if r.get("obligation_end_date_yyyymmdd")]
    trailing = rows[:12]
    rec = {
        "kind": "alcohol_receipts",
        "period": months[0] if months else "",
        "trailing_12_usd": round(sum(_num(r.get("total_receipts")) for r in trailing)),
        "latest_month_usd": round(_num(rows[0].get("total_receipts"))),
        "months": len([m for m in months[:12]]),
        "permit": rows[0].get("tabc_permit_number") or "",
        "matched_name": rows[0].get("location_name") or "",
        "address": rows[0].get("location_address") or "",
    }
    rec["source_url"] = (f"https://{TX_RECEIPTS[0]}/resource/{TX_RECEIPTS[1]}.json"
                         f"?permit={rec['permit']}&through={rec['period']}")
    return rec


def collect(con, brand_id: str, now: str | None = None, fetch_fn=None) -> dict:
    """
    name:      collect
    purpose:   Probe every official capacity/receipts source for a brand's US stores and persist results.
    arguments: con; brand_id; now — UTC stamp; fetch_fn — injectable IO for tests.
    returns:   summary {stores, receipts_found, occupant_found, unavailable, inserted, duplicates, rows}.
    effects:   INSERTs 'capacity' rows into pipeline_signals (idempotent on source_url); sets
               stores.occupant_load when an occupant-load source returns one.
    other:     'unavailable' counts stores whose jurisdiction has no machine-readable occupant-load feed
               — a reported gap, not a failure, and never filled with a guess.
    """
    now = now or _utcnow()
    tokens = brand_tokens(con, brand_id)
    stores = us_stores(con, brand_id)
    seen = {r[0] for r in con.execute(
        "SELECT source_url FROM pipeline_signals WHERE signal_type='capacity' AND source_url IS NOT NULL")}
    summ = {"stores": len(stores), "receipts_found": 0, "occupant_found": 0, "unavailable": 0,
            "inserted": 0, "duplicates": 0, "rows": []}

    def _ins(store, summary, source, url, filed, conf, raw_ref=None):
        if url in seen:
            summ["duplicates"] += 1
            return False
        con.execute(
            "INSERT INTO pipeline_signals(signal_type,brand_id,location_id,filed_date,summary,"
            "raw_ref,source,source_url,retrieved_at,confidence) VALUES('capacity',?,?,?,?,?,?,?,?,?)",
            (brand_id, store["store_id"], filed or None, summary, raw_ref, source, url, now, conf))
        seen.add(url)
        summ["inserted"] += 1
        return True

    for s in stores:
        # 1) Occupant load, when the store's jurisdiction has a confirmed official feed.
        src = OCC_SOURCES.get((s.get("state"), s.get("city")))
        if src is not None:
            rec = src(s, now, fetch_fn=fetch_fn)
            if rec and rec.get("occupant_load"):
                con.execute("UPDATE stores SET occupant_load=? WHERE store_id=?",
                            (int(rec["occupant_load"]), s["store_id"]))
                summ["occupant_found"] += 1
                _ins(s, f"Occupant load {rec['occupant_load']} (official CO/assembly permit)",
                     rec.get("source", "city records"), rec.get("source_url", ""),
                     rec.get("filed_date", ""), "high")
        elif not s.get("occupant_load"):
            summ["unavailable"] += 1

        # 2) Texas alcohol receipts (an official per-store revenue floor).
        if (s.get("state") or "").upper() == "TX":
            r = tx_receipts(s, tokens, fetch_fn=fetch_fn)
            if r:
                summ["receipts_found"] += 1
                msg = (f"TX mixed-beverage receipts: ${r['trailing_12_usd']:,} trailing "
                       f"{r['months']} mo (latest {r['period']} ${r['latest_month_usd']:,}); "
                       f"permit {r['permit']}; {r['matched_name']}")
                if _ins(s, msg, "TX Comptroller (Mixed Beverage Gross Receipts)",
                        r["source_url"], r["period"], "high"):
                    summ["rows"].append({"store_id": s["store_id"], **r})
    con.commit()
    return summ


# --- Reconciliation: do the official receipts square with the modeled AUV? -----------------------

# A sit-down restaurant's alcohol share of total sales. Hotpot skews low (tea/soup-forward, many
# non-drinkers), full-service skews higher. Outside this generous band, either the receipts or the
# modeled AUV is suspect and the pairing is flagged for a human — this catches a grossly wrong AUV
# (e.g. a 50x overestimate drives the implied alcohol share to a fraction of a percent).
ALCOHOL_SHARE_MIN, ALCOHOL_SHARE_MAX = 0.003, 0.40


def reconcile(con, brand_id: str, period: str = "2025") -> dict:
    """
    name:      reconcile
    purpose:   Cross-check the modeled AUV against each store's official TX alcohol receipts.
    arguments: con; brand_id; period — the financial_anchors period holding the AUV.
    returns:   {auv_annual_usd, checks:[{store_id, trailing_12_usd, implied_alcohol_share, ok}], flags}.
    effects:   None (read-only).
    other:     implied_alcohol_share = official trailing-12-mo alcohol receipts / modeled annual AUV.
               A plausible share supports the AUV; an implausible one flags the pair. Read-only: it
               reports, and leaves the decision (and any estimate suppression) to revenue.estimate.
    """
    arow = con.execute(
        "SELECT value,unit FROM financial_anchors WHERE brand_id=? AND period=? AND metric='auv'",
        (brand_id, period)).fetchone()
    if not arow:
        return {"brand": brand_id, "period": period, "skipped": "no AUV anchor to reconcile against"}
    auv_annual = arow[0] * 1000 * 365 if arow[1] == "USD_thousands_per_day" else arow[0]

    checks, flags = [], 0
    # Receipts rows carry the TX Comptroller source; read the latest trailing figure per store.
    rows = con.execute(
        "SELECT location_id, summary FROM pipeline_signals WHERE signal_type='capacity' AND brand_id=? "
        "AND source='TX Comptroller (Mixed Beverage Gross Receipts)' ORDER BY retrieved_at DESC",
        (brand_id,)).fetchall()
    best = {}
    for loc, summary in rows:
        if loc in best:
            continue
        # pull the trailing dollar figure back out of the stored summary
        try:
            amt = int(summary.split("$", 1)[1].split(" ", 1)[0].replace(",", ""))
        except (IndexError, ValueError):
            continue
        best[loc] = amt
    for loc, amt in best.items():
        share = amt / auv_annual if auv_annual else 0
        ok = ALCOHOL_SHARE_MIN <= share <= ALCOHOL_SHARE_MAX
        flags += 0 if ok else 1
        checks.append({"store_id": loc, "trailing_12_usd": amt,
                       "implied_alcohol_share": round(share, 4), "ok": ok})
    return {"brand": brand_id, "period": period, "auv_annual_usd": round(auv_annual),
            "alcohol_share_band": [ALCOHOL_SHARE_MIN, ALCOHOL_SHARE_MAX],
            "checks": sorted(checks, key=lambda c: c["store_id"]), "flags": flags}


def run(con, brand_id: str = "haidilao", now: str | None = None) -> dict:
    """
    name:      run
    purpose:   The capacity pass: probe official sources for a brand's US stores, then reconcile.
    arguments: con; brand_id (default the Super Hi / Haidilao pilot); now.
    returns:   {collect: <summary>, reconcile: <summary>}.
    effects:   Network; pipeline_signals INSERTs; stores.occupant_load updates (all idempotent).
    """
    now = now or _utcnow()
    c = collect(con, brand_id, now=now)
    return {"collect": c, "reconcile": reconcile(con, brand_id)}

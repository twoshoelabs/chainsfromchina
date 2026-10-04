# Phase 2 spec — US revenue per outlet and per chain (the "Revenue & prices" engine)

Status: draft, 2026-10-04. Owner: Twoshoe Labs. This is the spec for the **revenue model** deferred
out of [Phase 1](phase1_spec.md). It is the engine behind the Pro/Team "Revenue & prices (Modeled)"
module. Prices are a sibling spec (Phase 2b); this covers **revenue only**.

## 0. The core idea

We cannot observe per-outlet revenue — these are private operations and the US arms do not file
US-only P&Ls. So revenue is a **model**, not a measurement, and it is built the only honest way:

> **Anchor on the few hard, officially-disclosed numbers we *can* get, then scale them across the
> store count we already have.**

The expensive, defensible asset is already ours: an **accurate, current US store count per chain**
(the daily census + hand-verified sightings). Revenue is then:

```
per-outlet revenue ≈ AUV (average unit volume, from a disclosed anchor)
chain US total     ≈ AUV × (our US store count)        [or a disclosed US figure directly]
```

Everything this produces is **Modeled**: it lives behind the measured/modeled wall, carries a
**Modeled** badge, shows its method, cites the anchor filing, and is a **range**, never a false-
precision point estimate.

## 1. Scope

**In Phase 2 (revenue):**
1. Stand up a **`financial_anchors` collector** against three clean, official sources — SEC/EDGAR,
   HKEX, and US state **FDD Item 19** — pulling disclosed facts (segment revenue, store count, AUV,
   same-store sales) with full provenance.
2. Add a **`revenue_estimates`** table (the modeled outputs) and a small, versioned **model** that
   turns anchors + our store count into a per-outlet and chain-US-total range.
3. Build **one collector + the model end to end on a single pilot chain** (Super Hi / Haidilao),
   exactly as Phase 1 did with USPTO, before fanning out.

**Explicitly out of scope here:** menu/list **prices** (Phase 2b); any model that needs review
velocity, foot-traffic, card-panel or POS data (gray-area/paid — forbidden by the legal posture);
SKU-level or category-mix revenue; forecasting. v1 is a flat per-chain AUV; **format / metro /
maturity modifiers are v2**, not v1.

## 2. What is and isn't an anchor

A **financial anchor** is a number a company (or a franchisor) put in an official document. Only
these three kinds of facts anchor a revenue estimate; anything else is context, never an input.

- **Segment revenue** — total revenue for a geographic segment that includes the US ("Americas",
  "North America", or "overseas" when the US is the dominant sub-market). Disclosed in annual/
  interim reports.
- **Store count** — units open at a period end, ideally by country/segment. Used both to apportion
  segment revenue to the US and as the denominator for AUV.
- **AUV / average store sales** — average revenue per unit, disclosed directly (some filings), or
  derivable (segment revenue ÷ segment store count), or taken from **FDD Item 19** for US
  franchisors (average/median gross sales per franchised unit, often by quartile).
- **Same-store sales (SSS)** growth — used only to *age* a stale AUV forward a period, never as a
  level.

Not anchors (record as context, or not at all): aggregate company revenue with no geographic split,
analyst estimates, press "sources say" figures, delivery-app GMV, our own guesses.

## 3. Data model

### 3.1 `financial_anchors` (table lands in Phase 1; filled here)

Already specced — reuse as-is:

`id, brand_id, period, metric (us_revenue|americas_revenue|auv|store_count|sss|overseas_segment),
value, unit, page_ref, source, source_url, retrieved_at, confidence`.

Conventions for this phase:
- `period` is a normalized `YYYY` (annual) or `YYYY-H1/H2` (interim); store the fiscal-period label
  verbatim in `page_ref` context if it differs.
- `unit` carries currency + magnitude (e.g. `CNY_thousands`, `USD`, `stores`). **Do not pre-convert
  FX in the anchor** — store the filed figure and the currency; FX is applied in the model with its
  own dated rate, so the raw disclosed number stays auditable.
- `metric` gains a segment qualifier where needed via a `scope` note in `page_ref` (e.g. the segment
  name as filed: "Overseas", "Americas", "North America"). If the registry grows, add an
  `americas_segment` / `na_segment` enum value rather than overloading `overseas_segment`.
- `confidence` reflects the disclosure, not the model: a number lifted from an audited annual report
  = high; from an interim/earnings-call transcript = medium; from an FDD Item 19 with a small
  reporting pool or heavy footnotes = medium/low.

### 3.2 `revenue_estimates` (new) — the modeled outputs

`id, brand_id, scope (outlet|us_total), store_id (nullable, set for outlet scope), period,
low, mid, high, unit (USD), method_version, anchors_used (json: anchor ids + weights),
store_count_used, store_count_as_of, modeled=TRUE, notes, generated_at`.

Rules:
- **`modeled` is always TRUE** here — this table never holds an observed figure.
- `anchors_used` makes every estimate reproducible: which `financial_anchors` rows fed it, the FX
  rate + date, the apportionment share, and the model version. A reader (or auditor, or a Pro
  customer) can trace a number back to a filing page.
- `store_count_used` + `store_count_as_of` pin the census snapshot the total was built from, so a
  later census change produces a *new* estimate row rather than silently mutating an old one.
- Ranges, not points: `low/mid/high` always populated; `low==mid==high` is disallowed (if an anchor
  is exact, widen by the modeled uncertainty band, see §5).

## 4. Source cards

### 4.1 SEC / EDGAR — US-listed parents (and US-listed foreign filers)

- **Source:** SEC EDGAR full-text search + the submissions/companyfacts JSON APIs, and the filed
  documents themselves (10-K/10-Q for domestic; **20-F / 6-K** for foreign private issuers listed in
  the US). https://www.sec.gov/edgar and https://data.sec.gov. Covers e.g. **Super Hi International
  (HDL)**, **Chagee (CHA)**, **Miniso (MNSO)**, **Luckin** (OTC filings where available).
- **Terms status:** CLEAN. US government work; filings are public; official APIs and bulk data
  exist; no third-party scraping. Respect the documented SEC fair-access rate limits + User-Agent
  rule.
- **Expected volume:** low. A handful of listed parents × a few filings/year. Diff against last run;
  only new periods write.
- **Cadence:** quarterly (aligned to filing calendars), plus an on-demand run when an 8-K/6-K drops.
- **What it writes:** raw capture (saved + sha256) → parsed `financial_anchors` rows (segment
  revenue, store count, AUV/SSS where disclosed) with `page_ref` = the exhibit + page/section.
- **Matching:** link `brand_id` via the company/parent entity in the entities graph; a US-listed
  China retailer with no brand match is a discovery lead, not an auto-add.
- **Manual fallback:** the figures can be read by hand from the filing PDF for the ~dozen listed
  parents if parsing fails; degrade to "skipped this period", never guess.
- **Idempotent:** dedupe on (accession number + metric + segment).

### 4.2 HKEX — Hong-Kong-listed parents

- **Source:** HKEX news/filings (annual + interim reports) via hkexnews.hk, and the issuers' IR
  pages. Covers e.g. **Mixue (2097)**, **Guming**, **Pop Mart (9992)**, **Nayuki/Naisnow (2150)**,
  **ChaPanda/Chabaidao**, **Auntea Jenny**, **Anta (2020)**, **JNBY (3306)**, **Super Hi (9658)**,
  **Miniso (9896)**.
- **Terms status:** CLEAN for the official filings (public regulatory disclosure). Read the PDF/
  HTML reports; do not scrape a paywalled data terminal. Respect robots + rate limits.
- **Expected volume:** low — semiannual reporting, ~15 issuers.
- **Cadence:** semiannual (HK interims + annuals), on-demand for a profit alert/announcement.
- **What it writes:** same as EDGAR — `financial_anchors` rows, currency usually `CNY`/`HKD`,
  `page_ref` to the segment-information note (that note is where overseas/by-region revenue and
  store counts live).
- **Matching / fallback / idempotent:** as §4.1 (dedupe on filing id + metric + segment).
- **Gotcha:** HK interims are less granular than annuals; prefer the annual for the segment split
  and use the interim only to age it forward.

### 4.3 US state franchise registries — FDD Item 19

- **Source:** state Franchise Disclosure Document registries that publish FDDs (CA DFPI, MN, WI,
  and others), specifically **Item 19 — Financial Performance Representations**. Covers the US
  **franchisors** without a useful listed parent: e.g. **YGF/Yangguofu**, **Fish With You**, and any
  chain we already flag as FDD-backed.
- **Terms status:** CLEAN. Public state filings. Download the registered FDD; read Item 19.
- **Expected volume:** very low — a few franchisors, annual FDD renewals.
- **Cadence:** annual (FDDs renew yearly), checked when our `fdd` flag flips for a chain.
- **What it writes:** `financial_anchors` rows with `metric='auv'` (average/median gross sales per
  unit; capture quartiles as separate rows when given), `page_ref` = "Item 19, Table N", plus the
  reporting-pool size as a `confidence` input.
- **Caveat:** Item 19 is **average/median gross sales**, usually for *franchised* units and often a
  self-selected reporting subset — treat as a soft AUV with medium/low confidence, and never mistake
  it for total chain revenue.

## 5. The model (anchor → estimate)

Deterministic, versioned (`method_version`), and auditable. v1:

1. **Pick the AUV.** In priority order: (a) a disclosed AUV/average-store-sales for the US/Americas
   segment; (b) **segment revenue ÷ segment store count** (derived AUV); (c) FDD Item 19 average;
   (d) if none, a **sector-format benchmark** (median AUV of same-sector chains we *do* have an
   anchor for) — flagged lowest confidence.
2. **FX + period.** Convert to USD at the period's average rate (store the rate + date in
   `anchors_used`). If the AUV is older than the current census, **age it** by disclosed SSS (capped;
   no SSS → leave as-is and widen the band).
3. **Apportion to the US.** If the anchor is "Americas"/"overseas", the US share = (our US store
   count) ÷ (segment store count from the same filing). This is exactly what the census is for.
4. **Compute.**
   - `per-outlet mid = AUV_usd`.
   - `chain US total mid = AUV_usd × (our US store count)` — **our** count (more current than the
     filing), *unless* a US/Americas **revenue** figure is disclosed directly, in which case use the
     disclosed figure for the total and derive per-outlet from it.
5. **Band (low/high).** Combine: the spread across available anchors, the FX/period-aging
   uncertainty, and a fixed model band (v1: ±25% when the only AUV is derived or benchmarked, ±12%
   when a direct AUV is disclosed). Record the band's drivers in `notes`.

v2 (later): per-outlet modifiers for **format** (kiosk vs flagship vs sit-down), **metro** (a Times
Square flagship ≠ a suburban strip-mall unit), and **maturity** (ramp curve for stores open < 12
months). v2 refines per-outlet spread while the chain total stays anchored to the same disclosed
envelope.

### 5.1 The reality check — official capacity & receipts (`chain_atlas/capacity.py`, BUILT)

Before any estimate is written, `revenue.unit_economics` turns the modeled AUV, via the chain's own
disclosed **spend-per-guest** and **table-turnover**, into an implied **peak simultaneous-seated**
count. That peak must fit a real house. The `capacity` probe pulls the official facts that bound it —
all first-party open data, no scraping:

- **Occupant load** — the fire-code maximum on a store's Certificate of Occupancy / Place-of-Assembly
  permit. Stored on `stores.occupant_load`; when present it is the **hard cap** (no slack) the check
  uses, ahead of the square-footage estimate. *Coverage is the honest limit here:* probing found
  occupant load is **not** in the queryable city open-data APIs — NYC's CO datasets (`bs8b-p36w`,
  `pkdm-hqz6`) carry only residential dwelling-unit counts, and "place of assembly" in the catalog is
  political districts. The real number lives on the CO PDF, behind a records request. So `OCC_SOURCES`
  is a registry that is **empty until a jurisdiction's feed is confirmed**; stores with no feed are
  reported `unavailable`, never guessed.
- **Alcohol receipts** — Texas publishes every mixed-beverage permittee's monthly beer/wine/liquor
  sales (TX Comptroller, Socrata `naix-2893`). For a licensed restaurant this is a hard, official
  **revenue floor**. `reconcile()` divides the official trailing-12-month receipts by the modeled
  annual AUV and checks the **implied alcohol share** against a plausible band (0.3%–40%): a sane share
  corroborates the AUV, an absurd one (e.g. a 50× overestimate drives the share to a fraction of a
  percent) flags the pair. Verified live on the two Texas Haidilao stores — Frisco (~$88k trailing,
  implied ~1.07%) and Katy (~$86k, ~1.04%) — both inside the band, so the pilot AUV is not flagged.

Writes: occupant load → `stores.occupant_load`; every probe outcome → `pipeline_signals`
(`signal_type='capacity'`, `location_id`), idempotent on a per-store-per-period `source_url`, so a
monthly refresh appends one row and re-running a month adds nothing. CLI: `python -m chain_atlas
capacity [--chain X]`.

## 6. First collector + model — the Super Hi / Haidilao pilot

Build **one source (EDGAR 20-F/6-K + HKEX 9658) and the model end to end on Super Hi International**,
then fan out. It is the gold case:

- Super Hi (Haidilao's overseas operator) discloses, by segment, **overseas revenue**, **restaurant
  count by region (incl. North America)**, and an **average daily revenue per restaurant** plus
  spend-per-guest and table-turnover — so a US per-outlet figure falls out almost directly from
  `disclosed average daily revenue per restaurant × operating days`.
- **Caution (learned the hard way):** an apparent second method —
  `(overseas revenue × US-restaurants/overseas-restaurants) ÷ US restaurants` — looks independent but
  is **circular** when the regional split is itself built from the same per-restaurant daily rate, so
  its "agreement" validates nothing. The real validation is external: the **unit-economics + official
  capacity/receipts** reality check in §5.1 (implied peak-seated vs occupant load; implied alcohol
  share vs TX receipts), which can actually contradict a wrong AUV. Only an anchor that appears in the
  primary filing is recorded — a figure seen only in a search summary is not (that error is what
  removed the unverified "NA segment revenue" anchor).

Deliverable: `financial_anchors` rows for Super Hi, a `revenue_estimates` row for US-total + each US
Haidilao outlet, both rendered in the chain page's Pro module with the **Modeled** badge, the method
line, and the filing citation.

## 7. Build order

1. `revenue_estimates` table + the `method_version` model scaffold (empty, provenance-carrying).
2. The **EDGAR collector**, proven end to end on **Super Hi** (§6), writing anchors + estimates.
3. Add **HKEX** for the other listed parents (Mixue, Pop Mart, Miniso, Chagee, Nayuki, ChaPanda,
   Auntea Jenny, Anta, JNBY).
4. Add **FDD Item 19** for the US franchisors (YGF, Fish With You).
5. Sector-format **benchmark fallback** for anchored-less chains (lowest confidence, clearly marked).
5a. **Capacity / official-receipts reality-check probe** (§5.1) — *built*: `stores.occupant_load`,
    `capacity.py` (TX mixed-beverage receipts live; occupant-load registry ready for the first
    confirmed city feed), wired into `revenue.unit_economics`.
6. Wire `revenue_estimates` into the Pro "Revenue & prices" module + the Pro CSV/GeoJSON export.
7. (Later) v2 per-outlet modifiers; Phase 2b prices.

## 8. Legal posture

First-party / official only, same rule as Phase 1: **SEC/EDGAR, HKEX filings, state FDD registries,
company IR pages.** No scraping of Yelp/Google/Amazon/delivery apps/Tmall/JD, no review-velocity, no
card-panel or foot-traffic data, no paid terminals. Store the raw disclosed figure + currency and
apply FX in the model, so every estimate is reproducible from public documents. Anything that can't
be anchored to such a document is a **benchmark estimate, flagged as such**, or is left blank — never
invented.

## 9. Display (the measured/modeled wall)

- Every revenue number carries the **Modeled** badge and a one-line method ("Modeled from [filing],
  [period]: [AUV] × [N] US outlets").
- Always a **range** (low–high), never a bare point.
- Per-outlet estimates on the map/profile are **opt-in Pro**, shown as ranges; the free tier shows
  none.
- Show the **as-of** period of the anchor and the **as-of** date of the store count used.
- A chain with no anchor shows "Not yet modeled", not a zero and not a guess.

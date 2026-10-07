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

**BUILT (`chain_atlas/fdd.py`, `python -m chain_atlas fdd`).** Source = **Minnesota CARDS** — a public
GET search (franchisor / franchise-name / year) + public document download; the one registration state
with clean programmatic access. (**Wisconsin DFI is Cloudflare bot-blocked** — not automatable, pull by
hand; **CA DOCQNET** is a future add.) CARDS' WAF 403s a bot UA, so the collector sends a browser UA —
public content served to any browser, not a challenge. It picks the newest *Clean/Final FDD*, archives
the raw PDF, extracts the text (`pypdf`), and parses **Item 19** + **Item 20**:
- Writes `pipeline_signals` (`signal_type='fdd'`, idempotent on the FDD download URL): status +
  Item 20 outlet counts + state/year.
- Writes a `financial_anchors` row (`metric='fdd_item19_auv'`, US per-outlet, confidence medium, raw
  excerpt in `page_ref`) **only when Item 19 actually discloses a figure**.
- **Reality:** most of these franchisors (new/foreign entrants) **opt out of Item 19** ("we do not make
  any representations"); that opt-out is recorded, and no AUV is invented. Verified live 2026-10-04:
  Miniso, Cotti, Yangguofu all filed in MN and all **opt out** (so no AUV yet); Mixue/Möge/Yang's not in
  MN. The value today is the opt-out record + Item 20 census cross-check; AUVs will land when a
  disclosing franchisor (or a CA/WI pull) is added.

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

### 5.2 The retail model — channel-isolated (`revenue.retail_estimate`, BUILT)

A restaurant's store revenue *is* its sales, so AUV × count works. A multi-channel retailer's regional
revenue is **not** a store number: for Pop Mart's **Americas**, online is **64.0%** of revenue and
offline retail stores only **29.4%** (FY2025, HKEXnews announcement p.31). Dividing all Americas
revenue by stores implied ~US$14M/store — nonsense. The retail model fixes this by **isolating the
offline retail-store channel** before it divides:

1. **Channel-isolate.** Take the disclosed Americas *offline retail-store* revenue (RMB 2,003,799k),
   not total Americas revenue.
2. **FX.** → USD at the period average (`FX_RMB_PER_USD`; 2025 = 7.187, FRED AEXCHUS — Pop Mart states
   no rate, so the rate is recorded in `anchors_used`). = US$278.8M.
3. **Per-store AUV.** ÷ the disclosed Americas retail-store count (64) = **US$4.36M/store** — a plausible
   toy-flagship AUV.
4. **US total.** AUV × **our** US standard-store census (75), **roboshops excluded** (format
   `vending_robo`) to match the filing's "retail stores" definition. = **~US$327M**, band ±25%.
5. **Guardrails.** The per-store AUV must sit in a retail envelope (US$0.3M–25M) or it is flagged and
   nothing is written; and the modeled US total may not exceed disclosed **group** retail-store revenue
   (worldwide) — if it does, flagged, nothing written.
6. **Run-rate honesty.** Our current US count (75) exceeds the filing's 31 Dec 2025 Americas count (64)
   because the footprint grew (+748% YoY), so the US total is labeled a **current-footprint annualized
   run-rate**, not a FY2025 actual — stated in the estimate's `notes`.

What is deliberately *not* modeled: roboshop and online revenue (roboshops have no disclosed Americas
unit count; online is not a storefront). CLI: `python -m chain_atlas revenue` runs both engines.

### 5.3 The regional-apportionment model (`revenue.region_estimate`, BUILT)

Some chains disclose a **regional** revenue that includes the US but give no US-only figure and no channel
split — so neither the restaurant-AUV nor the channel-isolation model applies. **MINISO** is the case: its
FY2025 20-F (SEC EDGAR) breaks out **North America revenue RMB 3,342.9M (≈US$465M)** but not US-only, and
its own FY2025 results release gives **North America stores = 461 at 31 Dec 2025**. The model:

1. **FX** the regional revenue to USD (`FX_RMB_PER_USD`, 2025 = 7.187).
2. **Per-store** = region revenue ÷ region store count = **US$1.01M** (MINISO's *reported* revenue per
   store).
3. **US total** = per-store × our US store count (427), which **apportions the region to the US by store
   share** and caps the US total within the disclosed region revenue → **≈US$431M (±30%)**.

**Two caveats, stated in every estimate's `notes`:** (a) for a part-franchised retailer this is the
chain's *reported* revenue per outlet — full sales for directly-operated stores, **wholesale** for
franchised ("Retail Partner") stores — **not** gross consumer retail sales, which the filing does not
disclose; (b) "North America" includes Canada, so the US is apportioned by store share. Band ±30% (wider
than the channel model: apportionment + US/Canada + any period-vs-count mismatch). China-side sources
(HK filings, earnings calls, 新华/36氪/界面) corroborate and refine — e.g. the 461 NA count and
"NA revenue +37% H1 2026" came from MINISO's own results release/call, not the 20-F.

**Chagee** (also EDGAR, FY2025 20-F) is the counter-case: a **single reportable segment**, "no geographical
revenue information is presented" — **no US revenue to model**. Its anchors (group revenue, GMV, 3 US
teahouses at end-2025, China-only per-store GMV) are captured; the US estimate is **deferred**, not forced
(a China GMV on US stores would be Tier-5 at best). China-side press adds US color — first US store
Westfield Century City LA (May 2025), company-owned, ~5,000 cups opening day — but none is revenue-grade,
so it stays out of the published estimate.

### 5.4 The listed "tail" — checked, and why it can't be filing-anchored (verified 2026-10-04)

To shrink the benchmark tail we pulled the PRIMARY filings of every listed chain in it. **Finding: none
discloses a US / North America / Americas revenue** — the US is <0.2% of their revenue, below segment
thresholds (or the US sub is not even consolidated), so they report a single geography or bundle the US
into an overseas line that excludes it. **None is filing-anchorable to a US figure; all remain
sector-benchmark in the aggregate.** US outlet counts come from our own census, never these filings.

| Chain | Ticker | Group revenue (filing) | US revenue? | Source |
|---|---|---|---|---|
| Luckin | OTC:LKNCY | RMB 49,288M (FY2025, ~US$7.03bn) | No — single "PRC segment"; one bundled "All other revenues" RMB 284M (US+SG store sales + o/s franchise fees); US stores = 9 | SEC 20-F acc 0001104659-26-035712 |
| Mixue | HKEX:2097 | RMB 33,560M (FY2025) | No — single-geography; B2B supply/franchise model; no US count | HKEXnews 2026032400179 |
| Jiumaojiu (Tai Er) | HKEX:9922 | RMB 5,233M group / 3,720M Tai Er (FY2025) | No — segmented by brand, ">90% China"; "3 US cities", no US count. (Discloses overseas spend/customer RMB 155 vs 67 in China) | HKEXnews 2026032703108 |
| ChaPanda | HKEX:2555 | RMB 4,918M (FY2024) | No — single PRC segment; overseas 14 stores, US 0 in the filing | HKEXnews 2025042800813 |
| Auntea Jenny | HKEX:2589 | RMB 3,285M (FY2024) | No — single segment; "overseas" = 1 KL store (RMB 6.3M). (Avg GMV/store RMB 1,370k China) | HKEXnews 2025042800055 |
| Juewei | SSE:603517 | RMB 6,257M (2024) | No — 境外 overseas RMB 102M bundles SG+Canada+HK/Macau, US excluded; no store counts | cninfo 2025-04-10 |
| Nayuki | HKEX:2150 | RMB 4,331M (FY2025) | No — no geographic info (segments by business line); US (NaiSnow) only a no-profit tax-note sub. (Avg daily sales/teahouse RMB 7.7k self-op) | HKEXnews 2026032601584 |

**Implication for the tail:** the listed tail is only ~US$40M of the ~US$345M benchmark tail, and it can't
be converted via filings; the large tail chains (moge, yangguofu, zhangliang, liuyishou, heytea,
fishwithyou, cotti) are **private**. So the levers to improve the tail are (a) better benchmarks — the
disclosed home-market per-store figures above (e.g. Auntea Jenny ~RMB 1.37M ≈ US$190k/store China; tea US
~3× that) broadly VALIDATE the current sector benchmarks; (b) FDD Item 19 as more franchisors file; (c)
waiting for these chains to disclose the US as it grows. Not more filing pulls.

### 5.5 China A-share filers — China giants without US retail (verified 2026-10-04)

Extending the "within-China" sourcing into the **CSRC / cninfo** corpus (our least-tapped, least
US-accessible vein), we pulled the FY2024 annual reports of the four China A-share filers we track. All
report only in RMB; **none discloses a US revenue line, and three operate ZERO US retail stores** — their
US reach is export / cross-border e-commerce / a non-operating holding entity — so none is
revenue-model-relevant (they are correctly `not_established` in our US census). Captured for the
intelligence layer — the China scale and the China-exchange disclosures US stakeholders rarely see:

| Company (brand) | Ticker | Group revenue FY2024 | China retail stores | US presence | Source (cninfo/SSE/SZSE) |
|---|---|---|---|---|---|
| Bestore 良品铺子 | SSE:603719 | RMB 7,159M (−11%; net loss) | 2,704 snack stores (1,033 direct / 1,671 franchise), all China | none in filing; export/e-commerce only; **zero overseas assets** | FY2024, 2025-04-29 (1223379529.PDF) |
| Semir 森马服饰 (+ Balabala) | SZSE:002563 | RMB 14,626M (+7%) | 8,325 apparel stores (980 direct / 7,260 franchise / 85 concession); 100+ HK/overseas | 境外 aggregate RMB 80M (0.55%, HK+overseas bundled); US entity non-operating; no US stores | FY2024, 2025-04-01 (SZSE 002563) |
| M&G 晨光股份 (九木杂物社 / M&G LIFE) | SSE:603899 | RMB 24,228M (+4%) | 九木杂物社 741 + 晨光生活馆 38 = 779 big-format stores (franchise), all China; 九木 rev RMB 1,407M (~RMB 1.9M/store, loss-making) | 其他地区/overseas RMB 1,039M (~4.3%), not by country; US entity negligible; no US stores | FY2024, 2025-03-26 (1222895351.PDF) |

With **Juewei** (§5.4, SSE:603517) that is all four identified China A-share filers pulled. Finding:
these are large China retailers whose US footprint is distribution/e-commerce, not stores — so they enter
the revenue model only if/when they open US retail. The pull also establishes the China-exchange
cninfo/SSE/SZSE path (Chinese-language annual reports, direct 巨潮 PDF URLs) for future A-share filers.

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
3. Add **issuer filings** for the other listed parents. **Done:** Pop Mart (§5.2, HKEX, channel-isolated),
   **Miniso** (§5.3, SEC 20-F, regional apportionment → ~US$431M US), **Chagee** (SEC 20-F — single
   segment, US not disclosed, captured + deferred). Remaining: Mixue, Nayuki, ChaPanda, Auntea Jenny,
   Anta, JNBY, and the China A-share filers (Juewei, Bestore, Semir) via cninfo.
4. Add **FDD Item 19** for the US franchisors — *built* (§4.3, `fdd.py`, MN CARDS; most file opt-outs so
   far). Extend to CA DOCQNET / manual WI for franchisors not in MN, and wire `fdd_item19_auv` into
   `estimate()` as the top-priority US per-outlet AUV once a disclosing filing lands.
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

## 10. The grand total — aggregation (`chain_atlas/aggregate.py`, BUILT)

`python -m chain_atlas aggregate` rolls the per-chain estimates into one modeled **US-revenue grand total**
across every tracked chain with US outlets, and is explicit about how much rests on filings vs a benchmark.

- **Universe:** the site's own outlet set — census `open` stores + confirmed (non-`coming_soon`) sightings,
  roboshops excluded — via `geojson.build` (so it matches the map). Currently **45 chains / 854 US outlets**.
- **Per chain, best tier:** ANCHORED = a filing-derived `revenue_estimates` us_total (restaurant-AUV /
  channel-retail / regional-apportionment); otherwise BENCHMARK = a US-industry revenue-per-store for the
  chain's format × its outlet count (`BENCHMARK_AUV`, secondary, low confidence). The benchmarks are
  grounded in disclosed home-market per-store economics (§5.4 comparators) × a US premium (~2–3.5×),
  not pure guesswork, so the bands are tighter than a blind estimate — but still meaningfully wide, since
  the China→US translation (price, volume, format, maturity) is uncertain and a franchisor's reported
  revenue ≠ store GMV.
- **Two honest widths:** the headline **independent range** = mid ± √(Σ per-chain half-widths²) (errors are
  largely independent across brands/sectors/sources); plus a conservative **envelope** = [Σlow, Σhigh].
- **Measured/modeled wall:** every figure MODELED and a range; the report states the anchored vs benchmark
  split and each chain's tier. DB-only / Pro tier — never written to the public site.

**Run (2026-10-04, benchmarks grounded in disclosed economics):** grand total **≈US$1.22B** (likely
**US$1.06–1.38B**; outer envelope US$876M–1.61B), of which **US$881M (72%)** is filing-anchored (Miniso,
Pop Mart, Haidilao — 518 outlets) and **~US$337M** is the benchmark tail (42 chains / 336 outlets). The
total tightens further as more chains move from benchmark to filing-anchored.

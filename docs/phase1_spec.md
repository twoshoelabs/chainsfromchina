# Phase 1 spec — cross-sector brand registry, status events, and the first clean pipeline collector

Status: draft, 2026-09-30. Owner: Twoshoe Labs. This is the first phase of turning `chain_atlas`
from a US-map measurement project (food/tea/toys-forward) into a multi-sector
**China-retail-into-the-US intelligence** dataset. It covers only Phase 1 of the agreed build
order; later phases (shopping centers, pricing, revenue models) get their own specs.

## 1. Scope

**In Phase 1:**
1. Generalise the brand registry across all sectors (schema + backfill the non-food brands already
   found in the 2026-09-30 sector scan).
2. Keep the existing locator census + `status_events` engine; extend `locations` with the fields
   the intelligence product needs (metro, center, format, size, operator).
3. Stand up the **entities** graph (US LLCs / franchisees / officers) and **financial_anchors**
   tables as empty, provenance-carrying tables ready to fill.
4. Build ONE pipeline-signal collector end to end: **USPTO trademark filings** (the cleanest,
   most legally unambiguous, highest-signal source).

**Explicitly deferred (later phases, do not build now):** shopping-center / co-tenancy view;
catalogs / products / price observations; revenue models; `review_metrics` (legal landmine —
review-velocity needs Yelp/Google data the guardrails forbid scraping); customs import records
(licensing); foot-traffic (paid). State-registry, permit, mall-directory and job-posting
collectors are Phase 2/3 — the schema below is built so they slot in without migration.

## 2. What counts (scope: retail chains of brick-and-mortar outlets)

The subject is **retail chains**: companies that reach consumers through a **network (chain) of their
own branded, consumer-facing brick-and-mortar outlets** — company-owned, franchise or
dealer-operated. Starbucks and CVS are retail chains; Formica (a materials manufacturer sold through
fabricators/wholesale) and a product house like Gucci are not the subject. A single-brand company
that runs its own store chain (Anta, Urban Revivo, JNBY, MINISO) IS a retail chain and is in scope.

**Ownership is not a filter.** Company-owned, franchise, and dealer-operated outlets all count, as
long as they are outlets of an in-scope retail chain.

**Chain, not a lone flagship.** Chain-ness is judged at the brand level: the company must run a
*network* of its own outlets as an ongoing retail channel. A company whose consumer distribution is
wholesale / authorised resellers / online, with only one or two brand flagships, is a **product
brand, not a retail chain** — out of scope entirely, not recorded even as a signal (decision
2026-09-30). Out on this test: DJI (one US flagship + reseller/online), Insta360 (one Times Square
flagship), Anker (one Berlin store), Narwal (one KL flagship). Xiaomi is IN — 100+ franchised Mi
Stores is a network. Note a chain's US footprint may itself be a single store (More Yogurt,
Grandma's Home) — a chain with one US outlet is different from a brand that has no store network.

COUNTS — a branded consumer retail store/outlet of an in-scope chain: company-owned, franchise, or
dealer-operated; flagship, standard, mall inline, street, kiosk, food hall, or the brand's own
staffed shop-in-shop / counter.

DOES NOT COUNT (record as context / signal, never as a store, never in a store total or revenue
estimate):
- **Manufacturers / product brands with no own retail-outlet chain** — reach consumers via
  wholesale, distributors, fabricators or third-party retailers (Formica; furniture wholesalers
  Kuka, Man Wah, Mlily, Markor).
- Third-party retailer shelves, marketplace / e-commerce, and department-store concessions only
  (Ulta/Sephora/Best Buy/Target/Costco/Sam's Club shelves; Amazon/Tmall/Weee!/Yamibuy; beauty
  shelf-only such as Proya and Florasis-in-US).
- **Order-and-install design showrooms** — custom kitchen / cabinet / furniture studios where the
  customer designs and orders and the product is manufactured and installed later (Oppein,
  Suofeiya). Branded and consumer-facing, but not a retail store; treat as a manufacturer showroom.
  (Decision 2026-09-30: OUT.)
- **Lone-flagship product brands** — no own-store network; one or two brand flagships plus
  wholesale / authorised-reseller / online distribution (DJI, Insta360, Anker, Narwal).
  (Decision 2026-09-30: OUT entirely — not recorded, not a signal.)
- Trade / industry-show showrooms (e.g. High Point Market) and authorised-reseller shop-in-shops.
- Pop-ups count only as `format='pop_up'` with planned start/end dates, held out of the permanent
  store total.
- A stock listing, an IPO, a corporate/sales office, or a namesake/copycat brand.

Encode with fields, not prose: a brand enters the registry only if it is a **retail chain** — it runs
a network of its own branded retail outlets. A company that is only a manufacturer/wholesaler
(Formica, Kuka), sells only through third parties/online, runs only order-and-install showrooms
(Oppein, Suofeiya), or has only a lone flagship (DJI) does not qualify and is not added. Where an
in-scope chain has an individual non-retail location (a one-off showroom or a pop-up), tag it via
`format` so it is held out of the store count and revenue. Ownership model (company / franchise /
dealer) never excludes on its own.

Origin gate (unchanged): mainland-China origin only. Exclude Taiwan- and Hong-Kong-origin brands;
record ambiguous cases (Man Wah, Shang Xia, Hsu Fu Chi, Feiyue trademark split, Narwal) with a note
and keep them out until resolved.

## 3. Sector taxonomy

`sector` (one of) with free-text `sub_category`:

- `food_drink` — restaurants, hotpot, fast food, regional cuisine (existing).
- `tea`, `coffee` — kept as their own sectors (they dominate the existing set and the site's food map).
- `bakery` — bakery / dessert.
- `grocery_convenience` — supermarkets, convenience, fresh-food, specialty-food *retail* (sells
  packaged/fresh goods, distinct from food-service).
- `snacks` — packaged-snack / braised-deli retail.
- `apparel` — fashion, sportswear, footwear, bags, jewellery.
- `beauty` — cosmetics, skincare, fragrance, personal care.
- `lifestyle_variety` — variety/value stores, stationery, gifts, art toys, collectibles.
- `electronics` — phones, accessories, appliances, robotics, cameras.
- `home` — furniture, homeware, home improvement.

The site's public taxonomy (register categories) maps onto these; keep the mapping in one place so
the page cannot disagree with the data.

## 4. Data model

Guiding rules (from the project brief): every table carries `source`, `source_url`, `retrieved_at`
(UTC ISO-8601) and `confidence` (high/medium/low). Raw captures are kept and hashed; a new parsed
version is written only when the hash changes (the `runs.raw_path` / `runs.raw_sha256` mechanism
already does this — extend it to every collector). **Append-only: records are never overwritten;
a correction is a new row that references the one it supersedes** (`supersedes_id`). History is the
product.

### 4.1 Reuse, don't fork

The intelligence model's `brands`, `locations` and `status_events` already exist — extend them,
do not create parallel tables.

| Brief table | Existing home | Action |
|---|---|---|
| brands | `chains` (DB, US census) + `register.json.chains` (international) | unify on `chain_id`; add columns (4.2) |
| locations | `stores` + `manual/sightings.json` | add columns (4.3) |
| status_events | `events` | add provenance columns (4.4) |
| (raw capture + hash) | `runs.raw_path`, `runs.raw_sha256` | reuse pattern for every collector |

Note the current split to close: brand identity lives in two places — the DB `chains` table (US
census) and `register.json.chains` (international register). They already share `chain_id`. Phase 1
makes `chain_id` the single brand key across both, and the new brand-level fields live in ONE
canonical place (propose: `register.json.chains`, exported into the DB), so `name_us`, `global`,
`sector`, `ticker` etc. never diverge.

### 4.2 `chains` (brands) — add columns

Current: `chain_id, country, name, name_zh, origin, parent, format, closure_n_days`
(+ `name_us`, `global` in register.json).

Add:
- `sector` TEXT — §3 enum.
- `sub_category` TEXT.
- `tickers` TEXT — JSON array, e.g. `["HKEX:2020"]`; empty for private.
- `us_entry_date` TEXT — first US store open date (NULL if not in US).
- `operating_model` TEXT — `company_owned | franchise | master_franchise | license | jv | wholesale | dealer`.
- `fdd_available` INTEGER — 0/1 (US franchise disclosure document on file).
- `franchise_available_us` INTEGER — 0/1.
- Keep `format` for the store format descriptor of the *typical* outlet, but the sector lives in
  `sector`.

### 4.3 `stores` (locations) — add columns

Current includes `store_key, addr_*, city, state, zip, lat, lon, coord_src, first_seen, last_seen,
opened_on, status` (`active | pre_opening | closed | temp_closed | withdrawn`).

Add:
- `metro` TEXT — Census CBSA code (free join: we already geocode via Census).
- `center_id` TEXT — FK to `shopping_centers` (NULL for street/standalone).
- `format` TEXT — `flagship | standard | mall_inline | street | food_hall | kiosk | pop_up |
  shop_in_shop | vending_robo | showroom`.
- `square_footage` INTEGER — NULL if unknown.
- `operator_entity_id` TEXT — FK to `entities` (the US LLC/franchisee that runs it).
- `closed_on` TEXT — mirrors `opened_on`.
- `popup_start`, `popup_end` TEXT — required when `format='pop_up'`.
Sightings (`manual/sightings.json`) gain the same optional fields per location.

The existing `status` enum already matches the brief's pipeline/open/temporarily-closed/closed
(map `pre_opening`→pipeline, `active`→open, `temp_closed`→temporarily closed, `closed`→closed,
`withdrawn`→removed). No new status values needed.

### 4.4 `events` (status_events) — add provenance

Current: `detected_date, event_date, chain_id, store_id, event_type, details(JSON)`.
Add first-class columns (don't bury in `details`): `source`, `source_url`, `retrieved_at`,
`confidence`, `evidence` (what changed: locator appeared/disappeared, permit, news, lease, review
silence, manual visit), `supersedes_id`.

### 4.5 New tables

`shopping_centers` (created empty in Phase 1; filled in Phase 2):
`id, name, owner_reit, class_tier, metro (CBSA), anchors(JSON), source, source_url, retrieved_at,
confidence`. Define `class_tier` with an explicit rubric before filling (avoid subjective drift).

`entities`:
`id, kind (operator|franchisee|master_franchisee|licensee|us_subsidiary|importer_of_record),
name, state, file_number, registered_agent, officers(JSON), linked_brand_ids(JSON),
source, source_url, retrieved_at, confidence, supersedes_id`.

`pipeline_signals`:
`id, signal_type (uspto|entity|permit|mall_listing|job_posting|customs|lease|news), brand_id,
location_id(NULL), filed_date, summary, raw_ref (path+sha256), source, source_url, retrieved_at,
confidence`.

`financial_anchors` (created empty; filled from FDD/filings in a later phase, but table lands now):
`id, brand_id, period, metric (us_revenue|americas_revenue|auv|store_count|sss|overseas_segment),
value, unit, page_ref, source, source_url, retrieved_at, confidence`.

## 5. First collector — USPTO trademark filings

Before building, per the brief's build-order rule, the source card:

- **Source:** USPTO — Trademark Search API / TSDR, plus the USPTO bulk data products (trademark
  daily/annual XML). https://developer.uspto.gov and https://tsdr.uspto.gov.
- **Terms status:** CLEAN. US government work; trademark records are public. Official API and bulk
  downloads exist; no scraping of a third party required. Respect documented rate limits.
- **Expected volume:** low per run. Two query sets: (a) exact/fuzzy match on every registry brand
  name (tens of brands → low hundreds of marks total, mostly unchanged week to week); (b) new
  filings in retail-relevant Nice classes by applicants with a China address — a few hundred new
  filings/week to triage, most irrelevant. Diff against last run so only changes are written.
- **Cadence:** weekly.
- **Relevant Nice classes:** 25 apparel/footwear, 3 cosmetics/personal care, 9 electronics,
  28 toys/games, 35 retail-store services, 43 food & drink services, 30 food staples, 20 furniture,
  14 jewellery. Class 35 is the strongest "opening a US retail operation" tell.
- **What it writes:** raw capture (saved + sha256) → parsed rows into `pipeline_signals`
  (`signal_type='uspto'`, linked to `brand_id` when the applicant matches a known brand/parent,
  else held as an unlinked lead). A filing is a *pipeline* signal, never a store.
- **Matching:** match on brand name, parent/applicant name, and known US operator entities; a
  China applicant address in a retail class with no brand match is a **discovery lead** (a brand we
  may not track yet) — surface it, don't auto-add.
- **Manual fallback:** if the API is unavailable, the weekly TSDR/registry lookup can be done by
  hand for the registry brands (the discovery sweep degrades gracefully to "skipped this week").
- **Idempotent:** re-running for the same week must not create duplicate signals (dedupe on
  serial number + filing event).

## 6. Coding conventions (unchanged, restated)

- Every function opens with the standard block: `# name: / # purpose: / # arguments: / # returns:
  / # effects: / # other:`.
- Collectors are idempotent per date; append-only history; corrections reference the superseded row.
- Sector differences are handled with fields and channel tags, never separate databases.
- Measured vs modeled stays walled: nothing in Phase 1 emits an estimate. When estimates arrive
  (later phase) they live behind their own table and are never rendered as a reported figure.

## 7. Phase-1 deliverables (order)

1. Schema migration: additive columns on `chains`, `stores`, `events`; create `shopping_centers`,
   `entities`, `pipeline_signals`, `financial_anchors` (empty, provenance columns present).
2. Brand-identity unification on `chain_id`; move brand-level fields to one canonical store.
3. Backfill the 2026-09-30 sector-scan brands (apparel/beauty/electronics/home/grocery) into the
   registry with `sector`, `operating_model`, `tickers` — retail chains only. Set US sightings for the
   confirmed US-present store-chains: **Anta, Urban Revivo, JNBY, Meilleur Moment** (Peak pending live
   re-verification; exact current US store lists to confirm before load). Excluded, NOT added: DJI,
   Insta360, Anker, Narwal (lone-flagship product brands); Oppein, Suofeiya (order-and-install
   showrooms); furniture wholesalers (Kuka, Man Wah, Mlily, Markor) and beauty shelf-only brands
   (Proya, Florasis-US). Overseas-only chains (Bosideng, Semir/Balabala, Xtep, Laopu Gold, Florasis,
   Mao Geping, Judydoll, Joocyee, The Colorist, HotMaxx, Xiaomi, etc.) go to the international
   register without US rows.
4. USPTO collector (§5), end to end, weekly, writing `pipeline_signals`.
5. Tests: schema round-trip; inclusion-rule unit tests (dealer showroom / wholesale excluded);
   USPTO collector idempotency; validate() extended for the new brand fields.

## 8. Legal posture

First-party, official, licensed or manual only. Clean for Phase 1: USPTO, SEC/EDGAR, HKEX,
state business registries, city permit open-data, brand first-party sites, US Census geocoder.
Do not build any collector against Yelp, Google Maps, Amazon, DoorDash, Uber Eats, Tmall/JD/Taobao
or Meituan/Dianping. Any gray-area source (review metrics, customs, foot-traffic) is flagged and
deferred, not built.

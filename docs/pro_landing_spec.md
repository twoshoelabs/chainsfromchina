# Pro: US Landing intelligence schema

Two Pro-tier datasets that model the *landing* side of China→US expansion — the signal the public
map structurally can't show. Data lives in **`manual/pro_landing.json`**, logic in
**`chain_atlas/pro_landing.py`**, surfaced only via `python -m chain_atlas pro-landing [--full]`.
**Not published** — kept out of `map/data`, never exported into `stores.json` (paywalled, like
`us_entry_models`). Source insight: the Zhixiang Chuhai interviews with the US-landing service layer
(see memory `cfc-pro-landing-ecosystem`).

Both datasets are keyed by `chain_id` (so they cover any brand, including ones with no
`register.chains` entry). The CLI joins each to the current counted US outlet total from
`stores.geojson` — so you see *outlets that exist* next to *the ceiling / the readiness grade*.

## 1. `noncompete_cap` — realistic US store-count ceiling

US landlords grant **category exclusivity** (one coffee / one bubble-tea / one dumpling brand per
mall or plaza), so a late-entrant's addressable venue universe is capped regardless of brand size.
This estimates how many US stores a brand can *ever* open.

| field | type | meaning |
|---|---|---|
| `category` | str | the competitive category the non-compete applies to (`coffee`, `bubble_tea`, `hotpot`, `dumpling`, …) |
| `incumbent_blockers` | str[] | who holds the exclusivity in prime venues (e.g. `Starbucks`, `Dunkin'`) or the clause type |
| `channel_access` | obj | per channel `{a_malls, strip_plazas, street, food_court, campus, grocery_anchored}` → `blocked` \| `limited` \| `open` |
| `cap_estimate` | `{low,high}` int | realistic US store ceiling |
| `cap_method` | str | how the range was derived (the venue-universe logic) |
| `basis` | str | evidence / quote |
| `confidence` | `low\|medium\|high` | |
| `as_of` | `YYYY-MM` | |

**Why it matters for Pro:** a buyer evaluating a brand's US runway needs the *ceiling*, not just
today's count. e.g. coffee brands hit the Starbucks wall in A-malls and are pushed to street/secondary
(Luckin's Manhattan-street-first strategy); `grocery_anchored` (99 Ranch / H-Mart centers) is often
the open channel for Asian-focused brands.

## 2. `landing_readiness` — execution-quality grade

Seven **0–5** dimensions, weighted (sum = 1.0, defined in `rubric.readiness_dimensions`), roll up to a
**0–100 score** and an **A–F grade**. The score is *computed by the module, never stored*, so the
rubric weights are the single source of truth.

| dimension | weight | 5 ↔ 1 |
|---|---|---|
| `entry_model` | 0.15 | company-direct ↔ pure franchise "horse-racing" |
| `fdd_discipline` | 0.15 | registered US FDD ↔ franchising with **no FDD** (illegal); `na` if not franchising |
| `territory_protection` | 0.20 | clear radius grants ↔ none (franchisees cannibalize — "2 stores / 500 m") |
| `supply_chain` | 0.20 | central US commissary ↔ each franchisee builds own / none |
| `us_ops_team` | 0.10 | experienced landing team ↔ "2 junior hires" |
| `localization` | 0.10 | US menu/marketing/pricing adapted ↔ copy-paste China playbook |
| `pace_discipline` | 0.10 | measured site-by-site ↔ overexpanded then retrenched |

Plus `stage` (`preparing\|trial\|expansion\|steady\|contracting\|exited`), `risk_flags[]` (the article's
failure patterns — `no_fdd`, `no_territory_protection`, `us_franchisee_supply_gap`,
`cannibalization`, `overexpansion`, …), `confidence`, `as_of`. Each dimension carries `{value, score,
note}`.

Grade bands: **A ≥ 85, B ≥ 70, C ≥ 55, D ≥ 40, F < 40**.

**Why it matters for Pro:** turns the article's cautionary tale (a tea brand franchised with no FDD,
no territory protection, 7 franchisees fighting one location, cannibalizing Flushing stores → HQ pulled
back) into a repeatable *execution grade* that flags over-expansion risk before the outlet count does.

## Validation & seeds

`pro_landing.validate()` checks: rubric dimensions present and weights sum to 1.0; every readiness
record has all 7 dimensions with integer 0–5 scores and a valid `stage`; every cap has all six
`channel_access` channels with valid values and a sane `cap_estimate`. Seeded examples: Luckin
(direct, A), Mixue (franchise + supply-chain strength, C), Cotti (early, D); caps for Luckin/Cotti
(coffee, Starbucks wall) and CHAGEE/Mixue (bubble-tea, one-per-plaza).

## Extending

Add a brand by adding its `chain_id` to either map. Keep the two decoupled — a brand can have a cap
without a readiness grade and vice-versa. When filling readiness, reuse the register's
`franchise_available_us` / `fdd_available` and `us_entry_models` model as inputs to `entry_model` /
`fdd_discipline`. Re-run `python -m chain_atlas pro-landing --full` to see the recomputed grades.

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

`chain_atlas` is the collector behind the *Chains From China* site (chainsfromchina.com): a daily
census of US store locators for mainland-China-origin chains, plus a hand-typed international
register. `README.md` is long and is the design record: read the relevant section before changing
a rule. Most "why is it done this way" answers are there.

## Commands

Always use the venv interpreter (`.venv/bin/python`, built with `uv`). Dependencies are only
`requests` and `certifi`. There is no build step and no linter config.

```
.venv/bin/python -m chain_atlas run [--chain X] [--date YYYY-MM-DD] [--force]   # daily pass, idempotent per (chain, day)
.venv/bin/python -m chain_atlas reparse [--chain X] [--date D]  # re-derive a day from stored raw captures, no network
.venv/bin/python -m chain_atlas status                         # stock, pipeline, reason for every blocked chain
.venv/bin/python -m chain_atlas probe --chain X                # print one chain's live locator, archive untouched
.venv/bin/python -m chain_atlas recheck [--chain X]            # re-probe blocked chains' RECHECK URLs
.venv/bin/python -m chain_atlas watch [--chain X]              # launch-watch on blocked chains' pages
.venv/bin/python -m chain_atlas geocode [--chain X]            # US Census geocoder, fills NULL coords only
.venv/bin/python -m chain_atlas export                         # writes map/data/*.json (gitignored)
.venv/bin/python -m chain_atlas register [--chain X] [--market XX] [--gaps] [--stale]
.venv/bin/python scripts/serve_map.py                          # http://127.0.0.1:8765/ (no-store cache headers on purpose)
```

**Tests are plain scripts, not pytest.** Each file under `tests/` has a `main()`, prints PASS/FAIL
lines, and exits non-zero on failure. Run one at a time:

```
.venv/bin/python tests/test_register.py
CHAIN_ATLAS_DATA=$(mktemp -d) .venv/bin/python tests/test_events.py   # needs a throwaway archive
```

The same pattern applies to `test_usaddr`, `test_miniso`, `test_miniso_ae`, `test_popmart`,
`test_normalise`, `test_sightings`, `test_coverage`, `test_permits` and `test_watch`. Fixtures in
`tests/fixtures/` are real slices of live captures. `test_register.py` also validates the shipped
`register.json`, so run it after any edit to that file.

## Where state lives

All collected state is under `CHAIN_ATLAS_DATA` (default `~/chain_atlas_data`), never in the repo:
`chain_atlas.sqlite`, `raw/<chain>/<date>.<ext>.gz` (immutable; a second capture on the same day
writes `.2`, `.3`), logs, geocode cache, and the watchers' `review_*.csv` queues. `.env` is sourced
by `scripts/run_daily.sh` and **overrides** the environment. The live archive is the real
production dataset. Do not run `run --force` or write to it casually; use a temp
`CHAIN_ATLAS_DATA` when experimenting.

Production runs from a launchd agent (`scripts/com.dansilver.chain_atlas.plist`) at 06:00 and
13:30 via `run_daily.sh`, which does run → export → watch → `deploy.sh`. The deploy force-pushes
`map/` plus the exported data to the `gh-pages` branch of `twoshoelabs/chainsfromchina`. That
publishes the site, so don't run `deploy.sh` unless asked.

## Architecture

**Pipeline** (`run.py`): for each enabled adapter, `capture` fetches and saves the raw payload →
`adapter.parse(raw)` → `normalise()` (state fallback, drop points outside the US) → `identity.store_key`
→ write `observations` → `events.diff` against prior days → `runs` row. `reparse` goes through the
same `normalise` path from the stored raw file. `run` and `reparse` must stay one code path; a
divergence between them once silently lost stores.

**Adapters** (`chain_atlas/adapters/`): one module per chain *per market*, registered in
`REGISTRY` in `adapters/__init__.py`. `fetch_raw()` returns the whole footprint (partial is worse
than failure); `parse()` must be pure so history can be re-parsed. The adapter alone decides
`trading` (open vs. coming soon). Class attributes carry metadata: `country`, `name_us`/`aliases`,
`ENABLED`, `BLOCKED_REASON`, `RECHECK`, `KNOWN_COUNT`, `PROVENANCE`, `register_chain`. Chains with
no usable source stay in `REGISTRY` as disabled stubs (`stubs.py`) with a reason. Collectability
never decides membership. MINISO US and MINISO UAE are separate adapters and chain ids.

**Events** (`events.py`) apply conservative rules: closure needs N consecutive *collected* days
of absence (failed days don't count); `coming_soon` is `pre_opening` and never counts as a store;
disappearing before trading is `withdrawn`, not closed; a day whose count moves >30% is
suppressed pending human review. Baseline day emits nothing.

**Three kinds of knowledge that must not mix:**
1. The census: `stores`/`observations`/`events`, collected only, with a raw capture behind every number.
2. `KNOWN_COUNT`: a first-party number with no roster.
3. `manual/sightings.json` (via `sightings.py`): hand-entered partial rosters. These never enter
   stores/observations/events or `by_state`/`meta.counts`. A group with `complete_as_of` becomes a
   separate `manual_rosters` count of `confirmed` rows only.

`coverage.py` / `manual/coverage.json` score collected vs. sighted chains without inventing ratios.

**International register** (`register.py`, `register.json`, `map/register.html`): hand-typed, one
row per chain×market, with source, confidence and as-of date. The validator enforces the schema:
unpublished counts are `null` (never inferred or split from regional totals), undated counts are
rejected, `no_evidence` ≠ `none`, `present` rows need a source or note. A collecting adapter with
`register_chain` supersedes the typed row visibly (`was_typed`), never silently.

**Watchers** (`scripts/`): health-department food-inspection feeds produce opening/closing
*candidates* into `review_*.csv` for a human. They never write to the census. Socrata metros are
rows in `scripts/jurisdictions.json` driven by `scripts/watch.py`; LA County and Santa Clara have
bespoke scripts. Shared name matching (whole-term, so BISCOTTI ≠ Cotti) and address fingerprinting
live in `permit_common.py`. Absence from a feed is never a closing.

**Geo**: `geo.py` keys cells with a Lambert azimuthal equal-area projection per market (mainland
US centred 45N 100W), and `map/app.js` uses the same formula. `usaddr.py` is the project's own US
address parser; add every newly seen address shape to `test_usaddr.py`. `stores.coord_src`
separates `published` from `geocoded` coordinates.

**Map** (`map/`): static, dependency-free SVG, with no map library or tiles. Filters to
`country='US'`. Before editing `app.js`/`style.css`, read the README's "Five traps in this page"
(CSS `stroke-width` on `.store`, viewBox-unit font sizes, `[hidden]` vs `display`, inset transform
scaling, browser caching).

## Project conventions

- Scope: mainland-China-origin chains only. Taiwan/HK brands and Asian grocers are out of scope
  as origins.
- Honour robots.txt and terms gates absolutely. Blocked-by-policy is recorded as a reason, not
  worked around (see Cotti's legal gate, Honolulu, MINISO UAE's `/wp-admin/`).
- Every adapter must be verified by reading its actual output rows, not just a 200 response.
- Functions use a structured docstring (`name / purpose / arguments / returns / effects / other`),
  and comments explain *why* with the concrete incident behind a rule. Match that style.
- Validation comments in `REGISTRY` record the date and count when an adapter was verified live.

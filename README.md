# us_chain_atlas — a daily census of Chinese chain locators in the United States

Sibling of `store_atlas` (門市帳), which does the same job for Taiwan. Same shape: one adapter per
chain, an immutable raw capture per chain per day, observations that are never updated, and
events derived from the difference between two days.

**Why it exists.** As of September 2026 nobody publishes a store-level, dated map of
mainland-China-origin chains in the US. Momentum Works tracks this category well but reports on
Southeast Asia in PDFs; Technomic's Top 500 is annual and these chains are still too small to
make it; the trade press counts them accurately but in prose, as snapshots. All of those are
pictures of a moment. The thing none of them has — and the only thing that answers "how fast" —
is a daily series, which cannot be bought later because nobody is keeping it.

## Scope

Mainland-China-origin chains trading in the United States. Taiwanese and Hong Kong brands
(Tiger Sugar, The Alley, Gong Cha) are an earlier and different wave and are out of scope.
Asian grocers such as 99 Ranch and H Mart sell Chinese products but are not Chinese chains.

## State of the collection — 21 September 2026

| Chain | | Source | Stores |
|---|---|---|---|
| MIXUE | 蜜雪冰城 | tRPC endpoint on the US franchise site | 10 open + 17 announced, with coordinates |
| CHAGEE | 霸王茶姬 | store list inside the Next.js flight payload | 11, with coordinates |
| Luckin Coffee | 瑞幸咖啡 | server-rendered store cards | 22, **no coordinates published** |
| MINISO | 名创优品 | Wix Data `Locations` collection | **430** across 46 states, with coordinates |
| POP MART | 泡泡玛特 | — | blocked: Cloudflare bot management |
| HEYTEA | 喜茶 | — | blocked: the site's store page is a global flagship showcase, not a locator |
| Cotti Coffee | 库迪咖啡 | — | blocked: no first-party US locator exists |

The blocked chains are listed on the map with their reasons. A tracker that quietly omits the
chains that were inconvenient will eventually report that Chinese retail in America is all tea
shops, and `status` prints the reason beside every chain so a hole is never silent.

**MINISO is the footprint.** 430 stores in 46 states, an order of magnitude larger than
everything else here combined, and the reason the map looks like a map.

**MIXUE is the leading indicator.** Its locator publishes `coming_soon` alongside `open`, so the pipeline is
visible weeks ahead and an opening can be dated to the day the status flips rather than to the
day a row appeared. Seventeen of its twenty-seven US listings were announced-but-not-trading on
the baseline day, most of them ringing the San Gabriel Valley.

## How MINISO was cracked, and what its data is really like

Worth reading before trusting any number from it. The locator is a Wix site and the store list
appears in neither the HTML nor any XHR the page makes — the fetch happens inside a Wix **web
worker**, which is why a normal network capture shows nothing at all. What gives it away is the
page's own router config for its `/locations/<slug>` pages:

    "prefix":"locations" ... "config":{"collection":"Locations", ...}

From there the collector asks Wix Data for that collection the same way the site's worker does:
`GET /_api/v1/access-tokens` for a session instance, then a `POST` to the CMS query endpoint with
the site's `gridAppId`. Two requests a day for the whole estate. (An unauthenticated query is a
400, so the token step is not optional.)

The harder half was the data. Miniso's CMS is a working business system, and **taking its 462
rows at face value overstates the chain by about 9%**:

- **`storeCode` is not unique.** 33 codes appear on 67 rows, because a bulk re-import on 1 July
  2026 re-added stores first entered on 8–9 June. Same shop, two rows, address written two ways —
  `6191 S StateStreet, Ste. D311` and `6191 S State St #1195`.
- **`storeCode` is not unambiguous either.** Five codes cover genuinely *different* stores
  hundreds of kilometres apart, because America has more than one Southlake Mall, Columbia Mall,
  Northpark Mall and SouthPark Mall. `USFA` covers two different Chinatown Centers — Houston and
  Austin — **both in Texas**, so the state does not separate them. The city does.
- **Three rows carry `storeCode: "Closed"`** with no address: stores Miniso has shut and kept in
  the CMS. Dropped from the roster, never counted as trading.
- **`stateTag` is unreliable** — seven real stores carry the literal string `"#N/A"` — so the
  state is read from the address with this project's own parser and the CMS field is a last
  resort.

Identity is therefore **(storeCode, city)**, which merges the re-import duplicates and keeps the
same-name malls apart, falling back to the Wix item id for rows whose code is not a real code.
A group whose members turn out to be more than 2 km apart is split back to per-row identity: the
key failing to discriminate should cost an unmerged duplicate, never a disappeared store.

462 rows − 3 closed − 29 merged = **430 stores**, which squares with Miniso's own announcement of
its 400th US store in August 2026.

## Setup

```
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -r requirements.txt
cp .env.example .env        # set US_CHAIN_ATLAS_DATA and a real mailto in the User-Agent
.venv/bin/python -m us_chain_atlas run        # first run is the baseline; no openings emitted
.venv/bin/python -m us_chain_atlas export     # writes map/data/*.json
.venv/bin/python scripts/serve_map.py         # http://127.0.0.1:8765/
```

Build the venv with `uv`, not a Homebrew interpreter — the sibling project lost two days of
collection in September 2026 to a venv whose `python3` symlinked into a Cellar path that a
`brew upgrade` then removed.

## Scheduling

Installed on this machine (21 Sep 2026) as a user LaunchAgent:

```
cp scripts/com.dansilver.us_chain_atlas.plist ~/Library/LaunchAgents/
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.dansilver.us_chain_atlas.plist
```

06:00 local, with a **13:30 retry**. The retry is nearly free and is the whole safety net: `run`
is idempotent per (chain, day), so chains already `ok` are skipped without re-crawling and only
the ones that failed in the morning are tried again. A site being down at six in the morning
therefore does not cost the archive a day.

This Mac sleeps, so launchd runs the pass at the next wake rather than at exactly 06:00. That is
acceptable by design: the archive records *which* days were collected, and the closure rule
counts collected days rather than calendar days, so a missed day is a recorded gap and never a
wave of invented closures.

`run_daily.sh` sources `.env` (gitignored — copy `.env.example`), and refuses to start on a
missing or too-old interpreter with exit 78 rather than silently falling back to system Python.
Note that `.env` **overrides** the environment, so `US_CHAIN_ATLAS_DATA=... ./scripts/run_daily.sh`
will not do what it looks like it does; point `.env` at the other archive instead.

Useful afterwards:

```
launchctl print gui/$(id -u)/com.dansilver.us_chain_atlas     # state, run count, last exit code
launchctl kickstart -p gui/$(id -u)/com.dansilver.us_chain_atlas   # run it now
tail ~/us_chain_atlas_data/logs/daily.log                     # what it did
launchctl bootout gui/$(id -u)/com.dansilver.us_chain_atlas   # stop it
```

A note on the interpreter, inherited from the sibling project: build the venv against Homebrew's
stable `opt` path, never a versioned `Cellar` path. This one resolves through
`/opt/homebrew/opt/python@3.14/bin/python3.14`, so a `brew upgrade` repoints it rather than
deleting it out from under a scheduled job — which is exactly what stopped `store_atlas`
collecting for two days in September 2026.

## Commands

| | |
|---|---|
| `run [--chain X] [--date YYYY-MM-DD] [--force]` | daily pass; idempotent per (chain, day). Chains already `ok` for the date are skipped |
| `reparse [--chain X] [--date YYYY-MM-DD]` | re-derive a day from the stored raw captures, no network. This is what makes "raw is the primary evidence" a fact: a parser fix is applied to history without re-asking the chains |
| `status` | stock, pipeline and last run per chain, with the reason for every chain that is not collecting |
| `export [--out DIR]` | write `map/data/stores.json` and `events.json` |
| `probe --chain X` | print one chain's live locator without touching the archive |

## The rules, and why each is conservative

- **A closure needs N consecutive _collected_ days of absence.** Absence on a day the collector
  failed is not absence. A network outage must never manufacture a wave of shutdowns, so the
  closure test counts only days with a successful run for that chain.
- **An announcement is not an opening.** A `coming_soon` listing is recorded as `pre_opening` and
  never added to a store count. If it starts trading, that day is the opening. If it disappears
  without trading, it is `withdrawn` — a cancelled plan, not a closure.
- **A day whose count moves more than 30% is suppressed,** not recorded. The raw capture is kept
  and nothing is derived from it until a human looks, because a truncated page and a mass closure
  are the same shape.
- **Unlocated stores are counted, not dropped.** Luckin publishes no coordinates, so its 22 New
  York stores appear in every total and on no map, labelled as unplaced.
- **Raw captures are immutable.** A second run on the same date writes `.2`, `.3`; nothing ever
  overwrites the capture a published number was derived from.

## Tests

```
US_CHAIN_ATLAS_DATA=$(mktemp -d) .venv/bin/python tests/test_events.py
.venv/bin/python tests/test_usaddr.py
.venv/bin/python tests/test_miniso.py
```

`test_miniso.py` runs the deduplication over a real slice of the 21 Sep 2026 capture, chosen to
carry every shape that matters: two pairs that must merge, two same-code pairs that must not,
the `Closed` rows, and the `#N/A` rows whose state has to come from the address.

`test_usaddr.py` holds every address shape that has actually appeared in a capture, including the
four that silently dropped stores from the state totals before the parser was rewritten: a missing
comma before the state (`Orange CA 92868`), two spaces where a comma belongs, a hyphen before the
ZIP (`CA-90067`), and a trailing `, USA` or `, United States`. It also checks that a two-letter
token which is not a USPS state cannot become one.

`test_events.py` drives synthetic days through the diff engine: the baseline emitting nothing, a
`coming_soon` flipping to open, absence short of N days declaring nothing, a failed collection day
closing nothing, a withdrawal distinguished from a closure, and address normalisation collapsing
`133 4th Avenue` / `133 4TH AVE.` / `133 4th Ave` into one store while keeping `#249A` and `#250`
apart.

## The map

`map/` is a static page with no dependencies — no map library, no tile server, no API key. It
projects with the same Lambert azimuthal equal-area formula the collector keys cells with
(`geo.py`), so a dot on the map and a cell in the database are the same piece of ground.

Two views, and the difference between them matters:

- **Stores** — one dot per store the collector can place. Filled = trading, hollow ring =
  announced but not yet open. Precise, and incomplete: Luckin publishes no coordinates, so its
  22 New York stores are missing from this view entirely.
- **By state** — counts taken from the roster rather than from the dots, so stores with no
  coordinates are still counted. **This view is the more complete one.** A state with announced
  stores but nothing trading yet (Massachusetts, Utah) is drawn in a dashed tint rather than left
  blank, because "two stores coming" is not the same as "no presence".

Drag to pan, scroll to zoom, double-click to reset.

Dots are drawn **largest chain first**, so the smallest chain ends up on top. This is not
cosmetic: SVG paints in document order, and the archive's natural order put MINISO's 430 dots
last, which covered all 11 CHAGEE stores completely — both are mall chains and sit in the same
malls, so CHAGEE simply could not be found on the map while being collected perfectly. A chain
with a tenth of the footprint has to win the overlap or it reads as absent.

### Four traps in this page, all of which bit once

1. Do not add `stroke-width` to `.store` in CSS. A CSS declaration overrides the presentation
   attribute `app.js` scales with the view, and the announced-store rings get drawn 1.6 metres
   wide — i.e. invisible, while the DOM looks perfectly correct.
2. Do not set a state label's `font-size` in viewBox units. The viewBox is in metres, so that
   asks for ~115,000px of type, which browsers silently clamp (5,000px in Chrome) and the label
   renders three pixels wide. Labels are drawn at 14 units and scaled by a transform instead.
3. Do not rely on the `hidden` attribute alone for anything given `display` in CSS — an
   element-level `display:flex` beats the UA rule for `[hidden]`.
4. `scripts/serve_map.py` sends `Cache-Control: no-store` deliberately. Without it the browser
   reuses a cached `app.js` after an edit and the page runs the OLD code while the file on disk
   and the file on the wire both look correct — a fix that is present everywhere except in the
   running page.

## Who these companies are

`profiles.py` holds a paragraph on each chain — who founded it, where it is listed, how big it is
worldwide, when it reached the US — shown in the map sidebar and expandable per company. It is
kept deliberately separate from the collector: everything else in this project is something the
collector saw for itself and can produce a raw capture for, while these are hand-typed facts from
company filings and the trade press, carrying the date they were true. No US store count lives
there; that is the number this project measures, and keeping a hand-typed copy beside the measured
one is how a tracker ends up quoting its own stale note back at itself.

## What this is not

Change is only as old as the archive, which begins on the first collected day (21 September 2026).
Nothing is backfilled from press reports or a chain's own history. The store counts come from what
each chain publishes about itself: a store that opens without the chain updating its locator is
invisible here, and corroborating against a second source is not built yet.

## Next

1. **Geocode Luckin** so New York stops being a hole in the Stores view. It is already counted
   correctly by state, which is why that view exists.
2. **POP MART** — ask for access, or budget one real browser session a day. Not a workaround to
   reach for casually.
3. **Corroborate MINISO.** Its count now dominates every total here, and it rests on one CMS whose
   duplicate rows we clean up ourselves. A second source would turn a careful guess into a fact.
4. **Small-state labels** on the state view overlap in the northeast; they need leader lines.
5. **Monitoring.** The job is scheduled but nothing watches it. The sibling project learned the
   hard way that a collector cannot report its own death: it needs an external dead-man's switch
   that fires on the *absence* of a ping, not a check that runs on the same sleeping machine.

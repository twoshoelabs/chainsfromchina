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
| POP MART | 泡泡玛特 | — | blocked: Cloudflare bot management |
| MINISO | 名创优品 | — | blocked: Wix Data query not yet identified (~400 US stores) |
| HEYTEA | 喜茶 | — | blocked: the site's store page is a global flagship showcase, not a locator |
| Cotti Coffee | 库迪咖啡 | — | blocked: no first-party US locator exists |

The blocked chains are listed on the map with their reasons. A tracker that quietly omits the
chains that were inconvenient will eventually report that Chinese retail in America is all tea
shops, and `status` prints the reason beside every chain so a hole is never silent.

**MIXUE is the prize.** Its locator publishes `coming_soon` alongside `open`, so the pipeline is
visible weeks ahead and an opening can be dated to the day the status flips rather than to the
day a row appeared. Seventeen of its twenty-seven US listings were announced-but-not-trading on
the baseline day, most of them ringing the San Gabriel Valley.

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
```

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

### Three traps in this page, all of which bit once

1. Do not add `stroke-width` to `.store` in CSS. A CSS declaration overrides the presentation
   attribute `app.js` scales with the view, and the announced-store rings get drawn 1.6 metres
   wide — i.e. invisible, while the DOM looks perfectly correct.
2. Do not set a state label's `font-size` in viewBox units. The viewBox is in metres, so that
   asks for ~115,000px of type, which browsers silently clamp (5,000px in Chrome) and the label
   renders three pixels wide. Labels are drawn at 14 units and scaled by a transform instead.
3. Do not rely on the `hidden` attribute alone for anything given `display` in CSS — an
   element-level `display:flex` beats the UA rule for `[hidden]`.

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

1. **MINISO** — drive the Wix locator widget once in a browser, capture the `/_api/cloud-data`
   query with its collection id, then call it directly. ~400 US stores, the largest footprint in
   scope and the biggest single gap.
2. **Geocode Luckin** so New York stops being a hole in the Stores view. It is already counted
   correctly by state, which is why that view exists.
3. **POP MART** — ask for access, or budget one real browser session a day. Not a workaround to
   reach for casually.
4. **Schedule it.** `scripts/com.dansilver.us_chain_atlas.plist` runs the pass daily; the series
   is worth nothing until it has length.

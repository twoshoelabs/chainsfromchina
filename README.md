# chain_atlas — the collector behind *Chains From China*

Published as **Chains From China** (chainsfromchina.com, registered 21 Sep 2026). The repo keeps
its own name on purpose: the site is the publication, `chain_atlas` is the instrument.

Two records of the same subject, kept deliberately apart because they are different kinds of
claim:

1. **A daily census of US store locators.** One adapter per chain, an immutable raw capture per
   chain per day, observations that are never updated, and events derived from the difference
   between two days. Every number has a gzipped capture behind it. Sibling of `store_atlas`
   (門市帳), which does the same job for Taiwan.
2. **An international register**, reviewed periodically rather than crawled: which chains have
   set up in Korea, Japan, Singapore, the UAE, Australia, Canada and Western Europe, how many
   locations, and when the first one opened. Hand-typed from filings and the trade press, with
   a source and a confidence on every row.

The project was called `us_chain_atlas` until the register outgrew the name.

Both pages carry a standing disclaimer: this is an independent measurement project, not
affiliated with or endorsed by any company it names. Brand names identify the businesses being
measured — which is nominative use, and is why no brand appears in the domain, the logo or the
page styling.

**Why it exists.** As of September 2026 nobody publishes a store-level, dated map of
mainland-China-origin chains in the US. Momentum Works tracks this category well but reports on
Southeast Asia in PDFs; Technomic's Top 500 is annual and these chains are still too small to
make it; the trade press counts them accurately but in prose, as snapshots. All of those are
pictures of a moment. The thing none of them has — and the only thing that answers "how fast" —
is a daily series, which cannot be bought later because nobody is keeping it.

## Who this is for

**A US audience.** The product is the American picture: which mainland-China-origin chains are
open here, where, and what changes week to week.

The international register exists to serve that, not to compete with it. Its job is to answer
"which chains are expanding outside China, and therefore might turn up here" — so it is
deliberately **broad and shallow abroad**. That ChaPanda entered Korea, Australia, Malaysia and
Thailand and then opened in Flushing in August 2025 is the useful fact; a precise count of its
Korean stores is not. Breadth and timing are the signal.

One consequence worth stating plainly: the MINISO UAE daily collector is deeper than this
framing needs. It was built when the scope looked wider, it costs seven requests a day, and it
stays because it works — but it is not a template for more non-US adapters.

## Scope

Mainland-China-origin chains, in any market this project covers. Taiwanese and Hong Kong brands
(Tiger Sugar, The Alley, Gong Cha) are an earlier and different wave and are out of scope as
*origins*. Asian grocers such as 99 Ranch and H Mart sell Chinese products but are not Chinese
chains. Hong Kong is out of scope as an origin and in scope as a *destination* — the two are
different axes.

**Collectability is not a test for inclusion.** A chain earns its place by trading in a covered
market; whether we can read its locator decides the *method*, never the membership. Chains with
no usable source stay on the roster as disabled adapters or hand-typed register rows, carrying
the reason, so `status` and the register show the shape of the category rather than the shape of
what happened to be scrapable. The clearest case is Yang's Braised Chicken Rice: trading in
America since 2017, no locator anyone has found, and invisible under any other rule.

## State of the collection — 21 September 2026

| Chain | | Source | Stores |
|---|---|---|---|
| MIXUE | 蜜雪冰城 | tRPC endpoint on the US franchise site | 10 open + 17 announced, with coordinates |
| CHAGEE | 霸王茶姬 | store list inside the Next.js flight payload | 11, with coordinates |
| Luckin Coffee | 瑞幸咖啡 | server-rendered store cards | 22, **no coordinates published** |
| MINISO | 名创优品 | Wix Data `Locations` collection | **430** across 46 states, with coordinates |
| MINISO UAE | 名创优品 | seven emirate pages on the UAE site | **46** across all 7 emirates, no coordinates |
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

## The first non-US market

MINISO UAE (`miniso_ae`) is the archive's first market outside America, and adding it forced a
real change rather than a copy-paste: every row now carries a `country`, `geo.py` keys cells
against a projection centre per market, and the US map filters to `country='US'` so a Gulf
estate cannot leak onto a map of America. One adapter covers one market — MINISO's US and UAE
estates are published by different sites in different shapes, so they are two adapters and two
chain ids, never one. Pretending otherwise would make a broken UAE page look like US closures.

**The route not taken.** The site runs WP Store Locator, whose usual endpoint is
`/wp-admin/admin-ajax.php?action=store_search` — one request instead of seven, and almost
certainly carrying the coordinates this adapter lacks. This site's `robots.txt` disallows
`/wp-admin/`, so it is not used. The plugin's REST route, `/wp-json/wp/v2/wpsl_stores`, is
allowed but returns an empty array. The seven emirate pages are first-party, explicitly allowed,
and are what a visitor sees; seven polite requests a day is the price of not walking through a
door marked shut.

**What it yields:** 46 stores — Dubai 19, Abu Dhabi 14, Sharjah 6, Ras Al Khaimah 3, Fujairah 2,
Ajman 1, Umm Al Quwain 1. A mall name and an emirate, nothing more: no address, no coordinates,
no store code. So they are counted and never mapped, exactly like Luckin's New York estate.

**A register row graduated.** MINISO/UAE was previously a hand-typed register entry reading
"present, count unknown", annotated as the best candidate for promotion into real collection.
It now reads **46&#9733;** — measured, high confidence — with the original typed claim preserved
beneath it in `was_typed`. That promotion from research to evidence is the point of keeping the
two records in one project, and `register.py` marks it rather than silently overwriting.

**One character worth the test it got.** "AL GHURAIR CENTER" carries a zero-width space in the
page source. Left in the identity key, it would rewrite that store's key the day an editor
removes it, and the archive would report a closure and an opening in the same Dubai mall on the
same day.

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

## The international register

A second, different thing, kept deliberately apart from the collector: **which PRC-origin chains
have set up in which markets**, how many locations they have there, and when the first one
opened. Markets covered: South Korea, Japan, Singapore, the UAE, Australia, Canada, and Western
Europe (UK, France, Germany, Spain, Italy, Netherlands).

```
python -m chain_atlas register                 # the chain x market matrix, then the detail
python -m chain_atlas register --chain heytea  # one chain
python -m chain_atlas register --market SG     # one market
python -m chain_atlas register --gaps          # pairs nobody has checked
python -m chain_atlas register --stale         # entries not reviewed in 90 days
```

Data lives in hand-edited `register.json`; the page is `map/register.html`.

**A register is not a census, and the difference is the whole design.** Every number on the US
map is something the collector saw for itself and can produce a gzipped raw capture for. Nothing
in the register is — these are facts from filings, exchange announcements and the trade press,
typed in by hand. So the schema forces what that implies, and `test_register.py` enforces it:

- **An unpublished count is `null`.** Never inferred, never split out of a regional total. Super
  Hi reports 13 restaurants across Japan *and* South Korea; that is recorded as a note on both and
  a count on neither, because an invented split is worse than a blank.
- **A count with no as-of date is rejected outright.** An undated number is a rumour.
- **`no_evidence` is not `none`.** It means a search did not find a presence, which is a claim
  about the search. Luckin is `no_evidence` in Japan and Korea, not absent from them.
- **Every `present` row must cite a source or explain itself**, and every count below high
  confidence must carry a note saying why.

### What the first pass found

- **Luckin in Singapore is the best-documented entry anywhere here**: opened 31 March 2023, 60
  stores at the two-year mark, **82 as of 31 March 2026** — an exact day and a company-disclosed
  count.
- **HEYTEA is the earliest mover**, opening at ION Orchard in Singapore in November 2018, five
  years before London Chinatown (August 2023) made it the first of this wave outside Asia.
- **CHAGEE in Singapore is the entry that justifies the schema**: it entered by franchise in 2019,
  reached twelve outlets by 2021, **withdrew entirely in early 2024**, then re-entered
  company-owned that August. A register that stored only "present" would have flattened a full
  retreat and re-entry into a tick.
- **POP MART's per-country numbers are the weakest data here** and are marked low confidence
  throughout. Pop Mart discloses regionally — 630 stores across 20 countries at end-2025 — so the
  per-country figures come from a commerce aggregator and should not be quoted until an IR
  breakdown is found.
- **MINISO in the UAE is the best candidate for promotion out of the register and into real
  collection**: it runs a dedicated UAE site with its own store locator, the same shape as the US
  one already collected daily.

**51 of 96 chain/market pairs have not been checked at all.** They are blank on purpose and
`--gaps` lists them; an unchecked pair is not an absence.

## What a day of investigation established

All twelve chains known to trade in the US were investigated on 21 September 2026. Five are
collected; seven are not, and the reasons are specific rather than "no locator found".

### A locator that lies is worse than one that is blocked

Tai Er's parent publishes a store finder whose endpoint answers instantly, reports 12 stores with
5 in the United States, and returns **the same Guangzhou restaurant for every row**. An adapter
written against it without reading the rows would have put "5 US stores" into the archive, where
it would have looked exactly like every correct number beside it. A blocked chain announces
itself in `status` every morning; a lying locator says nothing at all.

That is why every adapter here reads its own output before trusting it — MINISO's duplicate CMS
rows, CHAGEE's flight-payload parse, Tai Er's repeated record. "The endpoint responded" is never
evidence that an adapter works.

### A blocker is a fact about a date, not a verdict

`recheck` re-probes the URL behind each blocked chain and prints what it answers today beside the
reason recorded when someone last gave up. ChaPanda has no locator because it has two American
shops; a chain with thirty will build one. The interesting moment is the day it appears, and
nothing but a periodic re-probe would notice.

### Two walls that are not technical

**Cotti** has a US store finder — `mobile.us.cotticoffee.global`, a Flutter app that renders to
canvas and opens on a **Legal Statement** requiring acceptance of Terms and Conditions. This
project will not accept an agreement on the operator's behalf. Collectable in principle, blocked
pending a human decision.

**Yang's** serves browsers and hangs on everything else. `yangschicken.ca` resolves, loads in a
browser, and times out from `curl` run in the operator's own terminal — same machine, same
network, 25 seconds, no bytes. Both chains now reduce to one question: drive a real browser
session daily, or do not collect them.

Before paying that price for Yang's, settle this: its own page lists the Tustin restaurant as
trading while Yelp marks that address closed. **A census detects a closure by a store
disappearing from the list.** A list that never removes anything cannot produce one — it would
report a chain growing monotonically forever while the archive faithfully recorded the fiction.

### Haidilao, and the cost of looking on the obvious hosts

Haidilao's 15 US restaurants are collected from
`haidilao-inc.com/us/eportal/store/listObjByPosition` — one request, with coordinates, a stable
per-store id, phone and hours. Every obvious host was a decoy: **haidilao.com** serves only
Greater China whatever country is passed, **superhiinternational.com** publishes country summaries
and no store list, and **haidilao.us / hdlus.com / haidilaousa.com** do not resolve.

The lat/lon in that URL are a **sort origin, not a filter** — the same fifteen ids return from
Taiwan, Kansas or New York, verified from three origins before the adapter was written, because an
endpoint silently returning "nearest N" would truncate the estate the day it outgrew N.

Its parent's country endpoint reports **13 US restaurants in 8 cities** where the locator lists
**15 in 15 cities**: a company's published summary of itself being the less accurate of its two
first-party sources.

### The alias sweep

Several chains trade under a different English name in America, and searching the wrong one makes
a chain look absent:

| Chain | At home | Trades in the US as |
|---|---|---|
| ChaPanda | 茶百道 | **TeaByDo** |
| Naixue | 奈雪的茶 | **NaiSnow** (shopfronts: "Nayuki Tea & Bakery") |
| Juewei | 绝味鸭脖 | **Juewei Yabo** (King of Braise in Singapore) |
| Tai Er | 太二 | Tai Er Sichuan Cuisine — same brand, no trap |

**Juewei was recorded as "US presence not established". It has been trading in Los Angeles and
San Gabriel all along.** Both pages now show every chain as it trades here, with its Chinese name
beside it and the alternate English brand where they differ.

### POP MART: the defended thing was the website, not the data

Pop Mart was recorded all day as uncollectable. `www.popmart.com/us/store-list` returns a
Cloudflare challenge to any non-browser client, and so does the Hong Kong equivalent, so the
block looked site-wide and deliberate. That conclusion was dated, recorded — and wrong.

It broke open by reading **Overture's provenance**. Its eight New York Pop Mart rows cited
`dataset=AllThePlaces`, an open-source project that scrapes brand store locators exactly as this
project does. Its Pop Mart spider never touches the website. It calls the app's API host:

    POST https://prod-intl-api.popmart.com/shop/v1/store/mapStoreList

Empty bounds and a single-space query return the whole global estate — 384 stores, **182 of them
American** — with coordinates, addresses, phone, hours and a stable `uniqCode`. No challenge, no
token, and robots.txt 404s on that host. One request a day, lighter than the seven the UAE site
costs.

**A chain can defend its storefront and publish the same records openly through the API its own
app uses**, and no amount of probing the website would have revealed it. Every remaining "no
locator exists" verdict deserves the same suspicion: they describe where somebody looked, not
what exists.

Its country labelling is not reliable either. The feed lists a roboshop at "100 City Centre Dr"
as country "United States"; the coordinate is Mississauga, Ontario. The pipeline drops rows whose
coordinates land in no US state and prints the count.

### Three bugs that came with it, all of the quiet kind

Adding 182 stores in unfamiliar address formats exposed three faults worth recording:

1. **A fix that broke more than it fixed.** Spelling out full state names ("Rosemont, Illinois
   60018") was implemented as a substitution across the whole address — which rewrote *cities*
   that share a state's name. "New York, NY" became "NY, NY" and "Washington, DC" became "WA,
   DC", corrupting every New York City store. The existing tests caught it within a minute. The
   state is now matched in position, never substituted.
2. **Two code paths over one archive.** The state fallback and the outside-US check lived only in
   `run()`, so a `reparse` of the same raw file produced 182 POP MART rows where `run` produced
   181, and twenty-one stores lost their state. Both paths now call one `normalise()`.
3. **Reparse destroyed derived data.** It rebuilds store rows from the raw capture, and a
   geocoded coordinate is not in the raw capture — so reparsing silently unplaced all 22 Luckin
   stores. It now re-derives them from the geocode cache, which costs nothing.

## Three shapes of partial knowledge

Keeping these apart is most of what makes the archive trustworthy:

| | example |
|---|---|
| **a census** — complete roster, re-read daily, so absence means something | MINISO's 430 |
| **a count without a roster** — a number, no addresses (`Adapter.KNOWN_COUNT`) | Haidilao's parent saying "13 US restaurants" and naming none |
| **a roster without completeness** (`manual/sightings.json`) | Cotti's 15 known New York shops |

**Sightings never enter stores, observations or events.** Put a partial roster in the census and
the day a complete source is read, every store beyond the partial list is recorded as an
**opening that never happened** — growth invented by the act of learning more. They draw as open
squares, are excluded from every total, and a sighting graduates by being deleted.

Sightings carry their own confidence: confirmed rows draw solid, ones the operator flagged
"maybe" draw dashed, and the chip separates them.

### Dated manual rosters: hand data as a count, never a census

A sighting group can carry an explicit `complete_as_of` and `complete_scope`, which turns it into
a **count** — while staying rigorously outside the collected census. The completeness flag is a
claim a human writes, never one the code infers; only `confirmed` locations are counted, and the
number lives in its own `manual_rosters` field that never touches `by_state` or `meta.counts`, so
it can never manufacture an opening or a closure. The first is Cotti, **complete for New York City
as of 22 Sep 2026 — 13 confirmed**, shown with a "hand-assembled, not monitored" caveat.

## Watchers: opening and closing candidates for chains we cannot scrape

Four of the chains here publish no US roster this project can read, so the census cannot see them
open a store. A city or county health department can. A **watcher** reads one jurisdiction's own
food-establishment records for these chains and produces OPENING and, where the data supports it,
CLOSING **candidates** for a human to verify. Like the Overture pass, a watcher feeds the review
queue and never writes to stores, observations or events — a machine-found location is a lead, and
the base rate of leads in this subject does not earn trust unseen. The shared logic — whole-term
name matching (so BISCOTTI is never Cotti) and a street fingerprint that lines one source's address
up with another's — lives in `scripts/permit_common.py`.

**New York** (`scripts/nyc_permits.py`) queries the city's live inspection feed. Its gift is the
`Pre-permit (Non-operational) / Initial Inspection`, which happens *before* a restaurant opens — the
closest thing to an authoritative opening signal found for a chain we cannot scrape, with a date.
The first run matched 52 establishments, 25 already ours, **24 new candidates including 18 HEYTEA
against the 6–8 any other source had**, 8 carrying a pre-opening signal.

**Los Angeles County** (`scripts/la_permits.py`) covers the San Gabriel Valley, this project's
densest region after Flushing. It is a different shape of source and the watcher says so: a whole-
years CSV export (no live query), no pre-permit inspection (the opening proxy is the earliest
inspection date), and no coordinates (cross-reference is by street fingerprint) — but it publishes
a `PROGRAM STATUS` of ACTIVE/INACTIVE, a **closing** signal New York does not carry. The first run
found new HEYTEA across Beverly Hills, Monterey Park and Rowland Heights, a second Cotti in Rowland
Heights, a NaiSnow in San Gabriel, and two INACTIVE MINISO records to check as closings — one of
them a store the census still counts.

**Neither watcher reports a closing from absence.** A store missing from an inspection feed is not
shut any more than one missing from Overture is; only an explicit INACTIVE status is a closing
candidate, and even that is a lead for a human, never an automatic closure.

### Derived coordinates, and keeping them labelled

Luckin publishes 22 New York addresses and no latitudes. `chain_atlas geocode` resolves US
addresses through the **US Census Bureau** geocoder — free, keyless, authoritative, no terms that
conflict with republishing a derived point. All 22 matched first pass.

`stores.coord_src` keeps `published` and `geocoded` apart: geocoded points draw at lower opacity
and say so on hover. Geocoding only ever fills a NULL — the chain is the authority on where its
own shop is. Results cache by normalised address, because a geocode is a derived fact about a
string, not an observation. US-only, permanently: MINISO's 46 UAE stores publish a mall name and
an emirate.

## What third-party place data was worth, measured

Overture Maps was cross-checked against New York (`scripts/overture_review.py`). For chains
already collected it held about **a third** of what first-party collection holds — Luckin 1
against 22, MINISO 6 against 15, MIXUE 0 against 11.

Two of its rows claimed a store this project does not hold. The operator verified both. **Both
were wrong:**

| Overture said | Reality |
|---|---|
| Haidilao, 170-16 39th Ave, **open**, confidence 0.972 | Phantom. Flushing is 138-23 39th Ave — which Overture *also* lists, 24 m from ours |
| MINISO, 579 Broadway, **open**, confidence 0.77 | Permanently closed |

Meanwhile all three of its Cotti candidates — at 0.515, 0.289 and **0.138**, the lowest scores in
the sample — were confirmed real. Five verified rows is not a study, but it is enough to stop
using `confidence` as a filter.

### Why it missed so much, and why that is structural

Cotti has **15 confirmed New York shops**. Overture has **3**, and the query was not at fault:
re-running over the NYC bounding box with no region or country filter returns the same three.

| | Overture had |
|---|---|
| Chinese-American neighbourhoods — Flushing ×2, Sunset Park ×2, Bensonhurst, Lower East Side | **0 of 6** |
| Elsewhere in NYC | 3 of 9 |

Six for six missed, and the mechanism is visible in the data: every Cotti row Overture *does* have
is sourced from **`meta`** — Facebook's place data. Overture is assembled from Meta, Microsoft,
Foursquare and AllThePlaces, all of which need a business to maintain a Western-platform listing.
The shops it missed serve communities that find them through WeChat, Xiaohongshu, Fantuan and
Chowbus.

**That bias points directly at this project's subject.** Chinese chains open disproportionately in
the neighbourhoods these datasets cover worst, so third-party place data is least reliable exactly
where this archive most needs it.

Foursquare OS Places is moot twice over: its public S3 dump now holds only LICENSE.txt and
NOTICE.txt, the advertised PMTiles archive 404s, and access has moved behind a Places Portal
account — and Overture already ingests Foursquare, so a separate pull would partly retest what
was just tested.

## Setup

```
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -r requirements.txt
cp .env.example .env        # set CHAIN_ATLAS_DATA and a real mailto in the User-Agent
.venv/bin/python -m chain_atlas run        # first run is the baseline; no openings emitted
.venv/bin/python -m chain_atlas export     # writes map/data/*.json
.venv/bin/python scripts/serve_map.py         # http://127.0.0.1:8765/
```

Build the venv with `uv`, not a Homebrew interpreter — the sibling project lost two days of
collection in September 2026 to a venv whose `python3` symlinked into a Cellar path that a
`brew upgrade` then removed.

## Scheduling

Installed on this machine (21 Sep 2026) as a user LaunchAgent, relabelled
`com.dansilver.chain_atlas` when the project was renamed:

```
cp scripts/com.dansilver.chain_atlas.plist ~/Library/LaunchAgents/
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.dansilver.chain_atlas.plist
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
Note that `.env` **overrides** the environment, so `CHAIN_ATLAS_DATA=... ./scripts/run_daily.sh`
will not do what it looks like it does; point `.env` at the other archive instead.

Useful afterwards:

```
launchctl print gui/$(id -u)/com.dansilver.chain_atlas     # state, run count, last exit code
launchctl kickstart -p gui/$(id -u)/com.dansilver.chain_atlas   # run it now
tail ~/chain_atlas_data/logs/daily.log                     # what it did
launchctl bootout gui/$(id -u)/com.dansilver.chain_atlas   # stop it
```

### If you rename this project again

It is more than a text substitution, and one step is easy to miss. In order: `launchctl bootout`
the agent first so nothing fires mid-move; rewrite the code and the `CHAIN_ATLAS_*` environment
names; move the repo; checkpoint the WAL before moving the archive (`PRAGMA
wal_checkpoint(TRUNCATE)`) and rename the `.sqlite` with it; **rewrite `runs.raw_path`**, which
stores absolute paths and silently breaks `reparse` otherwise; rebuild the venv, whose scripts
carry absolute paths; rewrite `.env`, which is gitignored and so is untouched by any code-wide
rename; then reinstall the agent under its new label and confirm the old one is gone. Verify with
a `reparse`, which is the one command that reads the stored paths back.

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
| `recheck [--chain X]` | re-probe the URLs behind each blocked chain and report what they answer now. Touches nothing |
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
CHAIN_ATLAS_DATA=$(mktemp -d) .venv/bin/python tests/test_events.py
.venv/bin/python tests/test_usaddr.py
.venv/bin/python tests/test_miniso.py
.venv/bin/python tests/test_miniso_ae.py
.venv/bin/python tests/test_register.py
```

`test_register.py` checks that the register's validator actually refuses the mistakes a person
makes while typing at midnight — an undated count, a presence with no source, a duplicated pair,
a date with no stated precision — and that the shipped `register.json` passes all of them.

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

**Alaska, Hawaii, Puerto Rico and Guam are insets**, framed and captioned because their scale is
not the mainland's. Each is projected about **its own centre** rather than the mainland's 45N
100W: Guam sits 97 degrees of arc from that centre, where this projection is still valid but
visibly shears whatever is drawn in it. An inset is its own small map and nothing is compared
across the frame, so a local centre costs nothing and keeps the shapes honest. The mainland
keeps 45N 100W exactly, because that is the centre `geo.py` keys its cells with.

Puerto Rico and Guam hold **no stores yet** — the insets are there so that the first one does not
have to be discovered the way Hawaii's were. Their geometry comes from Natural Earth 10m,
vendored into `map/us-states.geojson` alongside the 50 states. The US Virgin Islands, American
Samoa and the Northern Marianas are *not* covered; `usaddr.py` accepts those codes, so a store in
one would parse and count correctly and then appear in the off-map banner below, which is the
signal to add another entry to `INSETS` — a four-line change using the same vendored source.

They are not decoration: MINISO has two Hawaii stores — Pearlridge Center in Aiea and Waikele
Premium Outlets in Waipahu — and before the insets existed they were collected every day,
projected correctly, and drawn 3,440 km off the left-hand edge of the canvas. Nothing was wrong
with the data, which is why no test caught it.

Hawaii is also the clearest case of this archive understating a state: Cotti Coffee has a Pearl
City store that the trade press reported in 2024, and Cotti publishes no first-party US locator,
so it is not collected. Hawaii's real number is higher than the two shown.

The page now runs `offMapCheck()` on load: any store that falls outside the mapped area and is
not in an inset is reported in a banner above the map rather than silently vanishing, the same
way the archive counts stores with no coordinates instead of dropping them.

Dots are drawn **largest chain first**, so the smallest chain ends up on top. This is not
cosmetic: SVG paints in document order, and the archive's natural order put MINISO's 430 dots
last, which covered all 11 CHAGEE stores completely — both are mall chains and sit in the same
malls, so CHAGEE simply could not be found on the map while being collected perfectly. A chain
with a tenth of the footprint has to win the overlap or it reads as absent.

### Five traps in this page, all of which bit once

1. Do not add `stroke-width` to `.store` in CSS. A CSS declaration overrides the presentation
   attribute `app.js` scales with the view, and the announced-store rings get drawn 1.6 metres
   wide — i.e. invisible, while the DOM looks perfectly correct.
2. Do not set a state label's `font-size` in viewBox units. The viewBox is in metres, so that
   asks for ~115,000px of type, which browsers silently clamp (5,000px in Chrome) and the label
   renders three pixels wide. Labels are drawn at 14 units and scaled by a transform instead.
3. Do not rely on the `hidden` attribute alone for anything given `display` in CSS — an
   element-level `display:flex` beats the UA rule for `[hidden]`.
4. Anything inside an inset `<g>` is already scaled by that group's transform, so dot radii,
   stroke widths and label scales must be divided back out — otherwise Alaska's dots render a
   third the size of Ohio's and read as smaller stores rather than as a smaller map. Alaska's
   Aleutian rings also cross the antimeridian and inflate its bounding box to 2,800 km wide;
   they are dropped, as printed US maps drop them.
5. `scripts/serve_map.py` sends `Cache-Control: no-store` deliberately. Without it the browser
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

**Priorities follow the US framing.** Anything that deepens the American picture beats anything
that widens the foreign one:

1. **The seven US chains that are here and uncounted** — Pop Mart, HEYTEA, Cotti, Yang's, Tai Er,
   Haidilao, ChaPanda, Naixue. The US census currently covers four chains out of twelve known to
   trade here; that gap is the product's biggest hole. Tai Er and Haidilao are the best targets
   (listed parents that disclose counts, so a locator read can be checked against a filing) and
   ChaPanda the most time-sensitive (it arrived in Aug 2025, so starting now captures nearly its
   whole US history).
2. **Geocode Luckin** so New York stops being a hole in the Stores view. It is already counted
   correctly by state, which is why that view exists.
3. **POP MART** — ask for access, or budget one real browser session a day. Not a workaround to
   reach for casually.
4. **Corroborate MINISO.** Its count now dominates every total here, and it rests on one CMS whose
   duplicate rows we clean up ourselves. A second source would turn a careful guess into a fact.
5. **Small-state labels** on the state view overlap in the northeast; they need leader lines.
6. **Monitoring.** The job is scheduled but nothing watches it. The sibling project learned the
   hard way that a collector cannot report its own death: it needs an external dead-man's switch
   that fires on the *absence* of a ping, not a check that runs on the same sleeping machine.

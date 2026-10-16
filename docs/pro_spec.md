# PRO spec — building, verifying, and selling the Pro/Intelligence edition

Status: draft, 2026-10-16 (repositioned). Owner: Twoshoe Labs. The US census is complete or nearly so;
this spec covers the next phase — turning the measured census and the Pro-tier dimensions
([china_stores](../manual/china_stores.json), [financial_anchors](phase2_revenue_spec.md),
[dossiers](../manual/dossiers.json), the [FDD miner](../chain_atlas/fdd.py)) into a **researched,
verifiable, sellable PRO product**.

This is a formalization, not a rebuild: ~70% of the platform already exists (the typed stores, the
hash-chained [provenance ledger](../chain_atlas/provenance.py), the daily routines, `contribute.html`).
The work is to connect them into one **intake → verify → assemble → gate** pipeline on one schema — and
to point that pipeline at the three things that are actually defensible.

---

## 0. Strategic thesis — what PRO is, and why it is defensible

**PRO is a proprietary-data-and-monitoring business, not a content business.** The distinction is the
whole strategy, and it is set by one test: *could a committed buyer reproduce this with a capable LLM
and a weekend?*

- **Yes, for the analysis layer.** A per-brand write-up — history, founders, IP portfolio, the read on a
  public HKEX filing — is desk research an LLM now does in minutes. The 52TOYS economics were assembled
  from a handful of web searches. **We must assume every buyer can do this, and therefore never price it
  as the product.** Selling "nicely-written company profiles" is dead on arrival.
- **No, for the observation layer.** "Every China-origin chain's every US outlet — operator-verified,
  deduped, closings tracked, updated daily" **does not exist in any public source**. An LLM cannot
  retrieve it, because there is nothing to retrieve; it exists only because we go and look and maintain
  it. A buyer who wanted it would have to *become us*: stand up the collection, run it daily, and make
  the scope and identity calls. That cost is what a subscription lets them avoid.

LLMs do not threaten this product — they **sharpen the wedge**. By commoditizing the knowledge layer,
they make the scarce asset the *verified, maintained, complete observation* that no amount of searching
reproduces. The analysis becomes the convenience wrapper; the data is the asset.

### The three pillars PRO is sold on

1. **Census — the proprietary measured dataset.** The complete, deduped, authenticity-resolved roster of
   China-origin chains operating in the US, plus home-market scale. The moat has four parts, each
   un-searchable: the **measured outlets** themselves; **coverage of the full universe** (knowing that
   JiBeiChuan, Hwa ShooShoo, Makkee, Bingxue even exist — the 85-brand long tail *is* the product, not
   the 15 famous names); the **longitudinal time-series** (openings/closings pace — point-in-time search
   can never back-fill *when* a store opened or closed); and the **cross-entity structure** (co-tenancy,
   parent/sister lineage, the multi-market register).
2. **Alerts — monitoring is the recurring-revenue hook.** The renewable value is not a document a buyer
   reads once; it is the push that says *a new China-origin chain just entered the US*, or *a tracked one
   opened / closed / signed a lease*. This is impossible to DIY precisely because it requires continuous
   watching, and it is what a landlord or investor renews for every month. Documents are bought once;
   monitoring is subscribed to.
3. **Provenance — trust is what clears the buyer's bar.** For the buyer who must *act* on the number — an
   investor in diligence, a REIT underwriting a lease — "an LLM told me" fails. A sourced, dated,
   hash-chained, confidence-tiered datum clears diligence. Provenance is not hygiene; it is the feature
   that lets the data be *used*, and the one an LLM-generated profile structurally lacks.

### Honest framing of the market

This is a **boutique data subscription**, not a venture-scale SaaS. The vertical — China-origin chains
in the US — has realistically low-hundreds of plausible buyers (China-consumer investors, mall landlords
and REITs, suppliers chasing inbound chains, franchise advisors, competing US operators, the chains'
own advisors). A six-to-low-seven-figure ARR ceiling, executed on a low cost base (automation + owner
expertise), is the realistic prize — and a good business. It is a **freshness product**: value is in
maintenance, and lapses in updating erode it faster than any competitor could. Price and staff
accordingly.

---

## 1. Organizing principles — the data/analysis taxonomy

Five principles, in priority order.

1. **The provenance wall is the product.** Every datum carries *how it was obtained*, on a four-rung
   ladder — **measured** (our own operator-observed census; audited FDD Item 21) → **filed** (primary
   HKEX / A-share / FDD figures) → **modeled** (revenue/capacity estimates) → **reported** (press /
   company statement). Already enforced via `confidence` fields, the ledger, and the public `~`
   unverified marker. **No number ships without its rung visible.** This is pillar 3: competitors (and
   LLMs) emit numbers; we emit *sourced* numbers a buyer can act on.

2. **Four data layers, mapped to buyer questions** (not to source):
   - **Presence** — the census: who / where / status / authenticity. *Done.* The proprietary core (pillar 1).
   - **Scale & trajectory** — home-market store counts, opening/closing pace, US-vs-home ratio
     (`china_stores`, `openings`). The time-series that feeds alerts (pillar 2).
   - **Economics** — unit economics, revenue/capacity estimates, build-out cost, AUV
     (`revenue` / `capacity` / FDD Items 7, 19, 21).
   - **Structure & intent** — corporate lineage, operating model, franchise terms, supply chain,
     pipeline, risk (FDD Items 1–8/20, register, listings).

   Economics and structure are the *least* defensible layers (most of their raw inputs are public). They
   add value only when (a) curated and normalized across the whole universe, and (b) tied to the
   proprietary measured footprint. They are features of the dataset, never the standalone product.

3. **Buyers are lenses, not segments.** Build one four-layer record; *recombine* it per decision.
   CRE → pipeline + co-tenancy + survival. Competing chains → roster + pace + unit economics.
   Suppliers → supply-chain structure (Item 8) + scale. Investors → China financials + US traction +
   lineage. The brands → rivals' rollout. A "lens" is a saved query over the four layers — and each lens
   has a natural **alert** (its records changing is the thing the buyer wants pushed).

4. **The dossier is the on-ramp, not the product.** A per-brand dossier is the *demonstration* of the
   proprietary data and the convenient wrapper around it — a sample sells the subscription; it is not
   itself the moat, because its narrative layer is LLM-reproducible (§0). Keep dossier assembly a
   one-command operation, but treat a free or low-cost sample dossier as **lead-gen for the dataset and
   the alerts**, not as the primary revenue line. Revenue comes from access to the *maintained, complete,
   verified* dataset and from *monitoring*, which a one-off document cannot substitute for.

5. **Cadence matches volatility — and cadence is a product.** Census = daily (adapters). Scale/economics
   = per-filing/quarterly (intel routine). Structure = annual (FDD/filings). The *detection of change at
   each cadence is the alert stream* (pillar 2): a daily-cadence new-outlet detection is a push; a
   quarterly filing is a scale-update push. Don't hand-refresh what changes yearly; don't batch-refresh
   what changes daily; and surface every detected change as a monitorable event.

---

## 2. Manual vs automated research

Rule: **automate structured public retrieval; reserve humans for judgment, Chinese-language sourcing,
and narrative.**

| Research task | Mode | Form | → PRO |
|---|---|---|---|
| Census refresh | **Automated** (daily adapters) | store records | geojson + counts |
| FDD mining (MN CARDS) | **Automated** (done) | `fdd_extracts` + anchors | economics/structure |
| Filings (HKEX/cninfo) | **Automated** (`filings.py`) | `financial_anchors` | scale/economics |
| New-outlet discovery | **Automated** (daily routine) | push-notified leads | human verifies → census → **alert** |
| **Identity resolution** (real vs copycat/authorized) | **Manual** | correct Chinese chars + brand's own site | gates what *counts* — the core skill |
| **China home-market financials** | **Hybrid** (routine drafts → human verifies) | patch → review → merge | `china_stores`/`dossiers`/anchors |
| **Dossier narrative** (history, items, flagships) | **Manual, but low-priority** | sourced prose | the on-ramp wrapper, not the moat |
| Authenticity / measured-vs-modeled calls | **Manual** | provenance-tagged | the `~` wall |

**One schema, two inputs.** Manual and automated research both produce records in the *same*
provenance-tagged schema (§4). The product never cares *how* a datum was obtained — only how well it is
sourced. Automated outputs that are ambiguous set `status: submitted` / `needs_human_read` and queue for
a human; they never silently become sellable. CA DFPI and WI DFI stay manual (no free public FDD
library — see `fdd.py`); **identity resolution stays manual by design — it is the moat** (the thing an
LLM gets wrong: real vs copycat vs authorized, namesake disambiguation, scope calls). Dossier narrative
stays manual but is explicitly *de-prioritized*: it is LLM-reproducible, so invest the least human effort
that keeps the on-ramp credible, and spend the saved time on coverage and verification instead.

---

## 3. The submission platform — intake → verify → assemble → gate

1. **Intake (the front door).** One schema (§4), four channels:
   - *Automated* — the cloud routines write submissions (the intel-refresh / lead-discovery pattern).
   - *Owner/manual* — the owner console (`chain_atlas/console.py`) and CLI writing a record + source.
   - *Crowdsourced* — `map/contribute.html` from sighting tips to source submission.
   - *Field/paid researchers* — same schema, first-class input.
2. **Verify (the gate that makes it sellable).** Every submission enters at its *claimed* tier/
   confidence and must clear verification (human for judgment; cross-source otherwise) before reaching
   full-confidence PRO output. The **provenance ledger** records the chain of custody;
   `status ∈ {submitted, verified, rejected, superseded}` plus the `watch` verdict (real-but-not-open)
   and `needs_human_read`/`unverified` are the hold states. The **verification queue**
   (`chain_atlas/verify.py`) is built.
3. **Detect & alert (pillar 2 — the recurring product).** Every verified change is an **event**: a new
   brand entering the US, an outlet opening or closing, a tracked chain crossing a count threshold, a new
   lease or filing. The event stream is the monitoring product — delivered as push/email/digest, scoped
   to a buyer's lens. The daily lead-discovery routine and the intel routine are already event sources;
   the missing piece is a **typed event log** (brand, kind, before→after, as_of, provenance) that both
   feeds alerts and *is* the longitudinal time-series. Build this; it is the subscription's renewable core.
4. **Assemble.** Verified records → the dataset exports (the primary product) and, secondarily,
   `dossiers` assembly (the on-ramp sample) and the `revenue`/`capacity` CLIs (estimates).
5. **Gate & deliver.** Tier-gated exports (`chain_atlas/tier_export.py`): Public (census) / Observer /
   Pro (full dataset + analytics, DB-gated) / Intelligence (bespoke + alerts to the access-controlled
   location). The provenance wall + confidence tiers decide what each level sees. Keep Pro-only
   splits/sources out of public (`register.py` lifts only the worldwide `total`, never the splits).

---

## 3a. Packaging — how the three pillars are sold

| Tier | Contains | Role | Cadence |
|---|---|---|---|
| **Public** (free) | the map + counts; **one sample dossier** | on-ramp / proof the proprietary data exists | daily |
| **Observer** (low) | full roster + closings + abroad register, read-only | shows the *completeness* of coverage | daily |
| **Pro** (subscription) | the **full maintained dataset** (all four layers), exportable + citable, **+ alerts** scoped to the buyer's lens | the core product — census + provenance + monitoring | live / push |
| **Intelligence** (bespoke) | custom lenses, deep dossiers, direct analyst access, priority alerting | high-touch, for a specific decision | on demand |

Principles: the sample dossier is **lead-gen, priced at or near zero**; the recurring line is **Pro**
(dataset access + alerts), because that is what cannot be DIY'd and what renews; Intelligence monetizes
the owner's judgment for a specific diligence/underwriting question. Never gate the *analysis* and leave
the *data* free — gate the proprietary observation and the monitoring, and let the analysis be the free
taste.

---

## 4. The canonical submission record (keystone)

Every datum from every channel is one **submission record** — the reconciled superset of the field
shapes already in `sightings`, `china_stores`, `financial_anchors`, `fdd_extracts`, `dossiers`,
`closings` and `register`. Implemented and validated in
[`chain_atlas/submissions.py`](../chain_atlas/submissions.py).

```
{
  "id":            "<stable hash — brand|dimension|metric|value|as_of|source>",
  "brand":         "<chain_id>",                         # the chain
  "dimension":     "presence|scale|economics|structure|narrative",
  "metric":        "<slug>",      # outlet | store_count_total | us_revenue | invest_low | operating_model
                                  #  | litigation | history | popular_item | market_presence | …
  "value":         <number|string|object>,              # the datum
  "unit":          "<USD|stores|counters|…>" | null,
  "as_of":         "YYYY-MM-DD",                         # when the fact was TRUE
  "geo":           {address, city, state, lat, lon} | null,   # presence/outlet records
  "provenance_tier":"measured|filed|modeled|reported",
  "confidence":    "high|medium|low",                   # sightings' confirmed→high / uncertain→low
  "source":        "<human-readable source>",
  "source_url":    "<url>" | null,
  "source_capture":"<ledger path to screenshot/PDF>" | null,
  "submitter":     "owner | routine:<trigger_id> | contributor | researcher:<name>",
  "submitted_at":  "<ISO-8601 UTC>",
  "status":        "submitted|verified|rejected|superseded",   # default submitted
  "verified_by":   "<who/how>" | null,
  "verified_at":   "<ISO-8601 UTC>" | null,
  "supersedes":    "<id>" | null,
  "note":          "<free text>" | null
}
```

`(dimension, metric)` routes a verified record to its typed store (presence→sightings/closings,
scale→china_stores, economics/structure→financial_anchors/fdd_extracts, narrative→dossiers). Required
fields: `brand, dimension, metric, value, as_of, source, provenance_tier, confidence, submitter`.
Intake is an **append-only JSONL** (`manual/submissions.jsonl`), the sibling of the provenance ledger;
`id` dedupes and `supersedes` chains corrections. A verified record that *changes* a prior value emits
an **event** (§3 step 3) — the join between the schema and the alert stream.

---

## 5. Build order

Reordered to put the defensible pillars first.

1. ~~Freeze the submission schema~~ (`submissions.py`) — **done.** The keystone.
2. ~~Dossier-assembly command~~ — **done**, and intentionally demoted to the on-ramp sample.
3. ~~Verification queue~~ (`verify.py`, with the `watch` verdict) — **done.** Pillar 3's workflow.
4. ~~Tier-gated exporter~~ + ~~full-dataset Pro export~~ (`tier_export.py`) — **done.** `dataset()` /
   `write_dataset()` emit the primary product: flat tier-gated tables (brands, outlets, closings, abroad,
   scale, economics, structure, narrative) + the event-log time-series, aggregates, a manifest and a
   README, as JSON *and* CSV. Tables derive from the already-gated per-brand slices, so the paywall
   allowlist stays single-sourced. `export-tier <tier> --dataset --out DIR`.
5. **Event log + alerts (pillar 2) — the priority build.** A typed, append-only event stream
   (brand, kind ∈ {entered_us, outlet_opened, outlet_closed, count_threshold, new_filing, lease_signed},
   before→after, as_of, provenance) derived at each cadence. It (a) powers push/email/digest alerts
   scoped to a lens, and (b) *is* the longitudinal time-series the census cannot back-fill. This is the
   renewable core of the subscription and the least substitutable by an LLM.
6. **Coverage expansion over narrative depth.** Spend manual effort widening the verified universe (the
   long tail is the moat) and resolving identity, not on polishing LLM-reproducible prose.
7. Extend `contribute.html` into a full source-submission form writing the schema.

**Cautions.** (1) Do not automate identity resolution — it is the moat; make it efficient, not automated.
(2) Do not over-invest in dossier narrative — it is the on-ramp, not the product, and an LLM reproduces
it. (3) Do not gate the analysis while leaving the data free — gate the proprietary observation and the
monitoring. (4) Price and staff for a freshness product: a lapse in maintenance erodes value faster than
any competitor could.

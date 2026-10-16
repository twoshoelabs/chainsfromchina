# PRO spec — building, verifying, and selling the Pro/Intelligence edition

Status: draft, 2026-10-16. Owner: Twoshoe Labs. The US census is complete or nearly so; this spec
covers the next phase — turning the measured census and the Pro-tier dimensions
([china_stores](../manual/china_stores.json), [financial_anchors](phase2_revenue_spec.md),
[dossiers](../manual/dossiers.json), the [FDD miner](../chain_atlas/fdd.py)) into a **researched,
verifiable, sellable PRO product**. It defines three things the owner asked for: (a) the organizing
principles, (b) the manual-vs-automated research framework, and (c) the submission platform — plus the
**canonical submission record** (implemented in [`chain_atlas/submissions.py`](../chain_atlas/submissions.py)),
which is the keystone everything else conforms to.

This is a formalization, not a rebuild: ~70% of the platform already exists (the typed stores, the
hash-chained [provenance ledger](../chain_atlas/provenance.py), the daily routines, `contribute.html`).
The work is to connect them into one **intake → verify → assemble → gate** pipeline on one schema.

---

## 1. Organizing principles — the data/analysis taxonomy

Five principles, in priority order.

1. **The provenance wall is the product.** Every datum carries *how it was obtained*, on a four-rung
   ladder — **measured** (our own operator-observed census; audited FDD Item 21) → **filed** (primary
   HKEX / A-share / FDD figures) → **modeled** (revenue/capacity estimates) → **reported** (press /
   company statement). Already enforced via `confidence` fields, the ledger, and the public `~`
   unverified marker. **No number ships without its rung visible.** This is the integrity *and* the
   moat: competitors sell numbers; we sell *sourced* numbers.

2. **Four data layers, mapped to buyer questions** (not to source):
   - **Presence** — the census: who / where / status / authenticity. *Done.* The free base.
   - **Scale & trajectory** — home-market store counts, opening/closing pace, US-vs-home ratio
     (`china_stores`, `openings`).
   - **Economics** — unit economics, revenue/capacity estimates, build-out cost, AUV
     (`revenue` / `capacity` / FDD Items 7, 19, 21).
   - **Structure & intent** — corporate lineage, operating model, franchise terms, supply chain,
     pipeline, risk (FDD Items 1–8/20, register, listings).

3. **Buyers are lenses, not segments.** Build one four-layer record; *recombine* it per decision.
   CRE → pipeline + co-tenancy + survival. Competing chains → roster + pace + unit economics.
   Suppliers → supply-chain structure (Item 8) + scale. Investors → China financials + US traction +
   lineage. The brands → rivals' rollout. A "lens" is a saved query over the four layers.

4. **The dossier is the atomic sellable unit.** The per-brand dossier that assembles all four layers
   into a narrative is what commands report-level money ($3.5–9.5K each); subscriptions and exports are
   views onto the same records. *Make dossier assembly from the stores a one-command operation* — the
   single highest-leverage build.

5. **Cadence matches volatility.** Census = daily (adapters). Scale/economics = per-filing/quarterly
   (intel routine). Structure = annual (FDD/filings). Don't hand-refresh what changes yearly; don't
   batch-refresh what changes daily.

---

## 2. Manual vs automated research

Rule: **automate structured public retrieval; reserve humans for judgment, Chinese-language sourcing,
and narrative.**

| Research task | Mode | Form | → PRO |
|---|---|---|---|
| Census refresh | **Automated** (daily adapters) | store records | geojson + counts |
| FDD mining (MN CARDS) | **Automated** (done) | `fdd_extracts` + anchors | economics/structure |
| Filings (HKEX/cninfo) | **Automated** (`filings.py`) | `financial_anchors` | scale/economics |
| New-outlet discovery | **Automated** (daily routine) | push-notified leads | human verifies → census |
| **Identity resolution** (real vs copycat/authorized) | **Manual** | correct Chinese chars + brand's own site | gates what *counts* — the core skill |
| **China home-market financials** | **Hybrid** (routine drafts → human verifies) | patch → review → merge | `china_stores`/`dossiers`/anchors |
| **Dossier narrative** (history, items, flagships) | **Manual** | sourced prose | the Intelligence product |
| Authenticity / measured-vs-modeled calls | **Manual** | provenance-tagged | the `~` wall |

**One schema, two inputs.** Manual and automated research both produce records in the *same*
provenance-tagged schema (§4). The product never cares *how* a datum was obtained — only how well it
is sourced. Automated outputs that are ambiguous set `status: submitted` / `needs_human_read` and queue
for a human; they never silently become sellable. CA DFPI and WI DFI stay manual (no free public FDD
library — see `fdd.py`); identity resolution and dossier narrative stay manual *by design* — they are
the moat, to be made **efficient** (templates, source-capture), never automated away.

---

## 3. The submission platform — intake → verify → assemble → gate

1. **Intake (the front door).** One schema (§4), four channels:
   - *Automated* — the cloud routines write submissions (the intel-refresh / lead-discovery pattern).
   - *Owner/manual* — a CLI (`python -m chain_atlas submit …`) or small form writing a record + source.
   - *Crowdsourced* — extend `map/contribute.html` from sighting tips to a source-submission form.
   - *Field/paid researchers* — same schema, first-class input.
2. **Verify (the gate that makes it sellable).** Every submission enters at its *claimed* tier/
   confidence and must clear verification (human for judgment; cross-source otherwise) before reaching
   full-confidence PRO output. The **provenance ledger** records the chain of custody;
   `status ∈ {submitted, verified, rejected, superseded}` and `needs_human_read`/`unverified` are the
   hold states. The **verification queue** (a list of unverified / needs-human records with the source
   attached) is the main piece not yet built.
3. **Assemble.** Verified records → `dossiers` assembly (per-brand product) and the `revenue`/
   `capacity` CLIs (estimates). One command per brand → a complete, sourced dossier.
4. **Gate & deliver.** Tier-gated exports: Public (census) / Observer / Pro (analytics, DB-gated) /
   Intelligence (bespoke dossiers to the access-controlled location). The provenance wall + confidence
   tiers decide what each level sees. Keep Pro-only splits/sources out of public (`register.py` already
   lifts only the worldwide `total`, never the China/overseas split).

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
`id` dedupes and `supersedes` chains corrections.

---

## 5. Build order

1. **Freeze the submission schema** — §4, in `submissions.py` (validate + canonicalize + mappers from
   the existing stores). *This commit.* The keystone; everything else conforms.
2. **Dossier-assembly command** — stores → one sourced per-brand dossier. Highest revenue leverage.
3. **Verification queue** — a list of `submitted`/`needs_human_read`/`unverified` records awaiting a
   human call, with the source attached. Turns the backlog into a workflow.
4. **Extend `contribute.html`** into a source-submission form writing the schema.
5. **Tier-gated exporter** — one command emitting the right slice per tier.

**Cautions.** (1) Do not automate identity resolution or dossier narrative — they are the moat; make
them efficient, not automated. (2) Do not over-build the platform — schema + ledger + verification
queue + dossier assembly is 80% of a sellable PRO; a fancy intake UI is not where the value is.

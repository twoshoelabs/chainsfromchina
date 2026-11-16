# Dataset fingerprinting

Two layers let us prove that a third-party copy of the public data came from Chains From China.

## 1. Overt snapshot fingerprint (easy to strip)

Every public feed carries, in its `meta`:

- `meta.license` — the attribution + terms-of-use notice (see `map/terms.html`).
- `meta.fingerprint` — `cfc-<YYYY-MM-DD>-<16 hex>`, a SHA-256 over the canonical `stores`
  payload. It uniquely identifies the snapshot and ties a verbatim copy to a dated point in our
  own git history and provenance ledger (`manual/provenance_ledger.jsonl`).

Generated in `chain_atlas/mapdata.py` (`_fingerprint`, `DATA_LICENSE`) and mirrored into
`stores.geojson` via `chain_atlas/geojson.py`. A copier can delete these — but stripping the
attribution and license notice only strengthens a copying/removal claim.

## 2. Record-level canaries (strip-resistant)

`manual/fingerprint.json` (internal, **never published**) lists real, correct records whose
exact representation in the public data is a deliberate, documented fingerprint:

- **Manual coordinates.** For mall units the US Census geocoder cannot resolve, we set the
  latitude/longitude by hand to a specific precision. The Census can never reproduce these exact
  values, so a third-party dataset carrying the identical lat/lon pair for the same store is
  reproducing our hand-set figure — not independently geocoding it.
- **Name / formatting idiosyncrasies.** A specific, accurate-but-non-obvious spelling or unit
  notation that is ours.

None of these alters accuracy: every canary value is correct. They are watermarks hidden in
legitimate data. **Do not "tidy" a canary value** — changing it weakens the fingerprint. When you
add a hand-set coordinate or an idiosyncratic record representation, add it here.

### How to use it in an enforcement claim

1. Pull the suspect dataset.
2. Match it against `manual/fingerprint.json`. Verbatim reproduction of a hand-set coordinate (to
   full precision) or an idiosyncratic record string is strong evidence of copying.
3. Combine with the snapshot `meta.fingerprint` (if present) and our provenance ledger to date the
   copy. Then pursue the remedies in `map/terms.html` (takedown, claims under applicable law).

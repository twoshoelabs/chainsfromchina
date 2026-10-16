"""
The PRO submission record — one provenance-tagged schema for every datum, from every channel.

Manual research, the daily/intel cloud routines, crowdsourced tips and paid researchers all produce
the SAME record (docs/pro_spec.md §4). It is the reconciled superset of the field shapes already in
`sightings`, `china_stores`, `financial_anchors`, `fdd_extracts`, `dossiers`, `closings` and
`register`: a `(brand, dimension, metric, value, as_of)` fact, carrying its source, provenance tier
and confidence, plus who submitted it and whether it has been verified.

WHY a single schema: the product must not care HOW a datum was obtained, only how well it is sourced.
A record enters at its claimed tier/confidence with `status='submitted'`; it reaches full-confidence
PRO output only once a human (or a cross-source check) marks it `verified`. `(dimension, metric)` then
routes a verified record to its typed store (presence→sightings/closings, scale→china_stores,
economics/structure→financial_anchors/fdd_extracts, narrative→dossiers).

STORE: an append-only JSONL (`manual/submissions.jsonl`), the sibling of the hash-chained provenance
ledger. `id` (a content hash) dedupes; `supersedes` chains corrections. This module is the schema +
validation + the mappers that turn each existing store's rows into canonical records; it never writes
to the typed stores itself (verification + promotion is a later step).
"""
import hashlib
import json
import re
from datetime import datetime, timezone

DIMENSIONS = {"presence", "scale", "economics", "structure", "narrative"}
TIERS = {"measured", "filed", "modeled", "reported"}       # the provenance wall, strongest first
CONFIDENCE = {"high", "medium", "low"}
STATUS = {"submitted", "verified", "rejected", "superseded"}

# Known metric slugs per dimension. NOT a closed set (new slugs are allowed), but the canonical ones
# keep manual and automated submitters aligned and let a lens query a stable vocabulary.
METRICS = {
    "presence":  {"outlet", "closure", "market_presence"},
    "scale":     {"store_count_total", "store_count_china", "store_count_overseas", "openings_pace"},
    "economics": {"us_revenue", "auv", "invest_low", "invest_high", "group_revenue", "net_profit",
                  # the slugs financial_anchors actually uses (FDD + filings) so they don't warn
                  "fdd_item19_auv", "fdd_item7_invest_low", "fdd_item7_invest_high",
                  "fdd_item21_us_revenue", "fdd_item21_net_income", "fdd_item21_total_assets"},
    "structure": {"operating_model", "parent", "principals", "litigation", "bankruptcy",
                  "supply_flags", "projected_openings"},
    "narrative": {"history", "popular_item", "flagship", "note"},
}

REQUIRED = ("brand", "dimension", "metric", "value", "as_of", "source", "provenance_tier",
            "confidence", "submitter")
_OPTIONAL_DEFAULTS = {"unit": None, "geo": None, "source_url": None, "source_capture": None,
                      "verified_by": None, "verified_at": None, "supersedes": None, "note": None}
# Confidence synonyms other stores use -> the canonical three.
_CONF_SYNONYM = {"confirmed": "high", "uncertain": "low", "unconfirmed": "low", "announced": "low"}
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def record_id(rec: dict) -> str:
    """
    name:      record_id
    purpose:   A stable content hash so the same fact dedupes and corrections can reference it.
    arguments: rec — a (partial) record with at least brand/dimension/metric/value/as_of/source.
    returns:   'sub_' + 16 hex chars.
    other:     Hashes the IDENTITY of the fact (not confidence/status/submitter), so re-submitting the
               same datum with a firmer confidence yields the SAME id — an update, not a duplicate.
    """
    key = "|".join([str(rec.get("brand", "")), str(rec.get("dimension", "")),
                    str(rec.get("metric", "")),
                    json.dumps(rec.get("value"), ensure_ascii=False, sort_keys=True),
                    str(rec.get("as_of", "")), str(rec.get("source", ""))])
    return "sub_" + hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]


def infer_tier(dimension: str, metric: str, source: str, confidence: str) -> str:
    """
    name:      infer_tier
    purpose:   Suggest a provenance tier when a mapper or submitter did not set one explicitly.
    arguments: dimension, metric, source, confidence.
    returns:   one of TIERS.
    other:     Best-effort only — an explicit tier always wins. measured = our own observation / audited;
               filed = a primary company/regulatory filing; modeled = an estimate we computed; reported
               = press or a company statement. Ambiguity falls to 'reported', the weakest rung.
    """
    s = (source or "").lower()
    m = (metric or "").lower()
    if any(k in s for k in ("operator-observed", "google business", "census", "audited", "we observed")):
        return "measured"
    if "model" in s or "estimate" in m or "capacity" in m:
        return "modeled"
    if any(k in s for k in ("annual report", "annual results", "prospectus", "hkex", "sse:", "szse:",
                            "cninfo", "10-k", "20-f", "fdd", "franchise disclosure", "item 21", "filing")):
        return "filed" if confidence == "high" else "reported"
    return "reported"


def canonicalize(rec: dict) -> dict:
    """
    name:      canonicalize
    purpose:   Normalise a record: fill defaults, map confidence synonyms, lowercase enums, stamp id/time.
    arguments: rec — a raw submission dict.
    returns:   a NEW normalised dict (does not mutate the input).
    effects:   None.
    other:     Idempotent. Maps sightings' 'confirmed'/'uncertain' to high/low; defaults status to
               'submitted' and submitted_at to now; computes id and provenance_tier if absent.
    """
    r = dict(_OPTIONAL_DEFAULTS)
    r.update({k: v for k, v in rec.items() if v is not None or k in rec})
    for f in ("brand", "dimension", "metric", "provenance_tier", "confidence", "status", "submitter"):
        if isinstance(r.get(f), str):
            r[f] = r[f].strip()
    for f in ("dimension", "provenance_tier", "confidence", "status"):
        if isinstance(r.get(f), str):
            r[f] = r[f].lower()
    r["confidence"] = _CONF_SYNONYM.get(r.get("confidence"), r.get("confidence"))
    r.setdefault("status", "submitted")
    r["status"] = r.get("status") or "submitted"
    r.setdefault("submitted_at", None)
    r["submitted_at"] = r.get("submitted_at") or _utcnow()
    if not r.get("provenance_tier"):
        r["provenance_tier"] = infer_tier(r.get("dimension"), r.get("metric"),
                                          r.get("source"), r.get("confidence"))
    r["id"] = rec.get("id") or record_id(r)
    return r


def validate(rec: dict) -> list:
    """
    name:      validate
    purpose:   Check a record against the schema; return a list of human-readable errors ([] = valid).
    arguments: rec — a record (canonicalised or not).
    returns:   list[str].
    effects:   None.
    other:     Enforces required fields, the enums, an ISO date for as_of, a coherent (dimension, metric)
               and a geo shape for presence records. Unknown metric slugs are allowed but WARNED so the
               vocabulary stays visible; the warning is returned prefixed 'warn:' and is not an error.
    """
    r = canonicalize(rec)
    errs = []
    for f in REQUIRED:
        if r.get(f) in (None, ""):
            errs.append(f"missing required field: {f}")
    if r.get("dimension") not in DIMENSIONS:
        errs.append(f"dimension not in {sorted(DIMENSIONS)}: {r.get('dimension')!r}")
    if r.get("provenance_tier") not in TIERS:
        errs.append(f"provenance_tier not in {sorted(TIERS)}: {r.get('provenance_tier')!r}")
    if r.get("confidence") not in CONFIDENCE:
        errs.append(f"confidence not in {sorted(CONFIDENCE)}: {r.get('confidence')!r}")
    if r.get("status") not in STATUS:
        errs.append(f"status not in {sorted(STATUS)}: {r.get('status')!r}")
    if not _DATE.match(str(r.get("as_of", ""))):
        errs.append(f"as_of must be YYYY-MM-DD: {r.get('as_of')!r}")
    if r.get("dimension") == "presence" and not (isinstance(r.get("geo"), dict)
                                                 and r["geo"].get("address")):
        errs.append("presence records need geo with an address")
    dim, metric = r.get("dimension"), r.get("metric")
    if dim in METRICS and metric and metric not in METRICS[dim]:
        errs.append(f"warn: unknown metric '{metric}' for dimension '{dim}' "
                    f"(known: {sorted(METRICS[dim])})")
    return errs


# --- Mappers: the proof the schema reconciles the existing stores -------------------------------

def from_sighting(chain: str, group: dict, loc: dict, submitter: str = "owner") -> dict:
    """One sightings.json location -> a presence/outlet submission record."""
    return canonicalize({
        "brand": chain, "dimension": "presence", "metric": "outlet",
        "value": loc.get("name"), "unit": None,
        "as_of": group.get("reviewed") or group.get("supplied_on"),
        "geo": {"address": loc.get("address"), "lat": loc.get("lat"), "lon": loc.get("lon")},
        "provenance_tier": "measured",
        "confidence": loc.get("confidence"),
        "source": loc.get("verified_by") or group.get("source"),
        "submitter": submitter, "note": group.get("scope")})


def from_china_stores(brand: str, entry: dict, submitter: str = "owner") -> dict:
    """One china_stores.json brand entry -> a scale/store_count_total submission record."""
    return canonicalize({
        "brand": brand, "dimension": "scale", "metric": "store_count_total",
        "value": entry.get("total"), "unit": "stores",
        "as_of": entry.get("as_of"),
        "provenance_tier": "filed" if entry.get("confidence") == "high" else "reported",
        "confidence": entry.get("confidence"),
        "source": entry.get("source"),
        "submitter": submitter, "note": entry.get("note")})


def from_financial_anchor(row: dict, submitter: str = "owner") -> dict:
    """One financial_anchors row (dict) -> an economics submission record."""
    return canonicalize({
        "brand": row.get("brand_id"), "dimension": "economics", "metric": row.get("metric"),
        "value": row.get("value"), "unit": row.get("unit"),
        "as_of": _as_date(row.get("period")),
        "confidence": row.get("confidence"),
        "source": row.get("source"), "source_url": row.get("source_url"),
        "source_capture": row.get("page_ref"),
        "submitter": submitter})


def from_dossier_item(brand: str, kind: str, item: dict, submitter: str = "owner") -> dict:
    """One dossiers.json item (history dict, or a popular_items/flagship entry) -> a narrative record."""
    metric = {"history": "history", "popular_items": "popular_item",
              "flagship_outlets": "flagship", "notes": "note"}.get(kind, "note")
    value = item.get("text") or item.get("name")
    return canonicalize({
        "brand": brand, "dimension": "narrative", "metric": metric,
        "value": value, "as_of": item.get("as_of"),
        "provenance_tier": "reported", "confidence": item.get("confidence"),
        "source": item.get("source"), "submitter": submitter, "note": item.get("note")})


def _as_date(period) -> str:
    """A filing period like '2025' or 'FY2025/26' -> a best-effort YYYY-12-31 as_of (schema needs a date)."""
    s = str(period or "")
    m = re.search(r"(19|20)\d\d", s)
    return f"{m.group(0)}-12-31" if m else _utcnow()[:10]


# --- Append-only intake store --------------------------------------------------------------------

def append(rec: dict, path: str = "manual/submissions.jsonl") -> dict:
    """
    name:      append
    purpose:   Validate, canonicalise and append one submission to the intake JSONL.
    arguments: rec — a raw record; path — the intake log.
    returns:   the canonicalised record that was written.
    effects:   Appends one JSON line. Raises ValueError on a hard validation error (warnings pass).
    other:     Append-only, like the provenance ledger: corrections are new records that set
               `supersedes` to the prior id, never edits in place.
    """
    r = canonicalize(rec)
    errs = [e for e in validate(r) if not e.startswith("warn:")]
    if errs:
        raise ValueError("invalid submission: " + "; ".join(errs))
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return r


def iter_submissions(path: str = "manual/submissions.jsonl"):
    """Yield each submission record from the intake JSONL (empty/absent file -> nothing)."""
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    yield json.loads(line)
    except FileNotFoundError:
        return

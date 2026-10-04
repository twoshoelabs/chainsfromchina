"""
USPTO trademark collector — the first pipeline-signal source (docs/phase1_spec.md §5).

WHY THIS ONE FIRST. Of every pipeline source on the roadmap, USPTO is the cleanest: it is
US-government data, the records are public, there is an official API, and nothing here requires
scraping a third party. A US trademark filing in a retail class — especially class 35, retail-store
services — is one of the earliest legible signals that a brand intends to trade here.

WHAT IT IS AND IS NOT. A trademark filing is a PIPELINE SIGNAL, never a store. It goes into
`pipeline_signals`, never into stores/observations/events. A filing by a China applicant that
matches no brand we track is not discarded — it is kept as an unlinked DISCOVERY LEAD (a brand we
may not know yet), for a human to triage.

TERMS / VOLUME / FALLBACK (stated before building, per the project's rule):
  * Source: USPTO Open Data Portal trademark search + TSDR. Public records, official API.
  * Terms: clean. Respect the documented rate limits; the API needs a free key (USPTO_API_KEY).
  * Volume: low per run. Registry-brand queries are tens of terms, mostly unchanged week to week;
    the China-applicant discovery sweep surfaces a few hundred filings to triage, most irrelevant.
    A diff against what is already stored keeps only what is new.
  * Manual fallback: with no key or no network the collector SKIPS cleanly — the weekly lookup can
    be done by hand for the registry brands — and never fabricates a signal.

IDEMPOTENT. Re-running for the same marks inserts nothing new: a mark is deduped on its serial
number (carried in `source_url` as the TSDR link).

NOTE. The live endpoint path and response field names must be confirmed against USPTO's current API
docs before the first live run; `parse()` is the only piece that depends on them and is isolated for
exactly that reason. Everything downstream (match, classify, dedupe, insert) is tested offline
against a fixture.
"""
import hashlib
import json
from datetime import datetime, timezone

from . import register
from .config import USPTO_API_KEY, USPTO_API_BASE

# Nice classes that signal retail intent. 35 (retail-store services) is the strongest "opening a US
# retail operation" tell; the rest are the goods classes for the sectors we track.
RETAIL_CLASSES = {3, 9, 14, 20, 25, 28, 30, 35, 43}


def _utcnow() -> str:
    """name: _utcnow / purpose: UTC ISO-8601 stamp / arguments: none / returns: str / effects: none."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def tsdr_url(serial: str) -> str:
    """
    name:      tsdr_url
    purpose:   The public TSDR link for a serial number — also our dedupe key.
    arguments: serial
    returns:   URL string
    effects:   None
    """
    return f"https://tsdr.uspto.gov/#caseNumber={serial}&caseType=SERIAL_NO&searchType=statusSearch"


def build_index(d: dict) -> tuple[dict, dict]:
    """
    name:      build_index
    purpose:   Index the registry's brands by the strings a filing might match on.
    arguments: d — a register dict
    returns:   (name_index, parent_index): {lowercased string: chain_id}
    effects:   None
    other:     name_index holds each brand's English/US/Chinese names; parent_index holds the
               listed-entity / franchisor string, matched as a substring of an applicant name.
    """
    name_index, parent_index = {}, {}
    for cid, c in d.get("chains", {}).items():
        for key in (c.get("name"), c.get("name_us"), c.get("name_zh")):
            if key and key.strip():
                name_index[key.strip().lower()] = cid
        parent = (c.get("parent") or "").strip().lower()
        if parent:
            # strip a trailing ticker parenthetical, e.g. "Anta Sports Products (HKEX 2020)"
            parent_index[parent.split("(")[0].strip()] = cid
    return name_index, parent_index


def parse(raw) -> list[dict]:
    """
    name:      parse
    purpose:   Turn a USPTO trademark-search response into normalised mark records.
    arguments: raw — the API response (JSON text or already-parsed dict/list)
    returns:   list of {serial, mark, applicant, applicant_country, filing_date, classes:[int]}
    effects:   None
    other:     Defensive: tolerates missing fields and both a top-level list and a {results:[...]}
               / {trademarks:[...]} envelope. This is the ONLY function tied to the API's exact
               shape; confirm field names against USPTO's live docs and adjust here alone.
    """
    if isinstance(raw, (str, bytes)):
        raw = json.loads(raw)
    if isinstance(raw, dict):
        rows = raw.get("results") or raw.get("trademarks") or raw.get("items") or []
    else:
        rows = raw or []
    out = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        classes = r.get("classes") or r.get("internationalClasses") or r.get("class_codes") or []
        norm_classes = []
        for c in classes:
            try:
                norm_classes.append(int(str(c).strip().lstrip("0") or "0"))
            except (TypeError, ValueError):
                pass
        out.append({
            "serial": str(r.get("serial") or r.get("serialNumber") or r.get("serial_number") or "").strip(),
            "mark": (r.get("mark") or r.get("markText") or r.get("wordMark") or "").strip(),
            "applicant": (r.get("applicant") or r.get("applicantName") or r.get("owner") or "").strip(),
            "applicant_country": (r.get("applicant_country") or r.get("applicantCountry")
                                  or r.get("ownerCountry") or "").strip().upper(),
            "filing_date": (r.get("filing_date") or r.get("filingDate") or r.get("filed") or "").strip(),
            "classes": sorted(set(norm_classes)),
        })
    return [m for m in out if m["serial"]]


def classify(mark: dict, name_index: dict, parent_index: dict) -> tuple[str | None, str] | None:
    """
    name:      classify
    purpose:   Decide whether a mark is relevant, and to which brand.
    arguments: mark — a parsed mark; name_index, parent_index — from build_index
    returns:   (brand_id, kind) where kind is 'brand_match' or 'discovery_lead', or None to drop
    effects:   None
    other:     A brand/parent match links the signal (brand_id set). Otherwise a China applicant in
               a retail class is kept as an unlinked discovery lead. Everything else is dropped —
               this is a targeted watch, not a firehose.
    """
    mtext = mark["mark"].strip().lower()
    appl = mark["applicant"].strip().lower()
    if mtext and mtext in name_index:
        return name_index[mtext], "brand_match"
    if appl and appl in name_index:
        return name_index[appl], "brand_match"
    for pstr, cid in parent_index.items():
        if pstr and pstr in appl:
            return cid, "brand_match"
    if mark["applicant_country"] == "CN" and (set(mark["classes"]) & RETAIL_CLASSES):
        return None, "discovery_lead"
    return None


def ingest(con, raw, d: dict, raw_ref: str = "", now: str | None = None) -> dict:
    """
    name:      ingest
    purpose:   Parse one raw response, classify its marks, and insert new pipeline signals.
    arguments: con — DB connection; raw — API response; d — register dict; raw_ref — the saved
               raw capture's "path@sha256"; now — UTC stamp (defaults to real now)
    returns:   summary {parsed, brand_matches, discovery_leads, inserted, duplicates}
    effects:   INSERTs into pipeline_signals. Never updates or deletes.
    other:     Idempotent: a mark already present (same serial, carried in source_url) is skipped,
               so re-running a week's capture adds nothing.
    """
    now = now or _utcnow()
    name_index, parent_index = build_index(d)
    seen = {r[0] for r in con.execute(
        "SELECT source_url FROM pipeline_signals WHERE signal_type='uspto'").fetchall()}
    parsed = parse(raw)
    summ = {"parsed": len(parsed), "brand_matches": 0, "discovery_leads": 0,
            "inserted": 0, "duplicates": 0}
    for m in parsed:
        verdict = classify(m, name_index, parent_index)
        if verdict is None:
            continue
        brand_id, kind = verdict
        summ["brand_matches" if kind == "brand_match" else "discovery_leads"] += 1
        url = tsdr_url(m["serial"])
        if url in seen:
            summ["duplicates"] += 1
            continue
        cls = ",".join(str(c) for c in m["classes"])
        lead = "" if brand_id else " [discovery lead]"
        summary = (f"Mark '{m['mark']}' — {m['applicant']} "
                   f"({m['applicant_country'] or '??'}) — Nice classes {cls or '?'}{lead}")
        con.execute(
            "INSERT INTO pipeline_signals(signal_type,brand_id,location_id,filed_date,summary,"
            "raw_ref,source,source_url,retrieved_at,confidence) VALUES('uspto',?,?,?,?,?,?,?,?,?)",
            (brand_id, None, m["filing_date"] or None, summary, raw_ref or None,
             "USPTO", url, now, "high" if brand_id else "low"),
        )
        seen.add(url)
        summ["inserted"] += 1
    con.commit()
    return summ


def queries_from_registry(d: dict) -> list[str]:
    """
    name:      queries_from_registry
    purpose:   The search terms for the registry-brand sweep: each brand's US/English name.
    arguments: d — register dict
    returns:   list of unique term strings
    effects:   None
    other:     Chinese names and parents are matched at classify() time; the API text search runs on
               the Latin brand name a US filing would use.
    """
    terms = set()
    for c in d.get("chains", {}).values():
        for key in (c.get("name_us"), c.get("name")):
            if key and key.strip():
                terms.add(key.strip())
    return sorted(terms)


def _fetch(term: str, api_key: str, base: str):
    """
    name:      _fetch
    purpose:   Query the USPTO trademark search API for one term; return the raw response text.
    arguments: term; api_key; base — the API origin
    returns:   raw text, or None on any failure (the caller then skips the term)
    effects:   One network request via the shared capture session (robots-checked, retried).
    other:     Endpoint path/params are USPTO's to define; confirm against the live docs. Isolated
               here so a shape change touches only this function and parse().
    """
    from . import capture
    url = f"{base}/api/v1/trademark/search"
    try:
        resp = capture.fetch(url, method="GET",
                             params={"query": term, "rows": 100},
                             headers={"X-API-KEY": api_key, "Accept": "application/json"})  # capture sets timeout
        return resp.text
    except Exception:                                            # noqa: BLE001
        return None


def run(con, d: dict | None = None, api_key: str | None = None,
        terms: list[str] | None = None, now: str | None = None,
        fetch_fn=None, save_raw_fn=None) -> dict:
    """
    name:      run
    purpose:   Weekly pass: fetch trademark filings for the registry brands and the China-applicant
               sweep, store raw, and record new pipeline signals.
    arguments: con; d — register (defaults to load()); api_key (defaults to config); terms (defaults
               to the registry sweep); now; fetch_fn / save_raw_fn — injectable IO for tests
    returns:   summary dict
    effects:   Network requests, raw captures on disk, INSERTs into pipeline_signals.
    other:     With no api_key (and no injected fetch_fn) it SKIPS — the manual fallback — and
               records nothing. Idempotent via ingest().
    """
    d = d if d is not None else register.load()
    api_key = api_key if api_key is not None else USPTO_API_KEY
    now = now or _utcnow()
    terms = terms if terms is not None else queries_from_registry(d)

    if fetch_fn is None:
        if not api_key:
            return {"skipped": "no USPTO_API_KEY set — manual fallback", "queried": 0, "inserted": 0}
        fetch_fn = lambda t: _fetch(t, api_key, USPTO_API_BASE)  # noqa: E731
    if save_raw_fn is None:
        from . import capture
        save_raw_fn = lambda payload: capture.save_raw("uspto", now[:10], payload, ext="json")  # noqa: E731

    total = {"queried": 0, "fetched": 0, "inserted": 0, "brand_matches": 0,
             "discovery_leads": 0, "duplicates": 0, "skipped_terms": 0}
    for term in terms:
        total["queried"] += 1
        raw = fetch_fn(term)
        if not raw:
            total["skipped_terms"] += 1
            continue
        total["fetched"] += 1
        try:
            path, sha = save_raw_fn(raw)
            raw_ref = f"{path}@{sha}"
        except Exception:                                        # noqa: BLE001
            raw_ref = f"sha256:{hashlib.sha256(raw.encode('utf-8', 'ignore')).hexdigest()}"
        s = ingest(con, raw, d, raw_ref=raw_ref, now=now)
        for k in ("inserted", "brand_matches", "discovery_leads", "duplicates"):
            total[k] += s[k]
    return total

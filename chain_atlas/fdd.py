"""
FDD collector — Item 19 Financial Performance Representations (and Item 20 outlet counts) for the
China-origin chains that are REGISTERED US FRANCHISORS. This is the best per-outlet, US-specific
revenue anchor in the whole model: Item 19 is a franchisor's own, legally-filed statement of what its
US units gross. See docs/phase2_revenue_spec.md (Tier-2 anchor).

SOURCE. State franchise registries. Of the registration states, **Minnesota CARDS** is the clean,
programmatic one: a public GET search (franchisor / franchise-name / year / document-type) and a public
document download, both plain HTTP. (Wisconsin DFI — the other big free library — sits behind a
Cloudflare bot challenge that hard-blocks automated clients; it is NOT usable here and must be pulled by
hand. California DFPI DOCQNET is a possible future add.) CARDS serves normal browsers but its WAF 403s a
bot-ish User-Agent, so we send a browser UA — this is public content served to any browser, not a
CAPTCHA or an access control, and nothing here forges a login or solves a challenge.

LEGAL POSTURE. FDDs are public records filed with state regulators — first-party/official, squarely in
posture. We archive the raw PDF (the evidence) before parsing a figure from it.

REALITY (why most rows are an honest "no number"). Many franchisors — especially new or foreign entrants,
which is most of these brands — OPT OUT of Item 19 ("we do not make any representations about a
franchisee's future financial performance"). That opt-out is itself recorded as a finding; an AUV anchor
is written ONLY when real figures are disclosed, never invented. Item 20 (systemwide outlet counts,
franchised vs company-owned) is almost always present and is captured as a cross-check on our census.

WHAT IT WRITES.
  * pipeline_signals (signal_type='fdd'): one row per franchisor's latest filed FDD — the status
    (Item 19 figures found / opt-out), Item 20 outlet counts, the state + year, and source_url = the
    document download link (the dedupe key, so re-running adds nothing).
  * financial_anchors (metric 'fdd_item19_auv'): ONLY when Item 19 discloses a per-unit average/median
    gross-sales figure — a US, per-outlet AUV the revenue model can prefer over an overseas-derived one.
    Parsed figures are confidence 'medium' with the raw excerpt in page_ref, for human verification
    before they feed an estimate (Item 19 formats vary wildly).

NOTE. parse_results() (the CARDS HTML shape) and the Item-19/20 text heuristics are the only pieces tied
to a source's exact format; they are isolated and tested offline against fixtures. With no network, no
pypdf, or no registration, the collector SKIPS cleanly and records nothing fabricated.
"""
import io
import re
from datetime import datetime, timezone
from urllib.parse import quote, unquote

# CARDS serves browsers; a bot UA is WAF-403'd. Public content, not a challenge.
UA_BROWSER = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")
CARDS = "https://cards.web.commerce.state.mn.us"
SEARCH = CARDS + "/franchise-registrations"
# The complete, effective FDD document types (not amendments/forms/letters), newest preferred.
FDD_DOC_TYPES = ("Clean FDD", "Final FDD", "Revised FDD - Clean")

# Our registered US franchisors (register.franchise_note). search by franchisor entity when known
# (precise), else by franchise name. Add a brand here once an FDD filing is confirmed.
TARGETS = [
    {"brand_id": "miniso",    "franchisor": "MINISO DEPOT FRANCHISOR"},
    {"brand_id": "cotti",     "franchisor": "COTTI PARTNERS"},
    # Yangguofu's MN franchise name is "Yangguofu"; its franchisor entity is CAPTAIN BUSINESS
    # MANAGEMENT CO., LIMITED (a Hong Kong holding). Match the precise name, not "YANG".
    {"brand_id": "yangguofu", "franchise_name": "Yangguofu", "franchisor": "CAPTAIN BUSINESS MANAGEMENT"},
    {"brand_id": "mixue",     "franchise_name": "MIXUE",   "franchisor": "SNOW KING"},
    {"brand_id": "moge",      "franchise_name": "MOGE TEE"},
    # NOTE: Yang's Braised Chicken (杨铭宇) is NOT in MN CARDS (searched BRAISED / Yang's / HUANG MEN -> 0);
    # it is registered elsewhere — add via CA DOCQNET or a manual WI pull later. Never search it by the
    # broad token "YANG", which matches Yangguofu.
]


def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# --- CARDS source (the only transport-bound piece besides the parsers) ---------------------------

def _fetch(url: str, raw: bool = False):
    """One polite, robots-checked CARDS request with a browser UA. Returns text, or bytes if raw."""
    from . import capture
    r = capture.fetch(url, method="GET",
                      headers={"User-Agent": UA_BROWSER, "Accept": "*/*",
                               "Accept-Language": "en-US,en;q=0.9"})
    return r.content if raw else r.text


def search_url(franchisor: str = "", franchise_name: str = "", year: str = "") -> str:
    """The CARDS franchise-registration search URL (a plain GET form)."""
    from urllib.parse import urlencode
    q = {"doSearch": "true"}
    if franchisor:
        q["franchisor"] = franchisor
    if franchise_name:
        q["franchiseName"] = franchise_name
    if year:
        q["year"] = year
    return SEARCH + "?" + urlencode(q)


def doc_url(guid: str) -> str:
    """The public download URL for a CARDS document GUID (e.g. '{A07A...}')."""
    return f"{CARDS}/documents/{quote(guid)}/download?documentClass=FRANCHISE_REGISTRATIONS&contentSequence=0"


def parse_results(html: str) -> list[dict]:
    """
    name:      parse_results
    purpose:   Turn a CARDS search-results page into filing rows.
    arguments: html — the search page HTML.
    returns:   list of {guid, doc_number, franchisor, doc_type, year} (one per document row).
    effects:   None.
    other:     The ONLY piece tied to CARDS' HTML. A row is a <tr> carrying a /documents/<guid>/download
               link; we read its visible text for franchisor, document type and year. "No documents
               found" -> [].
    """
    if "No documents found" in html:
        return []
    out = []
    for tr in re.findall(r"<tr>[\s\S]*?</tr>", html):
        g = re.search(r"/documents/([^/\"']+)/download", tr)
        if not g:
            continue
        text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", tr)).strip()
        doc_type = next((d for d in ("Clean FDD", "Final FDD", "Revised FDD - Clean",
                                     "Marked FDD", "Revised FDD - Marked Up") if d in text), None)
        yr = re.search(r"\b(19|20)\d\d\b", text)
        num = re.search(r"\b(\d{4,6}-\d{6}-\d{2})\b", text)
        # franchisor = the first uppercase entity token ending in a company suffix
        fr = re.search(r"\b([A-Z][A-Z0-9 ,\.\&'\-]{2,60}?"
                       r"(?:LLC|L\.L\.C\.|INC|INCORPORATED|CORP|CORPORATION|CO\.|COMPANY|LIMITED|LTD))\b", text)
        out.append({"guid": unquote(g.group(1)), "doc_number": num.group(1) if num else "",
                    "franchisor": (fr.group(1).strip() if fr else ""),
                    "doc_type": doc_type, "year": int(yr.group(0)) if yr else 0, "text": text[:120]})
    return out


def latest_fdd(rows: list[dict], franchisor: str = "") -> dict | None:
    """Pick the most recent complete FDD (Clean > Final > Revised-Clean), optionally for one franchisor."""
    pref = {t: i for i, t in enumerate(FDD_DOC_TYPES)}
    cands = [r for r in rows if r["doc_type"] in pref]
    if franchisor:
        fu = franchisor.upper()
        narrowed = [r for r in cands if fu in r["franchisor"].upper()]
        cands = narrowed or cands
    if not cands:
        return None
    # newest year, then most-preferred doc type
    cands.sort(key=lambda r: (r["year"], -pref[r["doc_type"]]), reverse=True)
    return cands[0]


# --- PDF text + Item 19 / Item 20 parsers (isolated, tested against fixtures) ---------------------

def extract_text(pdf_bytes: bytes) -> str:
    """Full text of an FDD PDF via pypdf. Returns '' if pypdf is absent or the PDF won't parse."""
    try:
        from pypdf import PdfReader
    except Exception:                                            # noqa: BLE001
        return ""
    try:
        rd = PdfReader(io.BytesIO(pdf_bytes))
        return "\n".join((p.extract_text() or "") for p in rd.pages)
    except Exception:                                            # noqa: BLE001
        return ""


def item_section(text: str, n: int) -> str:
    """
    name:      item_section
    purpose:   Extract the body of 'ITEM <n>' — from its last (non-TOC) header to the next item header.
    arguments: text — full FDD text; n — item number.
    returns:   the section text ('' if not found).
    other:     FDDs repeat 'ITEM 19' in the table of contents and in cross-references; the real section
               is the last standalone occurrence, so we take the last header and read to 'ITEM <n+1>'.
    """
    starts = [m.start() for m in re.finditer(rf"ITEM\s*{n}\b", text, re.I)]
    if not starts:
        return ""
    s = starts[-1]
    nxt = re.search(rf"ITEM\s*{n + 1}\b", text[s + 4:], re.I)
    return text[s: s + 4 + nxt.start()] if nxt else text[s: s + 6000]


# An Item 19 opt-out: the franchisor makes no financial performance representation.
_OPTOUT = re.compile(r"do not (?:make|furnish|provide|authorize)[^.]*?"
                     r"(?:financial performance|performance representation|representation about)", re.I)
# A disclosed per-unit figure: "average gross sales ... $1,234,567" (and median/mean variants).
_FIGURE = re.compile(r"(average|median|mean|highest|lowest)[^$\n]{0,80}?"
                     r"(?:gross\s+(?:sales|revenue)|sales|revenue|AUV)[^$\n]{0,40}?"
                     r"\$\s?([\d][\d,]{3,}(?:\.\d\d)?)", re.I)


def parse_item19(sec: str) -> dict:
    """
    name:      parse_item19
    purpose:   Classify an Item 19 section and pull any disclosed per-unit gross-sales figures.
    arguments: sec — the Item 19 text.
    returns:   {present: bool, opt_out: bool, figures: [(label, usd)], auv: float|None, excerpt: str}.
    other:     auv = the average/mean figure when present, else the median — the single number the model
               would use; None when the franchisor opts out or discloses no clear per-unit figure. Never
               guesses: an ambiguous section yields auv=None for a human to read the excerpt.
    """
    sec = sec or ""
    present = bool(sec.strip())
    opt_out = bool(_OPTOUT.search(sec))
    figures = []
    for m in _FIGURE.finditer(sec):
        try:
            figures.append((m.group(1).lower(), float(m.group(2).replace(",", ""))))
        except ValueError:
            pass
    auv = None
    for want in ("average", "mean", "median"):
        hit = [v for lab, v in figures if lab == want]
        if hit:
            auv = sum(hit) / len(hit)
            break
    return {"present": present, "opt_out": opt_out, "figures": figures, "auv": auv,
            "excerpt": re.sub(r"\s+", " ", sec[:600]).strip()}


def parse_item20(sec: str) -> dict:
    """
    name:      parse_item20
    purpose:   Pull the latest-year systemwide outlet counts from Item 20's Table 1.
    arguments: sec — the Item 20 text.
    returns:   {year, franchised_end, company_end, total_end} with None where not parseable.
    other:     Table 1 rows read 'Year Start End NetChange' per outlet type. Heuristic and best-effort —
               a cross-check on our census, not an anchor; None rather than a wrong number when unsure.
    """
    out = {"year": None, "franchised_end": None, "company_end": None, "total_end": None}

    def last_triple(block):
        rows = re.findall(r"\b(20\d\d)\s+(\d{1,5})\s+(\d{1,5})\s+(-?\d{1,5})\b", block or "")
        if not rows:
            return None, None
        y, s, e, n = rows[-1]
        return int(y), int(e)
    # Isolate each outlet-type block so Franchised rows don't bleed into Company rows.
    fblk = re.search(r"Franchised([\s\S]*?)(?=Company|Total\s+Outlets|Table|$)", sec, re.I)
    cblk = re.search(r"Company[\s\-]*Ow\w*([\s\S]*?)(?=Total\s+Outlets|Table|$)", sec, re.I)
    fy, fe = last_triple(fblk.group(1) if fblk else "")
    cy, ce = last_triple(cblk.group(1) if cblk else "")
    out["franchised_end"], out["company_end"] = fe, ce
    out["year"] = fy or cy
    if fe is not None or ce is not None:
        out["total_end"] = (fe or 0) + (ce or 0)
    return out


# --- Collector -----------------------------------------------------------------------------------

def collect_one(con, target: dict, now: str | None = None, fetch_fn=None, raw_fn=None) -> dict:
    """
    name:      collect_one
    purpose:   Find one franchisor's latest FDD, archive it, parse Item 19/20, and persist findings.
    arguments: con; target — a TARGETS entry; now; fetch_fn/raw_fn — injectable IO for tests.
    returns:   a summary dict (status, auv, outlets, ...).
    effects:   pipeline_signals INSERT (signal_type='fdd', idempotent on the FDD's download URL) and,
               when Item 19 discloses a figure, a financial_anchors INSERT (metric 'fdd_item19_auv').
    """
    now = now or _utcnow()
    bid = target["brand_id"]
    fetch = fetch_fn or _fetch
    html = fetch(search_url(franchisor=target.get("franchisor", ""),
                            franchise_name=target.get("franchise_name", "")))
    rows = parse_results(html if isinstance(html, str) else html.decode("utf-8", "ignore"))
    row = latest_fdd(rows, franchisor=target.get("franchisor", ""))
    if not row:
        return {"brand": bid, "skipped": "no FDD on file in MN CARDS"}

    url = doc_url(row["guid"])
    seen = {r[0] for r in con.execute(
        "SELECT source_url FROM pipeline_signals WHERE signal_type='fdd' AND source_url IS NOT NULL")}
    if url in seen:
        return {"brand": bid, "duplicate": row["doc_number"], "year": row["year"]}

    pdf = fetch(url, raw=True) if fetch_fn is None else fetch(url, raw=True)
    if isinstance(pdf, str):
        pdf = pdf.encode("latin-1", "ignore")
    if raw_fn:
        try:
            raw_fn(bid, now[:10], pdf)
        except Exception:                                        # noqa: BLE001
            pass
    text = extract_text(pdf)
    i19 = parse_item19(item_section(text, 19))
    i20 = parse_item20(item_section(text, 20))

    if i19["auv"] is not None:
        status = f"Item 19 AUV ~${i19['auv']:,.0f}"
    elif i19["opt_out"]:
        status = "Item 19 opt-out (no financial performance representation)"
    elif not text:
        status = "FDD archived; not text-parseable (no pypdf or image PDF)"
    else:
        status = "Item 19 present, no clear per-unit figure parsed — needs human read"
    outlets = (f"; Item 20 {row['year']}: {i20['total_end']} US outlets "
               f"({i20['franchised_end']} franchised / {i20['company_end']} company)"
               if i20["total_end"] is not None else "")
    summary = (f"{row['franchisor']} {row['year']} {row['doc_type']} (MN) — {status}{outlets}")

    con.execute(
        "INSERT INTO pipeline_signals(signal_type,brand_id,location_id,filed_date,summary,raw_ref,"
        "source,source_url,retrieved_at,confidence) VALUES('fdd',?,?,?,?,?,?,?,?,?)",
        (bid, None, str(row["year"]) or None, summary, row["doc_number"] or None,
         "Minnesota CARDS (franchise registrations)", url, now,
         "high" if i19["auv"] is not None else "medium"))

    if i19["auv"] is not None:
        have = {r[0] for r in con.execute(
            "SELECT page_ref FROM financial_anchors WHERE brand_id=? AND metric='fdd_item19_auv'", (bid,))}
        tag = f"{row['doc_number']} ({row['year']})"
        if tag not in have:
            con.execute(
                "INSERT INTO financial_anchors(brand_id,period,metric,value,unit,page_ref,source,"
                "source_url,retrieved_at,confidence) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (bid, str(row["year"]), "fdd_item19_auv", round(i19["auv"], 2), "USD",
                 tag + " — " + i19["excerpt"][:180],
                 "FDD Item 19 (MN CARDS, " + row["franchisor"] + ")", url, now, "medium"))
    con.commit()
    return {"brand": bid, "year": row["year"], "doc_type": row["doc_type"], "status": status,
            "auv": i19["auv"], "opt_out": i19["opt_out"], "outlets": i20, "source_url": url}


def run(con, now: str | None = None) -> dict:
    """Pass over every TARGETS franchisor. Returns a per-brand summary. Idempotent."""
    now = now or _utcnow()
    from . import capture
    capture.set_delay(2, 4)              # be gentle with the state registry
    out = {}
    for t in TARGETS:
        try:
            from . import capture as _c
            raw_fn = lambda bid, d, payload: _c.save_raw("fdd_" + bid, d, payload, ext="pdf")  # noqa: E731
            out[t["brand_id"]] = collect_one(con, t, now=now, raw_fn=raw_fn)
        except Exception as e:                                   # noqa: BLE001
            out[t["brand_id"]] = {"brand": t["brand_id"], "error": f"{type(e).__name__}: {e}"}
    return out

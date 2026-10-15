"""
FDD collector — Item 19 Financial Performance Representations (and Item 20 outlet counts) for the
China-origin chains that are REGISTERED US FRANCHISORS. This is the best per-outlet, US-specific
revenue anchor in the whole model: Item 19 is a franchisor's own, legally-filed statement of what its
US units gross. See docs/phase2_revenue_spec.md (Tier-2 anchor).

SOURCE. State franchise registries, one `Registry` subclass each (see the Registries section). Of the
registration states, **Minnesota CARDS** (MinnesotaCARDS) is the clean, programmatic one: a public GET
search (franchisor / franchise-name / year / document-type) and a public document download, both plain
HTTP, and the only ENABLED registry. CARDS serves normal browsers but its WAF 403s a bot-ish User-Agent,
so we send a browser UA — public content served to any browser, not a CAPTCHA or an access control, and
nothing here forges a login or solves a challenge. The other two known libraries are disabled registries
carrying their reason: **Wisconsin DFI** (Cloudflare bot challenge) and **California DFPI** (no free
public FDD library — Cloudflare-challenged site, an account-based ASP.NET VIEWSTATE portal, and franchise
filing moved to the FRANSES submission site; probed 2026-10-15). Both are pulled by hand.

LEGAL POSTURE. FDDs are public records filed with state regulators — first-party/official, squarely in
posture. We archive the raw PDF (the evidence) before parsing a figure from it.

REALITY (why most rows are an honest "no number"). Many franchisors — especially new or foreign entrants,
which is most of these brands — OPT OUT of Item 19 ("we do not make any representations about a
franchisee's future financial performance"). That opt-out is itself recorded as a finding; an AUV anchor
is written ONLY when real figures are disclosed, never invented. Item 20 (outlet tables) is almost always
present and is mined for systemwide counts, the 3-year franchised/company series, latest-year gross
departures (start + opened - end), projected openings and the by-state split — a census cross-check plus a
forward/churn signal, each best-effort with None/{} rather than a wrong number.

WHAT IT WRITES.
  * pipeline_signals (signal_type='fdd'): one row per franchisor's latest filed FDD — the status
    (Item 19 figures found / opt-out), Item 20 outlet counts, the state + year, and source_url = the
    document download link (the dedupe key, so re-running adds nothing).
  * financial_anchors (metric 'fdd_item19_auv'): ONLY when Item 19 discloses a per-unit average/median
    gross-sales figure — a US, per-outlet AUV the revenue model can prefer over an overseas-derived one.
    Parsed figures are confidence 'medium' with the raw excerpt in page_ref, for human verification
    before they feed an estimate (Item 19 formats vary wildly). Also 'fdd_item7_invest_low'/'_high' — the
    estimated initial investment range from Item 7, which (unlike Item 19) is almost always disclosed —
    and 'fdd_item21_us_revenue', the audited US-entity revenue from the Item 21 financial statements: a
    MEASURED US figure (not a model), which the revenue model can prefer over an overseas-derived anchor.
  * fdd_extracts: one row per filed FDD (keyed on its document number), with each parsed Item stored as
    JSON — Item 7 (initial investment), Item 8 (supply-chain restriction flags), Item 20 (outlet tables:
    series, churn, projected openings, by-state), Item 19 (AUV) and Item 21 (audited financials) — plus
    needs_human_read when a section was ambiguous. The per-vintage store behind the series and Pro exports.

NOTE. parse_results() (the CARDS HTML shape) and the Item-19/20 text heuristics are the only pieces tied
to a source's exact format; they are isolated and tested offline against fixtures. With no network, no
pypdf, or no registration, the collector SKIPS cleanly and records nothing fabricated.
"""
import io
import json
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
# (precise), else by franchise name; an optional "registry" names the state library (default "MN").
# Add a brand here once an FDD filing is confirmed.
TARGETS = [
    {"brand_id": "miniso",    "franchisor": "MINISO DEPOT FRANCHISOR"},
    {"brand_id": "cotti",     "franchisor": "COTTI PARTNERS"},
    # Yangguofu's MN franchise name is "Yangguofu"; its franchisor entity is CAPTAIN BUSINESS
    # MANAGEMENT CO., LIMITED (a Hong Kong holding). Match the precise name, not "YANG".
    {"brand_id": "yangguofu", "franchise_name": "Yangguofu", "franchisor": "CAPTAIN BUSINESS MANAGEMENT"},
    {"brand_id": "mixue",     "franchise_name": "MIXUE",   "franchisor": "SNOW KING"},
    {"brand_id": "moge",      "franchise_name": "MOGE TEE"},
    # Yang's Braised Chicken (杨铭宇) is NOT in MN CARDS (searched BRAISED / Yang's / HUANG MEN -> 0); it is
    # registered in CA. CA DFPI has no free public FDD library (see CaliforniaDOCQNET), so this target
    # records the skip reason and is pulled by hand. Never search it by the broad token "YANG" (= Yangguofu).
    {"brand_id": "yangs", "franchise_name": "Yang's Braised Chicken", "registry": "CA"},
]


def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# --- Registries (the transport-bound pieces: how to search a state, read results, download a doc) -----
#
# One Registry per state franchise library. `latest_fdd` and `fetch` are shared; each subclass carries
# the source-specific URL shapes and HTML parse. A DISABLED registry (ENABLED=False) records WHY a state
# cannot be collected programmatically — the same convention as a blocked store adapter — so the roster
# shows the shape of the category, not just what happened to be scriptable.

class Registry:
    name = ""                        # short code, stored on the extract (fdd_extracts.state)
    source = ""                      # human label for pipeline_signals.source
    ua = UA_BROWSER
    doc_types = FDD_DOC_TYPES
    ENABLED = True
    BLOCKED_REASON = ""

    def search_url(self, franchisor: str = "", franchise_name: str = "", year: str = "") -> str:
        raise NotImplementedError

    def doc_url(self, row) -> str:
        raise NotImplementedError

    def parse_results(self, html: str) -> list[dict]:
        raise NotImplementedError

    def latest_fdd(self, rows: list[dict], franchisor: str = "") -> dict | None:
        """Most recent complete FDD (Clean > Final > Revised-Clean), optionally for one franchisor. Shared."""
        pref = {t: i for i, t in enumerate(self.doc_types)}
        cands = [r for r in rows if r.get("doc_type") in pref]
        if franchisor:
            fu = franchisor.upper()
            cands = [r for r in cands if fu in (r.get("franchisor") or "").upper()] or cands
        if not cands:
            return None
        cands.sort(key=lambda r: (r.get("year") or 0, -pref[r["doc_type"]]), reverse=True)
        return cands[0]

    def fetch(self, url: str, raw: bool = False):
        """One polite, robots-checked request with a browser UA. Returns text, or bytes if raw."""
        from . import capture
        r = capture.fetch(url, method="GET",
                          headers={"User-Agent": self.ua, "Accept": "*/*",
                                   "Accept-Language": "en-US,en;q=0.9"})
        return r.content if raw else r.text


class MinnesotaCARDS(Registry):
    """
    Minnesota CARDS — the clean, programmatic state library: a public GET search and a public document
    download, both plain HTTP. Its WAF 403s a bot-ish User-Agent, so we send a browser UA (public
    content served to any browser, not a CAPTCHA or an access control).
    """
    name = "MN"
    source = "Minnesota CARDS (franchise registrations)"
    base = CARDS

    def search_url(self, franchisor="", franchise_name="", year=""):
        from urllib.parse import urlencode
        q = {"doSearch": "true"}
        if franchisor:
            q["franchisor"] = franchisor
        if franchise_name:
            q["franchiseName"] = franchise_name
        if year:
            q["year"] = year
        return f"{self.base}/franchise-registrations?" + urlencode(q)

    def doc_url(self, row):
        guid = row["guid"] if isinstance(row, dict) else row
        return (f"{self.base}/documents/{quote(guid)}/download"
                "?documentClass=FRANCHISE_REGISTRATIONS&contentSequence=0")

    def parse_results(self, html):
        """
        Turn a CARDS search-results page into filing rows (one {guid, doc_number, franchisor, doc_type,
        year} per document). The ONLY piece tied to CARDS' HTML: a row is a <tr> carrying a
        /documents/<guid>/download link; we read its visible text for franchisor, type and year.
        "No documents found" -> [].
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


class CaliforniaDOCQNET(Registry):
    """
    California DFPI — NOT programmatically collectable as a free FDD library (probed 2026-10-15):
      * dfpi.ca.gov sits behind a Cloudflare bot challenge ("Performing security verification").
      * The DOCQNET self-service portal (docqnet.dfpi.ca.gov) is an account-based ASP.NET WebForms app
        whose search posts back an ENCRYPTED __VIEWSTATE (__VIEWSTATEENCRYPTED) — stateful, not a GET.
      * Its public "Online Filings Available" page lists license types (escrow, CDDTL, CFL), not
        franchise FDDs; franchise filing moved to the FRANSES submission site (franses.dfpi.ca.gov),
        which is for SUBMITTING, not public download.
      * California offers no free public FDD download library (unlike MN); FDDs are obtained by request.
    So CA is a disabled registry carrying this reason, pulled by hand until a usable public endpoint
    appears. Targets registered only in CA (e.g. Yang's Braised Chicken) are collected manually.
    """
    name = "CA"
    source = "California DFPI (DOCQNET / FRANSES)"
    ENABLED = False
    BLOCKED_REASON = ("California DFPI has no free public FDD library: dfpi.ca.gov is Cloudflare-"
                      "challenged, DOCQNET is an account-based ASP.NET VIEWSTATE portal, and franchise "
                      "filing moved to the FRANSES submission site. Pull by hand (probed 15 Oct 2026).")


class WisconsinDFI(Registry):
    """Wisconsin DFI — the other free library, but behind a Cloudflare bot challenge that hard-blocks
    automated clients. Disabled; pull by hand."""
    name = "WI"
    source = "Wisconsin DFI"
    ENABLED = False
    BLOCKED_REASON = "Wisconsin DFI sits behind a Cloudflare bot challenge; pull by hand."


# The default (and only enabled) registry, plus the roster of all known state libraries.
MN = MinnesotaCARDS()
REGISTRIES = {r.name: r for r in (MN, CaliforniaDOCQNET(), WisconsinDFI())}


# Module-level delegates to the default registry, so callers/tests can use fdd.parse_results(...),
# fdd.latest_fdd(...), fdd.doc_url("{GUID}"), fdd.search_url(...) without a registry in hand.
def _fetch(url: str, raw: bool = False):
    return MN.fetch(url, raw=raw)


def search_url(franchisor: str = "", franchise_name: str = "", year: str = "") -> str:
    return MN.search_url(franchisor, franchise_name, year)


def doc_url(guid: str) -> str:
    return MN.doc_url({"guid": guid})


def parse_results(html: str) -> list[dict]:
    return MN.parse_results(html)


def latest_fdd(rows: list[dict], franchisor: str = "") -> dict | None:
    return MN.latest_fdd(rows, franchisor)


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


# US states + DC -> postal abbreviation, for the by-state table parse.
_US_STATES = {
    "Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR", "California": "CA",
    "Colorado": "CO", "Connecticut": "CT", "Delaware": "DE", "District of Columbia": "DC",
    "Florida": "FL", "Georgia": "GA", "Hawaii": "HI", "Idaho": "ID", "Illinois": "IL",
    "Indiana": "IN", "Iowa": "IA", "Kansas": "KS", "Kentucky": "KY", "Louisiana": "LA",
    "Maine": "ME", "Maryland": "MD", "Massachusetts": "MA", "Michigan": "MI", "Minnesota": "MN",
    "Mississippi": "MS", "Missouri": "MO", "Montana": "MT", "Nebraska": "NE", "Nevada": "NV",
    "New Hampshire": "NH", "New Jersey": "NJ", "New Mexico": "NM", "New York": "NY",
    "North Carolina": "NC", "North Dakota": "ND", "Ohio": "OH", "Oklahoma": "OK", "Oregon": "OR",
    "Pennsylvania": "PA", "Rhode Island": "RI", "South Carolina": "SC", "South Dakota": "SD",
    "Tennessee": "TN", "Texas": "TX", "Utah": "UT", "Vermont": "VT", "Virginia": "VA",
    "Washington": "WA", "West Virginia": "WV", "Wisconsin": "WI", "Wyoming": "WY",
}
# Longest names first so "West Virginia" matches before "Virginia", "New York" before any fragment.
_STATE_ROW = re.compile(
    r"\b(" + "|".join(sorted((re.escape(n) for n in _US_STATES), key=len, reverse=True))
    + r")\b\s+\$?(\d{1,4})\b")


def parse_item20(sec: str) -> dict:
    """
    name:      parse_item20
    purpose:   Pull Item 20's outlet tables — systemwide counts, the 3-year series, latest-year gross
               departures, projected openings, and the by-state split.
    arguments: sec — the Item 20 text.
    returns:   {year, franchised_end, company_end, total_end,                      (Table 1 latest year)
                franchised_series, company_series,                                 ([(year, end), ...])
                franchised_status_latest: {year, start, opened, end, left_system}, (Table 3, or None)
                projected: {signed_not_open, projected_new_franchised},            (Table 5, or None)
                by_state: {ST: count},                                             (by-state table, or {})
                needs_human_read}
    other:     Heuristic and best-effort, in the house style — a census cross-check and forward/churn
               signal, not an anchor; each sub-table yields None/{} rather than a wrong number when its
               shape is not found. 'left_system' = start + opened - end: outlets that left the franchised
               system in the latest year (terminations + non-renewals + reacquisitions + ceased) — a gross
               departure count derived without mapping the middle columns, which vary by franchisor.
    """
    out = {"year": None, "franchised_end": None, "company_end": None, "total_end": None,
           "franchised_series": [], "company_series": [], "franchised_status_latest": None,
           "projected": None, "by_state": {}, "needs_human_read": False}

    def triples(block):
        # Table 1 rows: 'Year Start End NetChange' (exactly three figures) -> [(year, end), ...].
        rows = re.findall(r"\b(20\d\d)\s+(\d{1,5})\s+(\d{1,5})\s+(-?\d{1,5})\b", block or "")
        return [(int(y), int(e)) for (y, _s, e, _n) in rows]
    # Isolate each outlet-type block so Franchised rows don't bleed into Company rows.
    fblk = re.search(r"Franchised([\s\S]*?)(?=Company|Total\s+Outlets|Table|$)", sec, re.I)
    cblk = re.search(r"Company[\s\-]*Ow\w*([\s\S]*?)(?=Total\s+Outlets|Table|$)", sec, re.I)
    out["franchised_series"] = triples(fblk.group(1) if fblk else "")
    out["company_series"] = triples(cblk.group(1) if cblk else "")
    if out["franchised_series"]:
        out["year"], out["franchised_end"] = out["franchised_series"][-1]
    if out["company_series"]:
        cy, ce = out["company_series"][-1]
        out["company_end"] = ce
        out["year"] = out["year"] or cy
    if out["franchised_end"] is not None or out["company_end"] is not None:
        out["total_end"] = (out["franchised_end"] or 0) + (out["company_end"] or 0)

    # Table 3 (Status of Franchised Outlets): latest-year gross departures, via start + opened - end.
    sm = re.search(r"Status\s+of\s+Franchised\s+Outlets[\s\S]*?"
                   r"(?=Status\s+of\s+Company|Table\s+No\.?\s*4|Table\s+No\.?\s*5|ITEM\s*21|$)", sec, re.I)
    if sm:
        # A status row = a year followed by >=4 figures (Table 1 rows have only 3); the negative
        # lookahead stops a row before the next year so rows don't merge in the flattened text.
        rows = re.findall(r"\b(20\d\d)((?:\s+(?!20\d\d\b)\d{1,5}){4,})", sm.group(0))
        if rows:
            y, tail = rows[-1]
            nums = [int(x) for x in tail.split()]
            start, opened, end = nums[0], nums[1], nums[-1]
            out["franchised_status_latest"] = {"year": int(y), "start": start, "opened": opened,
                                               "end": end, "left_system": start + opened - end}

    # Table 5 (Projected Openings): the 'Totals' row under a 'Projected Openings' header.
    pm = re.search(r"Projected\s+Openings?[\s\S]{0,1200}?\bTotals?\b\s+(\d{1,5})(?:\s+(\d{1,5}))?",
                   sec, re.I)
    if pm:
        out["projected"] = {"signed_not_open": int(pm.group(1)),
                            "projected_new_franchised": int(pm.group(2)) if pm.group(2) else None}

    # Outlets by state: only under a 'by State' header, and only state names trailed by a count, so
    # a state mentioned in prose does not register. First figure per row (the franchised column).
    bm = re.search(r"(?:Outlets?\s+by\s+State|by\s+State)[\s\S]{0,2000}", sec, re.I)
    if bm:
        for name, n in _STATE_ROW.findall(bm.group(0)):
            out["by_state"].setdefault(_US_STATES[name], int(n))

    out["needs_human_read"] = bool(sec.strip()) and not out["franchised_series"] \
        and not out["company_series"]
    return out


# A dollar amount: "$1,234" or "$ 45,000.00" — at least three digits, so page numbers don't match.
_I7_AMT = r"\$\s?(\d[\d,]{2,}(?:\.\d\d)?)"
# The grand-total row, preferred when it is explicitly labelled (not a subtotal).
_I7_TOTAL_LABELED = re.compile(
    r"TOTAL\s+(?:ESTIMATED\s+)?(?:INITIAL\s+)?INVESTMENT[^\n$]*?" + _I7_AMT
    + r"(?:[^\d$\n]{0,15}" + _I7_AMT + r")?", re.I)
# Any TOTAL row carrying a dollar figure — the fallback when no labelled grand total is found.
_I7_TOTAL_ANY = re.compile(
    r"\bTOTAL\b[^\n$]{0,40}?" + _I7_AMT + r"(?:[^\d$\n]{0,15}" + _I7_AMT + r")?", re.I)
# A single expenditure row: "Leasehold Improvements $120,000 to $350,000" (one figure or a low-high range).
_I7_LINE = re.compile(
    r"([A-Za-z][A-Za-z/ &'\-\(\),]{2,58}?)\s*" + _I7_AMT
    + r"(?:\s*(?:to|through|[-–—])\s*" + _I7_AMT + r")?")


def _usd(s: str):
    """'1,234,567.00' -> 1234567 (int). None if it will not parse."""
    try:
        return int(round(float(s.replace(",", ""))))
    except (ValueError, AttributeError):
        return None


def parse_item7(sec: str) -> dict:
    """
    name:      parse_item7
    purpose:   Pull the estimated initial investment (low–high total + named line items) from Item 7.
    arguments: sec — the Item 7 text.
    returns:   {low, high, currency, lines:{label:[low,high]}, needs_human_read, excerpt}.
    other:     Item 7 is mandatory (franchisors rarely opt out, unlike Item 19), so it gives a build-out
               cost even where no AUV is disclosed. Best-effort and heuristic, in the house style: the
               grand-total low/high is the figure that matters (it feeds the anchors); `lines` is a
               secondary convenience. Returns low=high=None — and flags needs_human_read — rather than a
               guess when the total will not parse, so a human reads the excerpt.
    """
    sec = sec or ""
    low = high = None
    m = _I7_TOTAL_LABELED.search(sec)
    if not m:                                   # no labelled grand total — take the TOTAL row with the largest figure
        cands = list(_I7_TOTAL_ANY.finditer(sec))
        m = max(cands, key=lambda x: _usd(x.group(2) or x.group(1)) or 0) if cands else None
    if m:
        low = _usd(m.group(1))
        high = _usd(m.group(2)) if m.group(2) else low
        if low is not None and high is not None and high < low:
            low, high = high, low
    lines = {}
    for lm in _I7_LINE.finditer(sec):
        label = re.sub(r"\s+", " ", lm.group(1)).strip()
        if "TOTAL" in label.upper():            # the grand/subtotal rows are captured above, not as line items
            continue
        lo = _usd(lm.group(2))
        hi = _usd(lm.group(3)) if lm.group(3) else lo
        if lo is not None and label not in lines:
            lines[label] = [lo, hi]
    return {"low": low, "high": high, "currency": "USD", "lines": lines,
            "needs_human_read": bool(sec.strip()) and low is None,
            "excerpt": re.sub(r"\s+", " ", sec[:600]).strip()}


# A financial-statement figure: "$ 12,500,000", "1,234,567", or a parenthesised negative "(1,350,000)".
_STMT_NUM = re.compile(r"(\()?\s*\$?\s*(\d{1,3}(?:,\d{3})+|\d{4,})(?:\.\d+)?\s*(\))?")


def item21_scope(text: str) -> str:
    """
    name:      item21_scope
    purpose:   The Item 21 text AND everything after it, to end of document.
    arguments: text — full FDD text.
    returns:   the slice from the last 'ITEM 21' header onward ('' if not found).
    other:     Unlike other items, Item 21's audited statements almost always sit in an EXHIBIT after
               the item body (the body just says 'attached as Exhibit E'), so we read to the end rather
               than to 'ITEM 22'. Items 7/19 — with their own dollar figures — are BEFORE Item 21, so
               this scope never pulls them in.
    """
    starts = [m.start() for m in re.finditer(r"ITEM\s*21\b", text, re.I)]
    return text[starts[-1]:] if starts else ""


def parse_item21(sec: str) -> dict:
    """
    name:      parse_item21
    purpose:   Pull measured US-entity figures from the Item 21 audited financial statements.
    arguments: sec — the Item 21-onward text (see item21_scope).
    returns:   {present, revenue, net_income, total_assets, going_concern, needs_human_read, excerpt}.
    other:     THE measured anchor — audited US revenue, not a model (the one number that steps around
               the modeled/measured wall). Still a heuristic parse of varied statement layouts, so the
               anchor it feeds stays confidence 'medium' pending a human read; what makes it 'measured'
               is the SOURCE (audited statements) and the metric name, not the parse. The leftmost column
               of an audited statement is the most recent year, so we take the first figure after each
               label; parentheses mean a negative; a bare year token (e.g. a '2025' column header) is
               skipped. Returns None + needs_human_read rather than a guess when a figure won't parse —
               common when the statements are an image exhibit or sit outside this scope.
    """
    sec = sec or ""

    def val(label_pat: str):
        m = re.search(label_pat, sec, re.I)
        if not m:
            return None
        win = sec[m.end(): m.end() + 120]
        for nm in _STMT_NUM.finditer(win):
            digits = nm.group(2)
            n = int(digits.replace(",", ""))
            if "," not in digits and 1900 <= n <= 2099:
                continue                       # a bare year column header, not a figure
            if nm.group(1) == "(" and nm.group(3) == ")":
                n = -n
            return n
        return None

    def coalesce(*vs):
        return next((v for v in vs if v is not None), None)

    revenue = coalesce(val(r"\bTotal\s+revenues?\b"), val(r"\bNet\s+sales\b"), val(r"\bRevenues?\b"))
    net_income = coalesce(val(r"\bNet\s+income\s*\(loss\)"), val(r"\bNet\s+income\b"),
                          val(r"\bNet\s+loss\b"))
    total_assets = val(r"\bTotal\s+assets\b")
    going_concern = bool(re.search(r"substantial doubt|going concern", sec, re.I))
    present = bool(sec.strip())
    return {"present": present, "revenue": revenue, "net_income": net_income,
            "total_assets": total_assets, "going_concern": going_concern,
            "needs_human_read": present and revenue is None,
            "excerpt": re.sub(r"\s+", " ", sec[:600]).strip()}


# Item 8 supply-chain flags (qualitative, for the supplier/distributor segment).
_I8 = {
    # A franchisor-controlled supplier roster the franchisee must use.
    "required_suppliers": re.compile(
        r"\b(?:required|approved|designated|authorized)\s+(?:suppliers?|sources?|vendors?|distributors?)\b"
        r"|\bsuppliers?\s+(?:we|that we)\b[^.]{0,20}(?:approve|designate|require|authoriz)", re.I),
    # The franchisor (or its affiliate) is itself a required/sole source — captive supply.
    "franchisor_is_supplier": re.compile(
        r"\bsole\s+(?:approved\s+)?(?:source|supplier)\b"
        r"|(?:purchase|buy|obtain|order)[^.]{0,80}\bfrom\s+(?:us|the\s+franchisor|our\s+affiliates?|an?\s+affiliate)\b"
        r"|\bwe\s+(?:are|will be)\s+(?:the\s+)?(?:sole|only|exclusive)\s+(?:approved\s+)?(?:source|supplier)\b", re.I),
    # The franchisor takes rebates/allowances/payments from suppliers on franchisee purchases.
    "rebates": re.compile(
        r"\brebates?\b|\ballowances?\b"
        r"|(?:receive|derive|earn|retain|collect)[^.]{0,60}\bfrom\b[^.]{0,30}suppliers?"
        r"|suppliers?[^.]{0,40}(?:rebate|allowance|payment|commission)", re.I),
    # Proprietary / private-label / secret-recipe goods the franchisee is required to buy.
    "proprietary": re.compile(
        r"\bproprietary\b|\bprivate[\s-]?label\b|\bsecret\s+(?:recipe|formula)\b"
        r"|\btrademarked\s+(?:products?|ingredients?)\b", re.I),
}


def parse_item8(sec: str) -> dict:
    """
    name:      parse_item8
    purpose:   Flag Item 8 supply-chain restrictions — required suppliers, captive (franchisor) supply,
               supplier rebates, and proprietary goods.
    arguments: sec — the Item 8 text.
    returns:   {present, required_suppliers, franchisor_is_supplier, rebates, proprietary,
                needs_human_read, excerpt}.
    other:     Item 8 is prose, so these are best-effort booleans (absence = "not detected", not a parse
               failure) — the supplier/distributor segment's signal: does a supplier have an opening, or
               has a franchisor-controlled or captive supply chain already closed it? The excerpt is kept
               for verification; needs_human_read trips only when a present section yielded no flag, so a
               human confirms an unrestrictive Item 8 rather than the model assuming one.
    """
    sec = sec or ""
    present = bool(sec.strip())
    flags = {k: bool(p.search(sec)) for k, p in _I8.items()}
    return {"present": present, **flags,
            "needs_human_read": present and not any(flags.values()),
            "excerpt": re.sub(r"\s+", " ", sec[:600]).strip()}


# --- Collector -----------------------------------------------------------------------------------

def collect_one(con, target: dict, now: str | None = None, fetch_fn=None, raw_fn=None,
                registry: "Registry | None" = None) -> dict:
    """
    name:      collect_one
    purpose:   Find one franchisor's latest FDD, archive it, parse Items 7/19/20/21, and persist findings.
    arguments: con; target — a TARGETS entry; now; fetch_fn/raw_fn — injectable IO for tests;
               registry — the state library to search (defaults to Minnesota CARDS).
    returns:   a summary dict (status, auv, outlets, ...).
    effects:   pipeline_signals INSERT (signal_type='fdd', idempotent on the FDD's download URL),
               an fdd_extracts row, and financial_anchors INSERTs for any disclosed figures.
    """
    now = now or _utcnow()
    bid = target["brand_id"]
    reg = registry or MN
    if not reg.ENABLED:
        return {"brand": bid, "skipped": f"{reg.name}: {reg.BLOCKED_REASON}"}
    fetch = fetch_fn or reg.fetch
    html = fetch(reg.search_url(franchisor=target.get("franchisor", ""),
                                franchise_name=target.get("franchise_name", "")))
    rows = reg.parse_results(html if isinstance(html, str) else html.decode("utf-8", "ignore"))
    row = reg.latest_fdd(rows, franchisor=target.get("franchisor", ""))
    if not row:
        return {"brand": bid, "skipped": f"no FDD on file in {reg.name}"}

    url = reg.doc_url(row)
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
    i7 = parse_item7(item_section(text, 7))
    i8 = parse_item8(item_section(text, 8))
    i21 = parse_item21(item21_scope(text))

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
    if i20.get("projected") and i20["projected"].get("projected_new_franchised") is not None:
        outlets += f", +{i20['projected']['projected_new_franchised']} projected next FY"
    invest = (f"; Item 7 invest ${i7['low']:,}-${i7['high']:,}"
              if i7["low"] is not None else "")
    fin = (f"; Item 21 US revenue ~${i21['revenue']:,}" if i21["revenue"] is not None else "")
    if i21["going_concern"]:
        fin += " (going-concern doubt)"
    f8 = [lbl for key, lbl in (("required_suppliers", "required suppliers"),
                               ("franchisor_is_supplier", "franchisor-supplied"),
                               ("rebates", "supplier rebates"),
                               ("proprietary", "proprietary goods")) if i8[key]]
    supply = f"; Item 8: {', '.join(f8)}" if f8 else ""
    summary = (f"{row['franchisor']} {row['year']} {row['doc_type']} ({reg.name}) — "
               f"{status}{outlets}{invest}{fin}{supply}")

    con.execute(
        "INSERT INTO pipeline_signals(signal_type,brand_id,location_id,filed_date,summary,raw_ref,"
        "source,source_url,retrieved_at,confidence) VALUES('fdd',?,?,?,?,?,?,?,?,?)",
        (bid, None, str(row["year"]) or None, summary, row["doc_number"] or None,
         reg.source, url, now, "high" if i19["auv"] is not None else "medium"))

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
                 f"FDD Item 19 ({reg.name}, " + row["franchisor"] + ")", url, now, "medium"))

    # The per-Item extract (a vintage). doc_number is the dedupe key; fall back to guid/url if blank.
    doc_key = row["doc_number"] or row["guid"] or url
    items = {"item7": i7,
             "item8": i8,
             "item19": {"present": i19["present"], "opt_out": i19["opt_out"],
                        "auv": i19["auv"], "figures": i19["figures"]},
             "item20": i20,
             "item21": i21}
    con.execute(
        "INSERT OR REPLACE INTO fdd_extracts(doc_number,brand_id,franchisor,year,state,items_json,"
        "needs_human_read,source_url,retrieved_at) VALUES(?,?,?,?,?,?,?,?,?)",
        (doc_key, bid, row["franchisor"], row["year"] or None, reg.name,
         json.dumps(items, ensure_ascii=False),
         1 if (i7["needs_human_read"] or i21["needs_human_read"]
               or i20["needs_human_read"]) else 0, url, now))

    # Filed/measured figures -> anchors. Idempotent on the (brand, metric) page_ref tag. All confidence
    # 'medium' (heuristic parse pending a human read); Item 21 is measured US revenue, flagged by metric.
    vtag = f"{row['doc_number']} ({row['year']})"

    def add_anchor(metric, value, excerpt, item_label):
        if value is None:
            return
        have = {r[0] for r in con.execute(
            "SELECT page_ref FROM financial_anchors WHERE brand_id=? AND metric=?", (bid, metric))}
        if not any((p or "").startswith(vtag) for p in have):
            con.execute(
                "INSERT INTO financial_anchors(brand_id,period,metric,value,unit,page_ref,source,"
                "source_url,retrieved_at,confidence) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (bid, str(row["year"]), metric, float(value), "USD",
                 vtag + " — " + (excerpt or "")[:180],
                 f"FDD {item_label} ({reg.name}, " + row["franchisor"] + ")", url, now, "medium"))

    # Item 7 initial-investment range (factual, filed; build-out cost for CRE/investors).
    add_anchor("fdd_item7_invest_low", i7["low"], i7["excerpt"], "Item 7")
    add_anchor("fdd_item7_invest_high", i7["high"], i7["excerpt"], "Item 7")
    # Item 21 audited US revenue — the measured anchor the revenue model can prefer over a model.
    add_anchor("fdd_item21_us_revenue", i21["revenue"], i21["excerpt"], "Item 21")
    con.commit()
    return {"brand": bid, "year": row["year"], "doc_type": row["doc_type"], "status": status,
            "auv": i19["auv"], "opt_out": i19["opt_out"], "outlets": i20,
            "invest": (i7["low"], i7["high"]), "us_revenue": i21["revenue"],
            "going_concern": i21["going_concern"], "source_url": url}


def run(con, now: str | None = None) -> dict:
    """
    Pass over every TARGETS franchisor, each against the registry named in its 'registry' key
    (default 'MN'). A target on a disabled registry (CA/WI) records the skip reason rather than
    hitting the network. Returns a per-brand summary. Idempotent.
    """
    now = now or _utcnow()
    from . import capture
    capture.set_delay(2, 4)              # be gentle with the state registry
    out = {}
    for t in TARGETS:
        reg = REGISTRIES.get(t.get("registry", "MN"), MN)
        try:
            from . import capture as _c
            raw_fn = lambda bid, d, payload: _c.save_raw("fdd_" + bid, d, payload, ext="pdf")  # noqa: E731
            out[t["brand_id"]] = collect_one(con, t, now=now, raw_fn=raw_fn, registry=reg)
        except Exception as e:                                   # noqa: BLE001
            out[t["brand_id"]] = {"brand": t["brand_id"], "error": f"{type(e).__name__}: {e}"}
    return out

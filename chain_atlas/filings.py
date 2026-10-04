"""
Filings collector — the repeatable "China-domestic (+ SEC-for-Chinese-issuers) pull" for the chains with a
CONFIRMED US PRESENCE. It watches each US-present listed chain's primary filing venue, finds the latest
ANNUAL report, and records a pipeline signal when a NEW one appears — so the per-chain manual research we
were doing by hand becomes a scheduled check.

WHAT IT DOES AND DOES NOT DO. It PULLS and references filings; it does NOT auto-extract revenue figures.
Segment/US disclosure varies wildly filing to filing, and auto-parsing RMB tables or inferring a US
breakout is exactly where a wrong number would slip in (the Pop Mart "$164M" lesson). So this collector
SURFACES the filing (a `filing` pipeline_signal, idempotent on the document URL) and a human/agent
re-verifies the anchors from it — same split as the USPTO collector (discover + signal) and launch-watch.

VENUES (all official filing portals — first-party, in posture):
  * SEC EDGAR — the submissions JSON API (data.sec.gov) gives every filing with its accession, date and
    primary document; we pick the latest 20-F and build the document URL. Clean and fully automatable.
    Covers the US-listed Chinese issuers: Miniso, Chagee, Luckin, and Super Hi (Haidilao's US operator).
  * cninfo (巨潮资讯) — the mainland CSRC-designated disclosure site. topSearch resolves a stock code to
    its orgId; hisAnnouncement lists the 年度报告 (annual reports). Automatable. Covers A-share filers
    with US presence (Juewei).
  * HKEX (HKEXnews) — its filing search needs an internal `stockId` (not the 4-digit code) that its public
    lookup will not hand out to a server. So HKEX is AUTOMATED only when a `stockid` is supplied in the
    registry (titleSearchServlet then works); otherwise the collector emits a CHECK-LINK for a human. The
    stockId-mapping is the one piece left to resolve to make Pop Mart/Mixue/Nayuki/etc. fully auto.

SCOPE. Only chains with a confirmed US presence AND a listing (the registry below). A private chain has no
filing to pull; a listed chain with no US outlets is out of scope (handled elsewhere, e.g. the A-share
intelligence pull). DB-only / Pro tier.
"""
import json
import urllib.parse
from datetime import datetime, timezone

# SEC's fair-access policy requires a UA with an EMAIL contact (it 403s otherwise); we use the project's
# own domain, not a personal address. cninfo's WAF wants a browser UA (public content, not a challenge).
SEC_UA = "chainsfromchina.com filings collector; contact@chainsfromchina.com"
CN_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
         "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")

# US-present LISTED chains and where each files. venue drives the fetcher; the locator is the venue's key.
# HKEX entries carry no stockId yet -> check-link until the stockId mapping is resolved (then add "stockid").
FILERS = [
    {"brand_id": "miniso",      "venue": "SEC",    "cik": 1815846, "form": "20-F"},
    {"brand_id": "chagee",      "venue": "SEC",    "cik": 2013649, "form": "20-F"},
    {"brand_id": "luckin",      "venue": "SEC",    "cik": 1767582, "form": "20-F"},
    {"brand_id": "haidilao",    "venue": "SEC",    "cik": 1995306, "form": "20-F",
     "note": "Super Hi International (HDL) — Haidilao's overseas operator, the US-relevant filer"},
    {"brand_id": "popmart",     "venue": "HKEX",   "stock": "9992"},
    {"brand_id": "mixue",       "venue": "HKEX",   "stock": "2097"},
    {"brand_id": "nayuki",      "venue": "HKEX",   "stock": "2150"},
    {"brand_id": "aunteajenny", "venue": "HKEX",   "stock": "2589"},
    {"brand_id": "chabaidao",   "venue": "HKEX",   "stock": "2555"},
    {"brand_id": "taier",       "venue": "HKEX",   "stock": "9922", "note": "Jiumaojiu International (Tai Er's parent)"},
    {"brand_id": "jnby",        "venue": "HKEX",   "stock": "3306"},
    {"brand_id": "anta",        "venue": "HKEX",   "stock": "2020"},
    {"brand_id": "juewei",      "venue": "cninfo", "code": "603517", "column": "sse"},
]


def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _get(url, ua, method="GET", data=None, headers=None):
    """One polite, robots-checked request via the shared capture session. Returns text or None."""
    from . import capture
    h = {"User-Agent": ua, "Accept": "application/json, text/plain, */*"}
    if headers:
        h.update(headers)
    try:
        r = capture.fetch(url, method=method, headers=h, **({"data": data} if data is not None else {}))
        return r.text
    except Exception:                                            # noqa: BLE001
        return None


# --- SEC EDGAR -----------------------------------------------------------------------------------

def sec_latest(cik: int, form: str = "20-F", fetch_fn=None):
    """
    name:      sec_latest
    purpose:   The latest filing of a given form for a CIK, from the EDGAR submissions API.
    returns:   {date, accession, url, title} or None.
    other:     Isolated API-shape dependency. Builds the primary-document URL from accession + doc name.
    """
    raw = (fetch_fn or (lambda: _get(f"https://data.sec.gov/submissions/CIK{int(cik):010d}.json", SEC_UA)))()
    if not raw:
        return None
    try:
        d = json.loads(raw)
        rec = d["filings"]["recent"]
        for i, f in enumerate(rec["form"]):
            if f == form:
                acc = rec["accessionNumber"][i]
                doc = rec["primaryDocument"][i]
                url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc.replace('-', '')}/{doc}"
                return {"date": rec["filingDate"][i], "accession": acc, "url": url,
                        "title": f"{d.get('name', '')} {form} {rec['filingDate'][i]}".strip()}
    except Exception:                                            # noqa: BLE001
        return None
    return None


# --- cninfo (mainland A-shares) ------------------------------------------------------------------

def _cninfo_orgid(code: str, fetch_fn=None):
    raw = (fetch_fn or (lambda: _get(
        "http://www.cninfo.com.cn/new/information/topSearch/query", CN_UA, method="POST",
        data=urllib.parse.urlencode({"keyWord": code, "maxNum": "10"}).encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded",
                 "Referer": "http://www.cninfo.com.cn/"})))()
    if not raw:
        return None
    try:
        for row in json.loads(raw):
            if row.get("code") == code:
                return row.get("orgId")
    except Exception:                                            # noqa: BLE001
        return None
    return None


def cninfo_latest(code: str, column: str = "sse", fetch_fn=None, orgid_fn=None):
    """
    name:      cninfo_latest
    purpose:   The latest annual report (年度报告) for a mainland A-share code, from cninfo.
    returns:   {date, url, title} or None. url is the static.cninfo.com.cn PDF.
    other:     Prefers the full report over the 摘要 (summary). orgId is resolved first via topSearch.
    """
    orgid = (orgid_fn or (lambda: _cninfo_orgid(code)))()
    if not orgid:
        return None
    raw = (fetch_fn or (lambda: _get(
        "http://www.cninfo.com.cn/new/hisAnnouncement/query", CN_UA, method="POST",
        data=urllib.parse.urlencode({
            "stock": f"{code},{orgid}", "tabName": "fulltext", "pageSize": "10", "pageNum": "1",
            "column": column, "category": "category_ndbg_szsh",
            "plate": "sh" if column == "sse" else "sz", "isHLtitle": "true"}).encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded",
                 "Referer": "http://www.cninfo.com.cn/"})))()
    if not raw:
        return None
    try:
        anns = json.loads(raw).get("announcements") or []
    except Exception:                                            # noqa: BLE001
        return None
    # newest full annual report (skip 摘要 summaries); announcements are returned newest-first
    full = [a for a in anns if "摘要" not in (a.get("announcementTitle") or "")] or anns
    if not full:
        return None
    a = full[0]
    ts = a.get("adjunctUrl", "")
    url = "http://static.cninfo.com.cn/" + ts.lstrip("/")
    when = ""
    try:
        when = datetime.utcfromtimestamp(int(a["announcementTime"]) / 1000).strftime("%Y-%m-%d")
    except Exception:                                            # noqa: BLE001
        pass
    return {"date": when, "url": url, "title": (a.get("announcementTitle") or "").strip()}


# --- HKEX (auto only when a stockId is supplied; else a check-link) -------------------------------

def hkex_latest(stock: str, stockid: str | None = None, fetch_fn=None):
    """
    name:      hkex_latest
    purpose:   The latest annual report for an HKEX code — via titleSearchServlet IF a stockId is known.
    returns:   {date, url, title} when a stockId resolves it; else {manual: <search url>} for a human.
    other:     HKEXnews' code->stockId lookup is not available to a server, so without a stockId we return
               a check-link. Supply "stockid" in the FILERS entry to switch this chain to auto.
    """
    search_url = f"https://www1.hkexnews.hk/search/titlesearch.xhtml?lang=en&searchType=1&t=rpt&SEHKcode={stock}"
    if not stockid:
        return {"manual": search_url, "title": None}
    import time
    url = ("https://www1.hkexnews.hk/search/titleSearchServlet.do?sortDir=0&sortByOptions=DateTime"
           f"&category=0&market=SEHK&stockId={stockid}&documentType=-1&fromDate=&toDate="
           f"&title=Annual%20Report&searchType=1&t={int(time.time()*1000)}&lang=en")
    raw = (fetch_fn or (lambda: _get(url, CN_UA, headers={"X-Requested-With": "XMLHttpRequest",
           "Referer": "https://www1.hkexnews.hk/search/titlesearch.xhtml?lang=en"})))()
    if not raw:
        return {"manual": search_url, "title": None}
    try:
        rows = json.loads(raw).get("result")
        rows = json.loads(rows) if isinstance(rows, str) else rows
        if rows:
            r = rows[0]
            doc = r.get("FILE_LINK") or r.get("fileLink") or ""
            return {"date": (r.get("DATE_TIME") or "")[:10],
                    "url": "https://www1.hkexnews.hk" + doc if doc.startswith("/") else doc,
                    "title": (r.get("TITLE") or r.get("title") or "Annual Report").strip()}
    except Exception:                                            # noqa: BLE001
        pass
    return {"manual": search_url, "title": None}


def latest_filing(filer: dict, fetch_fn=None):
    """Dispatch to the right venue fetcher. fetch_fn (tests) overrides the network call."""
    v = filer["venue"]
    if v == "SEC":
        return sec_latest(filer["cik"], filer.get("form", "20-F"), fetch_fn=fetch_fn)
    if v == "cninfo":
        return cninfo_latest(filer["code"], filer.get("column", "sse"), fetch_fn=fetch_fn)
    if v == "HKEX":
        return hkex_latest(filer["stock"], filer.get("stockid"), fetch_fn=fetch_fn)
    return None


# --- Collector -----------------------------------------------------------------------------------

def collect(con, now: str | None = None, fetch_fns: dict | None = None) -> dict:
    """
    name:      collect
    purpose:   For each US-present listed filer, find its latest annual filing and signal a NEW one.
    effects:   INSERTs 'filing' pipeline_signals, idempotent on the document URL — so a new annual report
               (new URL) produces exactly one new signal (the prompt to re-verify that chain's anchors).
    returns:   summary {checked, new, duplicate, manual, rows}. HKEX check-links are reported (in `manual`),
               not stored, so they never nag.
    """
    now = now or _utcnow()
    seen = {r[0] for r in con.execute(
        "SELECT source_url FROM pipeline_signals WHERE signal_type='filing' AND source_url IS NOT NULL")}
    summ = {"checked": 0, "new": 0, "duplicate": 0, "manual": 0, "skipped": 0, "rows": []}
    for f in FILERS:
        summ["checked"] += 1
        fn = (fetch_fns or {}).get(f["brand_id"])
        info = latest_filing(f, fetch_fn=fn)
        if not info:
            summ["skipped"] += 1
            summ["rows"].append({"brand": f["brand_id"], "venue": f["venue"], "status": "unavailable"})
            continue
        if info.get("manual"):
            summ["manual"] += 1
            summ["rows"].append({"brand": f["brand_id"], "venue": f["venue"],
                                 "status": "check-link", "url": info["manual"]})
            continue
        url = info.get("url")
        if not url:
            summ["skipped"] += 1
            continue
        if url in seen:
            summ["duplicate"] += 1
            summ["rows"].append({"brand": f["brand_id"], "venue": f["venue"], "status": "current",
                                 "date": info.get("date"), "url": url})
            continue
        con.execute(
            "INSERT INTO pipeline_signals(signal_type,brand_id,location_id,filed_date,summary,raw_ref,"
            "source,source_url,retrieved_at,confidence) VALUES('filing',?,?,?,?,?,?,?,?,?)",
            (f["brand_id"], None, info.get("date") or None,
             f"NEW filing: {info.get('title') or 'annual report'}", None,
             f["venue"], url, now, "high"))
        seen.add(url)
        summ["new"] += 1
        summ["rows"].append({"brand": f["brand_id"], "venue": f["venue"], "status": "NEW",
                             "date": info.get("date"), "title": info.get("title"), "url": url})
    con.commit()
    return summ


def run(con, now: str | None = None) -> dict:
    """The filings pass over every US-present listed filer. Idempotent."""
    from . import capture
    capture.set_delay(1, 2)
    return collect(con, now=now)

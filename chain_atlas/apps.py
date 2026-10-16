"""
US app presence — a structure/intent datum (docs/pro_spec.md §1 principle 2, the structure layer).

A US mobile app is a public, checkable signal of real US commitment: it is a direct-to-consumer channel
(loyalty, ordering, delivery), and WHICH KIND of app a chain ships is itself intelligence — an own-brand
app (CHAGEE, Cotti, Dreame) signals deeper DTC investment than a third-party ordering platform app
(e.g. Chowbus powering several bubble-tea brands).

HOW IT IS COLLECTED (automate retrieval, reserve humans for judgment — the house rule). `probe()` queries
Apple's public iTunes Search API (US storefront) per brand and scores candidates by whether the brand
name appears in the app name and/or the developer. It NEVER writes the verified store: the App Store is
full of name collisions (an "Anta.kz" from Kazakhstan, a "Happy Lamb Stickers", a wellness app called
"Commune"), so candidates go to a human, exactly like a sighting. The verified truth lives in
`manual/apps.json`, curated by the owner. Google Play has no free API, so iOS is the automatable signal
and Android is a manual field.

PRO ONLY — a structure-layer datum; it rides the Pro export (structure), never the public map/data.
`python -m chain_atlas apps probe|report`.
"""
import json
import re
import time
from pathlib import Path

from . import config

_ROOT = Path(__file__).resolve().parents[1]
STORE = str(_ROOT / "manual" / "apps.json")

KINDS = ("own", "platform", "none")           # own-brand app / third-party ordering platform / no app
PLATFORMS = ("ios", "android")
ITUNES = "https://itunes.apple.com/search"


def _load(relpath, default=None):
    try:
        return json.loads((_ROOT / relpath).read_text(encoding="utf-8"))
    except Exception:                                            # noqa: BLE001
        return default if default is not None else {}


def load(path: str = STORE) -> dict:
    """The verified US-app store: {brands: {brand: record}}. Missing file = empty."""
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"brands": {}}


def verified(path: str = STORE) -> dict:
    """Brands with a confirmed US app (us_app true), keyed by chain_id."""
    return {b: r for b, r in load(path).get("brands", {}).items() if r.get("us_app")}


def record_of(brand: str, path: str = STORE) -> dict:
    """The verified US-app record for one brand, or None."""
    r = load(path).get("brands", {}).get(brand)
    return r if r and r.get("us_app") else None


def validate(path: str = STORE) -> list:
    """Structural checks on manual/apps.json. Returns a list of problems ([] = valid)."""
    d = load(path)
    problems = []
    for b, r in d.get("brands", {}).items():
        if "us_app" not in r:
            problems.append(f"{b}: missing us_app")
        if r.get("kind") not in KINDS:
            problems.append(f"{b}: kind must be one of {KINDS}")
        for p in r.get("platforms", []):
            if p not in PLATFORMS:
                problems.append(f"{b}: bad platform {p!r}")
        if r.get("us_app") and not (r.get("app_name") or r.get("ios_url")):
            problems.append(f"{b}: us_app true but no app_name/ios_url")
        if r.get("confidence") not in ("high", "medium", "low", None):
            problems.append(f"{b}: bad confidence {r.get('confidence')!r}")
    return problems


# --------------------------------------------------------------------------- probe (retrieval)

def _norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def score(term: str, track_name: str, seller: str):
    """
    name:      score
    purpose:   Pure match scorer for one App Store result against a brand search term.
    returns:   'high' (term in BOTH app name and developer), 'medium' (in one), or None (no match / term
               too short to trust).
    other:     The gate against name collisions is downstream human verification; this only RANKS.
    """
    tn = _norm(term)
    if len(tn) < 4:
        return None
    inn, ins = tn in _norm(track_name), tn in _norm(seller)
    return "high" if (inn and ins) else "medium" if (inn or ins) else None


def brand_terms() -> dict:
    """brand -> {display, terms[]}: Latin-script search names from the register, census directory and
    companies (the App Store search is Latin-only in the US storefront)."""
    reg = _load("register.json").get("chains", {})
    meta = _load("map/data/stores.json").get("meta", {}).get("chains", {})
    comp = _load("manual/companies.json").get("companies", {})
    from . import tier_export
    out = {}
    for b in tier_export._all_brands():
        terms, disp = [], None
        s = reg.get(b, {})
        if s.get("name"):
            disp = s["name"]
        terms += [s.get("name"), s.get("name_intl"), s.get("name_us")] + (s.get("aliases") or [])
        m = meta.get(b, {})
        disp = disp or m.get("name") or (comp.get(b) or {}).get("name") or b
        terms += [m.get("name"), m.get("name_us")] + (m.get("aliases") or []) + [(comp.get(b) or {}).get("name")]
        terms = [t for t in dict.fromkeys(terms)
                 if t and not any("一" <= c <= "鿿" for c in t)]
        out[b] = {"display": disp, "terms": terms[:3] or [disp]}
    return out


def probe(brands=None, pause: float = 2.2, session=None) -> dict:
    """
    name:      probe
    purpose:   Query the US App Store for each brand and return scored CANDIDATE apps for human review.
    arguments: brands — restrict to these chain_ids (else all); pause — seconds between calls (Apple
               rate-limits ~20/min); session — a requests.Session (injectable for tests).
    returns:   {brand: [ {app, seller, score, ios_url, ratings_n, updated} ]} — only brands with ≥1
               candidate. Does NOT write manual/apps.json.
    effects:   Network I/O. Retries each call up to 3× with backoff; a brand that never returns 200 is
               omitted (not recorded as 'no app').
    """
    import requests
    s = session or requests.Session()
    s.headers.setdefault("User-Agent", "chainsfromchina/1.0 (dgsilver@gmail.com)")
    terms = brand_terms()
    if brands:
        terms = {b: v for b, v in terms.items() if b in brands}
    hits = {}
    for b, info in terms.items():
        cands = {}
        for term in info["terms"][:2]:
            res = None
            for attempt in range(3):
                try:
                    r = s.get(ITUNES, params={"term": term, "country": "us",
                                              "entity": "software", "limit": 8}, timeout=15)
                    if r.status_code == 200:
                        res = r.json().get("results", [])
                        break
                except Exception:                               # noqa: BLE001
                    pass
                time.sleep(6 * (attempt + 1))
            if res is None:
                continue
            for a in res:
                sc = score(term, a.get("trackName", ""), a.get("artistName", ""))
                if sc:
                    cands[a.get("trackId")] = {
                        "app": a.get("trackName"), "seller": a.get("artistName"), "score": sc,
                        "ios_url": (a.get("trackViewUrl") or "").split("?")[0],
                        "ratings_n": a.get("userRatingCount"),
                        "updated": (a.get("currentVersionReleaseDate") or "")[:10]}
            if cands:
                break
            time.sleep(pause)
        if cands:
            hits[b] = sorted(cands.values(), key=lambda c: (c["score"] != "high", -(c["ratings_n"] or 0)))
        time.sleep(pause)
    return hits


def report(path: str = STORE):
    """Print the verified US-app roster, grouped by kind (own vs platform)."""
    v = verified(path)
    print(f"Verified US apps — {len(v)} brand(s)\n")
    for kind in ("own", "platform"):
        rows = {b: r for b, r in v.items() if r.get("kind") == kind}
        if not rows:
            continue
        print(f"  {kind.upper()} ({len(rows)})")
        for b, r in sorted(rows.items()):
            plat = "/".join(r.get("platforms", []))
            n = f"{r['ratings_n']} ratings" if r.get("ratings_n") else "—"
            print(f"    {b:16} {r.get('app_name','')[:32]:32} by {r.get('developer','')[:24]:24} [{plat}] {n}")

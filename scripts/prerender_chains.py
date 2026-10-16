#!/usr/bin/env python
"""Pre-render a static HTML page for every chain so search engines index (and rank) them.

Called by deploy.sh with the publish dir as argv[1], AFTER the cache-bust stamping, so the template
it reads (<dir>/chain.html) already carries the stamped CSS/JS versions and real ICONV/DATAV values.

The problem this solves: chain.html is ONE file; the chain is chosen by JavaScript from the ?c=<id>
query, so in the raw HTML Googlebot downloads first, all chains look byte-identical (same generic
<title>, description and empty body). Google has to render the JS to tell them apart and defers that,
so most chain pages never get indexed. Only a manual "Request indexing" (as done for Bingxue) forces
a render.

The fix: for each renderable chain we emit <dir>/chain/<id>/index.html — a copy of the stamped
chain.html template with the chain's real title, meta description, canonical/OG tags and a static,
crawlable body (name, one-line summary, US cities and states) baked into the HTML. The same JS then
hydrates the full interactive page on top (it reads window.CFC_CHAIN instead of ?c=). A <base href="/">
keeps every relative asset/data path resolving from the site root even though the file now lives two
levels deep. GitHub Pages serves /chain/<id>/ from that index.html automatically.

Renderable = meta.chains (daily-collected) ∪ meta.blocked (hand-tracked US entrants) — exactly what
chain.html itself keys off; register-only chains are skipped (chain.html shows "Unknown chain").
"""
import html
import json
import re
import sys
from pathlib import Path

DOMAIN = "https://chainsfromchina.com"
CJK = re.compile(r"[㐀-鿿豈-﫿]")
STATE_NAMES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California",
    "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware", "FL": "Florida", "GA": "Georgia",
    "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
    "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland", "MA": "Massachusetts",
    "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi", "MO": "Missouri", "MT": "Montana",
    "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico",
    "NY": "New York", "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
    "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VT": "Vermont",
    "VA": "Virginia", "WA": "Washington", "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming",
    "DC": "D.C.",
}


def a(s):
    """Escape a string for use inside a double-quoted HTML attribute."""
    return html.escape(str(s), quote=True)


def t(s):
    """Escape a string for use as HTML text."""
    return html.escape(str(s), quote=False)


def summary_for(m, comp, outlets, soon, has_robos):
    """Replicate chain.html's one-sentence data summary (blurb + counts + first store)."""
    sents = []
    blurb = (comp.get("blurb") or "").strip()
    if blurb:
        sents.append(re.split(r"(?<=\.)\s", blurb)[0])
    cs = ""
    if outlets:
        staffed = "staffed " if has_robos else ""
        cs = f"{outlets} {staffed}outlet{'s are' if outlets > 1 else ' is'} open in the US"
    if soon:
        cs += f" and {soon} more are announced" if cs else f"{soon} announced, none open yet"
    if cs:
        sents.append(cs + ".")
    fo = comp.get("first_outlet")
    first_city = fo.split("—")[0].split(",")[0].strip() if fo else ""
    if first_city and comp.get("us_since"):
        sents.append(f"Its first US store opened in {first_city} in {comp['us_since']}.")
    return " ".join(sents).strip()


def transform(template, cid, title, desc, canon, body):
    """Produce the per-chain HTML from the stamped chain.html template."""
    h = template
    # 1. <base href="/"> so relative asset/data paths resolve from the site root at /chain/<id>/.
    h = h.replace('<meta charset="utf-8">', '<meta charset="utf-8">\n<base href="/">', 1)
    # 2. Inject the chain id + canonical the hydration JS reads (instead of ?c=).
    inject = ('<script>window.CFC_CHAIN=' + json.dumps(cid) +
              ';window.CFC_CANON=' + json.dumps(canon) + ';</script>\n')
    h = re.sub(r'(<script src="site\.js)', inject + r'\1', h, count=1)
    # 3. Per-chain head: title, description, canonical, OG/Twitter. (A non-rendering crawler indexes
    #    these directly; the JS later sets the same values, so rendered and raw agree.)
    h = re.sub(r"<title>.*?</title>", "<title>" + t(title) + "</title>", h, count=1, flags=re.S)
    h = h.replace('<meta name="theme-color"',
                  '<link rel="canonical" href="' + a(canon) + '">\n<meta name="theme-color"', 1)
    h = re.sub(r'(<meta name="description" content=")[^"]*(">)', lambda mm: mm.group(1) + a(desc) + mm.group(2), h, count=1)
    h = re.sub(r'(<meta property="og:title" content=")[^"]*(">)', lambda mm: mm.group(1) + a(title) + mm.group(2), h, count=1)
    h = re.sub(r'(<meta property="og:description" content=")[^"]*(">)', lambda mm: mm.group(1) + a(desc) + mm.group(2), h, count=1)
    h = re.sub(r'(<meta property="og:url" content=")[^"]*(">)', lambda mm: mm.group(1) + a(canon) + mm.group(2), h, count=1)
    h = re.sub(r'(<meta name="twitter:title" content=")[^"]*(">)', lambda mm: mm.group(1) + a(title) + mm.group(2), h, count=1)
    h = re.sub(r'(<meta name="twitter:description" content=")[^"]*(">)', lambda mm: mm.group(1) + a(desc) + mm.group(2), h, count=1)
    # 4. Static, crawlable body (JS overwrites #profile on hydration, so users get the full page).
    h = h.replace('<div id="profile"><p class="loading">Loading…</p></div>',
                  '<div id="profile">' + body + '</div>', 1)
    return h


def main():
    out_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("map")
    template = (out_dir / "chain.html").read_text(encoding="utf-8")
    sj = json.loads((out_dir / "data" / "stores.json").read_text(encoding="utf-8"))
    gj = json.loads((out_dir / "data" / "stores.geojson").read_text(encoding="utf-8"))
    meta = sj.get("meta", {})
    collected = meta.get("chains", {}) or {}
    blocked = {b["chain_id"]: b for b in meta.get("blocked", []) if b.get("chain_id")}
    companies = ((meta.get("companies") or {}).get("companies")) or {}
    stores = sj.get("stores", []) or []

    # Group geojson features by chain once.
    feats_by = {}
    for f in gj.get("features", []):
        feats_by.setdefault(f["properties"].get("chain"), []).append(f)

    ids = sorted(set(collected) | set(blocked))
    n = 0
    for cid in ids:
        m = collected.get(cid) or blocked.get(cid) or {}
        comp = companies.get(cid, {})
        feats = feats_by.get(cid, [])
        props = [f["properties"] for f in feats]
        opn = sum(1 for p in props if p.get("status") == "open")
        hand = sum(1 for p in props if p.get("kind") == "sighting" and p.get("status") != "coming_soon")
        soon = sum(1 for p in props if p.get("status") == "coming_soon")
        outlets = opn + hand
        has_robos = any(s.get("chain") == cid and s.get("format") == "vending_robo"
                        and s.get("status") == "active" for s in stores)

        name = m.get("name") or cid
        zh = m.get("name_zh") or ""
        zh = zh if (zh and CJK.search(zh)) else ""

        title = re.sub(r"\s+", " ", f"{name} {zh} in the US — Chains From China").strip()
        summary = summary_for(m, comp, outlets, soon, has_robos)
        # A sensible fallback description if the chain has no blurb/counts yet.
        desc = summary or (f"{name}{(' ' + zh) if zh else ''}: a China-origin chain tracked in the "
                           f"United States — its US outlets, where it trades, and where it operates abroad.")

        # Static crawlable location lines (what makes "<chain> <city>" / "<chain> <state>" match).
        live = [p for p in props if p.get("status") != "coming_soon" and p.get("city") and p.get("state")]
        cities, seen = [], set()
        for p in sorted(live, key=lambda p: (p.get("state", ""), p.get("city", ""))):
            key = (p["city"], p["state"])
            if key not in seen:
                seen.add(key)
                cities.append(f"{p['city']}, {p['state']}")
        states = sorted({STATE_NAMES.get(p["state"], p["state"]) for p in live})

        canon = f"{DOMAIN}/chain/{cid}/"
        parts = [f'<h1>{t(name)}' + (f' <span class="zh" lang="zh-Hans">{t(zh)}</span>' if zh else "") + "</h1>"]
        if summary:
            parts.append(f'<p class="summary">{t(summary)}</p>')
        if cities:
            shown = cities[:60]
            more = f" and {len(cities) - 60} more" if len(cities) > 60 else ""
            parts.append(f'<p>Open in the US: {t("; ".join(shown))}{t(more)}.</p>')
        if states:
            parts.append(f'<p>US states with {t(name)} outlets: {t(", ".join(states))}.</p>')
        parts.append('<p><a href="/">Open the full US map →</a> · <a href="/intro.html">All chains →</a></p>')
        body = "".join(parts)

        page = transform(template, cid, title, desc, canon, body)
        dest = out_dir / "chain" / cid
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "index.html").write_text(page, encoding="utf-8")
        n += 1

    print(f"prerendered {n} chain pages (/chain/<id>/)")


if __name__ == "__main__":
    main()

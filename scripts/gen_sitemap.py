#!/usr/bin/env python
"""Generate sitemap.xml for chainsfromchina.com.

Called by deploy.sh with the publish dir as argv[1] (defaults to map/). Reads the exported
<dir>/data/stores.json to list every profiled chain's pre-rendered /chain/<id>/ page, alongside
the static indexable pages, so the sitemap always matches the live chain roster. lastmod is the
current NY date (the census cadence). Orphan dev/alt pages are intentionally excluded.
"""
import json
import sys
from datetime import date
from pathlib import Path
from xml.sax.saxutils import escape

DOMAIN = "https://chainsfromchina.com"

# static page -> (loc, changefreq, priority)
STATIC = [
    ("/", "daily", "1.0"),
    ("/intro.html", "weekly", "0.8"),
    ("/register.html", "weekly", "0.8"),
    ("/states.html", "weekly", "0.7"),
    ("/method.html", "monthly", "0.5"),
    ("/centers.html", "monthly", "0.5"),
    ("/contribute.html", "monthly", "0.4"),
]


def today_ny():
    try:
        from chain_atlas.config import today_ny as _t
        return _t()
    except Exception:
        return date.today().isoformat()


def chain_ids(out_dir: Path):
    # Only chains that chain.html can actually render: the daily-collected chains (meta.chains) and
    # the hand-tracked US entrants (meta.blocked stubs). chain.html keys off exactly these two and
    # shows "Unknown chain" for anything else — so register-only chains (no US presence, present only
    # in the Global register as fallback cards in meta.companies) must NOT be listed, or the sitemap
    # ships soft-404s. See chain.html: `m = meta.chains[id] || blocked[id]`.
    try:
        meta = json.loads((out_dir / "data" / "stores.json").read_text(encoding="utf-8"))["meta"]
        ids = set(meta.get("chains", {}))
        ids |= {b["chain_id"] for b in meta.get("blocked", []) if b.get("chain_id")}
        return sorted(ids)
    except Exception as e:  # noqa: BLE001
        print(f"  (no chain list: {e})", file=sys.stderr)
        return []


def main():
    out_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("map")
    lastmod = today_ny()
    rows = []
    for loc, cf, pr in STATIC:
        rows.append((DOMAIN + loc, cf, pr))
    for cid in chain_ids(out_dir):
        # Clean, pre-rendered per-chain URL (scripts/prerender_chains.py writes /chain/<id>/index.html).
        rows.append((f"{DOMAIN}/chain/{escape(cid)}/", "weekly", "0.6"))

    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for loc, cf, pr in rows:
        lines.append(
            f"  <url><loc>{loc}</loc><lastmod>{lastmod}</lastmod>"
            f"<changefreq>{cf}</changefreq><priority>{pr}</priority></url>")
    lines.append("</urlset>\n")
    (out_dir / "sitemap.xml").write_text("\n".join(lines), encoding="utf-8")
    print(f"sitemap.xml: {len(rows)} urls (lastmod {lastmod})")


if __name__ == "__main__":
    main()

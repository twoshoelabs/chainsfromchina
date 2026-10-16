"""
Per-brand dossier assembly — the atomic sellable PRO unit (docs/pro_spec.md §1.4, build order #2).

Pulls every layer the project already holds for ONE chain into a single provenance-carrying document:
  * presence  — the US census roster + count (+ logged closings)
  * scale     — home-market store counts (china_stores) and abroad presence (register)
  * economics — filing/FDD-derived anchors (financial_anchors) + the modeled US revenue estimate
  * structure — the stock listing (listings) + the latest FDD extract (fdd_extracts)
  * narrative — history / popular items / flagships (dossiers)

Read-only and honest: it assembles what has already been collected and verified, each datum shown WITH
its source, confidence and provenance tier (the wall). It never invents a number — a layer with no data
is reported as absent, not guessed. PRO only: it reads Pro-tier stores and must ride the Pro export, not
the public map/data. `python -m chain_atlas dossier <chain_id> [--md]`.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]


def _load(relpath: str, default=None):
    try:
        return json.loads((_ROOT / relpath).read_text(encoding="utf-8"))
    except Exception:                                            # noqa: BLE001
        return default if default is not None else {}


def _brand_meta(brand: str) -> dict:
    """name / name_zh from the register's chains{}, falling back to the census meta, then the id."""
    reg = _load("register.json").get("chains", {})
    if brand in reg:
        return {"name": reg[brand].get("name") or brand, "name_zh": reg[brand].get("name_zh")}
    for b in _load("map/data/stores.json").get("meta", {}).get("blocked", []):
        if b.get("chain_id") == brand:
            return {"name": b.get("name") or brand, "name_zh": b.get("name_zh")}
    return {"name": brand, "name_zh": None}


def _presence(brand: str) -> dict:
    """US roster + count from the published census, plus any logged closings for the brand."""
    rows = [s for s in _load("map/data/stores.json").get("stores", []) if s.get("chain") == brand]
    roster = [{"name": s.get("name"), "address": s.get("addr"), "city": s.get("city"),
               "state": s.get("state")} for s in rows]
    states = sorted({s.get("state") for s in rows if s.get("state")})
    closings = [{"name": c.get("name"), "address": c.get("address"), "closed_note": c.get("closed_note"),
                 "confidence": c.get("confidence"), "source": c.get("source")}
                for c in _load("manual/closings.json").get("closings", []) if c.get("chain") == brand]
    return {"us_outlets": len(rows), "states": states, "roster": roster, "closings": closings,
            "tier": "measured", "source": "daily US census (operator-observed / hand-verified)"}


def _scale(brand: str) -> dict:
    """Home-market counts (china_stores) and the abroad register markets."""
    home = _load("manual/china_stores.json").get("brands", {}).get(brand)
    abroad = [{"market": e.get("market"), "status": e.get("status"), "locations": e.get("locations"),
               "note": e.get("note"), "sources": e.get("sources")}
              for e in _load("register.json").get("entries", []) if e.get("chain") == brand]
    return {"home": home, "abroad": abroad}


def _economics(con, brand: str) -> dict:
    """Filing/FDD anchors + the latest modeled US-total revenue estimate (both DB-backed)."""
    anchors = []
    try:
        for r in con.execute(
                "SELECT period, metric, value, unit, source, source_url, confidence "
                "FROM financial_anchors WHERE brand_id=? ORDER BY metric", (brand,)):
            anchors.append({"period": r[0], "metric": r[1], "value": r[2], "unit": r[3],
                            "source": r[4], "source_url": r[5], "confidence": r[6],
                            "tier": "modeled" if "estimate" in (r[1] or "") else "filed"})
    except Exception:                                            # noqa: BLE001
        pass
    estimate = None
    try:
        row = con.execute(
            "SELECT period, low, mid, high, unit, method_version FROM revenue_estimates "
            "WHERE brand_id=? AND scope='us_total' ORDER BY generated_at DESC LIMIT 1", (brand,)).fetchone()
        if row:
            estimate = {"period": row[0], "low": row[1], "mid": row[2], "high": row[3],
                        "unit": row[4], "method": row[5], "tier": "modeled"}
    except Exception:                                            # noqa: BLE001
        pass
    return {"anchors": anchors, "us_revenue_estimate": estimate}


def _structure(con, brand: str) -> dict:
    """Stock listing (listings) + the operating model (register) + the latest FDD extract."""
    listing = _load("manual/listings.json").get("brands", {}).get(brand)
    if listing:
        listing = {"tickers": listing.get("tickers"), "exchange": listing.get("exchange"),
                   "status": listing.get("status"),
                   "parent": listing.get("group"),          # the parent group NAME (never the relationship slug)
                   "parent_zh": listing.get("group_zh"), "sisters": listing.get("sisters"),
                   "china_a_share": bool(listing.get("mainland")), "ir": listing.get("ir")}
    operating_model = _load("register.json").get("chains", {}).get(brand, {}).get("operating_model")
    fdd = None
    try:
        row = con.execute(
            "SELECT year, items_json, source_url FROM fdd_extracts WHERE brand_id=? "
            "ORDER BY year DESC LIMIT 1", (brand,)).fetchone()
        if row:
            items = json.loads(row[1] or "{}")
            i7, i8, i20 = items.get("item7", {}), items.get("item8", {}), items.get("item20", {})
            flags = [k for k in ("required_suppliers", "franchisor_is_supplier", "rebates", "proprietary")
                     if i8.get(k)]
            fdd = {"year": row[0], "source_url": row[2],
                   "initial_investment": [i7.get("low"), i7.get("high")],
                   "supply_flags": flags or None,
                   "projected_openings": (i20.get("projected") or {}).get("projected_new_franchised"),
                   "litigation": (items.get("item3") or {}).get("has_litigation"),
                   "bankruptcy": (items.get("item4") or {}).get("has_bankruptcy")}
    except Exception:                                            # noqa: BLE001
        pass
    return {"listing": listing, "operating_model": operating_model, "fdd": fdd}


def _narrative(brand: str) -> dict:
    """History / popular items / flagships / notes from the qualitative dossiers store."""
    return _load("manual/dossiers.json").get("brands", {}).get(brand)


def assemble(con, brand: str) -> dict:
    """
    name:      assemble
    purpose:   Build the full provenance-carrying dossier for one chain across all five layers.
    arguments: con — an open DB connection (for economics/structure); brand — a chain_id.
    returns:   a dossier dict {brand, name, name_zh, generated, presence, scale, economics,
               structure, narrative}.
    effects:   None (read-only).
    other:     A layer with no data comes back empty/None — never fabricated. Not brand-exists-checked:
               an unknown brand yields an empty-but-valid dossier (all layers absent).
    """
    meta = _brand_meta(brand)
    return {"brand": brand, "name": meta["name"], "name_zh": meta["name_zh"],
            "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "presence": _presence(brand), "scale": _scale(brand),
            "economics": _economics(con, brand), "structure": _structure(con, brand),
            "narrative": _narrative(brand)}


def render_markdown(d: dict) -> str:
    """A readable Markdown rendering of an assembled dossier (the sellable artifact's text form)."""
    def conf(c):
        return f" _({c})_" if c else ""
    L = []
    title = d["name"] + (f" {d['name_zh']}" if d.get("name_zh") else "")
    L.append(f"# {title} — PRO dossier")
    L.append(f"_chain_id `{d['brand']}` · assembled {d['generated'][:10]} · every datum carries its source_\n")

    p = d["presence"]
    L.append(f"## Presence (US) — {p['us_outlets']} outlets across {len(p['states'])} states")
    L.append(f"_{p['source']}_" + (f" · states: {', '.join(p['states'])}" if p["states"] else ""))
    for o in p["roster"][:40]:
        L.append(f"- {o['name']} — {o['address']}")
    if len(p["roster"]) > 40:
        L.append(f"- …and {len(p['roster']) - 40} more")
    if p["closings"]:
        L.append("\n**Logged closings:**")
        for c in p["closings"]:
            L.append(f"- {c['name']} — {c['address']}{conf(c['confidence'])}")

    s = d["scale"]
    L.append("\n## Scale & trajectory (home market)")
    if s["home"]:
        h = s["home"]
        parts = [f"**{h.get('total'):,} total**" if h.get("total") else ""]
        if h.get("china"):
            parts.append(f"{h['china']:,} China")
        if h.get("overseas"):
            parts.append(f"{h['overseas']:,} overseas")
        L.append(" · ".join([x for x in parts if x]) + f" (as of {h.get('as_of')}){conf(h.get('confidence'))}")
        L.append(f"_{h.get('source')}_")
        if h.get("note"):
            L.append(f"> {h['note']}")
    else:
        L.append("_No home-market store count on file._")
    if s["abroad"]:
        L.append("\n**Abroad (register):** " + ", ".join(
            f"{e['market']} ({e['status']}{', ' + str(e['locations']) if e.get('locations') else ''})"
            for e in s["abroad"]))

    e = d["economics"]
    L.append("\n## Economics")
    if e["us_revenue_estimate"]:
        est = e["us_revenue_estimate"]
        L.append(f"**Modeled US revenue:** {est['low']:,.0f}–{est['high']:,.0f} {est.get('unit','USD')} "
                 f"(mid {est['mid']:,.0f}) _(modeled — {est.get('method')})_")
    if e["anchors"]:
        L.append("\n**Anchors (filing/FDD-derived):**")
        for a in e["anchors"]:
            L.append(f"- {a['metric']} = {a['value']:,} {a.get('unit') or ''} "
                     f"({a.get('period')}){conf(a['confidence'])} — _{a.get('source')}_")
    if not e["us_revenue_estimate"] and not e["anchors"]:
        L.append("_No disclosed anchors or modeled estimate on file._")

    st = d["structure"]
    L.append("\n## Structure & intent")
    if st.get("operating_model"):
        L.append(f"- Operating model: **{st['operating_model']}**")
    if st["listing"] and st["listing"].get("tickers"):
        li = st["listing"]
        L.append(f"- Listed: {', '.join(li['tickers'])} ({li.get('exchange')})"
                 + (f" · China A-share" if li.get("china_a_share") else "")
                 + (f" · parent {li['parent_zh'] or li['parent']}" if li.get("parent") else "")
                 + (f" · sisters: {', '.join(li['sisters'])}" if li.get("sisters") else ""))
    elif st["listing"] and st["listing"].get("parent"):
        li = st["listing"]
        L.append(f"- Parent: {li['parent_zh'] or li['parent']}"
                 + (f" · sisters: {', '.join(li['sisters'])}" if li.get("sisters") else ""))
    if st["fdd"]:
        f = st["fdd"]
        inv = f["initial_investment"]
        if inv and inv[0] is not None:
            L.append(f"- FDD ({f['year']}): initial investment ${inv[0]:,}–${inv[1]:,}")
        if f["supply_flags"]:
            L.append(f"- FDD supply chain: {', '.join(f['supply_flags'])}")
        if f["projected_openings"] is not None:
            L.append(f"- FDD projected new franchised outlets next FY: {f['projected_openings']}")
        for lbl, v in (("Litigation disclosed", f["litigation"]), ("Prior bankruptcy", f["bankruptcy"])):
            if v:
                L.append(f"- {lbl}: yes")
    if not st.get("operating_model") and not st["listing"] and not st["fdd"]:
        L.append("_No listing, operating-model or FDD data on file._")

    n = d["narrative"]
    L.append("\n## Narrative")
    if n:
        if n.get("history"):
            L.append(f"**History.** {n['history'].get('text')}{conf(n['history'].get('confidence'))}")
            L.append(f"_{n['history'].get('source')}_")
        for it in (n.get("popular_items") or []):
            L.append(f"- Popular: **{it.get('name')}** — {it.get('note','')}{conf(it.get('confidence'))}")
        for it in (n.get("flagship_outlets") or []):
            L.append(f"- Flagship: {it.get('name')} ({it.get('city','')})")
    else:
        L.append("_No qualitative dossier on file._")
    return "\n".join(L)


def run(con, brand: str, as_markdown: bool = False) -> str:
    """Assemble `brand` and return it as Markdown (as_markdown) or pretty JSON."""
    d = assemble(con, brand)
    return render_markdown(d) if as_markdown else json.dumps(d, ensure_ascii=False, indent=1)

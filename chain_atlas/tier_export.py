"""
Tier-gated export — the deliverable (docs/pro_spec.md §3.4, build order #5).

Emits exactly the slice of data a tier is allowed to see. Four tiers, each a superset of the last:

  * public       — the free census: US roster/count + the public worldwide TOTAL (the "~"-marked one).
  * observer     — + logged closings, the full abroad register, the chain directory.
  * pro          — + home-market SCALE (china/overseas splits + sources), ECONOMICS (anchors + modeled
                   revenue/capacity), STRUCTURE (listing + FDD extracts), and the NARRATIVE.
  * intelligence — + the assembled per-brand dossier (the Markdown report).

This is a PAYWALL GATE, so it is built as an explicit ALLOWLIST, never a strip-denylist: a lower tier's
slice is assembled by naming the fields it may contain, so economics / china-overseas splits / anchors /
sources CANNOT leak into public or observer even if the upstream shape changes. Pro/Intelligence bundles
are access-controlled — write them to the git-ignored `pro/` tree, never the public map/data.
`python -m chain_atlas export-tier <public|observer|pro|intelligence> [--brand X] [--out DIR]`.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

from . import dossier

TIERS = ("public", "observer", "pro", "intelligence")
_RANK = {t: i for i, t in enumerate(TIERS)}
_ROOT = Path(__file__).resolve().parents[1]


def _all_brands() -> list:
    """Every chain_id we hold anything on — the union of the census, the register and china_stores."""
    brands = set()
    sj = dossier._load("map/data/stores.json")
    brands |= {s.get("chain") for s in sj.get("stores", []) if s.get("chain")}
    brands |= {b.get("chain_id") for b in sj.get("meta", {}).get("blocked", []) if b.get("chain_id")}
    brands |= set(dossier._load("register.json").get("chains", {}))
    brands |= set(dossier._load("manual/china_stores.json").get("brands", {}))
    return sorted(b for b in brands if b)


def _brand_slice(con, brand: str, tier: str) -> dict:
    """
    name:      _brand_slice
    purpose:   The per-brand object a tier may receive — assembled by EXPLICIT allowlist.
    arguments: con; brand; tier.
    returns:   a dict containing only the fields permitted at `tier`.
    other:     The gate. Public/observer are built field-by-field from the full dossier and never carry
               economics, scale splits, sources, structure or narrative — the fields are simply not copied
               in. Higher tiers add whole layers.
    """
    d = dossier.assemble(con, brand)
    rank = _RANK[tier]

    # --- public: presence + the public worldwide total only ---
    out = {"brand": brand, "name": d["name"], "name_zh": d["name_zh"]}
    out["presence"] = {"us_outlets": d["presence"]["us_outlets"],
                       "states": d["presence"]["states"],
                       "roster": d["presence"]["roster"]}
    home = d["scale"]["home"] or {}
    out["worldwide_total"] = ({"n": home.get("total"), "as_of": home.get("as_of"),
                               "unverified": home.get("confidence") != "high"}
                              if home.get("total") is not None else None)
    if rank == _RANK["public"]:
        return out

    # --- observer: + closings + full abroad register ---
    out["presence"]["closings"] = d["presence"]["closings"]
    out["abroad"] = d["scale"]["abroad"]
    if rank == _RANK["observer"]:
        return out

    # --- pro: + scale (splits/sources), economics, structure, narrative ---
    out["scale"] = d["scale"]
    out["economics"] = d["economics"]
    out["structure"] = d["structure"]
    out["narrative"] = d["narrative"]
    if rank == _RANK["pro"]:
        return out

    # --- intelligence: + the assembled dossier report ---
    out["dossier_markdown"] = dossier.render_markdown(d)
    return out


def export(con, tier: str, brands=None) -> dict:
    """
    name:      export
    purpose:   Build the full tier bundle: every brand's allowed slice for `tier`.
    arguments: con; tier — one of TIERS; brands — an explicit list, else all tracked brands.
    returns:   {tier, generated, brand_count, brands: {brand: slice}}.
    effects:   None. (Write with `write()`.)
    other:     Raises ValueError on an unknown tier.
    """
    if tier not in TIERS:
        raise ValueError(f"tier must be one of {TIERS}")
    brands = brands or _all_brands()
    return {"tier": tier, "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "brand_count": len(brands),
            "brands": {b: _brand_slice(con, b, tier) for b in brands}}


def write(bundle: dict, out_dir: str) -> list:
    """
    name:      write
    purpose:   Write a tier bundle to disk: bundle.json, plus per-brand .md for the intelligence tier.
    arguments: bundle — from export(); out_dir — the destination (pro/intelligence belong under pro/).
    returns:   list of written file paths.
    effects:   Creates out_dir and writes files.
    """
    d = Path(out_dir)
    d.mkdir(parents=True, exist_ok=True)
    written = []
    bp = d / "bundle.json"
    bp.write_text(json.dumps(bundle, ensure_ascii=False, indent=1), encoding="utf-8")
    written.append(str(bp))
    if bundle["tier"] == "intelligence":
        dd = d / "dossiers"
        dd.mkdir(exist_ok=True)
        for brand, sl in bundle["brands"].items():
            md = sl.get("dossier_markdown")
            if md:
                p = dd / f"{brand}.md"
                p.write_text(md, encoding="utf-8")
                written.append(str(p))
    return written


# =========================================================================== full dataset
# The PRIMARY product (docs/pro_spec.md build order #4): one cohesive, documented, tier-gated DATASET —
# flat analyzable tables, the longitudinal event stream, aggregates, a manifest and a README, emitted as
# JSON *and* CSV. Tables are DERIVED FROM the per-brand slices export() already gated, so the paywall
# allowlist stays single-sourced: a table can only carry a field the slice was allowed to contain. The
# one store not in a slice — the event log — is gated with an explicit pro-rank guard.

# table -> (min tier, ordered CSV columns). A table is emitted only when the export tier outranks it.
_TABLES = {
    "brands":    ("public", ["brand", "name", "name_zh", "us_outlets", "states",
                             "worldwide_total", "worldwide_as_of", "worldwide_unverified"]),
    "outlets":   ("public", ["brand", "name", "address", "city", "state", "source"]),
    "closings":  ("observer", ["brand", "name", "address", "closed_note", "confidence", "source"]),
    "abroad":    ("observer", ["brand", "market", "status", "locations", "note", "source"]),
    "scale":     ("pro", ["brand", "total", "china", "overseas", "as_of", "confidence", "source"]),
    "economics": ("pro", ["brand", "period", "metric", "value", "unit", "confidence", "tier",
                          "source", "source_url"]),
    "structure": ("pro", ["brand", "tickers", "exchange", "status", "parent", "china_a_share",
                          "operating_model", "fdd_year", "fdd_invest_low", "fdd_invest_high",
                          "litigation", "bankruptcy"]),
    "narrative": ("pro", ["brand", "history", "popular_items", "notes", "source", "confidence"]),
    "apps":      ("pro", ["brand", "us_app", "kind", "platforms", "app_name", "developer", "ios_url",
                         "android_url", "ratings_n", "confidence", "as_of"]),
    "events":    ("pro", ["id", "brand", "kind", "dimension", "key", "before", "after", "as_of",
                         "detected_at", "provenance_tier", "confidence", "source", "headline"]),
}


def _j(v):
    """Flatten a list/dict cell to a stable string so JSON and CSV rows match; pass scalars through."""
    if isinstance(v, list):
        return "; ".join(str(x) for x in v)
    if isinstance(v, dict):
        return json.dumps(v, ensure_ascii=False)
    return v


_SECTOR_CACHE = None


def _sector_map() -> dict:
    """brand -> sector, sourced authoritatively from the census store rows (each carries `sector`), then
    sightings, then companies.json. Built once per process."""
    global _SECTOR_CACHE
    if _SECTOR_CACHE is None:
        m = {}
        # Primary: the published geojson carries `sector` per outlet — covers every brand with US outlets.
        for f in dossier._load("map/data/stores.geojson").get("features", []):
            p = f.get("properties", {})
            if p.get("chain") and p.get("sector"):
                m.setdefault(p["chain"], p["sector"])
        # Fallbacks for brands with no mapped US outlet: the census chain directory's `format`, sightings.
        for b, c in dossier._load("map/data/stores.json").get("meta", {}).get("chains", {}).items():
            if (c or {}).get("format"):
                m.setdefault(b, c["format"])
        for g in dossier._load("manual/sightings.json").get("sightings", []):
            if g.get("chain") and g.get("sector"):
                m.setdefault(g["chain"], g["sector"])
        _SECTOR_CACHE = m
    return _SECTOR_CACHE


def _brand_sector(brand: str) -> str:
    return _sector_map().get(brand)


def dataset(con, tier: str, brands=None) -> dict:
    """
    name:      dataset
    purpose:   Build the full tier-gated DATASET: flat tables + aggregates + a manifest, from the gated
               per-brand slices (plus the event-log time-series at pro+).
    arguments: con; tier — one of TIERS; brands — explicit list, else all tracked brands.
    returns:   {tier, generated, manifest, aggregates, tables:{name:[rows]}}.
    effects:   None. (Write with write_dataset().) Raises ValueError on an unknown tier.
    other:     THE GATE. Every table is derived from slices export() already allowlisted, and each table
               carries a min tier; events are additionally guarded. Economics / scale / sources / events
               therefore cannot appear below their min tier even if an upstream shape changes.
    """
    if tier not in TIERS:
        raise ValueError(f"tier must be one of {TIERS}")
    rank = _RANK[tier]
    bundle = export(con, tier, brands)
    slices = bundle["brands"]

    def allowed(name):
        return rank >= _RANK[_TABLES[name][0]]

    tables = {name: [] for name in _TABLES if allowed(name)}

    for b, sl in slices.items():
        p = sl.get("presence", {})
        wt = sl.get("worldwide_total") or {}
        tables["brands"].append({"brand": b, "name": sl.get("name"), "name_zh": sl.get("name_zh"),
                                 "us_outlets": p.get("us_outlets"), "states": _j(p.get("states")),
                                 "worldwide_total": wt.get("n"), "worldwide_as_of": wt.get("as_of"),
                                 "worldwide_unverified": wt.get("unverified")})
        for o in p.get("roster", []):
            tables["outlets"].append({"brand": b, "name": o.get("name"), "address": o.get("address"),
                                      "city": o.get("city"), "state": o.get("state"),
                                      "source": o.get("source")})
        if "closings" in tables:
            for c in p.get("closings", []) or []:
                tables["closings"].append({"brand": b, "name": c.get("name"), "address": c.get("address"),
                                           "closed_note": c.get("closed_note"),
                                           "confidence": c.get("confidence"), "source": c.get("source")})
        if "abroad" in tables:
            for e in sl.get("abroad", []) or []:
                tables["abroad"].append({"brand": b, "market": e.get("market"), "status": e.get("status"),
                                         "locations": e.get("locations"), "note": e.get("note"),
                                         "source": _j(e.get("sources"))})
        if "scale" in tables:
            h = (sl.get("scale") or {}).get("home") or {}
            if h:
                tables["scale"].append({"brand": b, "total": h.get("total"), "china": h.get("china"),
                                        "overseas": h.get("overseas"), "as_of": h.get("as_of"),
                                        "confidence": h.get("confidence"), "source": h.get("source")})
        if "economics" in tables:
            for a in (sl.get("economics") or {}).get("anchors", []) or []:
                tables["economics"].append({"brand": b, "period": a.get("period"), "metric": a.get("metric"),
                                            "value": a.get("value"), "unit": a.get("unit"),
                                            "confidence": a.get("confidence"), "tier": a.get("tier"),
                                            "source": a.get("source"), "source_url": a.get("source_url")})
        if "structure" in tables:
            st = sl.get("structure") or {}
            li, fd = st.get("listing") or {}, st.get("fdd") or {}
            inv = fd.get("initial_investment") or [None, None]
            if li or st.get("operating_model") or fd:
                tables["structure"].append({"brand": b, "tickers": _j(li.get("tickers")),
                                            "exchange": li.get("exchange"), "status": li.get("status"),
                                            "parent": li.get("parent"),
                                            "china_a_share": li.get("china_a_share"),
                                            "operating_model": st.get("operating_model"),
                                            "fdd_year": fd.get("year"), "fdd_invest_low": inv[0],
                                            "fdd_invest_high": inv[1], "litigation": fd.get("litigation"),
                                            "bankruptcy": fd.get("bankruptcy")})
        if "apps" in tables:
            ua = (sl.get("structure") or {}).get("us_app")
            if ua:
                tables["apps"].append({"brand": b, "us_app": ua.get("us_app"), "kind": ua.get("kind"),
                                       "platforms": _j(ua.get("platforms")), "app_name": ua.get("app_name"),
                                       "developer": ua.get("developer"), "ios_url": ua.get("ios_url"),
                                       "android_url": ua.get("android_url"), "ratings_n": ua.get("ratings_n"),
                                       "confidence": ua.get("confidence"), "as_of": ua.get("as_of")})
        if "narrative" in tables:
            n = sl.get("narrative") or {}
            if n:
                hist = n.get("history") or {}
                tables["narrative"].append({"brand": b, "history": hist.get("text"),
                                            "popular_items": _j([i.get("name")
                                                                 for i in (n.get("popular_items") or [])]),
                                            "notes": _j([x.get("text") for x in (n.get("notes") or [])]),
                                            "source": hist.get("source"), "confidence": hist.get("confidence")})

    if "events" in tables:
        from . import alerts
        brand_set = set(slices)
        for e in alerts.load():
            if e.get("brand") in brand_set:
                tables["events"].append({k: e.get(k) for k in _TABLES["events"][1]})

    return {"tier": tier, "generated": bundle["generated"], "brand_count": bundle["brand_count"],
            "manifest": _manifest(tier, tables), "aggregates": _aggregates(tier, tables), "tables": tables}


def _aggregates(tier: str, tables: dict) -> dict:
    """At-a-glance rollups, each gated by the table it needs (so counts can't leak below their tier)."""
    from datetime import date, timedelta
    agg = {"brands_tracked": len(tables.get("brands", [])),
           "us_outlets_total": len(tables.get("outlets", []))}
    by_state = {}
    for o in tables.get("outlets", []):
        if o.get("state"):
            by_state[o["state"]] = by_state.get(o["state"], 0) + 1
    agg["states_covered"] = len(by_state)
    agg["outlets_by_state"] = dict(sorted(by_state.items(), key=lambda kv: -kv[1]))
    agg["outlets_by_sector"] = {}
    for b in tables.get("brands", []):
        sec = _brand_sector(b["brand"]) or "unknown"
        agg["outlets_by_sector"][sec] = agg["outlets_by_sector"].get(sec, 0) + (b.get("us_outlets") or 0)
    if "abroad" in tables:
        agg["abroad_markets"] = len({r["market"] for r in tables["abroad"] if r.get("market")})
    if "apps" in tables:
        agg["us_apps"] = {"total": len(tables["apps"]),
                          "own": sum(1 for r in tables["apps"] if r.get("kind") == "own"),
                          "platform": sum(1 for r in tables["apps"] if r.get("kind") == "platform")}
    if "events" in tables:                       # time-series rollups (pro+ only)
        cutoff = (date.today() - timedelta(days=90)).isoformat()
        recent = [e for e in tables["events"] if (e.get("detected_at") or "")[:10] >= cutoff]
        agg["new_us_entrants_90d"] = sum(1 for e in recent if e.get("kind") == "entered_us")
        agg["outlets_opened_90d"] = sum(1 for e in recent if e.get("kind") == "outlet_opened")
        agg["outlets_closed_90d"] = sum(1 for e in recent if e.get("kind") == "outlet_closed")
        agg["events_total"] = len(tables["events"])
    return agg


_TIER_NOTE = {
    "public": "Free census: US roster/count + the public worldwide total.",
    "observer": "+ logged closings, the full abroad register.",
    "pro": "+ home-market scale, economics, structure, narrative, and the event-log time-series.",
    "intelligence": "+ the assembled per-brand dossier reports.",
}


def _manifest(tier: str, tables: dict) -> dict:
    """The dataset's self-description: tier, table inventory with row counts + min tier, provenance and
    cadence legends, citation and a proprietary-use notice. A buyer reads this to know what they hold."""
    return {
        "product": "Chains From China — tiered dataset",
        "tier": tier, "tier_note": _TIER_NOTE.get(tier),
        "tables": [{"name": n, "rows": len(tables[n]), "min_tier": _TABLES[n][0],
                    "columns": _TABLES[n][1]} for n in _TABLES if n in tables],
        "provenance_tiers": {
            "measured": "our own operator-observed census / audited filing",
            "filed": "primary HKEX / A-share / FDD figures",
            "modeled": "our revenue/capacity estimates",
            "reported": "press / company statement"},
        "cadence": {"census/outlets": "daily", "scale/economics": "per-filing / quarterly",
                    "structure": "annual", "events": "continuous"},
        "citation": "Chains From China (chainsfromchina.com), Twoshoe Labs LLC.",
        "notice": ("Proprietary. The pro/intelligence tiers are licensed data, not for redistribution. "
                   "Every datum carries its source and provenance tier; cite accordingly."),
    }


def write_dataset(ds: dict, out_dir: str) -> list:
    """
    name:      write_dataset
    purpose:   Write the full dataset: bundle.json, manifest.json, one CSV per table, a README, and (for
               the intelligence tier) the per-brand dossier Markdown.
    arguments: ds — from dataset(); out_dir — destination (pro/intelligence belong under the git-ignored
               pro/ tree).
    returns:   the list of written file paths.
    effects:   Creates out_dir (+ a data/ subdir for CSVs) and writes files.
    """
    import csv
    d = Path(out_dir)
    (d / "data").mkdir(parents=True, exist_ok=True)
    written = []

    bp = d / "bundle.json"
    bp.write_text(json.dumps(ds, ensure_ascii=False, indent=1), encoding="utf-8")
    written.append(str(bp))
    mp = d / "manifest.json"
    mp.write_text(json.dumps(ds["manifest"], ensure_ascii=False, indent=1), encoding="utf-8")
    written.append(str(mp))

    for name, rows in ds["tables"].items():
        cols = _TABLES[name][1]
        p = d / "data" / f"{name}.csv"
        with open(p, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
            w.writeheader()
            for r in rows:
                w.writerow({c: ("" if r.get(c) is None else r.get(c)) for c in cols})
        written.append(str(p))

    rp = d / "README.md"
    rp.write_text(_readme(ds), encoding="utf-8")
    written.append(str(rp))

    if ds["tier"] == "intelligence":
        from . import db  # dossier markdown lives on the per-brand slice; re-use the slice bundle
        dd = d / "dossiers"
        dd.mkdir(exist_ok=True)
        for sl in export(db.connect(), "intelligence", list(
                {r["brand"] for r in ds["tables"].get("brands", [])}))["brands"].values():
            md = sl.get("dossier_markdown")
            if md:
                p = dd / f"{sl['brand']}.md"
                p.write_text(md, encoding="utf-8")
                written.append(str(p))
    return written


def _readme(ds: dict) -> str:
    """A human-readable README for the dataset buyer: what it is, the tables, provenance, cadence, cite."""
    m = ds["manifest"]
    a = ds["aggregates"]
    L = [f"# {m['product']} — {ds['tier']} tier",
         f"_generated {ds['generated']} · {ds['brand_count']} brands_\n",
         m["tier_note"], "",
         f"**At a glance:** {a.get('brands_tracked', 0)} brands · {a.get('us_outlets_total', 0)} US "
         f"outlets · {a.get('states_covered', 0)} states"
         + (f" · {a['new_us_entrants_90d']} new US entrants (90d)" if "new_us_entrants_90d" in a else "")
         + ".", "",
         "## Tables (`data/*.csv`)"]
    for t in m["tables"]:
        L.append(f"- **{t['name']}** — {t['rows']} rows · columns: {', '.join(t['columns'])}")
    L.append("\n## Provenance — every datum carries its tier")
    for k, v in m["provenance_tiers"].items():
        L.append(f"- **{k}** — {v}")
    L.append("\n## Refresh cadence")
    for k, v in m["cadence"].items():
        L.append(f"- {k}: {v}")
    L.append(f"\n## Citation\n{m['citation']}\n\n_{m['notice']}_")
    return "\n".join(L)

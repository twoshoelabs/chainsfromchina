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

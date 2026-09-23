"""
The coverage scorecard: for every chain, what this project holds against what the trade press
says exists. It answers the only question that matters for launch — "how much of each chain do we
actually have?" — with a number instead of a feeling.

TWO KINDS OF ROW, kept apart on purpose:

  collected   The chain publishes a locator we read daily, so what we hold IS the count. Coverage
              is complete by construction; the trade-press figure is shown only as a sanity check,
              never as the truth.
  sighted     The chain publishes no readable roster, so we hold sightings (first-party, filed, or
              permit-sourced) and compare them to a hand-typed, dated estimate from manual/
              coverage.json. The ratio is deliberately rough: an estimate is a rumour with a date,
              and the scorecard says so.

Nothing here is added to any collected total. The estimate is a yardstick, not a measurement, and
a chain with no credible published total shows its holdings against "no benchmark" rather than a
made-up denominator.
"""
import json
from pathlib import Path

from . import db
from .adapters import REGISTRY

COVERAGE_PATH = Path(__file__).resolve().parents[1] / "manual" / "coverage.json"


def _estimates():
    try:
        return json.loads(COVERAGE_PATH.read_text(encoding="utf-8"))
    except Exception:                                           # noqa: BLE001
        return {"as_of": None, "estimates": {}}


def scorecard() -> dict:
    """
    name:      scorecard
    purpose:   Per-chain coverage: held vs estimated, with a status a reader can scan.
    arguments: none
    returns:   {"as_of", "rows": [ {chain, name, kind, held, held_confirmed, estimate,
               estimate_text, confidence, source, as_of, ratio, status} ], "totals": {...}}
    effects:   Reads the archive (stores + sightings) and manual/coverage.json.
    other:     `held` for a collected chain is its live census; for a sighted chain it is the
               number of confirmed known locations (uncertain ones are reported but not counted
               toward the ratio, the same rule the map draws by).
    """
    est = _estimates()
    E = est.get("estimates", {})
    con = db.connect()

    # Census counts for collected chains.
    census = {r["chain_id"]: r["n"] for r in con.execute(
        "SELECT chain_id, COUNT(*) n FROM stores WHERE country='US' AND status='active'"
        " GROUP BY chain_id")}

    # Sighting counts (confirmed vs total) for the rest.
    sight_conf, sight_all = {}, {}
    try:
        from .sightings import load
        for g in load().get("sightings", []):
            for loc in g.get("locations", []):
                sight_all[g["chain"]] = sight_all.get(g["chain"], 0) + 1
                if loc.get("confidence") != "uncertain":
                    sight_conf[g["chain"]] = sight_conf.get(g["chain"], 0) + 1
    except Exception:                                           # noqa: BLE001
        pass

    rows = []
    for a in REGISTRY:
        if a.country != "US" or a.chain_id == "fixture":
            continue
        e = E.get(a.chain_id, {})
        if a.ENABLED:
            held = census.get(a.chain_id, 0)
            rows.append({
                "chain": a.chain_id, "name": a.name, "kind": "collected",
                "held": held, "held_confirmed": held,
                "estimate": e.get("us"), "estimate_text": e.get("us_text"),
                "confidence": e.get("confidence"), "source": e.get("source"), "as_of": e.get("as_of"),
                "ratio": None, "status": "complete"})
        else:
            held = sight_all.get(a.chain_id, 0)
            conf = sight_conf.get(a.chain_id, 0)
            estimate = e.get("us")
            ratio = round(conf / estimate, 2) if estimate else None
            status = ("no benchmark" if not estimate
                      else "strong" if ratio >= 0.8
                      else "partial" if ratio >= 0.35
                      else "sparse")
            rows.append({
                "chain": a.chain_id, "name": a.name, "kind": "sighted",
                "held": held, "held_confirmed": conf,
                "estimate": estimate, "estimate_text": e.get("us_text"),
                "confidence": e.get("confidence"), "source": e.get("source"), "as_of": e.get("as_of"),
                "note": e.get("note"), "ratio": ratio, "status": status})

    rows.sort(key=lambda r: (r["kind"] != "collected", -(r["held"] or 0)))
    collected = [r for r in rows if r["kind"] == "collected"]
    sighted = [r for r in rows if r["kind"] == "sighted"]
    return {
        "as_of": est.get("as_of"),
        "rows": rows,
        "totals": {
            "chains": len(rows),
            "collected": len(collected),
            "collected_stores": sum(r["held"] for r in collected),
            "sighted": len(sighted),
            "sighted_confirmed": sum(r["held_confirmed"] for r in sighted),
            "sighted_estimated": sum(r["estimate"] for r in sighted if r["estimate"]),
        },
    }

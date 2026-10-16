"""
The verification queue — the gate that makes a datum sellable (docs/pro_spec.md §3, build order #3).

A record enters the system at its CLAIMED tier/confidence; it reaches full-confidence PRO output only
once a human (or a cross-source check) marks it verified. This module gathers everything across the
stores that is still awaiting that call into ONE prioritized worklist, each item carrying its source so
the reviewer can act without hunting:

  * needs_human_read   — FDD extracts whose quantitative parse was ambiguous (fdd_extracts)
  * submitted          — new intake records not yet acted on (submissions.jsonl)
  * uncertain          — sightings held OUT of the count/map pending confirmation
  * unverified_anchor  — financial_anchors below 'high' (secondary/press, not a primary filing)
  * unverified_count   — china_stores totals below 'high' (the public "~"-marked figures)
  * register_pending   — register markets 'announced' (coming-soon), awaiting an open-confirmation

Verdicts append to `manual/verifications.jsonl` (append-only, like the provenance ledger and the
submission intake). The queue excludes anything already resolved. This module records the verdict; a
later promotion step applies a 'verified' verdict back to the source store — kept separate so the
queue never mutates data in place.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
VERDICT_LOG = str(_ROOT / "manual" / "verifications.jsonl")

# Lower number = surface first. Ordered by impact on sellable output: a mis-parsed FDD figure or an
# unconfirmed count change matters more than a coming-soon register note.
PRIORITY = {"needs_human_read": 1, "submitted": 2, "uncertain": 3,
            "unverified_anchor": 4, "unverified_count": 5, "register_pending": 6}


def _load(relpath: str, default=None):
    try:
        return json.loads((_ROOT / relpath).read_text(encoding="utf-8"))
    except Exception:                                            # noqa: BLE001
        return default if default is not None else {}


def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def resolved(path: str = VERDICT_LOG) -> dict:
    """
    name:      resolved
    purpose:   The latest verdict per queue item id, from the append-only verdict log.
    arguments: path — the verdict log.
    returns:   {queue_id: {verdict, by, at, note, new_confidence}} (latest wins).
    other:     Append-only means a later verdict supersedes an earlier one for the same id.
    """
    out = {}
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    v = json.loads(line)
                    out[v.get("queue_id")] = v
    except FileNotFoundError:
        pass
    return out


def _urlish(s):
    """Return s when it looks like a clickable http(s) link, else None."""
    return s if isinstance(s, str) and s.startswith(("http://", "https://")) else None


def _item(qid, brand, layer, metric, value, confidence, source, reason, store, ref,
          tier=None, source_url=None):
    return {"id": qid, "brand": brand, "layer": layer, "metric": metric, "value": value,
            "confidence": confidence, "tier": tier, "source": source, "source_url": source_url,
            "reason": reason, "store": store, "ref": ref, "priority": PRIORITY.get(reason, 9)}


def queue(con, include_resolved: bool = False, resolved_path: str = VERDICT_LOG) -> list:
    """
    name:      queue
    purpose:   Gather every record awaiting a human verdict into one prioritized worklist.
    arguments: con — DB connection (fdd_extracts, financial_anchors); include_resolved — keep items that
               already have a verdict; resolved_path — the verdict log consulted to drop resolved items.
    returns:   list of queue items (dicts), sorted by priority then brand.
    effects:   None (read-only). File-backed stores (china_stores, sightings, register, submissions) are
               read from manual/; the two DB-backed stores from `con`.
    """
    from . import submissions as S
    items = []

    # FDD extracts flagged for a human read (quantitative parse was ambiguous).
    try:
        for r in con.execute("SELECT doc_number, brand_id, year, source_url FROM fdd_extracts "
                             "WHERE needs_human_read=1"):
            items.append(_item(f"fdd:{r[0]}", r[1], "structure", "fdd_extract", f"FDD {r[2]}",
                               "low", r[3], "needs_human_read", "fdd_extracts", r[0],
                               source_url=_urlish(r[3])))
    except Exception:                                            # noqa: BLE001
        pass

    # Intake records not yet acted on.
    try:
        for rec in S.iter_submissions():
            if rec.get("status") == "submitted":
                items.append(_item(rec.get("id"), rec.get("brand"), rec.get("dimension"),
                                   rec.get("metric"), rec.get("value"), rec.get("confidence"),
                                   rec.get("source"), "submitted", "submissions", rec.get("id"),
                                   rec.get("provenance_tier"), source_url=_urlish(rec.get("source_url"))))
    except Exception:                                            # noqa: BLE001
        pass

    # Sightings held OUT of the count/map pending confirmation.
    for g in _load("manual/sightings.json").get("sightings", []):
        for loc in g.get("locations", []):
            if loc.get("confidence") in ("uncertain", "announced"):
                ref = f"{g.get('chain')}|{loc.get('address')}"
                items.append(_item(f"sight:{ref}", g.get("chain"), "presence", "outlet",
                                   loc.get("name"), loc.get("confidence"), loc.get("verified_by"),
                                   "uncertain", "sightings", ref,
                                   source_url=_urlish(loc.get("source_url") or loc.get("url"))))

    # financial_anchors below 'high' — secondary/press, not a primary filing.
    try:
        for r in con.execute("SELECT brand_id, metric, period, value, confidence, source, source_url "
                             "FROM financial_anchors WHERE confidence IS NOT 'high'"):
            items.append(_item(f"fa:{r[0]}:{r[1]}:{r[2]}", r[0], "economics", r[1], r[3],
                               r[4], r[5], "unverified_anchor", "financial_anchors",
                               f"{r[0]}|{r[1]}|{r[2]}", source_url=_urlish(r[6])))
    except Exception:                                            # noqa: BLE001
        pass

    # china_stores totals below 'high' — the public "~"-marked worldwide figures.
    for brand, e in _load("manual/china_stores.json").get("brands", {}).items():
        if e.get("total") is not None and e.get("confidence") != "high":
            items.append(_item(f"cs:{brand}", brand, "scale", "store_count_total", e.get("total"),
                               e.get("confidence"), e.get("source"), "unverified_count",
                               "china_stores", brand, source_url=_urlish(e.get("source_url"))))

    # register markets that are ANNOUNCED (coming-soon) — a watch item needing open-confirmation.
    # (Low-confidence abroad notes are NOT queued here: they are not gating sellable output and are
    #  handled by the monthly register-sweep routine; queuing them all would just flood the worklist.)
    for e in _load("register.json").get("entries", []):
        if e.get("status") == "announced":
            ref = f"{e.get('chain')}|{e.get('market')}"
            src0 = (e.get("sources") or [None])[0]
            items.append(_item(f"reg:{ref}", e.get("chain"), "presence", "market_presence",
                               f"{e.get('market')} ({e.get('status')})", e.get("confidence"),
                               src0, "register_pending", "register", ref, source_url=_urlish(src0)))

    if not include_resolved:
        done = resolved(resolved_path)
        items = [i for i in items if i["id"] not in done]
    items.sort(key=lambda i: (i["priority"], i["brand"] or "", i["id"]))
    return items


def summary(items: list) -> dict:
    """Counts by reason and the total — the at-a-glance state of the backlog."""
    by_reason = {}
    for i in items:
        by_reason[i["reason"]] = by_reason.get(i["reason"], 0) + 1
    return {"total": len(items), "by_reason": dict(sorted(by_reason.items(),
            key=lambda kv: PRIORITY.get(kv[0], 9)))}


VERDICTS = ("verified", "rejected", "watch")


def record_verdict(queue_id: str, verdict: str, by: str = "owner", note: str = None,
                   new_confidence: str = None, evidence: str = None, path: str = VERDICT_LOG) -> dict:
    """
    name:      record_verdict
    purpose:   Append one human verdict for a queue item to the verdict log.
    arguments: queue_id — the item's id; verdict — one of VERDICTS; by — who; note; new_confidence — the
               promoted confidence a later promotion step should apply; evidence — a path (or list of
               paths) to saved screenshots/docs backing the call; path — the log.
    returns:   the verdict record written.
    effects:   Appends one JSON line. Raises ValueError on an unknown verdict.
    other:     Append-only. Three verdicts, because the real/open question is not binary:
                 verified — confirmed true/open; promote it.
                 rejected — not real / wrong; drop it.
                 watch    — REAL but not yet open (announced / coming-soon / temporarily closed). Neither
                            counted nor dropped — acknowledged and kept on the watch list for re-check.
               Records the DECISION only; it does NOT edit the source store (promotion is separate), so the
               queue can never corrupt data. All three drop the item from the active queue (see resolved()).
    """
    if verdict not in VERDICTS:
        raise ValueError("verdict must be one of " + ", ".join(VERDICTS))
    rec = {"queue_id": queue_id, "verdict": verdict, "by": by, "at": _utcnow(),
           "note": note, "new_confidence": new_confidence, "evidence": evidence}
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def watching(path: str = VERDICT_LOG) -> list:
    """The items whose latest verdict is 'watch' — real-but-not-yet-open, for periodic re-check."""
    return [v for v in resolved(path).values() if v.get("verdict") == "watch"]


def render(items: list, limit: int = 40) -> str:
    """A compact text rendering of the queue: a reason summary then the top `limit` items."""
    s = summary(items)
    L = [f"Verification queue — {s['total']} open item(s)"]
    L.append("  " + "  ".join(f"{k}:{v}" for k, v in s["by_reason"].items()) if s["by_reason"] else "  (empty)")
    L.append("")
    for i in items[:limit]:
        val = str(i["value"])
        val = val if len(val) <= 50 else val[:47] + "…"
        L.append(f"[{i['reason']}] {i['brand']}/{i['layer']}:{i['metric']} = {val} "
                 f"({i['confidence']}) — {i['id']}")
    if len(items) > limit:
        L.append(f"…and {len(items) - limit} more (raise --limit)")
    return "\n".join(L)

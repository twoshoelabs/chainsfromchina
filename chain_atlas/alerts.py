"""
The PRO event log + alerts — pillar 2 of the repositioned PRO edition (docs/pro_spec.md §0, §3 step 3,
build order #5). The renewable, least-LLM-substitutable core of the subscription: a buyer does not pay
for a document they read once, they pay for the push that says *a new China-origin chain just entered
the US*, or *a tracked one opened / closed / expanded abroad*.

WHAT THIS IS, AND WHAT IT IS NOT. The existing `events.py` derives low-level census FACTS (opening /
closure / relocation) from the daily adapter collection in the DB, and `openings.py` derives store-count
PACE. Both only see the adapter-backed brands. This module sits ABOVE them: it is the cross-layer
monitoring stream that also catches the brands tracked only by hand-verified SIGHTINGS (52TOYS,
JiBeiChuan, Makkee…) — which have no adapter and are where most *new US entries* actually show up — and
folds in register (abroad), scale (china_stores) and filing (financial_anchors) changes. One typed,
append-only event stream that (a) powers alerts and (b) IS the longitudinal time-series the census
cannot back-fill.

HOW IT WORKS. A diff detector compares the current state of the manual layers against a stored baseline
snapshot and emits one event per change. It is conservative like events.py: a *first US entry* and a
*new outlet* are emitted from positive evidence (the census roster + confirmed sightings); a *closure*
comes from the authoritative `closings.json`, never merely from an outlet disappearing from a roster
regen. Event ids are stable (hash of brand|kind|key), so the log is idempotent — a stale or lost
baseline can never double-log an event; the baseline is only an optimization for the before→after value.

PRO ONLY. Events ride the Pro export and the owner's alert channel, never the public map/data.
`python -m chain_atlas alerts detect|digest|log`.
"""
import hashlib
import json
import re
from pathlib import Path

from . import config

_ROOT = Path(__file__).resolve().parents[1]
EVENT_LOG = str(_ROOT / "manual" / "event_log.jsonl")
BASELINE = str(_ROOT / "manual" / "event_baseline.json")
CURSOR = str(_ROOT / "manual" / "event_cursor.json")

# Kinds, in descending alert value. entered_us (a brand's FIRST US outlet) is the flagship alert.
KINDS = ("entered_us", "market_entered", "outlet_opened", "outlet_closed",
         "market_exited", "scale_changed", "new_filing")
_PRIORITY = {k: i for i, k in enumerate(KINDS)}
_DIM = {"entered_us": "presence", "outlet_opened": "presence", "outlet_closed": "presence",
        "market_entered": "presence", "market_exited": "presence",
        "scale_changed": "scale", "new_filing": "economics"}
_CONF_RANK = {"high": 3, "medium": 2, "low": 1, None: 0}


def _load(relpath, default=None):
    try:
        return json.loads((_ROOT / relpath).read_text(encoding="utf-8"))
    except Exception:                                            # noqa: BLE001
        return default if default is not None else {}


def _norm(a):
    return "".join((a or "").lower().split())


def _state_of(addr):
    m = re.search(r",\s*([A-Z]{2})\s+\d{5}", addr or "")
    return m.group(1) if m else None


def event_id(brand, kind, key):
    """Stable id from the change's identity (NOT its date) so the log is idempotent."""
    h = hashlib.sha1(f"{brand}|{kind}|{key}".encode("utf-8")).hexdigest()[:12]
    return f"evt_{h}"


# --------------------------------------------------------------------------- snapshot

def snapshot(con=None) -> dict:
    """
    name:      snapshot
    purpose:   Capture the current comparable state of every monitored layer.
    arguments: con — optional DB connection; when given, financial_anchors are included (filing layer).
    returns:   {as_of, presence{brand:{addr_norm:{...}}}, closings{brand:[addr_norm]},
               register{brand:{market:{status,locations}}}, scale{brand:{total,as_of,confidence,source}},
               anchors{brand:{"metric|period":{value,unit,source}}}}.
    effects:   None (read-only). Presence unions the published census roster with CONFIRMED sightings —
               the same rule the dossier presence layer uses — so sightings-only brands are covered.
    """
    pres = {}
    for s in _load("map/data/stores.json").get("stores", []):
        b = s.get("chain")
        if not b:
            continue
        pres.setdefault(b, {})[_norm(s.get("addr"))] = {
            "name": s.get("name"), "address": s.get("addr"), "city": s.get("city"),
            "state": s.get("state"), "source": "census roster"}
    for g in _load("manual/sightings.json").get("sightings", []):
        b = g.get("chain")
        if not b:
            continue
        for loc in g.get("locations", []):
            if loc.get("confidence") != "confirmed":
                continue
            k = _norm(loc.get("address"))
            if k in pres.get(b, {}):
                continue
            pres.setdefault(b, {})[k] = {
                "name": loc.get("name"), "address": loc.get("address"), "city": loc.get("city"),
                "state": loc.get("state") or _state_of(loc.get("address")),
                "source": "hand-verified sighting"}

    closings = {}
    for c in _load("manual/closings.json").get("closings", []):
        closings.setdefault(c.get("chain"), []).append(_norm(c.get("address")))

    register = {}
    for e in _load("register.json").get("entries", []):
        register.setdefault(e.get("chain"), {})[e.get("market")] = {
            "status": e.get("status"), "locations": e.get("locations"),
            "source": (e.get("sources") or [None])[0]}

    scale = {}
    for b, e in _load("manual/china_stores.json").get("brands", {}).items():
        if e.get("total") is not None:
            scale[b] = {"total": e.get("total"), "as_of": e.get("as_of"),
                        "confidence": e.get("confidence"), "source": e.get("source")}

    anchors = {}
    if con is not None:
        try:
            for r in con.execute("SELECT brand_id, metric, period, value, unit, source "
                                 "FROM financial_anchors"):
                anchors.setdefault(r[0], {})[f"{r[1]}|{r[2]}"] = {
                    "value": r[3], "unit": r[4], "source": r[5]}
        except Exception:                                        # noqa: BLE001
            pass

    return {"as_of": config.today_ny(), "presence": pres, "closings": closings,
            "register": register, "scale": scale, "anchors": anchors}


# --------------------------------------------------------------------------- detect (pure)

def _evt(brand, kind, key, before, after, as_of, tier, confidence, source, headline):
    return {"id": event_id(brand, kind, key), "brand": brand, "kind": kind,
            "dimension": _DIM.get(kind), "key": key, "before": before, "after": after,
            "as_of": as_of, "detected_at": config.now_ny("seconds"),
            "provenance_tier": tier, "confidence": confidence, "source": source,
            "headline": headline, "priority": _PRIORITY.get(kind, 9)}


def detect(prev: dict, curr: dict) -> list:
    """
    name:      detect
    purpose:   Diff a previous snapshot against the current one and emit one event per change.
    arguments: prev — the baseline snapshot (an empty dict on the first run means SEED-ONLY: nothing is
               emitted, so an initial run cannot flood the log with every existing brand as 'entered_us');
               curr — the current snapshot from snapshot().
    returns:   a list of event dicts, sorted by priority (entered_us first) then brand.
    effects:   None (pure). File I/O and baseline persistence are in run_detect().
    """
    if not prev:                                   # first run: establish the baseline, emit nothing
        return []
    out = []
    as_of = curr.get("as_of")

    # ---- presence: first US entry, then new outlets for brands already present ----
    for brand, outlets in curr.get("presence", {}).items():
        prev_out = prev.get("presence", {}).get(brand, {})
        if not prev_out and outlets:
            cities = sorted({o.get("city") or o.get("state") or "" for o in outlets.values()} - {""})
            out.append(_evt(brand, "entered_us", "entered_us", 0, len(outlets), as_of,
                            "measured", "high", "US census (operator-observed / hand-verified)",
                            f"{brand} ENTERED the US — {len(outlets)} outlet(s)"
                            + (f" ({', '.join(cities)})" if cities else "")))
            continue                               # the first-entry event subsumes per-outlet opens
        for k, o in outlets.items():
            if k not in prev_out:
                where = ", ".join(x for x in (o.get("city"), o.get("state")) if x)
                out.append(_evt(brand, "outlet_opened", k, None, o.get("address"), as_of,
                                "measured", "high", o.get("source") or "US census",
                                f"{brand} opened: {o.get('name') or o.get('address')}"
                                + (f" — {where}" if where else "")))

    # ---- closures: authoritative from closings.json (new entries only), never from disappearance ----
    for brand, addrs in curr.get("closings", {}).items():
        prev_addrs = set(prev.get("closings", {}).get(brand, []))
        for k in addrs:
            if k not in prev_addrs:
                out.append(_evt(brand, "outlet_closed", f"closed:{k}", None, k, as_of,
                                "measured", "high", "closings.json",
                                f"{brand} closed an outlet"))

    # ---- register: abroad market entries / exits ----
    for brand, markets in curr.get("register", {}).items():
        prev_m = prev.get("register", {}).get(brand, {})
        for mkt, e in markets.items():
            was = prev_m.get(mkt)
            if e.get("status") == "present" and (not was or was.get("status") != "present"):
                loc = e.get("locations")
                out.append(_evt(brand, "market_entered", mkt, (was or {}).get("status"), "present",
                                as_of, "reported", "medium", e.get("source") or "register",
                                f"{brand} present in {mkt}"
                                + (f" ({loc} location{'s' if loc and loc != 1 else ''})" if loc else "")))
            elif e.get("status") == "exited" and (not was or was.get("status") != "exited"):
                out.append(_evt(brand, "market_exited", mkt, (was or {}).get("status"), "exited",
                                as_of, "reported", "medium", e.get("source") or "register",
                                f"{brand} EXITED {mkt}"))

    # ---- scale: home-market store-count changes ----
    for brand, e in curr.get("scale", {}).items():
        was = prev.get("scale", {}).get(brand)
        if was and was.get("total") != e.get("total"):
            delta = e["total"] - was["total"]
            tier = "filed" if e.get("confidence") == "high" else "reported"
            out.append(_evt(brand, "scale_changed", f"{e.get('total')}@{e.get('as_of')}",
                            was.get("total"), e.get("total"), e.get("as_of") or as_of,
                            tier, e.get("confidence") or "medium", e.get("source") or "china_stores",
                            f"{brand} home-market count {was['total']:,} → {e['total']:,} "
                            f"({'+' if delta >= 0 else ''}{delta:,})"))

    # ---- filings: new financial_anchors (only when the DB was snapshotted) ----
    for brand, anchors in curr.get("anchors", {}).items():
        prev_a = prev.get("anchors", {}).get(brand, {})
        for key, a in anchors.items():
            if key not in prev_a:
                metric, period = (key.split("|", 1) + [""])[:2]
                out.append(_evt(brand, "new_filing", key, None, a.get("value"), as_of,
                                "filed", "medium", a.get("source") or "filing",
                                f"{brand} new filed figure: {metric} ({period})"))

    out.sort(key=lambda e: (e["priority"], e["brand"] or "", e["id"]))
    return out


# --------------------------------------------------------------------------- log I/O

def append(events, path: str = EVENT_LOG) -> int:
    """Append new events to the log, skipping any id already present. Returns the count written."""
    seen = {e["id"] for e in load(path)}
    n = 0
    with open(path, "a", encoding="utf-8") as f:
        for e in events:
            if e["id"] in seen:
                continue
            seen.add(e["id"])
            f.write(json.dumps({k: v for k, v in e.items() if k != "priority"}, ensure_ascii=False) + "\n")
            n += 1
    return n


def load(path: str = EVENT_LOG) -> list:
    """The full event log, oldest first. Missing log = []."""
    out = []
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    out.append(json.loads(line))
    except FileNotFoundError:
        pass
    return out


def _slim(snap: dict) -> dict:
    """
    Reduce a snapshot to only what detect() reads from the PRIOR state — key membership and before-values
    — so the persisted baseline stays small (the current snapshot's full records live in `curr`, not the
    baseline). Presence/anchors keep just their keys; register keeps status; scale keeps the total.
    """
    return {"as_of": snap.get("as_of"),
            "presence": {b: list(o) for b, o in snap.get("presence", {}).items()},
            "closings": snap.get("closings", {}),
            "register": {b: {m: {"status": e.get("status")} for m, e in mk.items()}
                         for b, mk in snap.get("register", {}).items()},
            "scale": {b: {"total": e.get("total")} for b, e in snap.get("scale", {}).items()},
            "anchors": {b: list(a) for b, a in snap.get("anchors", {}).items()}}


def run_detect(con=None, log_path: str = EVENT_LOG, baseline_path: str = BASELINE) -> list:
    """
    name:      run_detect
    purpose:   The file-backed detection cycle: snapshot → diff against the saved baseline → append new
               events → save the new baseline.
    arguments: con — optional DB connection (adds the filing layer); log_path, baseline_path — overridable
               for tests.
    returns:   the list of NEW events written (empty on the seeding first run, or when nothing changed).
    effects:   Appends to the event log and overwrites the baseline. The id-dedupe in append() makes this
               safe to re-run even if the baseline is stale or was lost.
    """
    curr = snapshot(con)
    try:
        prev = json.loads(Path(baseline_path).read_text(encoding="utf-8"))
    except Exception:                                           # noqa: BLE001
        prev = {}
    events = detect(prev, curr)
    append(events, log_path)
    Path(baseline_path).write_text(json.dumps(_slim(curr), ensure_ascii=False), encoding="utf-8")
    return events


# --------------------------------------------------------------------------- alerts / digest

def _brand_sector(brand: str) -> str:
    for g in _load("manual/sightings.json").get("sightings", []):
        if g.get("chain") == brand and g.get("sector"):
            return g.get("sector")
    comp = _load("manual/companies.json").get("companies", {})
    if isinstance(comp, dict):
        return (comp.get(brand) or {}).get("sector")
    return None


def filter_events(events, lens: dict = None, since: str = None) -> list:
    """
    name:      filter_events
    purpose:   Scope an event list to a buyer's lens and/or a time window.
    arguments: events; lens — {kinds[], brands[], sectors[], min_confidence}; since — ISO 'detected_at'
               lower bound (exclusive).
    returns:   the matching events (input order preserved).
    """
    lens = lens or {}
    kinds = set(lens.get("kinds") or [])
    brands = set(lens.get("brands") or [])
    sectors = set(lens.get("sectors") or [])
    minc = _CONF_RANK.get(lens.get("min_confidence"), 0)
    out = []
    for e in events:
        if since and (e.get("detected_at") or "") <= since:
            continue
        if kinds and e.get("kind") not in kinds:
            continue
        if brands and e.get("brand") not in brands:
            continue
        if sectors and _brand_sector(e.get("brand")) not in sectors:
            continue
        if _CONF_RANK.get(e.get("confidence"), 0) < minc:
            continue
        out.append(e)
    return out


def digest(events, lens: dict = None, since: str = None, title: str = "CFC alerts") -> str:
    """A compact Markdown alert digest, grouped by kind in descending alert value. '' when empty."""
    evs = filter_events(events, lens, since)
    if not evs:
        return ""
    by_kind = {}
    for e in evs:
        by_kind.setdefault(e.get("kind"), []).append(e)
    labels = {"entered_us": "🇺🇸 New US entrants", "market_entered": "🌏 New abroad markets",
              "outlet_opened": "➕ Outlets opened", "outlet_closed": "➖ Outlets closed",
              "market_exited": "↩︎ Market exits", "scale_changed": "📈 Home-market scale changes",
              "new_filing": "📄 New filings"}
    L = [f"**{title}** — {len(evs)} event(s)"]
    for k in KINDS:
        rows = by_kind.get(k)
        if not rows:
            continue
        L.append(f"\n**{labels.get(k, k)}** ({len(rows)})")
        for e in rows:
            L.append(f"- {e.get('headline')}  _({e.get('confidence')}, {e.get('as_of')})_")
    return "\n".join(L)


def read_cursor(path: str = CURSOR) -> str:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8")).get("last_delivered_at")
    except Exception:                                           # noqa: BLE001
        return None


def undelivered(events=None, cursor_path: str = CURSOR, log_path: str = EVENT_LOG) -> list:
    """Events detected after the delivery cursor — what an alert run still needs to push."""
    events = events if events is not None else load(log_path)
    return filter_events(events, since=read_cursor(cursor_path))


def mark_delivered(events=None, cursor_path: str = CURSOR, log_path: str = EVENT_LOG) -> str:
    """Advance the delivery cursor to the newest event's detected_at. Returns the new cursor value."""
    events = events if events is not None else load(log_path)
    newest = max((e.get("detected_at") or "" for e in events), default=None)
    if newest:
        Path(cursor_path).write_text(json.dumps({"last_delivered_at": newest}), encoding="utf-8")
    return newest


def _macos_notify(summary: str, title: str = "CFC alerts"):
    """Best-effort local macOS notification; silently a no-op off a Mac user session."""
    import subprocess
    body = re.sub(r'["\\]', "", summary)[:230]
    try:
        subprocess.run(["osascript", "-e", f'display notification "{body}" with title "{title}"'],
                       check=False, timeout=10, capture_output=True)
    except Exception:                                           # noqa: BLE001
        pass


def notify(con=None, digest_path: str = None, cursor_path: str = CURSOR,
           log_path: str = EVENT_LOG, baseline_path: str = BASELINE, macos: bool = True) -> dict:
    """
    name:      notify
    purpose:   The daily local-refresh hook: detect today's changes, surface any NOT yet delivered, and
               advance the cursor. Intended to run after `export` and before `deploy.sh`, so the updated
               event log + baseline ride the same Refresh commit.
    arguments: con — optional DB connection (adds the filing layer); digest_path — where to append the
               Markdown digest (default DATA_DIR/alerts/digest.md); the rest are test overrides; macos —
               post a best-effort local notification.
    returns:   {detected, undelivered, digest, digest_path}.
    effects:   Runs run_detect() (appends events, rewrites baseline), appends the digest to disk, posts a
               local notification, and advances the delivery cursor. Idempotent: a no-change day writes
               nothing and delivers nothing.
    """
    from . import config
    new = run_detect(con, log_path=log_path, baseline_path=baseline_path)
    pending = undelivered(cursor_path=cursor_path, log_path=log_path)
    if not pending:
        return {"detected": len(new), "undelivered": 0, "digest": "", "digest_path": None}
    body = digest(pending, title="CFC alerts")
    if digest_path is None:
        d = config.DATA_DIR / "alerts"
        d.mkdir(parents=True, exist_ok=True)
        digest_path = str(d / "digest.md")
    with open(digest_path, "a", encoding="utf-8") as f:
        f.write(f"## {config.now_ny('minutes')} NY\n\n{body}\n\n")
    if macos:
        top = next((e["headline"] for e in pending), "")
        _macos_notify(f"{len(pending)} new — {top}")
    mark_delivered(cursor_path=cursor_path, log_path=log_path)
    return {"detected": len(new), "undelivered": len(pending), "digest": body, "digest_path": digest_path}

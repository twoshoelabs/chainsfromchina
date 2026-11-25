"""
Mall tenant snapshots: the dated, comparable record behind "new openings in malls".

THE METHOD (owner's design, 24 Nov 2026). Pick a start date. On that date record EVERY store a
tracked mall lists (the baseline). Then re-read the same directory periodically and compare the
newest list with the baseline: a store that is trading now and was not trading at the baseline is
a NEW OPENING in that window; a store that was trading at the baseline and is gone is a closure.
Each opening is then marked China-origin or not, by matching it to the register's tracked chains.

This replaces the earlier figure built from the malls' own "New" / "Coming Soon" tags, which had no
defined time frame (each mall decides how long a store stays tagged "New").

WHAT A SNAPSHOT IS. One JSON file per mall per reading, in manual/mall_snapshots/<mall-id>/
<YYYY-MM-DD>.json, holding every tenant with a stable id, its name and — where the directory
publishes it — the date the store starts trading. A tenant whose start date is after the reading
date is "coming soon": listed, not yet open. Files are never edited after capture; they are the
evidence a comparison is rebuilt from.

WHO CAN BE READ BY SCRIPT. Westfield (URW) directories embed their full tenant list, with start
dates, in the page itself and permit crawling (robots.txt), so they are captured by `capture()`.
Other operators' directories need a per-site reader or a hand capture; until one exists a mall
simply has no snapshot and is left out of the comparison (never guessed).
"""
import json
import re
from pathlib import Path

from . import capture as _capture
from .config import today_ny

ROOT = Path(__file__).resolve().parents[1]
SNAP_DIR = ROOT / "manual" / "mall_snapshots"
_WF_PAGES = ("retailers", "restaurants", "entertainment")   # "services" (concierge etc.) are not stores
_WF_URL = "https://www.westfield.com/en/united-states/{slug}/{page}"
_HREF = re.compile(r'/united-states/[a-z0-9-]+/(retailers|restaurants|entertainment)/([^/"\\]+)/(\d+)')


def _store_objects(html: str) -> list[dict]:
    """Every {"store_id": …} object embedded in a Westfield directory page (escaped JSON in the HTML)."""
    u = html.replace('\\"', '"').replace("\\\\", "\\")
    out, i = [], 0
    while True:
        i = u.find('{"store_id":"', i)
        if i < 0:
            break
        depth, j, in_str, esc = 0, i, False, False
        while j < len(u):                       # brace-match, ignoring braces inside strings
            c = u[j]
            if in_str:
                if esc:
                    esc = False
                elif c == "\\":
                    esc = True
                elif c == '"':
                    in_str = False
            elif c == '"':
                in_str = True
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        try:
            out.append(json.loads(u[i:j + 1]))
        except Exception:                       # noqa: BLE001 — a malformed fragment; skip it
            pass
        i = j + 1
    return out


def read_westfield(slug: str) -> list[dict]:
    """
    name:      read_westfield
    purpose:   The full tenant list of one Westfield mall, as its public directory publishes it.
    arguments: slug — the mall's path segment on westfield.com (e.g. "topanga")
    returns:   list of {id, name, kind, slug, starts_at, ends_at, state, level}, one per tenant
    effects:   Three polite GETs (retailers, restaurants, entertainment) via capture.fetch, which
               honours robots.txt and the project's delay.
    other:     Raises if a page yields no tenants — an empty read must never be saved as a
               snapshot, or the next comparison would report every store as closed.
    """
    tenants: dict[str, dict] = {}
    for page in _WF_PAGES:
        html = _capture.fetch(_WF_URL.format(slug=slug, page=page)).text
        slugs = {m.group(3): m.group(2) for m in _HREF.finditer(html)}
        objs = _store_objects(html)
        if page == "retailers" and not objs:
            raise RuntimeError(f"westfield/{slug}: no tenants parsed from the stores page — refusing the read")
        for o in objs:
            sid = str(o.get("store_id"))
            st = o.get("status") or {}
            tenants.setdefault(sid, {
                "id": sid, "name": (o.get("name") or "").strip(), "kind": page,
                "slug": slugs.get(sid), "level": o.get("store_level") or None,
                "starts_at": (st.get("starts_at") or "")[:10] or None,
                "ends_at": (st.get("ends_at") or "")[:10] or None,
                "state": st.get("state")})
    return sorted(tenants.values(), key=lambda t: (t["name"].lower(), t["id"]))


def capture(mall: dict, on: str | None = None) -> Path:
    """
    name:      capture
    purpose:   Read one mall's directory now and save it as a dated snapshot.
    arguments: mall — a malls[] row from manual/mall_openings.json carrying
               "directory": {"type": "westfield", "slug": …}; on — snapshot date (default NY today)
    returns:   the path written
    effects:   Network reads; writes manual/mall_snapshots/<mall-id>/<date>.json (overwrites a
               same-day file, never an earlier one).
    """
    d = mall.get("directory") or {}
    if d.get("type") != "westfield":
        raise ValueError(f"{mall['id']}: no scripted reader for this mall's directory yet")
    on = on or today_ny()
    tenants = read_westfield(d["slug"])
    path = SNAP_DIR / mall["id"] / f"{on}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "mall": mall["id"], "captured_on": on,
        "source": f"westfield.com/en/united-states/{d['slug']} — stores, food & drink, entertainment",
        "method": "script (first-party directory page, robots-permitted)",
        "tenants": tenants}, ensure_ascii=False, indent=1), encoding="utf-8")
    return path


_SIMON_HREF = re.compile(r'href="(?:https?://www\.simon\.com)?/mall/[a-z0-9-]+/stores/([a-z0-9][a-z0-9-]*)"[^>]*>(.*?)</a>', re.S | re.I)


def read_saved_simon(html: str) -> list[dict]:
    """Tenants from a saved copy of a Simon mall's "Stores" page. Simon links every tenant as
    /mall/<mall>/stores/<tenant-slug>; the slug is the stable id. Simon publishes no opening dates,
    so "coming soon" is taken from the words on the tenant's own link/card."""
    tenants: dict[str, dict] = {}
    for m in _SIMON_HREF.finditer(html):
        slug, inner = m.group(1), re.sub(r"<[^>]+>", " ", m.group(2))
        text = re.sub(r"\s+", " ", inner).strip()
        if slug in ("directory", "map") or not text:
            continue
        soon = bool(re.search(r"coming soon|opening soon", text, re.I))
        name = re.sub(r"\b(coming soon|opening soon|now open|new)\b[:!\s-]*", "", text, flags=re.I).strip() or slug
        cur = tenants.get(slug)
        if cur is None or len(name) < len(cur["name"]):
            tenants[slug] = {"id": slug, "name": name, "kind": "stores", "slug": slug, "level": None,
                             "starts_at": None, "ends_at": None,
                             "state": "preview" if (soon or (cur and cur["state"] == "preview")) else "live"}
        elif soon:
            cur["state"] = "preview"
    return sorted(tenants.values(), key=lambda x: (x["name"].lower(), x["id"]))


def capture_saved(mall: dict, path: Path, on: str | None = None) -> Path:
    """
    name:      capture_saved
    purpose:   Save a snapshot from a copy of a mall's stores page that a person saved by hand
               (Simon's directories answer scripts and automated browsers with a human check).
    arguments: mall — malls[] row; path — the saved .html file; on — the date the page was saved
               (default NY today; pass the real date if importing later)
    returns:   the snapshot path written
    effects:   Writes manual/mall_snapshots/<mall-id>/<date>.json.
    other:     Refuses a page that yields fewer than 20 tenants — almost certainly the verification
               page or a partial save, and an empty snapshot would read as mass closures.
    """
    html = Path(path).read_text(encoding="utf-8", errors="ignore")
    tenants = read_saved_simon(html)
    if len(tenants) < 20:
        raise RuntimeError(f"{mall['id']}: only {len(tenants)} tenants found in {path} — not a full "
                           "stores page (verification page or partial save?); nothing written")
    on = on or today_ny()
    out = SNAP_DIR / mall["id"] / f"{on}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "mall": mall["id"], "captured_on": on,
        "source": f"saved copy of the mall's own stores page ({Path(path).name})",
        "method": "hand-saved page, parsed by script",
        "tenants": tenants}, ensure_ascii=False, indent=1), encoding="utf-8")
    return out


def snapshots(mall_id: str) -> list[dict]:
    """A mall's saved snapshots, oldest first."""
    d = SNAP_DIR / mall_id
    if not d.exists():
        return []
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(d.glob("*.json"))]


def _norm(name: str) -> str:
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", (name or "").lower())


def classifier(doc: dict):
    """
    A function tenant-name -> chain_id | None, deciding China-origin by an EXACT normalised-name match
    against the register's chain names and aliases (never a substring — "Chain" must not match), with
    manual overrides from mall_openings.json `tenant_overrides` taking precedence either way.
    """
    from . import register
    reg = register.load()
    chains = reg["chains"] if isinstance(reg, dict) else reg.chains
    table: dict[str, str] = {}
    for cid, c in chains.items():
        names = [c.get("name"), c.get("name_us"), c.get("name_intl"), c.get("name_zh")] + list(c.get("aliases") or [])
        for n in names:
            k = _norm(n or "")
            if len(k) >= 4:                       # short keys ("dr", "ep") are too collision-prone
                table.setdefault(k, cid)
    over = {_norm(k): v for k, v in (doc.get("tenant_overrides") or {}).items()}

    def classify(name: str):
        k = _norm(name)
        if k in over:
            return over[k].get("chain") if over[k].get("china_origin", True) else None
        return table.get(k)
    return classify


def _soon(t: dict, on: str) -> bool:
    """Listed but not yet trading on `on`: the directory holds it in a non-live state ("preview" —
    Westfield's coming-soon state, sometimes with no date at all), or its start date is still ahead."""
    return (t.get("state") not in (None, "live")) or bool(t.get("starts_at") and t["starts_at"] > on)


def compare(doc: dict) -> dict:
    """
    name:      compare
    purpose:   Baseline-vs-latest comparison for every mall that has snapshots.
    arguments: doc — parsed manual/mall_openings.json (for the mall list and overrides)
    returns:   the publishable metric (aggregates + named China-origin openings; no full tenant lists)
    effects:   None (reads snapshot files).
    """
    classify = classifier(doc)
    malls = {m["id"]: m for m in doc.get("malls", [])}
    per_mall, opened, closed, soon_now = [], [], [], []
    base_total = base_china = 0
    starts, lasts = [], []
    for mid, m in malls.items():
        snaps = snapshots(mid)
        if not snaps:
            continue
        base, last = snaps[0], snaps[-1]
        b_on, l_on = base["captured_on"], last["captured_on"]
        starts.append(b_on)
        lasts.append(l_on)
        ov = (doc.get("status_overrides") or {}).get(mid, {})

        def is_open(t, on, _ov=ov):
            """Trading on `on`? The directory's own state, unless the owner has overridden it: a store
            the directory shows live but that is not actually open (open=false, until opened_on), or
            one it holds in an undated non-live state that is in fact trading (open=true)."""
            o = _ov.get(t["id"])
            if o is not None:
                if o.get("open") is True:
                    return True
                return bool(o.get("opened_on") and on >= o["opened_on"])
            return not _soon(t, on)

        b_open = {t["id"]: t for t in base["tenants"] if is_open(t, b_on)}
        l_open = {t["id"]: t for t in last["tenants"] if is_open(t, l_on)}
        base_total += len(b_open)
        base_china += sum(1 for t in b_open.values() if classify(t["name"]))
        row = {"mall": m["name"], "operator": m.get("operator"), "metro": m.get("metro"),
               "baseline_on": b_on, "latest_on": l_on, "readings": len(snaps),
               "stores_at_baseline": len(b_open), "opened": 0, "opened_china": 0, "closed": 0}
        for t in last["tenants"]:
            if not is_open(t, l_on):
                soon_now.append({"mall": m["name"], "name": t["name"], "chain": classify(t["name"]),
                                 "opens": t.get("starts_at")})
        if len(snaps) >= 2:
            for tid, t in l_open.items():
                if tid not in b_open:               # absent, or only "coming soon", at the baseline
                    cid = classify(t["name"])
                    opened.append({"mall": m["name"], "metro": m.get("metro"), "name": t["name"],
                                   "chain": cid, "opened": t.get("starts_at")})
                    row["opened"] += 1
                    row["opened_china"] += 1 if cid else 0
            last_ids = {t["id"] for t in last["tenants"]}
            for tid, t in b_open.items():
                if tid not in last_ids:
                    closed.append({"mall": m["name"], "name": t["name"], "chain": classify(t["name"])})
                    row["closed"] += 1
        per_mall.append(row)
    compared = [r for r in per_mall if r["readings"] >= 2]
    n_open = len(opened)
    n_china = sum(1 for o in opened if o["chain"])
    return {
        "method": "snapshot",
        "universe_label": doc.get("universe_label", "25 of the top US malls"),
        "malls_tracked": len(malls),
        "malls_baselined": len(per_mall),
        "malls_compared": len(compared),
        "tracking_since": min(starts) if starts else None,
        "latest_reading": max(lasts) if lasts else None,
        "stores_at_baseline": base_total,
        "china_origin_at_baseline": base_china,
        "opened": n_open,
        "opened_china_origin": n_china,
        "opened_china_origin_share": round(n_china / n_open, 4) if n_open else None,
        "opened_china_origin_list": sorted((o for o in opened if o["chain"]), key=lambda o: (o["mall"], o["name"])),
        "closed": len(closed),
        "closed_china_origin": sum(1 for c in closed if c["chain"]),
        "coming_soon": len(soon_now),
        "coming_soon_china_origin_list": sorted((s for s in soon_now if s["chain"]), key=lambda s: (s["mall"], s["name"])),
        "per_mall": sorted(per_mall, key=lambda r: r["mall"]),
    }

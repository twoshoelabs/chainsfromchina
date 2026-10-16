"""
US app presence — a structure-layer datum (chain_atlas/apps.py). These pin: the live manual/apps.json
validates and carries own-vs-platform records; the pure match scorer; the probe against a FAKE session
(no network); and the three integrations — the dossier structure layer surfaces us_app, the Pro dataset
exposes an `apps` table that is pro-gated (absent public/observer), and the alerts detector emits an
`app_shipped` event when a brand's first US app appears.

Run: .venv/bin/python tests/test_apps.py
"""
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from chain_atlas import apps, dossier, tier_export as T, alerts  # noqa: E402


def fresh():
    con = sqlite3.connect(":memory:")
    con.executescript("""
    CREATE TABLE financial_anchors(anchor_id INTEGER PRIMARY KEY AUTOINCREMENT, brand_id TEXT,
        period TEXT, metric TEXT, value REAL, unit TEXT, page_ref TEXT, source TEXT, source_url TEXT,
        retrieved_at TEXT, confidence TEXT);
    CREATE TABLE revenue_estimates(estimate_id INTEGER PRIMARY KEY AUTOINCREMENT, brand_id TEXT,
        scope TEXT, store_id INTEGER, period TEXT, low REAL, mid REAL, high REAL, unit TEXT,
        method_version TEXT, anchors_used TEXT, store_count_used INTEGER, store_count_as_of TEXT,
        modeled INTEGER, notes TEXT, generated_at TEXT);
    CREATE TABLE fdd_extracts(doc_number TEXT PRIMARY KEY, brand_id TEXT, franchisor TEXT, year INTEGER,
        state TEXT, items_json TEXT, needs_human_read INTEGER, source_url TEXT, retrieved_at TEXT);
    """)
    return con


class _Resp:
    def __init__(self, payload): self._p = payload; self.status_code = 200
    def json(self): return self._p


class _FakeSession:
    """Returns one matching app for CHAGEE, nothing otherwise — no network."""
    def __init__(self): self.headers = {}
    def get(self, url, params=None, timeout=None):
        term = (params or {}).get("term", "").lower()
        if "chagee" in term:
            return _Resp({"results": [
                {"trackId": 1, "trackName": "CHAGEE USA", "artistName": "Chagee",
                 "trackViewUrl": "https://apps.apple.com/us/app/chagee-usa/id6737460668?x=1",
                 "userRatingCount": 39, "currentVersionReleaseDate": "2026-09-01T00:00:00Z"},
                {"trackId": 2, "trackName": "Unrelated App", "artistName": "Someone Else",
                 "userRatingCount": 5}]})
        return _Resp({"results": []})


def main():
    fails = []

    def check(label, got, want=True):
        ok = got == want
        print(("PASS" if ok else "FAIL"), label, "" if ok else f"(got {got!r}, want {want!r})")
        if not ok:
            fails.append(label)

    # --- live store validates + shape ---
    check("manual/apps.json validates", apps.validate(), [])
    v = apps.verified()
    check("verified includes chagee (own)", v.get("chagee", {}).get("kind"), "own")
    check("verified includes a platform app", any(r.get("kind") == "platform" for r in v.values()), True)
    check("record_of known brand", apps.record_of("chagee")["app_name"], "CHAGEE USA")
    check("record_of unknown brand is None", apps.record_of("nope_zzz"), None)

    # --- pure scorer ---
    check("score: name+seller -> high", apps.score("chagee", "CHAGEE USA", "Chagee"), "high")
    check("score: name only -> medium", apps.score("chagee", "Chagee Rewards", "Acme Inc"), "medium")
    check("score: no match -> None", apps.score("chagee", "Panda App", "Acme"), None)
    check("score: too-short term -> None", apps.score("abc", "abcdef", "abc"), None)

    # --- probe against the fake session (no network) ---
    hits = apps.probe(brands=["chagee"], pause=0, session=_FakeSession())
    check("probe finds the chagee candidate", "chagee" in hits, True)
    check("probe strips the query string from the url",
          hits["chagee"][0]["ios_url"].endswith("id6737460668"), True)
    check("probe excludes the unrelated app", all(c["app"] != "Unrelated App" for c in hits["chagee"]), True)

    # --- dossier structure layer surfaces us_app ---
    con = fresh()
    d = dossier.assemble(con, "chagee")
    check("dossier structure carries us_app", d["structure"]["us_app"]["app_name"], "CHAGEE USA")
    check("dossier markdown shows the US app", "US app:" in dossier.render_markdown(d), True)

    # --- Pro dataset: apps table, pro-gated ---
    rds = T.dataset(con, "pro", brands=["chagee"])
    pds = T.dataset(con, "public", brands=["chagee"])
    check("apps table present at pro", "apps" in rds["tables"], True)
    check("apps table absent at public", "apps" not in pds["tables"], True)
    check("apps row for chagee", any(r["brand"] == "chagee" and r["app_name"] == "CHAGEE USA"
                                     for r in rds["tables"]["apps"]), True)
    check("pro aggregates count us_apps", rds["aggregates"]["us_apps"]["own"] >= 1, True)
    check("public has no us_apps aggregate", "us_apps" not in pds["aggregates"], True)

    # --- alerts: app_shipped on a brand's first US app ---
    curr = alerts.snapshot()
    check("snapshot has an apps layer", "chagee" in curr.get("apps", {}), True)
    prev = alerts._slim(curr)
    prev["apps"] = [b for b in prev["apps"] if b != "chagee"]     # pretend chagee had no app last run
    evs = alerts.detect(prev, curr)
    check("app_shipped emitted for chagee", any(e["kind"] == "app_shipped" and e["brand"] == "chagee"
                                                for e in evs), True)

    print("\n" + ("ALL PASS" if not fails else f"{len(fails)} FAIL: " + ", ".join(fails)))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())

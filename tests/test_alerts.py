"""
The PRO event log + alerts (docs/pro_spec.md pillar 2, build order #5). These pin the pure diff detector
(first-run seeding emits nothing; first US entry vs a later single-outlet open; abroad market entry/exit;
home-market scale change; new filing; authoritative closure), the idempotent append (stable ids dedupe),
the lens/since filtering, the grouped digest, and the delivery cursor. All against crafted snapshots and
temp files — never the real event log.

Run: .venv/bin/python tests/test_alerts.py
"""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from chain_atlas import alerts  # noqa: E402


def main():
    fails = []

    def check(label, got, want=True):
        ok = got == want
        print(("PASS" if ok else "FAIL"), label, "" if ok else f"(got {got!r}, want {want!r})")
        if not ok:
            fails.append(label)

    # ---------- pure detect ----------
    base = {"as_of": "2026-10-10",
            "presence": {"haidilao": {"a1": {"address": "1 A St", "city": "Frisco", "state": "TX"}}},
            "closings": {}, "register": {"haidilao": {"CA": {"status": "present", "locations": 2}}},
            "scale": {"mixue": {"total": 45000, "as_of": "2025-03", "confidence": "high"}},
            "anchors": {"mixue": {"group_revenue|2024": {"value": 1}}}}
    curr = {"as_of": "2026-10-16",
            "presence": {
                "haidilao": {"a1": {"address": "1 A St", "city": "Frisco", "state": "TX"},
                             "a2": {"address": "2 B St", "city": "Plano", "state": "TX"}},   # +1 open
                "toys52": {"g1": {"address": "x", "city": "Buford", "state": "GA"},
                           "g2": {"address": "y", "city": "Doraville", "state": "GA"}}},     # NEW entry
            "closings": {"bobobaba": ["glendaleaddr"]},                                      # new closure
            "register": {"haidilao": {"CA": {"status": "present", "locations": 2},
                                      "GB": {"status": "present", "locations": 1}},          # new market
                         "cotti": {"KR": {"status": "exited"}}},                             # exit
            "scale": {"mixue": {"total": 46000, "as_of": "2025-06", "confidence": "high"}},  # scale change
            "anchors": {"mixue": {"group_revenue|2024": {"value": 1},
                                  "net_profit|2024": {"value": 2}}}}                         # new filing

    check("first run (empty prev) emits nothing", alerts.detect({}, curr), [])

    evs = alerts.detect(base, curr)
    by = {}
    for e in evs:
        by.setdefault(e["kind"], []).append(e)
    check("toys52 ENTERED_US emitted", any(e["brand"] == "toys52" for e in by.get("entered_us", [])), True)
    check("entered_us after-count = 2", by["entered_us"][0]["after"], 2)
    check("new entrant does NOT also emit outlet_opened",
          not any(e["brand"] == "toys52" for e in by.get("outlet_opened", [])), True)
    check("haidilao (already present) emits outlet_opened", any(
        e["brand"] == "haidilao" for e in by.get("outlet_opened", [])), True)
    check("haidilao is NOT a new entrant", not any(
        e["brand"] == "haidilao" for e in by.get("entered_us", [])), True)
    check("market_entered GB", any(e["key"] == "GB" for e in by.get("market_entered", [])), True)
    check("market_exited KR", any(e["key"] == "KR" for e in by.get("market_exited", [])), True)
    check("scale_changed before/after", (by["scale_changed"][0]["before"], by["scale_changed"][0]["after"]),
          (45000, 46000))
    check("new_filing net_profit", any("net_profit" in e["key"] for e in by.get("new_filing", [])), True)
    check("closure from closings.json", any(e["brand"] == "bobobaba" for e in by.get("outlet_closed", [])), True)
    check("priority: entered_us sorts first", evs[0]["kind"], "entered_us")
    # no spurious events for unchanged things
    check("unchanged CA market not re-emitted", not any(e["key"] == "CA" for e in by.get("market_entered", [])), True)

    # ---------- idempotent append + load ----------
    tmp = tempfile.mkdtemp()
    log = os.path.join(tmp, "event_log.jsonl")
    check("append writes all", alerts.append(evs, log), len(evs))
    check("re-append writes none (stable-id dedupe)", alerts.append(evs, log), 0)
    check("load round-trips", len(alerts.load(log)), len(evs))
    check("priority stripped from stored rows", all("priority" not in e for e in alerts.load(log)), True)

    # ---------- filter + digest ----------
    loaded = alerts.load(log)
    check("filter by kind", all(e["kind"] == "entered_us"
          for e in alerts.filter_events(loaded, {"kinds": ["entered_us"]})), True)
    check("filter by brand", all(e["brand"] == "mixue"
          for e in alerts.filter_events(loaded, {"brands": ["mixue"]})), True)
    check("filter min_confidence drops medium", all(e["confidence"] == "high"
          for e in alerts.filter_events(loaded, {"min_confidence": "high"})), True)
    d = alerts.digest(loaded)
    check("digest non-empty", bool(d), True)
    check("digest leads with US entrants section", "New US entrants" in d, True)
    check("empty digest is ''", alerts.digest([]), "")

    # ---------- delivery cursor ----------
    cur = os.path.join(tmp, "cursor.json")
    check("all undelivered before cursor", len(alerts.undelivered(loaded, cur)), len(loaded))
    alerts.mark_delivered(loaded, cur)
    check("none undelivered after mark", len(alerts.undelivered(loaded, cur)), 0)

    # ---------- run_detect: seeds, then catches a change, idempotently ----------
    log2 = os.path.join(tmp, "l2.jsonl")
    bl = os.path.join(tmp, "baseline.json")
    n0 = alerts.run_detect(log_path=log2, baseline_path=bl)   # seeds from REAL current data
    check("run_detect first call seeds (no events)", n0, [])
    n1 = alerts.run_detect(log_path=log2, baseline_path=bl)   # nothing changed since seed
    check("run_detect second call (no change) empty", n1, [])
    check("baseline file written", os.path.exists(bl), True)

    print("\n" + ("ALL PASS" if not fails else f"{len(fails)} FAIL: " + ", ".join(fails)))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())

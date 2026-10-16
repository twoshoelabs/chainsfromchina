"""
The verification queue (docs/pro_spec.md build #3) gathers everything awaiting a human verdict into one
prioritized worklist and records verdicts to an append-only log. These tests pin: the DB-backed pulls
(needs_human_read FDD + sub-'high' anchors, from a seeded in-memory db), that file-backed unverified
counts surface, priority ordering, the summary, and the resolve → excluded-from-queue round-trip. The
file-backed layers read live manual/ data with loose assertions.

Run: .venv/bin/python tests/test_verify.py
"""
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from chain_atlas import verify  # noqa: E402


def fresh():
    con = sqlite3.connect(":memory:")
    con.executescript("""
    CREATE TABLE financial_anchors(anchor_id INTEGER PRIMARY KEY AUTOINCREMENT, brand_id TEXT,
        period TEXT, metric TEXT, value REAL, unit TEXT, page_ref TEXT, source TEXT, source_url TEXT,
        retrieved_at TEXT, confidence TEXT);
    CREATE TABLE fdd_extracts(doc_number TEXT PRIMARY KEY, brand_id TEXT, franchisor TEXT, year INTEGER,
        state TEXT, items_json TEXT, needs_human_read INTEGER, source_url TEXT, retrieved_at TEXT);
    """)
    return con


def main():
    fails = []

    def check(label, got, want=True):
        ok = got == want
        print(("PASS" if ok else "FAIL"), label, "" if ok else f"(got {got!r}, want {want!r})")
        if not ok:
            fails.append(label)

    con = fresh()
    con.execute("INSERT INTO fdd_extracts(doc_number,brand_id,year,needs_human_read,source_url) "
                "VALUES('doc-1','cotti',2026,1,'https://mn')")
    con.execute("INSERT INTO fdd_extracts(doc_number,brand_id,year,needs_human_read) "
                "VALUES('doc-2','miniso',2026,0)")   # NOT flagged -> must not appear
    con.execute("INSERT INTO financial_anchors(brand_id,period,metric,value,confidence,source,source_url) "
                "VALUES('aunteajenny','2025','store_count',11449,'medium','press','https://example.com/a1.pdf')")
    con.execute("INSERT INTO financial_anchors(brand_id,period,metric,value,confidence,source) "
                "VALUES('mixue','2025','group_revenue',33559923,'high','HKEX')")  # high -> must not appear
    con.commit()

    tmp = os.path.join(tempfile.mkdtemp(), "verifications.jsonl")
    q = verify.queue(con, resolved_path=tmp)
    ids = {i["id"] for i in q}
    by_reason = {r: [i for i in q if i["reason"] == r] for r in verify.PRIORITY}

    check("flagged FDD queued", "fdd:doc-1" in ids, True)
    check("UNflagged FDD not queued", "fdd:doc-2" not in ids, True)
    check("sub-high anchor queued", "fa:aunteajenny:store_count:2025" in ids, True)
    check("high anchor not queued", "fa:mixue:group_revenue:2025" not in ids, True)
    check("needs_human_read item has reason", by_reason["needs_human_read"] and by_reason["needs_human_read"][0]["id"], "fdd:doc-1")
    check("unverified_anchor present", len(by_reason["unverified_anchor"]) >= 1, True)
    check("anchor item carries a clickable source_url",
          by_reason["unverified_anchor"][0]["source_url"], "https://example.com/a1.pdf")
    # a non-URL source does not become a link (the china_stores 'source' is a label, not a URL)
    cs = next((i for i in q if i["id"] == "cs:juewei"), None)
    check("non-URL source stays unlinked", cs and cs.get("source_url"), None)
    # file-backed: a known sub-'high' china_stores total (juewei is low from the 2026-10-15 intel refresh)
    check("china_stores unverified_count surfaces", any(i["id"] == "cs:juewei" for i in q), True)
    check("uncertain sightings surface", len(by_reason["uncertain"]) >= 1, True)

    # priority: needs_human_read (1) sorts before unverified_count (5)
    order = [i["reason"] for i in q]
    if "needs_human_read" in order and "unverified_count" in order:
        check("priority ordering (needs_human_read before unverified_count)",
              order.index("needs_human_read") < order.index("unverified_count"), True)

    s = verify.summary(q)
    check("summary total matches", s["total"], len(q))
    check("summary by_reason has needs_human_read", s["by_reason"].get("needs_human_read"), 1)

    # render is a string with the header
    check("render produces header", "Verification queue" in verify.render(q), True)

    # resolve round-trip: a verdict drops the item from the next queue
    verify.record_verdict("fdd:doc-1", "verified", by="owner", note="read the PDF", path=tmp)
    check("verdict recorded", verify.resolved(tmp).get("fdd:doc-1", {}).get("verdict"), "verified")
    q2 = verify.queue(con, resolved_path=tmp)
    check("resolved item dropped from queue", "fdd:doc-1" not in {i["id"] for i in q2}, True)
    check("queue shrank by exactly one", len(q2), len(q) - 1)
    # include_resolved keeps it
    q3 = verify.queue(con, include_resolved=True, resolved_path=tmp)
    check("include_resolved keeps it", "fdd:doc-1" in {i["id"] for i in q3}, True)

    # --- 'watch' verdict (real-but-not-open) + evidence: valid, drops from queue, listed by watching() ---
    watch_id = next((i["id"] for i in q2 if i["reason"] == "uncertain"), None)
    verify.record_verdict(watch_id, "watch", by="owner", note="coming soon 2026",
                          evidence="sources/chahalo/shot.png", path=tmp)
    rv = verify.resolved(tmp).get(watch_id, {})
    check("watch is a valid verdict", rv.get("verdict"), "watch")
    check("evidence stored on the verdict", rv.get("evidence"), "sources/chahalo/shot.png")
    check("watching() lists the watch item", any(w["queue_id"] == watch_id for w in verify.watching(tmp)), True)
    q4 = verify.queue(con, resolved_path=tmp)
    check("watched item drops from queue (not re-asked)", watch_id not in {i["id"] for i in q4}, True)

    # bad verdict still raises
    raised = False
    try:
        verify.record_verdict("x", "maybe", path=tmp)
    except ValueError:
        raised = True
    check("bad verdict rejected", raised, True)

    print("\n" + ("ALL PASS" if not fails else f"{len(fails)} FAIL: " + ", ".join(fails)))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())

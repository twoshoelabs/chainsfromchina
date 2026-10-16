"""
The owner console (the private, localhost submit+verify workbench) is a thin HTTP dispatcher over three
pure handlers. These tests exercise those handlers directly (no sockets): submit validates + appends,
an invalid/bad-JSON submit is rejected without writing, verdicts append, and the queue reflects a seeded
DB and drops a resolved item. The served page carries the form + queue.

Run: .venv/bin/python tests/test_console.py
"""
import json
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from chain_atlas import console  # noqa: E402


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

    tmp = tempfile.mkdtemp()
    subs = os.path.join(tmp, "submissions.jsonl")
    verd = os.path.join(tmp, "verifications.jsonl")

    # --- submit: valid ---
    rec = {"brand": "mixue", "dimension": "scale", "metric": "store_count_total", "value": 59823,
           "as_of": "2025-12-31", "source": "FY2025 HKEX", "confidence": "high", "submitter": "owner"}
    st, pay = console.handle_submit(json.dumps(rec), subs_path=subs)
    check("valid submit -> 200", st, 200)
    check("valid submit ok + id stamped", pay["ok"] and pay["record"]["id"].startswith("sub_"), True)
    check("valid submit wrote one row", sum(1 for _ in open(subs)), 1)

    # --- submit: invalid (missing required) writes nothing ---
    st, pay = console.handle_submit(json.dumps({"dimension": "scale"}), subs_path=subs)
    check("invalid submit -> 400", st, 400)
    check("invalid submit ok=False", pay["ok"], False)
    check("invalid submit wrote nothing extra", sum(1 for _ in open(subs)), 1)

    # --- submit: bad JSON ---
    st, pay = console.handle_submit("{not json", subs_path=subs)
    check("bad JSON -> 400", st, 400)

    # --- verdict: valid + bad ---
    st, pay = console.handle_verdict(json.dumps({"queue_id": "cs:juewei", "verdict": "verified"}),
                                     verdict_path=verd)
    check("valid verdict -> 200", st, 200)
    check("verdict appended", sum(1 for _ in open(verd)), 1)
    st, _ = console.handle_verdict(json.dumps({"queue_id": "x", "verdict": "maybe"}), verdict_path=verd)
    check("bad verdict -> 400", st, 400)

    # --- queue: reflects a seeded DB; a resolved item is excluded ---
    con = fresh()
    con.execute("INSERT INTO fdd_extracts(doc_number,brand_id,year,needs_human_read) VALUES('d1','cotti',2026,1)")
    con.commit()
    st, pay = console.handle_queue(con, verdict_path=verd)
    check("queue -> 200", st, 200)
    ids = {i["id"] for i in pay["items"]}
    check("seeded flagged FDD in queue", "fdd:d1" in ids, True)
    check("already-resolved cs:juewei excluded", "cs:juewei" not in ids, True)
    check("summary total matches items", pay["summary"]["total"], len(pay["items"]))

    # --- the served page carries the form + queue ---
    check("page has submit form field", "id=value" in console._PAGE, True)
    check("page has queue container", 'id=queue' in console._PAGE, True)
    check("page is localhost-private labelled", "PRIVATE" in console._PAGE, True)

    print("\n" + ("ALL PASS" if not fails else f"{len(fails)} FAIL: " + ", ".join(fails)))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())

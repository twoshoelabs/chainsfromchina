"""
The owner console (the private, localhost drop-sources + verify workbench) is a thin HTTP dispatcher
over pure handlers. These tests exercise them directly (no sockets): a verdict appends (and a 'watch'
verdict with a screenshot saves the image into the chain's evidence library), the queue reflects a
seeded DB and drops a resolved item, and a dropped source lands in the library. Served page has it all.

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
    verd = os.path.join(tmp, "verifications.jsonl")

    # --- verdict: valid + bad + watch-with-screenshot ---
    st, pay = console.handle_verdict(json.dumps({"queue_id": "cs:juewei", "verdict": "verified"}),
                                     verdict_path=verd)
    check("valid verdict -> 200", st, 200)
    check("verdict appended", sum(1 for _ in open(verd)), 1)
    st, _ = console.handle_verdict(json.dumps({"queue_id": "x", "verdict": "maybe"}), verdict_path=verd)
    check("bad verdict -> 400", st, 400)
    # a 'watch' verdict with a screenshot saves the image into the chain's evidence library;
    # `evidence` is a LIST of paths. The legacy singular `screenshot` is still accepted (-> one-item list).
    import base64
    vlib = os.path.join(tmp, "vsources")
    shot = base64.b64encode(b"\x89PNG fake image").decode()
    st, pay = console.handle_verdict(json.dumps(
        {"queue_id": "sight:chahalo|1403 Research", "verdict": "watch", "brand": "chahalo",
         "note": "coming soon 2026", "screenshot": {"name": "rockville.png", "b64": shot}}),
        verdict_path=verd, lib=vlib)
    check("watch verdict -> 200", st, 200)
    check("watch verdict recorded", pay["verdict"]["verdict"], "watch")
    check("evidence is a list", isinstance(pay["verdict"]["evidence"], list), True)
    check("legacy screenshot -> one evidence path", pay["verdict"]["evidence"][0].endswith(".png"), True)
    check("evidence file exists under chain", os.path.exists(os.path.join(
        tmp, "vsources", "chahalo", os.path.basename(pay["verdict"]["evidence"][0]))), True)
    # MULTIPLE screenshots in one verdict -> multiple evidence files, all saved under the chain
    shots = [{"name": "a.png", "b64": base64.b64encode(b"\x89PNG a").decode()},
             {"name": "b.png", "b64": base64.b64encode(b"\x89PNG b").decode()}]
    st, pay = console.handle_verdict(json.dumps(
        {"queue_id": "sight:makkee|x", "verdict": "watch", "brand": "makkee", "screenshots": shots}),
        verdict_path=verd, lib=vlib)
    check("multi-screenshot verdict -> 200", st, 200)
    check("two evidence paths recorded", len(pay["verdict"]["evidence"]), 2)
    check("both evidence files exist", all(os.path.exists(os.path.join(
        tmp, "vsources", "makkee", os.path.basename(p))) for p in pay["verdict"]["evidence"]), True)
    # a verdict with no screenshots -> evidence None
    st, pay = console.handle_verdict(json.dumps(
        {"queue_id": "cs:x", "verdict": "verified"}), verdict_path=verd, lib=vlib)
    check("no-screenshot verdict has null evidence", pay["verdict"]["evidence"], None)

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

    # --- source library handlers (drop + list) ---
    import base64
    lib = os.path.join(tmp, "sources")
    st, pay = console.handle_source(json.dumps(
        {"chain": "chabaidao", "kind": "press", "title": "A report", "text": "some body text"}), lib=lib)
    check("drop text source -> 200", st, 200)
    check("drop returns source id", pay["ok"] and pay["source"]["id"].startswith("src_"), True)
    st, pay = console.handle_source(json.dumps(
        {"chain": "mixue", "kind": "financial", "title": "FY25",
         "file": {"name": "r.pdf", "b64": base64.b64encode(b"%PDF fake").decode()}}), lib=lib)
    check("drop file source -> 200", st, 200)
    check("drop file recorded", pay["source"]["file"].endswith(".pdf"), True)
    st, pay = console.handle_source(json.dumps({"kind": "press", "title": "x", "text": "t"}), lib=lib)
    check("drop without chain -> 400", st, 400)
    st, pay = console.handle_source("{bad", lib=lib)
    check("drop bad JSON -> 400", st, 400)
    # library view reflects the drops
    st, pay = console.handle_library(lib=lib)
    check("library -> 200", st, 200)
    check("library by_chain counts", pay["by_chain"], {"chabaidao": 1, "mixue": 1})
    check("library recent has titles", any(s["title"] == "A report" for s in pay["recent"]), True)

    # --- the served page carries the source drop + library + queue ---
    check("page has the source drop", "Drop a source" in console._PAGE, True)
    check("page has the content textarea", "id=text" in console._PAGE, True)
    check("page has the library", "Library" in console._PAGE, True)
    check("page has queue container", 'id=queue' in console._PAGE, True)
    check("page has the per-item screenshot space", "makeScreenSpace" in console._PAGE, True)
    check("page supports paste into the screenshot space", "'paste'" in console._PAGE, True)
    check("page is localhost-private labelled", "PRIVATE" in console._PAGE, True)

    print("\n" + ("ALL PASS" if not fails else f"{len(fails)} FAIL: " + ", ".join(fails)))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())

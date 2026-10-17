"""
The source/evidence library stores the raw research corpus (press/financial/analyst/filings) per chain,
git-ignored and local. These tests pin: validation, that text and files are written under
lib/<chain>/ with an index line + excerpt, the content-required and bad-metadata rejections, the stable
id, and list/by_chain. All against a temp library dir (never the real manual/sources/).

Run: .venv/bin/python tests/test_sources.py
"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from chain_atlas import sources as SR  # noqa: E402


def main():
    fails = []

    def check(label, got, want=True):
        ok = got == want
        print(("PASS" if ok else "FAIL"), label, "" if ok else f"(got {got!r}, want {want!r})")
        if not ok:
            fails.append(label)

    lib = Path(tempfile.mkdtemp()) / "sources"

    # --- add a pasted-text source ---
    rec = SR.add_source({"chain": "chabaidao", "kind": "press", "title": "ChaPanda hits 100 overseas",
                         "publisher": "Caixin", "date": "2026-03-23", "url": "https://caixin",
                         "tags": ["overseas"], "note": "scale"},
                        text="ChaPanda opened its 100th overseas store... as of Oct 2026.", lib=lib)
    check("text source id", rec["id"].startswith("src_"), True)
    check("text file written", (lib / "chabaidao" / f"{rec['id']}.txt").exists(), True)
    check("text path recorded", rec["text"], f"sources/chabaidao/{rec['id']}.txt")
    check("excerpt captured", rec["excerpt"].startswith("ChaPanda opened"), True)
    check("index line appended", sum(1 for _ in open(lib / "index.jsonl")), 1)

    # --- add a file source ---
    recf = SR.add_source({"chain": "chabaidao", "kind": "financial", "title": "FY2025 Annual Report",
                          "date": "2026-04-24"},
                         file_bytes=b"%PDF-1.5 fake", file_name="chapanda_FY2025.PDF", lib=lib)
    check("file source stored", (lib / "chabaidao" / f"{recf['id']}.pdf").exists(), True)
    check("file ext normalised to pdf", recf["file"].endswith(".pdf"), True)
    check("orig filename kept", recf["orig_name"], "chapanda_FY2025.PDF")
    check("byte count recorded", recf["bytes"], len(b"%PDF-1.5 fake"))

    # --- validation + content requirements ---
    bad = []
    try:
        SR.add_source({"chain": "", "kind": "press", "title": "x"}, text="t", lib=lib)
    except ValueError as e:
        bad.append(str(e))
    check("missing chain rejected", any("chain is required" in b for b in bad), True)
    try:
        SR.add_source({"chain": "x", "kind": "blog", "title": "y"}, text="t", lib=lib)
    except ValueError as e:
        check("bad kind rejected", "kind must be one of" in str(e), True)
    try:
        SR.add_source({"chain": "x", "kind": "press", "title": "y"}, lib=lib)   # no content
    except ValueError as e:
        check("no-content rejected", "needs content" in str(e), True)
    try:
        SR.add_source({"chain": "x", "kind": "press", "title": "y", "date": "Oct 2026"}, text="t", lib=lib)
    except ValueError as e:
        check("bad date rejected", "date must be" in str(e), True)
    # month precision (YYYY-MM) is accepted — many articles are dated only to the month (own lib,
    # so it doesn't disturb the list/by_chain counts below)
    mlib = Path(tempfile.mkdtemp()) / "sources"
    mrec = SR.add_source({"chain": "x", "kind": "press", "title": "month-dated", "date": "2023-05"},
                         text="t", lib=mlib)
    check("YYYY-MM date accepted", mrec["date"], "2023-05")

    # --- stable id (same citation -> same id) ---
    a = {"chain": "mixue", "title": "T", "date": "2026-01-01", "url": "u"}
    check("stable id", SR.source_id(a), SR.source_id(dict(a)))

    # --- list + by_chain ---
    SR.add_source({"chain": "mixue", "kind": "analyst", "title": "Mixue note"}, text="buy", lib=lib)
    allrows = SR.list_sources(lib=lib)
    check("list returns all", len(allrows), 3)
    check("list newest first", allrows[0]["chain"], "mixue")
    check("list filters by chain", len(SR.list_sources("chabaidao", lib=lib)), 2)
    check("by_chain counts", SR.by_chain(lib=lib), {"chabaidao": 2, "mixue": 1})
    # nothing leaked to the real library
    check("index is valid jsonl", all(json.loads(l) for l in open(lib / "index.jsonl") if l.strip()), True)

    print("\n" + ("ALL PASS" if not fails else f"{len(fails)} FAIL: " + ", ".join(fails)))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())

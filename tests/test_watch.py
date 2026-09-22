"""
The national watcher runs entirely from scripts/jurisdictions.json, so the registry has to be
well-formed and the driver's pure helpers have to be right. Neither talks to the network here.

Run: .venv/bin/python tests/test_watch.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import watch  # noqa: E402

REG = json.loads((ROOT / "scripts" / "jurisdictions.json").read_text())


def main():
    fails = []

    def check(label, got, want):
        ok = got == want
        print(f"  {'PASS' if ok else 'FAIL'}  {label}: {got!r}" + ("" if ok else f"  (want {want!r})"))
        if not ok:
            fails.append(label)

    # Registry hygiene: every Socrata entry declares the columns the driver will read.
    required = ["id", "platform", "domain", "resource", "name_field", "addr_fields",
                "date_field", "state", "states"]
    ids = set()
    ok_schema = True
    for j in REG["jurisdictions"]:
        ids.add(j["id"])
        for f in required:
            if f not in j:
                ok_schema = False
                print(f"    registry {j.get('id','?')} missing {f}")
    check("every jurisdiction declares the required fields", ok_schema, True)
    check("jurisdiction ids are unique", len(ids), len(REG["jurisdictions"]))

    # Date normalisation: ISO timestamps and YYYYMMDD both reduce to a date; junk to "".
    check("ISO timestamp", watch.iso("2026-08-24T00:00:00.000"), "2026-08-24")
    check("YYYYMMDD", watch.iso("20260409"), "2026-04-09")
    check("Socrata sentinel is a date, filtered elsewhere", watch.iso("1900-01-01T00:00:00"), "1900-01-01")
    check("blank -> empty", watch.iso(""), "")

    # The pre-opening rule: still pre-opening only if it has NO operating inspection yet.
    import re
    PRE = watch.PREOPEN_RE
    def is_pre(types, dates):
        real = [d for d in dates if d and d != "1900-01-01"]
        not_yet = bool(dates) and not real
        operating = [t for t in types if not PRE.search(t)]
        return not_yet or (bool(types) and not operating)
    check("only a pre-permit inspection -> pre-opening",
          is_pre(["Pre-permit (Non-operational) / Initial Inspection"], ["2026-08-01"]), True)
    check("has a routine inspection -> operating, not pre-opening",
          is_pre(["Pre-permit (Non-operational) / Initial Inspection", "Cycle Inspection"], ["2026-08-01"]), False)
    check("registered but not inspected -> pre-opening", is_pre([], ["1900-01-01"]), True)

    print("\n" + ("ALL PASS" if not fails else f"{len(fails)} FAILED: {fails}"))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())

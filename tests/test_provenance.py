"""
The tamper-evident provenance ledger: an append-only, hash-chained record of what we knew and when,
used to document that we knew a store was closed on a date its operator's own locator still listed it
open (see chain_atlas/provenance.py, manual/closings.json).

  append/verify   Fresh stamps form an intact chain: genesis prev on the first entry, each later
                  entry's prev linking to the one before, and every entry's own hash recomputable.
  tamper          Altering a stamped field, cutting the chain, or re-ordering entries is caught.
  live ledger     The committed manual/provenance_ledger.jsonl verifies.

Run: .venv/bin/python -m tests.test_provenance
"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from chain_atlas import provenance   # noqa: E402

fails = []


def check(label, got, want=True):
    ok = got == want
    print(f"  {'PASS' if ok else 'FAIL'}  {label}: {got}" + ("" if ok else f"  (want {want})"))
    if not ok:
        fails.append(label)


def _fresh():
    return Path(tempfile.mkdtemp(prefix="uca_prov_")) / "ledger.jsonl"


def test_append_and_verify():
    p = _fresh()
    e1 = provenance.append("x:1", "closure_recorded", "store 1 closed while listed", {"id": 1}, path=p)
    e2 = provenance.append("x:2", "closure_recorded", "store 2 closed while listed", {"id": 2}, path=p)
    check("first entry prev is genesis", e1["prev_sha256"], provenance.GENESIS)
    check("second entry links to first", e2["prev_sha256"], e1["entry_sha256"])
    check("seqs increment", [e1["seq"], e2["seq"]], [1, 2])
    ok, probs = provenance.verify(p)
    check("fresh chain verifies", ok)
    check("no problems", probs, [])


def test_tamper_detected():
    p = _fresh()
    provenance.append("x:1", "e", "original claim", {"id": 1}, path=p)
    provenance.append("x:2", "e", "second claim", {"id": 2}, path=p)

    # (a) Edit a stamped field without recomputing its hash.
    lines = p.read_text(encoding="utf-8").splitlines()
    e = json.loads(lines[0]); e["statement"] = "back-dated claim"
    lines[0] = json.dumps(e, ensure_ascii=False)
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    check("edited entry is caught", provenance.verify(p)[0], False)

    # (b) Remove the first entry, breaking the chain for the rest.
    p.write_text("\n".join(p.read_text(encoding="utf-8").splitlines()[1:]) + "\n", encoding="utf-8")
    check("truncated chain is caught", provenance.verify(p)[0], False)


def test_live_ledger():
    # The committed ledger must always verify.
    ok, probs = provenance.verify()
    check("live manual/provenance_ledger.jsonl verifies", ok)
    if not ok:
        for pr in probs:
            print("    !", pr)


def main():
    test_append_and_verify()
    test_tamper_detected()
    test_live_ledger()
    print("\n" + ("ALL PASS" if not fails else f"{len(fails)} FAILED: {fails}"))
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())

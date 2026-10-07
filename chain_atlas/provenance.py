"""
Tamper-evident provenance ledger — an append-only, hash-chained record of what this project knew and
when. Its first job is to document a gap between a company's own listing and reality: that we knew an
outlet was closed on a date the operator's own store locator still showed it open. The closure
signal may be a field visit or a third-party listing such as a Google "Permanently closed" banner;
an aggregator banner is recorded ONLY from a screenshot a person captured by hand (method
"manual_screenshot"), never an automated query or scrape, to stay within that platform's terms.

Each entry links to the one before it by hash — entry N stores the SHA-256 of entry N-1 — so no past
entry can be altered, removed or back-dated without breaking the chain for every entry after it. With
the chain head committed to git, any such rewrite is detectable. `verify()` walks the chain and
reports the first break.

An entry is a claim about WHEN WE RECORDED something: `ts` is the stamp time, and the evidence dates
(when a closure was observed, when the brand still listed it) live inside the stamped statement and
content. It is not a live mirror of a record and is not expected to change when that record is later
edited or retired; what is proven is the content as it stood when it was stamped.

This is an internal integrity record. Per-location closure detail built on top of it is Pro-tier and
is exported only to the access-controlled location, never to the public map/data. See closings.py,
manual/closings.json and cfc-analytics-paywall.
"""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

LEDGER_PATH = Path(__file__).resolve().parents[1] / "manual" / "provenance_ledger.jsonl"
GENESIS = "0" * 64

# The fields that are bound by the entry hash. `entry_sha256` is derived from exactly these, in this
# order-independent (sorted) canonical form, so verify() can recompute and catch any edit.
CORE_FIELDS = ("seq", "ts", "record_id", "event", "statement", "content_sha256", "prev_sha256")


def _canon(obj) -> bytes:
    """Deterministic bytes for hashing: sorted keys, no whitespace, UTF-8, non-ASCII preserved."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _sha(obj) -> str:
    return hashlib.sha256(_canon(obj)).hexdigest()


def load(path: Path | None = None) -> list[dict]:
    """Read the ledger as a list of entries, oldest first, or an empty list if there is none."""
    p = path or LEDGER_PATH
    if not p.exists():
        return []
    return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]


def _core(entry: dict) -> dict:
    return {k: entry.get(k) for k in CORE_FIELDS}


def append(record_id: str, event: str, statement: str, content, *, path: Path | None = None) -> dict:
    """Stamp a new entry onto the chain and return it.

    `content` is the record being attested — it is hashed into `content_sha256`, not stored in full,
    so the ledger proves what was stamped without duplicating (and later drifting from) the record.
    `statement` is the human-readable, immutable claim; `record_id` identifies what it is about
    (e.g. "moge:st-johns-fl"); `event` is a short slug (e.g. "closure_recorded").
    """
    p = path or LEDGER_PATH
    chain = load(p)
    seq = len(chain) + 1
    prev = chain[-1]["entry_sha256"] if chain else GENESIS
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    core = {"seq": seq, "ts": ts, "record_id": record_id, "event": event,
            "statement": statement, "content_sha256": _sha(content), "prev_sha256": prev}
    entry = {**core, "entry_sha256": _sha(core)}
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def verify(path: Path | None = None) -> tuple[bool, list[str]]:
    """Walk the chain and return (ok, problems): checks sequence, prev-hash linkage and each entry's
    own hash, so any altered, inserted, removed or re-ordered entry is reported."""
    chain = load(path)
    problems: list[str] = []
    prev = GENESIS
    for i, e in enumerate(chain, 1):
        rid = e.get("record_id")
        if e.get("seq") != i:
            problems.append(f"entry {i}: seq is {e.get('seq')!r}, expected {i}")
        if e.get("prev_sha256") != prev:
            problems.append(f"entry {i} ({rid}): prev hash does not link to entry {i - 1}")
        if _sha(_core(e)) != e.get("entry_sha256"):
            problems.append(f"entry {i} ({rid}): contents have been altered since it was stamped")
        prev = e.get("entry_sha256")
    return (not problems, problems)


def summary(path: Path | None = None) -> dict:
    chain = load(path)
    ok, problems = verify(path)
    return {"entries": len(chain), "ok": ok, "problems": problems,
            "head": chain[-1]["entry_sha256"] if chain else GENESIS}

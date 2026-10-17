"""
The source/evidence library — the raw research corpus PRO is built FROM (docs/pro_spec.md §2/§3).

This is where thorough material lands per chain: press reports, financial filings, analyst notes,
company statements — the depth that makes PRO real. Each source keeps the actual content (pasted text
and/or an uploaded file) plus citation metadata; a dossier's facts and a financial_anchor are then
EXTRACTED from these, each pointing back here for provenance. The structured facts get committed; the
source documents do NOT — they are often copyrighted and large, so `manual/sources/` is git-ignored and
stays on the owner's machine (the access-controlled evidence store).

LAYOUT. `manual/sources/<chain>/<id>.<ext>` holds each uploaded file; `<id>.txt` holds pasted text; and
`manual/sources/index.jsonl` is the lean, scannable metadata index (one line per source). Append-only,
like the other intake logs. Reached through the private owner console ('Drop a source') or `add_source()`.
"""
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
LIB = _ROOT / "manual" / "sources"
INDEX = LIB / "index.jsonl"

KINDS = {"press", "financial", "analyst", "filing", "company", "other"}
_DATE = re.compile(r"^\d{4}-\d{2}(-\d{2})?$")   # full date, or month precision (YYYY-MM)
_SAFE_EXT = re.compile(r"[^A-Za-z0-9]+")


def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _ext(file_name: str) -> str:
    """A safe lowercase extension (<=8 chars) from an uploaded filename; 'bin' if none."""
    e = (file_name or "").rsplit(".", 1)
    return (_SAFE_EXT.sub("", e[1]).lower()[:8] or "bin") if len(e) == 2 else "bin"


def source_id(meta: dict) -> str:
    """Stable id from the citation identity (chain + title + date + url) — re-dropping dedupes."""
    key = "|".join(str(meta.get(k, "")) for k in ("chain", "title", "date", "url"))
    return "src_" + hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]


def validate(meta: dict) -> list:
    """Errors ([] = ok): chain, a known kind and a title are required; date, if given, must be ISO."""
    errs = []
    if not meta.get("chain"):
        errs.append("chain is required")
    if meta.get("kind") not in KINDS:
        errs.append(f"kind must be one of {sorted(KINDS)}")
    if not (meta.get("title") or "").strip():
        errs.append("title is required")
    if meta.get("date") and not _DATE.match(str(meta["date"])):
        errs.append("date must be YYYY-MM-DD or YYYY-MM")
    return errs


def add_source(meta: dict, text: str = None, file_bytes: bytes = None, file_name: str = None,
               lib: Path = LIB) -> dict:
    """
    name:      add_source
    purpose:   Store one source — its content (text and/or a file) and citation metadata — in the library.
    arguments: meta — {chain, kind, title, publisher?, date?, url?, tags?, note?, submitter?}; text — pasted
               content; file_bytes/file_name — an uploaded document; lib — the library root (for tests).
    returns:   the saved index record.
    effects:   Writes under lib/<chain>/ and appends one line to the index. Raises ValueError on a hard
               validation error, or if neither text nor a file was supplied (a source must have content).
    other:     Content files are named by the stable id, so re-dropping the same citation overwrites its
               files and appends a fresh index line (append-only history); the index 'excerpt' makes the
               corpus scannable without opening files.
    """
    errs = validate(meta)
    if errs:
        raise ValueError("invalid source: " + "; ".join(errs))
    if not (text and text.strip()) and not file_bytes:
        raise ValueError("a source needs content: paste text or attach a file")
    chain = str(meta["chain"]).strip()
    sid = source_id(meta)
    cdir = Path(lib) / chain
    cdir.mkdir(parents=True, exist_ok=True)

    rec = {"id": sid, "chain": chain, "kind": meta["kind"], "title": meta["title"].strip(),
           "publisher": (meta.get("publisher") or "").strip() or None,
           "date": meta.get("date") or None, "url": (meta.get("url") or "").strip() or None,
           "tags": meta.get("tags") or [], "note": (meta.get("note") or "").strip() or None,
           "submitter": meta.get("submitter") or "owner", "added_at": _utcnow(),
           "file": None, "orig_name": None, "text": None, "excerpt": None}

    if text and text.strip():
        tp = cdir / f"{sid}.txt"
        tp.write_text(text, encoding="utf-8")
        rec["text"] = f"sources/{chain}/{sid}.txt"
        rec["excerpt"] = re.sub(r"\s+", " ", text).strip()[:240]
    if file_bytes:
        ext = _ext(file_name)
        fp = cdir / f"{sid}.{ext}"
        fp.write_bytes(file_bytes)
        rec["file"] = f"sources/{chain}/{sid}.{ext}"
        rec["orig_name"] = file_name
        rec["bytes"] = len(file_bytes)

    idx = Path(lib) / "index.jsonl"             # lib (and lib/<chain>) already created above
    with open(idx, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def list_sources(chain: str = None, lib: Path = LIB) -> list:
    """Every source in the index (latest first), optionally filtered to one chain."""
    idx = Path(lib) / "index.jsonl"
    out = []
    try:
        with open(idx, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    r = json.loads(line)
                    if chain is None or r.get("chain") == chain:
                        out.append(r)
    except FileNotFoundError:
        return []
    out.reverse()
    return out


def by_chain(lib: Path = LIB) -> dict:
    """Source counts per chain — the shape of the corpus (how much depth each chain has)."""
    counts = {}
    for r in list_sources(lib=lib):
        counts[r.get("chain")] = counts.get(r.get("chain"), 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: -kv[1]))

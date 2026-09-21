"""
The international register: which PRC-origin chains have set up in which markets.

A REGISTER, NOT A CENSUS, and the distinction is the whole design. Everything else in this
project is something the collector saw for itself and can produce a gzipped raw capture for.
Nothing here is. These are facts read out of company filings, exchange announcements and the
trade press, typed in by hand — so every row carries the date it was true, how far it should be
trusted, and where it came from, and the reader is told which kind of claim they are looking at.

Three rules keep it honest:

  * A count that is not published is `null`. Never inferred, never interpolated from a regional
    total. Super Hi reports 13 restaurants across Japan AND South Korea; this file records that
    as a note on both and a count on neither, because an invented split is worse than a blank.
  * `no_evidence` is not `none`. It means a search did not find a presence, which is a statement
    about the search. A chain that quietly opened in Osaka last month is `no_evidence` here and
    the register says so rather than asserting absence.
  * Nothing is daily. Entries carry a `reviewed` date and go stale; `--stale` lists what has not
    been looked at in ninety days, because the failure mode of a hand-kept register is not being
    wrong on the day it is written, it is being believed a year later.
"""
import json
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

REGISTER_PATH = Path(__file__).resolve().parents[1] / "register.json"
STALE_DAYS = 90

STATUSES = {"present", "announced", "exited", "no_evidence"}
CONFIDENCE = {"high", "medium", "low"}
PRECISION = {"day", "month", "year", None}


def load(path: Path | None = None) -> dict:
    """
    name:      load
    purpose:   Read and validate register.json.
    arguments: path — defaults to the repo's register.json
    returns:   dict
    effects:   None
    other:     Raises ValueError listing every problem at once rather than the first, because a
               hand-edited file usually has more than one.
    """
    d = json.loads((path or REGISTER_PATH).read_text(encoding="utf-8"))
    problems = validate(d)
    if problems:
        raise ValueError("register.json is invalid:\n  " + "\n  ".join(problems))
    return d


def validate(d: dict) -> list[str]:
    """
    name:      validate
    purpose:   Check every entry against the schema and the project's own evidence rules.
    arguments: d — the parsed register
    returns:   list of human-readable problems, empty when clean
    effects:   None
    other:     The interesting checks are not the type checks: a claim of presence with no
               source and no note is rejected, and a count with no as-of date is rejected,
               because an undated number is the thing this file exists to prevent.
    """
    out, seen = [], set()
    for i, e in enumerate(d.get("entries", [])):
        at = f"entry {i} ({e.get('chain')}/{e.get('market')})"
        if e.get("chain") not in d.get("chains", {}):
            out.append(f"{at}: unknown chain")
        if e.get("market") not in d.get("markets", {}):
            out.append(f"{at}: unknown market")
        key = (e.get("chain"), e.get("market"))
        if key in seen:
            out.append(f"{at}: duplicate chain/market pair")
        seen.add(key)
        if e.get("status") not in STATUSES:
            out.append(f"{at}: status must be one of {sorted(STATUSES)}")
        if e.get("confidence") not in CONFIDENCE:
            out.append(f"{at}: confidence must be one of {sorted(CONFIDENCE)}")
        if e.get("precision") not in PRECISION:
            out.append(f"{at}: precision must be one of day/month/year/null")
        if e.get("locations") is not None:
            if not isinstance(e["locations"], int) or e["locations"] < 0:
                out.append(f"{at}: locations must be a non-negative integer or null")
            if not e.get("locations_as_of"):
                out.append(f"{at}: a count needs locations_as_of — an undated number is a rumour")
        if e.get("first_opened") and not e.get("precision"):
            out.append(f"{at}: first_opened needs a precision (day/month/year)")
        if e.get("status") == "present" and not e.get("sources") and not e.get("note"):
            out.append(f"{at}: a claim of presence needs a source or an explaining note")
        if not e.get("reviewed"):
            out.append(f"{at}: missing reviewed date")
    return out


def matrix(d: dict) -> tuple[list[str], list[str], dict]:
    """
    name:      matrix
    purpose:   Arrange the register as chains x markets for display.
    arguments: d
    returns:   (chain_ids, market_codes, {(chain, market): entry})
    effects:   None
    other:     Markets are ordered by region so Western Europe reads as a block.
    """
    cells = {(e["chain"], e["market"]): e for e in d["entries"]}
    chains = sorted(d["chains"], key=lambda c: (-sum(1 for k in cells if k[0] == c), c))
    order = ["East Asia", "Southeast Asia", "Gulf", "Oceania", "North America", "Western Europe"]
    markets = sorted(d["markets"],
                     key=lambda m: (order.index(d["markets"][m]["region"])
                                    if d["markets"][m]["region"] in order else 99, m))
    return chains, markets, cells


def _cell(e) -> str:
    """One cell: what is there, and how much to trust it."""
    if e is None:
        return "."
    if e["status"] == "no_evidence":
        return "-"
    if e["status"] == "exited":
        return "x"
    n = e.get("locations")
    mark = {"high": "", "medium": "?", "low": "??"}[e["confidence"]]
    return f"{n}{mark}" if n is not None else f"Y{mark}"


def report(d: dict, chain: str | None = None, market: str | None = None):
    """
    name:      report
    purpose:   Print the register as a matrix, then the detail behind it.
    arguments: d; optional chain / market filters
    returns:   None
    effects:   Prints.
    other:     The matrix is the answer to "who is where"; the detail lines carry the dates and
               the caveats, because the matrix alone would flatten a retreat-and-re-entry into
               a tick.
    """
    chains, markets, cells = matrix(d)
    if chain:
        chains = [c for c in chains if c == chain]
    if market:
        markets = [m for m in markets if m == market]

    width = max(len(d["chains"][c]["name"]) for c in chains) + 2
    # One column width for the whole grid, sized to the widest cell: a count like "32??" is
    # four characters and would otherwise shove every column to its right out of line.
    cw = max([len(_cell(cells.get((c, m)))) for c in chains for m in markets] + [2]) + 1
    print(" " * width + "".join(m.rjust(cw) for m in markets))
    for c in chains:
        row = "".join(_cell(cells.get((c, m))).rjust(cw) for m in markets)
        print(d["chains"][c]["name"].ljust(width) + row)
    print(f"\n  number = locations, Y = present but count unpublished, - = no evidence found,"
          f"\n  x = exited, . = not looked at.  ? = medium confidence, ?? = low.\n")

    for c in chains:
        rows = [(m, cells[(c, m)]) for m in markets if (c, m) in cells]
        if not rows:
            continue
        print(f"{d['chains'][c]['name']} ({d['chains'][c]['name_zh']}) — {d['chains'][c]['global']}")
        for m, e in rows:
            bits = []
            if e.get("first_opened"):
                bits.append(f"first {e['first_opened']}")
            if e.get("locations") is not None:
                bits.append(f"{e['locations']} locations as of {e['locations_as_of']}")
            bits.append(e["confidence"])
            print(f"    {d['markets'][m]['name']:<16} {e['status']:<12} {', '.join(bits)}")
            if e.get("note"):
                for line in _wrap(e["note"], 78):
                    print(f"        {line}")
        print()


def stale(d: dict, days: int = STALE_DAYS) -> list[tuple[str, str, int]]:
    """
    name:      stale
    purpose:   List entries not reviewed within `days`.
    arguments: d, days
    returns:   list of (chain, market, age_days), oldest first
    effects:   None
    other:     This is the register's only scheduled obligation. It replaces a daily crawl with
               a periodic human pass, which is the right cadence for facts that come from press
               releases rather than from locators.
    """
    cutoff = date.today() - timedelta(days=days)
    out = []
    for e in d["entries"]:
        r = date.fromisoformat(e["reviewed"])
        if r < cutoff:
            out.append((e["chain"], e["market"], (date.today() - r).days))
    return sorted(out, key=lambda t: -t[2])


def gaps(d: dict) -> list[tuple[str, str]]:
    """
    name:      gaps
    purpose:   Chain/market pairs nobody has looked at at all.
    arguments: d
    returns:   list of (chain, market)
    effects:   None
    other:     A register's blank cells are as informative as its filled ones, so they are
               enumerated rather than left to be noticed.
    """
    cells = {(e["chain"], e["market"]) for e in d["entries"]}
    return [(c, m) for c in d["chains"] for m in d["markets"] if (c, m) not in cells]


def _wrap(text: str, n: int) -> list[str]:
    words, lines, cur = text.split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 > n:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        lines.append(cur)
    return lines


def export(out_dir: Path) -> dict:
    """
    name:      export
    purpose:   Copy the register to the page's data directory with derived summaries.
    arguments: out_dir — usually map/data
    returns:   summary dict
    effects:   Writes register.json into out_dir.
    other:     Derived counts are computed here rather than in the page, so the page cannot
               disagree with the CLI about what the register says.
    """
    d = load()
    out_dir.mkdir(parents=True, exist_ok=True)
    by_chain = defaultdict(int)
    for e in d["entries"]:
        if e["status"] == "present":
            by_chain[e["chain"]] += 1
    d["derived"] = {
        "markets_present": dict(by_chain),
        "entries": len(d["entries"]),
        "gaps": len(gaps(d)),
        "stale": len(stale(d)),
    }
    (out_dir / "register.json").write_text(json.dumps(d, ensure_ascii=False, indent=1))
    return d["derived"]

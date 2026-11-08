"""Locator Freshness — how up to date a chain's OWN store locator is.

PHANTOM-LISTINGS METRIC (v1). Many chains' official store finders keep listing
outlets that have already closed ("locator lag"). This measures that, per chain:

    freshness = open / (open + stale)          # 1.0 = locator fully up to date
    stale     = outlets we have VERIFIED CLOSED that still appear on the locator

Where "stale" comes from (the two ways this project records a closed-but-listed outlet):
  * collected chains — the adapter's ``PERMANENTLY_CLOSED`` set (addresses dropped on
    collection *because* the locator still lists them though they are closed).
  * roster chains    — ``uncertain`` sightings (held-out closures we flag "still on locator").

Honest limits, stated wherever the number is shown:
  * It is a VERIFIED FLOOR — only closures we have confirmed count, so true staleness is >=.
  * It is ONE-SIDED — it measures phantom listings (closed-but-listed), not undercount
    (open-but-unlisted). A full "locator accuracy" would combine both; this is v1.

Published only for chains with at least ``MIN_LISTED`` locator entries and at least one
verified stale listing (so we never imply a clean bill of health for a chain we have not
actually audited).

CLI: ``python -m chain_atlas locator``
"""
from __future__ import annotations

import importlib
import sys

MIN_LISTED = 8  # don't publish a score on a thin sample


def _collected_stale() -> dict[str, int]:
    """chain_id -> number of addresses in that chain's adapter PERMANENTLY_CLOSED set."""
    from .adapters import REGISTRY

    out: dict[str, int] = {}
    for cls in REGISTRY:
        mod = sys.modules.get(cls.__module__) or importlib.import_module(cls.__module__)
        pc = getattr(mod, "PERMANENTLY_CLOSED", None)
        cid = getattr(cls, "chain_id", None)
        if pc and cid:
            out[cid] = out.get(cid, 0) + len(pc)
    return out


def _roster_stale(sightings: list[dict]) -> dict[str, int]:
    """chain_id -> number of 'uncertain' (held-out, still-on-locator) sightings."""
    out: dict[str, int] = {}
    for s in sightings:
        if s.get("confidence") == "uncertain" and s.get("chain"):
            out[s["chain"]] = out.get(s["chain"], 0) + 1
    return out


def compute(open_by_chain: dict[str, int], sightings: list[dict],
            min_listed: int = MIN_LISTED) -> dict[str, dict]:
    """Per-chain locator freshness. Keys are chain ids; values carry the raw counts so the
    page can say "N of M listed stores are closed" and never just a bare percentage."""
    stale = _collected_stale()
    for ch, n in _roster_stale(sightings).items():
        stale[ch] = stale.get(ch, 0) + n

    out: dict[str, dict] = {}
    for ch, st in stale.items():
        if st <= 0:
            continue
        op = int(open_by_chain.get(ch, 0))
        listed = op + st
        if listed < min_listed:
            continue
        out[ch] = {
            "open": op,
            "stale": st,
            "listed": listed,
            "freshness": round(op / listed, 3),
        }
    return out


def report(open_by_chain: dict[str, int], sightings: list[dict]) -> None:
    """Print the leaderboard, worst (stalest) locators first."""
    data = compute(open_by_chain, sightings)
    rows = sorted(data.items(), key=lambda kv: kv[1]["freshness"])
    print(f"{'chain':14}{'open':>6}{'stale':>7}{'listed':>8}{'fresh':>8}")
    for ch, d in rows:
        print(f"{ch:14}{d['open']:>6}{d['stale']:>7}{d['listed']:>8}{d['freshness']*100:>7.0f}%")
    print("\nstale = verified-closed outlets still on the chain's own locator (phantom listings).")
    print("Verified floor; one-sided (does not count open-but-unlisted stores).")

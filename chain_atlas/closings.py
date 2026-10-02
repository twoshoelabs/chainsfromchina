"""
Known US closings assembled by hand — the record a daily census could not produce.

The census dates a closing by absence, but only for a chain with a live locator and only from the
day collection began. This file holds the closings that predate that window or belong to chains we
track by hand: field notes, press, and the chains' own "first_outlet (now closed)" admissions.

Like sightings, these never enter stores/observations/events and are never drawn on the map — a
closed store is not a place that exists, and the map shows only what does. They are a dated
historical record so the project's thesis (chains open AND quietly close) rests on data, not prose.
See manual/closings.json's _readme for the honesty-over-precision rules.
"""
import json
from pathlib import Path

CLOSINGS_PATH = Path(__file__).resolve().parents[1] / "manual" / "closings.json"


def load(path: Path | None = None) -> dict:
    """Read closings.json, or an empty set if there is none (absence is normal)."""
    p = path or CLOSINGS_PATH
    if not p.exists():
        return {"closings": []}
    return json.loads(p.read_text(encoding="utf-8"))


def summary(path: Path | None = None) -> dict:
    """Counts for the status line: total, confirmed, uncertain, and distinct chains."""
    rows = load(path).get("closings", [])
    confirmed = sum(1 for r in rows if r.get("confidence") == "confirmed")
    return {
        "total": len(rows),
        "confirmed": confirmed,
        "uncertain": len(rows) - confirmed,
        "chains": sorted({r["chain"] for r in rows}),
    }

"""
The PRO submission record is the one provenance-tagged schema every datum conforms to (docs/pro_spec.md
§4). These tests pin: the required-field + enum validation, canonicalisation (confidence synonyms,
defaults, stable id, inferred tier), and that the mappers from the EXISTING stores (sightings,
china_stores, financial_anchors, dossiers) each produce a valid canonical record — the proof the schema
reconciles what we already have. All offline.

Run: .venv/bin/python tests/test_submissions.py
"""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from chain_atlas import submissions as S  # noqa: E402


def main():
    fails = []

    def check(label, got, want=True):
        ok = got == want
        print(("PASS" if ok else "FAIL"), label, "" if ok else f"(got {got!r}, want {want!r})")
        if not ok:
            fails.append(label)

    def hard_errors(rec):
        """validation errors only — warnings (unknown-but-allowed metric slugs) don't count."""
        return [e for e in S.validate(rec) if not e.startswith("warn:")]

    # --- a complete valid record ---
    good = {"brand": "huaxiaoxiao", "dimension": "presence", "metric": "outlet",
            "value": "Flushing (Tangram)", "as_of": "2026-10-14",
            "geo": {"address": "37-09 College Point Blvd, Flushing, NY 11354"},
            "provenance_tier": "measured", "confidence": "high",
            "source": "Google Business operating listing", "submitter": "owner"}
    check("valid record -> no errors", S.validate(good), [])

    # --- canonicalize: synonyms, defaults, id, inferred tier ---
    c = S.canonicalize({"brand": "x", "dimension": "presence", "metric": "outlet", "value": "A",
                        "as_of": "2026-10-16", "geo": {"address": "1 Main St"},
                        "confidence": "confirmed",   # synonym -> high
                        "source": "Google Business operating", "submitter": "owner"})
    check("confirmed -> high", c["confidence"], "high")
    check("status defaults to submitted", c["status"], "submitted")
    check("submitted_at stamped", bool(c["submitted_at"]), True)
    check("id stamped", c["id"].startswith("sub_"), True)
    check("tier inferred = measured", c["provenance_tier"], "measured")

    # --- record_id stable: identity hash ignores confidence/status ---
    a = dict(good); b = dict(good); b["confidence"] = "low"; b["status"] = "verified"
    check("same fact -> same id regardless of confidence/status", S.record_id(a), S.record_id(b))
    d = dict(good); d["value"] = "Different"
    check("different value -> different id", S.record_id(a) != S.record_id(d), True)

    # --- validation catches problems ---
    check("missing required flagged", any("missing required" in e for e in S.validate({"dimension": "scale"})), True)
    bad_dim = dict(good); bad_dim["dimension"] = "nonsense"
    check("bad dimension flagged", any("dimension not in" in e for e in S.validate(bad_dim)), True)
    bad_date = dict(good); bad_date["as_of"] = "Oct 2026"
    check("bad as_of flagged", any("as_of must be" in e for e in S.validate(bad_date)), True)
    no_geo = dict(good); no_geo["geo"] = None
    check("presence without geo flagged", any("presence records need geo" in e for e in S.validate(no_geo)), True)
    odd_metric = dict(good); odd_metric["metric"] = "weird_thing"
    check("unknown metric -> warn (not hard error)", any(e.startswith("warn:") for e in S.validate(odd_metric)), True)
    check("unknown metric is ONLY a warning", [e for e in S.validate(odd_metric) if not e.startswith("warn:")], [])

    # --- infer_tier ---
    check("filing + high -> filed", S.infer_tier("scale", "store_count_total", "ChaPanda FY2025 Annual Report (HKEX:2555)", "high"), "filed")
    check("filing + medium -> reported", S.infer_tier("scale", "store_count_total", "FY2025 annual report (secondary press)", "medium"), "reported")
    check("estimate -> modeled", S.infer_tier("economics", "us_revenue_estimate", "revenue model v3", "medium"), "modeled")
    check("press -> reported", S.infer_tier("narrative", "history", "company-history press profiles", "medium"), "reported")

    # --- mappers from the existing stores all produce VALID records ---
    sg_group = {"chain": "makkee", "reviewed": "2026-10-16", "supplied_on": "2026-10-16",
                "source": "Google", "scope": "Makkee US outlets"}
    sg_loc = {"name": "Brooklyn (86th St)", "address": "2053 86th St, Brooklyn, NY 11214",
              "confidence": "confirmed", "verified_by": "Google Business operating", "lat": 40.6, "lon": -73.9}
    r1 = S.from_sighting("makkee", sg_group, sg_loc)
    check("from_sighting valid", hard_errors(r1), [])
    check("from_sighting -> presence/outlet", (r1["dimension"], r1["metric"], r1["confidence"]), ("presence", "outlet", "high"))

    cs = {"total": 8659, "china": 8621, "overseas": 38, "as_of": "2025-12-31",
          "source": "ChaPanda FY2025 Annual Report (HKEX:2555)", "confidence": "high", "note": "…"}
    r2 = S.from_china_stores("chabaidao", cs)
    check("from_china_stores valid", hard_errors(r2), [])
    check("from_china_stores -> scale, filed, 8659", (r2["dimension"], r2["provenance_tier"], r2["value"]), ("scale", "filed", 8659))

    anchor = {"brand_id": "miniso", "period": "2025", "metric": "fdd_item21_us_revenue",
              "value": 270550.0, "unit": "USD", "page_ref": "doc (2025)",
              "source": "FDD Item 21 (MN)", "source_url": "https://…", "confidence": "medium"}
    r3 = S.from_financial_anchor(anchor)
    check("from_financial_anchor valid", hard_errors(r3), [])
    check("from_financial_anchor -> economics, as_of year", (r3["dimension"], r3["as_of"]), ("economics", "2025-12-31"))

    doss = {"text": "Founded 2010 in Beijing by Wang Ning…", "as_of": "2026-10-15",
            "source": "press profiles", "confidence": "medium"}
    r4 = S.from_dossier_item("popmart", "history", doss)
    check("from_dossier_item valid", hard_errors(r4), [])
    check("from_dossier_item -> narrative/history", (r4["dimension"], r4["metric"]), ("narrative", "history"))

    # --- append round-trips to a temp JSONL; a bad record raises ---
    tmp = tempfile.mkdtemp()
    path = os.path.join(tmp, "submissions.jsonl")
    S.append(r1, path); S.append(r2, path)
    rows = list(S.iter_submissions(path))
    check("append wrote 2 rows", len(rows), 2)
    check("round-trip id preserved", rows[0]["id"], r1["id"])
    raised = False
    try:
        S.append({"dimension": "scale"}, path)
    except ValueError:
        raised = True
    check("append rejects an invalid record", raised, True)
    check("invalid append wrote nothing extra", len(list(S.iter_submissions(path))), 2)

    print("\n" + ("ALL PASS" if not fails else f"{len(fails)} FAIL: " + ", ".join(fails)))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())

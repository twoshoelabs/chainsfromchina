"""
MINISO UAE is the first non-US market in the archive, and its locator publishes less than any
other: a mall name and an emirate, nothing else. That makes the parser's two jobs unusually
load-bearing — telling a store apart from page furniture, and producing a key stable enough
that an invisible character cannot fake a closure.

The fixture is the real 21 Sep 2026 capture, trimmed to the heading markup the parser reads.
It still contains the genuine zero-width space in "AL GHURAIR CENTER".

Run: .venv/bin/python tests/test_miniso_ae.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from chain_atlas.adapters.miniso_ae import MinisoUAEAdapter  # noqa: E402
from chain_atlas.identity import store_key, norm_addr        # noqa: E402

RAW = json.loads((Path(__file__).parent / "fixtures" / "miniso_ae_sample.json").read_text())


def main():
    recs = MinisoUAEAdapter().parse(RAW)
    names = [r.name for r in recs]
    fails = []

    def check(label, got, want=True):
        ok = got == want
        print(f"  {'PASS' if ok else 'FAIL'}  {label}: {got}" + ("" if ok else f"  (want {want})"))
        if not ok:
            fails.append(label)

    check("two emirate pages yield 20 stores", len(recs), 20)
    check("Dubai stores counted", sum(1 for r in recs if r.city == "Dubai"), 19)
    check("Ajman stores counted", sum(1 for r in recs if r.city == "Ajman"), 1)

    # Page furniture uses the same heading widget as the stores do.
    check("section heading is not a store", any("Looking For" in n for n in names), False)
    check("instagram handle is not a store", any(n.startswith("@") for n in names), False)

    # The zero-width space: left in, it would rewrite this store's key the day an editor
    # removes it, and the archive would report a closure and an opening in the same mall.
    ghurair = [r for r in recs if "GHURAIR" in r.name.upper()]
    check("the zero-width-space store parsed", len(ghurair), 1)
    check("no zero-width space survives into the name", "​" in ghurair[0].name, False)
    check("nor into the identity key", "​" in store_key(ghurair[0]), False)
    check("key is stable against the character being edited out",
          norm_addr("AL GHURAIR CENTER​, Dubai, United Arab Emirates")
          == norm_addr("AL GHURAIR CENTER, Dubai, United Arab Emirates"))

    # Two shops in one mall are two shops.
    dubai_mall = [r for r in recs if r.name.strip().upper().startswith("THE DUBAI MALL")]
    check("both Dubai Mall stores kept apart", len(dubai_mall), 2)
    check("and they get different keys", len({store_key(r) for r in dubai_mall}), 2)

    check("every store has a key", all(store_key(r) for r in recs))
    check("keys are unique", len({store_key(r) for r in recs}), len(recs))
    check("nothing claims a coordinate", all(r.lat is None and r.lon is None for r in recs))
    check("no US state is invented", all(r.state is None for r in recs))
    check("adapter declares its market", MinisoUAEAdapter.country, "AE")
    check("and links to its register row", MinisoUAEAdapter.register_chain, "miniso")

    print(f"\n{'ALL PASS' if not fails else 'FAILURES: ' + ', '.join(fails)}")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())

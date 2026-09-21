"""
Cross-check one US state against Overture Maps, and produce a list for a human to review.

EXPLORATORY, and deliberately not wired into `run`. Overture is a corroboration and discovery
layer, never a census: absence from it is not evidence a store closed, and presence is not
evidence one is open. Nothing this script produces enters stores, observations or events.

Two things the first New York pass established, both worth keeping:

  * OVERTURE IS NOT A SUBSTITUTE for first-party collection. For the chains this project does
    collect, it held roughly a third of what we hold — Luckin 1 against our 22, MINISO 6 against
    our 15, MIXUE 0 against our 11 — and its one Luckin and five of its six MINISO rows were
    within 150 m of stores we already had. It adds almost nothing where we are already looking.
  * IT IS VALUABLE WHERE WE CANNOT LOOK. Eighteen of its twenty-seven New York candidates were
    for POP MART, HEYTEA, Cotti and Tai Er — four chains with no locator this project can read.

  * AND EVERY CLAIM IT MADE THAT WE COULD CHECK WAS FALSE. Two New York rows asserted a store
    this project does not hold. The operator verified both, and both were wrong:

        Haidilao, "170-16 39th Ave" 11358, open, confidence 0.972
            A phantom. The Flushing restaurant is 138-23 39th Ave — which Overture ALSO lists,
            separately, 24 m from ours. This row invents a second restaurant 2.7 km away that
            happens to share a street name.

        MINISO, "579 Broadway" 10012, open, confidence 0.77
            Permanently closed. Overture reports it trading.

    Two for two, both marked `operating_status: open`, one at 0.97 confidence. High confidence
    did not protect against either. This is the entire argument for keeping Overture out of the
    census in one result: had these been accepted as stores, the archive would now hold a
    restaurant that does not exist and a shop that has shut, in the right cities, on the right
    streets, indistinguishable from the 505 rows that are correct.

    It also sets the standard for the eighteen candidates in bucket C. They are LEADS. Every one
    needs verification before it becomes even a sighting, and the base rate observed here is not
    encouraging.

Also: substring matching is unusable. Searching "cotti" returns Biscotti, Scottish Inns and
Scotti\'s Record Shop; 69 of 96 raw hits were false positives before word-boundary filtering.
And a bounding box for New York State reaches into Ontario, so the region field must be checked
rather than trusted to geography.

Usage: .venv/bin/python scripts/overture_review.py     (writes a CSV to the data directory)
"""
import duckdb, os, re, csv, sys, sqlite3
sys.path.insert(0, os.path.expanduser("~/Projects/chain_atlas"))
from chain_atlas.identity import norm_addr

REL = "2026-08-19.0"
OUT = os.path.expanduser("~/chain_atlas_data/review_ny_overture.csv")

# term -> the chain_id we would file it under. Word-boundary matched, because a substring
# search for "cotti" returns Biscotti, Scottish and Scotti's Record Shop.
TERMS = {
    "mixue": "mixue", "蜜雪": "mixue",
    "chagee": "chagee", "霸王茶姬": "chagee",
    "luckin": "luckin",
    "miniso": "miniso", "名创优品": "miniso",
    "haidilao": "haidilao", "hai di lao": "haidilao", "海底捞": "haidilao",
    "pop mart": "popmart", "popmart": "popmart", "泡泡玛特": "popmart",
    "heytea": "heytea", "hey tea": "heytea", "喜茶": "heytea",
    "cotti": "cotti", "库迪": "cotti",
    "yang's braised": "yangs", "yangs braised": "yangs", "黄焖鸡": "yangs", "黃燜雞": "yangs",
    "tai er": "taier", "太二": "taier",
    "teabydo": "chabaidao", "tea by do": "chabaidao", "chapanda": "chabaidao", "茶百道": "chabaidao",
    "naisnow": "nayuki", "nayuki": "nayuki", "naixue": "nayuki", "奈雪": "nayuki",
    "juewei": "juewei", "king of braise": "juewei", "绝味": "juewei",
}

con = duckdb.connect()
con.execute("INSTALL httpfs; LOAD httpfs; SET s3_region='us-west-2'; SET enable_progress_bar=false;")
esc = lambda t: t.replace("'", "''")
like = " OR ".join([f"lower(names.primary) LIKE '%{esc(t)}%'" for t in TERMS]
                   + [f"lower(brand.names.primary) LIKE '%{esc(t)}%'" for t in TERMS])

rows = con.execute(f"""
  SELECT names.primary, brand.names.primary, brand.wikidata, categories.primary,
         operating_status, round(confidence,3), addresses[1].freeform, addresses[1].locality,
         addresses[1].region, addresses[1].postcode, round(bbox.xmin,6), round(bbox.ymin,6),
         list_distinct(list_transform(sources, s -> s.dataset)), id
  FROM read_parquet('s3://overturemaps-us-west-2/release/{REL}/theme=places/type=place/*.parquet')
  WHERE bbox.xmin BETWEEN -79.95 AND -71.70 AND bbox.ymin BETWEEN 40.40 AND 45.10
    AND addresses[1].region = 'NY' AND addresses[1].country = 'US'
    AND ({like})
""").fetchall()
print(f"raw NY hits: {len(rows)}")

# Word-boundary match, so Biscotti stops being a Cotti Coffee.
def classify(name, brand):
    hay = f"{name or ''} {brand or ''}".lower()
    hits = set()
    for term, chain in TERMS.items():
        pat = re.escape(term)
        if re.search(pat if not term.isascii() else rf"(?<![a-z]){pat}(?![a-z])", hay):
            hits.add(chain)
    return sorted(hits)

# What we already hold for NY.
db = os.path.expanduser("~/chain_atlas_data/chain_atlas.sqlite")
c = sqlite3.connect(f"file:{db}?mode=ro", uri=True); c.row_factory = sqlite3.Row
ours = {}
for r in c.execute("SELECT chain_id, name, addr_raw FROM stores WHERE state='NY' AND status!='withdrawn'"):
    ours[norm_addr(r["addr_raw"])] = (r["chain_id"], r["name"])

out, kept, dropped = [], 0, 0
for (name, brand, wd, cat, status, conf, addr, city, region, zipc, lon, lat, ds, oid) in rows:
    chains = classify(name, brand)
    if not chains:
        dropped += 1
        continue
    kept += 1
    key = norm_addr(addr or "")
    match = ours.get(key)
    out.append({
        "our_chain_guess": "|".join(chains), "overture_name": name, "overture_brand": brand or "",
        "brand_wikidata": wd or "", "category": cat or "", "operating_status": status or "",
        "confidence": conf, "address": addr or "", "city": city or "", "zip": zipc or "",
        "lat": lat, "lon": lon, "sources": "|".join(ds or []),
        "in_our_archive": "YES" if match else "no",
        "our_chain": match[0] if match else "", "our_store_name": match[1] if match else "",
        "overture_id": oid,
    })

out.sort(key=lambda r: (r["our_chain_guess"], r["in_our_archive"], r["city"]))
with open(OUT, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
    w.writeheader(); w.writerows(out)
print(f"kept {kept} after word-boundary filtering, dropped {dropped} substring false positives")
print(f"-> {OUT}")

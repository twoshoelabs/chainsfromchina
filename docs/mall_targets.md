# US mall-sweep targets — Asian-heavy metros & centers

The master target list for the monthly US mall-directory sweep (CFC US mall-directory sweep routine).
The sweep mines these centers' online tenant directories for China-origin chain outlets we miss via
brand locators + press. **Rotate a subset each run** (~8–12), favoring (a) flagship/destination malls,
(b) centers in dense Chinese/East-Asian trade areas, (c) anything recently in the news. Skip affluent,
non-Asian-trade-area lifestyle centers — they reliably yield nothing (e.g. Village at Corte Madera = 0).

**Yield rule of thumb (from the Oct 2026 live sweeps):** high yield at flagship/destination malls in
Asian metros (American Dream, Valley Fair, South Coast Plaza, Tysons); near-zero at neighborhood malls
whose only China tenant is a Miniso the adapter already has (Columbia, Oakridge), and at outlet malls
(Leesburg) and affluent non-Asian centers. Match tenants against register.json `chains`; flag unknown
China-looking names as new-chain candidates. Scope: China-ORIGIN only — exclude Taiwan (Gong cha, Kung
Fu Tea, Sushi Express, Din Tai Fung, Shihlin, Duan's Kitchen, TP Tea, 99 Ranch), Korea, Japan, and
US-founded (Panda Express, Chubby Cattle, MUMU Hot Pot, Nan Xiang) + DTC-only brands with no China B&M
(Shein, Cider, Vivaia — see the DTC scope rule).

---

## Sweep status & priority queue (as of 2026-10-18)

**Swept 2026-10-18 (fresh — rotate past these first):** American Dream, Tysons Corner, Westfield Montgomery,
Westfield Valley Fair, Great Mall Milpitas, Westfield Oakridge, South Coast Plaza, Fashion Island,
Westfield Santa Anita, Del Amo, Glendale Galleria, Bellevue Square, Westfield Old Orchard, Woodfield Mall,
Sugarloaf Mills, The Florida Mall, Dolphin Mall, Tangram + Sky View (Flushing), + Ala Moana/Katy (partial).
These are covered; the mainstream brands (Pop Mart, Miniso, Heytea, Chagee) are locked in those metros.

**KEY LEARNING (2026-10-18 web sweep of MOA / Las Vegas / Aventura):** the **Miniso and Pop Mart adapters
already cover those two brands nationwide** — so enclosed flagship malls in *every* metro are effectively
covered for Miniso + Pop Mart (MOA, Las Vegas Fashion Show, etc. all confirmed tracked). Sweeping flagship
malls mostly just re-confirms that. **The real remaining gap is the ADAPTER-LESS F&B chains** — Heytea,
Chagee, Mixue, Nayuki, Moge, Auntea Jenny, Yang's, the newer boba/malatang/dessert brands — which are
tracked only via sightings and **cluster in 99 Ranch / H-Mart strip plazas, not enclosed malls**. So:

**PRIORITY NEXT (where the yield actually is):**
1. **Strip-plaza F&B sweeps** (see the "Non-enclosed centers" section) — Convoy (SD), Spring Mountain (LV),
   Buford Hwy (ATL), Bellaire (HOU), Valley Blvd / San Gabriel Square / Rowland Heights (SGV), Richardson /
   Carrollton (DAL). Method = Google-Maps-area / 99-Ranch-nearby scan for the F&B brands above, not a directory.
2. **New-chain discovery** at enclosed malls still unswept (that's how XIMIVOGUE, DeRucci, Yogost were found —
   furniture/variety/dessert brands the adapters never see): Roosevelt Field, Garden State Plaza, Queens
   Center / New World / Queens Crossing, Houston Galleria + Katy Asian Town / Dun Huang, Irvine Spectrum /
   Diamond Jamboree, Stanford / Stonestown / Serramonte / Cupertino, Puente Hills, Oakbrook / Naperville.
Don't re-sweep flagships just for Miniso/Pop Mart — the adapters have those.

---

## California — San Francisco Bay Area (very high density)
- **Westfield Valley Fair** (Santa Clara) — flagship; Heytea, Pop Mart, Miniso, Rolife, DREAME, Tai Er
- **Great Mall** (Milpitas, Simon) — Miniso, Rolife
- **Westfield Oakridge** (San Jose) — Miniso
- **Stanford Shopping Center** (Palo Alto, Simon)
- **Serramonte Center** (Daly City)
- **Stonestown Galleria** (San Francisco)
- **Westfield San Francisco Centre / Emporium** (San Francisco)
- **Pacific Commons** (Fremont) + **Milpitas Square / 99 Ranch plazas** (Milpitas, Fremont, Cupertino, San Jose)
- **Cupertino** (Main Street Cupertino / Vallco redevelopment area)

## California — Greater Los Angeles / San Gabriel Valley (626) (very high density)
- **Westfield Santa Anita** (Arcadia) — SGV flagship
- **Puente Hills Mall** (City of Industry)
- **San Gabriel Square / Valley Blvd corridor** (San Gabriel, Monterey Park, Rowland Heights, Arcadia) — plaza clusters
- **Del Amo Fashion Center** (Torrance, Simon)
- **Westfield Culver City**, **Westfield Topanga** (Canoga Park)
- **The Shops at Montebello**, **Montebello Town Center**
- **Westfield Santa Anita** + **Pacific Place** (Arcadia)

## California — Orange County (high density)
- **South Coast Plaza** (Costa Mesa) — luxury flagship; Chagee, Heytea, Pop Mart
- **Fashion Island** (Newport Beach) — CHICJOC
- **Irvine Spectrum Center** + **Diamond Jamboree** (Irvine) — Asian F&B hub
- **Westminster / Little Saigon** (Viet-heavy; lower China-chain yield)

## California — San Diego & Sacramento
- **Pacific Pearl Plaza / Convoy District** (San Diego) — Asian F&B hub
- **Westfield UTC** (San Diego); **Mira Mesa** plazas
- **Sacramento** — 99 Ranch / Asian plaza clusters (Elk Grove, Natomas)

## New York / New Jersey (very high density)
- **American Dream** (East Rutherford NJ) — flagship; Yogost, Heytea, Little Sheep, Nayuki, Rolife, Pop Mart, Miniso
- **Flushing, Queens** — New World Mall, **Tangram**, **Sky View Center**, **Queens Crossing**, **Queens Center**
- **Roosevelt Field** (Garden City NY, Simon)
- **Westfield Garden State Plaza** (Paramus NJ)
- **Manhattan Chinatown** / Lower East Side; **Brooklyn** — Sunset Park (8th Ave), Bay Ridge
- **Edison / Iselin** (Oak Tree Rd, NJ — South-Asian heavy); **Palisades Center** (West Nyack NY)

## Washington — Seattle metro (high density)
- **Westfield Southcenter** (Tukwila)
- **Bellevue Square** + **Crossroads Bellevue** (Bellevue)
- **Alderwood** (Lynnwood)
- **Pacific Place** (downtown Seattle); **International District / Uwajimaya**

## Texas (high & growing)
- **Houston** — **Katy Asian Town** (Katy), **Hong Kong City Mall**, **Dun Huang Plaza**, **The Galleria**, **Memorial City**
- **Dallas / Plano** — **Legacy West** (Plano), **Richardson Chinatown**, **Carrollton** plazas
- **Austin** — Asian plaza clusters (N Lamar / Chinatown Center)

## Greater Washington DC / Virginia / Maryland (high density)
- **Tysons Corner Center** (Tysons/McLean VA) — flagship; Heytea, Pop Mart, Miniso, Moge Tee
- **Westfield Montgomery** (Bethesda MD) — Pop Mart, Heytea (coming), Miniso
- **Fair Oaks Mall** (Fairfax VA); **Rockville Pike corridor** (Rockville MD); **Gaithersburg** (Lakeforest area)
- (Eden Center, Falls Church = Vietnamese; lower China-chain yield)

## Florida / Southeast
- **Aventura Mall** (Aventura) + **Dadeland Mall** (Miami) + **Dolphin Mall** (Sweetwater) — Pop Mart, Miniso, Heytea
- **The Florida Mall** (Orlando) — Miniso, Pop Mart, Heytea(coming)
- **Sawgrass Mills** (Sunrise); **Brickell City Centre** (Miami)

## Other high-yield metros
- **Chicago** — **Chinatown Square**, **Westfield Old Orchard** (Skokie), **Oakbrook Center**, Naperville/Aurora plazas
- **Boston** — **Boston Chinatown**, **Quincy** (Asian-heavy), **Burlington Mall**, **Natick Mall**
- **Atlanta** — **Buford Hwy corridor** (Doraville/Chamblee/Duluth), **Sugarloaf Mills** (Lawrenceville, swept), Pleasant Hill plazas (Duluth)
- **Philadelphia** — **Chinatown**, **Dun Huang Plaza** (plus King of Prussia as a flagship, lower Asian density)
- **Las Vegas** — **Chinatown / Spring Mountain Rd** plazas (Shanghai Plaza, Chinatown Plaza), **Fashion Show Mall**
- **Honolulu** — **Ala Moana Center** (very high Asian-brand density)
- **Minneapolis** — **Mall of America** (Bloomington) — Rolife flagship + general flagship draw

---

## Non-enclosed centers & strip plazas (no tidy online directory — different method)
The fastest-moving small/new China F&B (Mixue, Chagee, Wedrink, newer boba/dessert/malatang brands) cluster in
**99 Ranch / H-Mart-anchored strip centers**, NOT enclosed malls — and these have no Simon/Westfield-style
tenant directory, so the adapters AND the enclosed-mall sweep both miss them. Reach them a different way:
scan the center's **Google Maps area** (or the 99 Ranch / H-Mart store's "nearby" tenant list) for our brands.
Highest-yield strips:
- **Convoy District** (San Diego); **Spring Mountain Rd** (Las Vegas); **Buford Hwy / Pleasant Hill** (Atlanta)
- **Bellaire Blvd Chinatown** (Houston); **Valley Blvd / San Gabriel Square / Rowland Heights** (SGV)
- **Richardson / Carrollton** (Dallas); **Edison / Palisades** (NJ); **99 Ranch plazas** in every metro above

**METHOD NOTE (learned 2026-10-18, six-area scan):** plain web search does NOT reach strip-plaza openings —
they live on Google Maps, brand apps and local blogs, not indexed news (the six-area web scan returned zero
confirmable new stores). Two things that DO work: (a) for the big adapter-less chains, reconcile the brand's
**own store locator** — Mixue and Chagee are still EARLY-stage in the US (Mixue ~10, all LA/NYC/Bay; Chagee
~12, all SoCal) and already fully in our census, so they are NOT the gap; (b) for the actual gap — small/new
regional chains unique to a plaza — you need a true **Google-Maps-area pass** (browse Maps around the 99 Ranch
pin), which plain WebSearch can't substitute for. Don't burn web searches on `Mixue <city>`; check the locator.

**PROVEN METHOD (piloted 2026-10-18, Convoy District San Diego):** in an interactive browser, open a Google Maps
search like `https://www.google.com/maps/search/bubble+tea/@<lat>,<lon>,15z` centered on the plaza, then
`get_page_text` the results panel and read the map pins; search a specific tracked brand (`Chabaidao 茶百道
<area>`) to pull its exact address. This found **Chabaidao / TeaByDo at 4425 Convoy St #216, San Diego** that
six web searches had missed, plus a new-chain lead (3CAT Handcrafted Beverage). Scan categories: `bubble tea`,
`malatang`, `hot pot`, `Chinese bakery/dessert`. **CAVEAT: this needs an interactive browser — the monthly
cloud routine (WebFetch/WebSearch only) can't do it.** So split the work: the cloud routine does enclosed-mall
directories + brand-locator reconciliation; **strip-plaza Google-Maps passes are a manual/session task.**

---

## Asian-supermarket food courts & in-store kiosks (delivery-app / operator-observation method)
A distinct blind spot from strip plazas: China-origin chains that run a **food-court STALL or boba KIOSK INSIDE**
an Asian supermarket — **99 Ranch "Tasty Place"** (~66 US stores, 11 states), **H-Mart "Market Eatery"**, and
**Great Wall / Hong Kong Supermarket / iFresh / Zion / Super 88**. Per the shop-in-shop precedent these **count
as US outlets** (e.g. Dusu Bakery inside Duo Duo Snacks; **Shuyi is literally inside the Fremont 99 Ranch**,
stored by its street address 46551 Mission Blvd).

**WHY MISSED:** these stalls have **NO individual Google Maps pin** (they sit under the food court's or the
store's own listing) and are not on the chains' brand locators — so BOTH our enclosed-mall sweep AND the
strip-plaza Google-Maps pass miss them. The Maps tight-zoom method FAILS here.

**METHOD (different again):** the stalls are indexed on **Chinese delivery apps** — **Fantuan** (fantuanorder.com),
**Chowbus**, **HungryPanda / 熊猫外卖** — listed under the supermarket's delivery area. BUT those apps are
JS-gated (need a login/delivery address; a cloud routine's WebFetch returns an empty shell, and even an
interactive browser needs address setup). So the gold-standard source is **OPERATOR firsthand observation**
(visit / order in person) — which is also our highest-confidence tier. Treat a supermarket food court as a
small "directory" to walk once and record its China-chain stalls.

**COUNTING RULE (learned 2026-10-19 pilot):** a branded on-site **KIOSK/STALL that prepares the item on site
COUNTS**; a supermarket merely **RESELLING a chain's PACKAGED product does NOT** — e.g. "HeyTea" showed up on a
Postmates listing for **99 Ranch Dublin**, but it was bottled HeyTea Bayberry Jasmine on the grocery shelf, not
a kiosk, so it does NOT count. Always confirm prepared-on-site before adding. Store by street address (geocodes
cleanly); note the host supermarket in the sighting's name/note.

**HIGHEST-YIELD food courts to walk:** 99 Ranch — Irvine, Daly City, Milpitas, San Gabriel/Rowland Heights,
Hacienda Heights, Houston/Katy, Flushing; H-Mart — Fort Lee NJ, Flushing, Cary NC, Katy TX, Niles IL, Las Vegas.

---

**Low-yield / skip:** outlet malls (Simon Premium Outlets, Tanger); affluent non-Asian-trade-area
lifestyle centers (e.g. Village at Corte Madera, most suburban "Village at …" centers); neighborhood
malls where Miniso is the only China tenant (already adapter-covered).

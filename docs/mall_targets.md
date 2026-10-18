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

---

**Low-yield / skip:** outlet malls (Simon Premium Outlets, Tanger); affluent non-Asian-trade-area
lifestyle centers (e.g. Village at Corte Madera, most suburban "Village at …" centers); neighborhood
malls where Miniso is the only China tenant (already adapter-covered).

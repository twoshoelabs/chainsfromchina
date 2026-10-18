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

## Other high-yield metros
- **Chicago** — **Chinatown Square**, **Westfield Old Orchard** (Skokie), **Oakbrook Center**, Naperville/Aurora plazas
- **Boston** — **Boston Chinatown**, **Quincy** (Asian-heavy), **Burlington Mall**, **Natick Mall**
- **Atlanta** — **Buford Hwy corridor** (Duluth/Gwinnett) Asian plazas
- **Philadelphia** — **Chinatown**, **Dun Huang Plaza** (plus King of Prussia as a flagship, lower Asian density)
- **Las Vegas** — **Chinatown / Spring Mountain Rd** plazas, **Fashion Show Mall**
- **Honolulu** — **Ala Moana Center** (very high Asian-brand density)
- **Minneapolis** — **Mall of America** (Bloomington) — Rolife flagship + general flagship draw

---

**Low-yield / skip:** outlet malls (Simon Premium Outlets, Tanger); affluent non-Asian-trade-area
lifestyle centers (e.g. Village at Corte Madera, most suburban "Village at …" centers); neighborhood
malls where Miniso is the only China tenant (already adapter-covered).

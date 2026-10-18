"""
Chains in scope that cannot be collected yet, and exactly why.

These are not placeholders to be tidied away. A tracker that silently omits Pop Mart because
Pop Mart was inconvenient is a tracker that will one day report "Chinese retail is all tea
shops". Each stub carries the evidence from the 21 Sep 2026 probe so the next attempt starts
where this one stopped, and `status` prints the reason beside the chains that do collect.
"""
from .base import Adapter


class HeyteaAdapter(Adapter):
    """
    HEYTEA US — https://www.heytea.com/en-us/store

    The site has a clean CMS API — POST /api/v1/page with {"key":"stores", "region":"DEFAULT",
    "lang":"English"} returns 200 — but what it returns is a curated showcase of flagship
    design stores worldwide (13 entries across heytea / lab / teabar / craft, of which exactly
    one is American). It is a brand page, not a locator, and using it as one would report
    HEYTEA as a single-store chain when the trade press counts roughly 28 US locations.

    RE-CHECKED 21 SEP 2026: us.heytea.com and order.heytea.com do not resolve. heyteaus.com does
    and looks promising at 190 KB — it is a third-party SEO menu site ("HEYTEA Menu 2026: Updated
    Prices, Calories"), not HEYTEA's. Worth naming because it is the exact shape of mistake this
    project must not make: a plausible domain, a plausible title, and no relationship to the
    company whose store count it would have supplied.

    Next step: the ordering app's shop endpoint, which is where the real US list lives.
    """
    chain_id, name, name_zh = "heytea", "HEYTEA", "喜茶"
    parent, format = "Heytea (Shenzhen Meixixi)", "tea"
    ENABLED = False
    # 22 Sep 2026: POST /api/v1/page {"key":"stores","region":"us","lang":"en","platform":"web"}
    # returns exactly 13 stores in four tiers (heytea / lab / teabar / craft) across Hong Kong,
    # Bangkok, New York and Guangzhou — a curated showcase of signature stores, no coordinates,
    # not a US roster. Passing region=us does not localise it. The verdict is unchanged.
    # 22 Sep 2026, app-API hunt (the method that unblocked POP MART): app.heytea.com is the
    # 喜茶GO ordering app, but it is native-only — it redirects a browser to the App Store and
    # an Android UA to an APK download, so the store list lives inside the native app behind
    # its own (likely signed) API, not a readable web endpoint. No app-API path found.
    BLOCKED_REASON = ("site's /api/v1/page key=stores is a 13-store global showcase, not a US"
                      " locator; the 喜茶GO ordering app is native-only (no readable web store"
                      " API); no US subdomain resolves (re-confirmed 22 Sep 2026)")
    RECHECK = ["https://www.heytea.com/en-us/store"]


class YangsAdapter(Adapter):
    """
    Yang's Braised Chicken Rice (杨铭宇黄焖鸡) — trading in the US since September 2017.

    In the archive because it is HERE, not because it is easy. It opened in Tustin, California in
    2017, franchised through Orange County and beyond, and the trade press counts roughly a
    hundred locations across the US, Australia, Japan and Singapore — making it one of the
    earliest and least-covered Chinese chains in America, operating for eight years while the
    attention went to the tea shops that arrived in 2023.

    No first-party US locator has been identified, and a second pass on 21 Sep 2026 did not find
    one. yangschicken.ca — the North American site that search engines still index — RESOLVES
    (142.93.152.61) and then does not answer: every connection times out. That is worth
    distinguishing from a domain that has lapsed, because a host that is merely unreachable from
    here may answer from elsewhere, and is worth one attempt from a different network before the
    chain is written off. yangsbraisedchicken.com, yangschickenrice.com, yangschicken.us,
    yangsbraisedchickenrice.us and ymyusa.com do not resolve at all.

    Meanwhile the US estate is visibly churning: Yelp lists the original Tustin store, Culver City
    and Cupertino as CLOSED, while trade coverage counts roughly eight restaurants in California.
    A chain opening and closing without any first-party list is precisely the case a census exists
    to catch and precisely the case it cannot reach.

    THAT ATTEMPT HAS NOW BEEN MADE, 21 SEP 2026, and the answer is stranger than "unreachable".
    The site loads normally in the operator's browser. It times out from `curl` run in the
    operator's OWN terminal, on the same machine and the same network, outside any sandbox — 25
    seconds, no bytes. The browser pane could not reach it either. So this is not a dead host, a
    lapsed domain or a sandbox restriction: the server serves browsers and refuses programmatic
    clients, silently, by hanging rather than answering.

    That rules out the cheap fixes. Collecting it would mean driving a real browser session daily,
    the same decision Pop Mart needs, and it should be made once for both rather than twice.

    BEFORE PAYING THAT PRICE, SETTLE THIS. A Yang's store page supplied on 21 Sep 2026 presents
    the Tustin restaurant — 13824 Red Hill Ave, the chain's FIRST US location, opened September
    2017 — as trading: current hours, a phone number, no closure notice. Yelp, updated September
    2026 with 354 reviews, marks that same address CLOSED, as it also does Culver City and
    Cupertino.

    If Yelp is right, Yang's own locator is carrying stores that have shut, and that would make it
    nearly worthless for this project's purpose whatever it cost to collect. A census detects a
    closure by a store DISAPPEARING from the list. A list that never removes anything cannot ever
    produce one: it would report a chain growing monotonically forever, and the archive would
    faithfully record the fiction. Tai Er's locator lied by repeating one record; this would be a
    quieter lie with a longer half-life.

    So the order of work is: verify Tustin on the ground (a phone call would do it), THEN decide
    about the browser session. Collecting a stale list daily produces a beautiful, dated, useless
    series.
    """
    chain_id, name, name_zh = "yangs", "Yang's Braised Chicken Rice", "杨铭宇黄焖鸡"
    parent, format = "Yang's Braised Chicken Rice", "restaurant"
    ENABLED = False
    BLOCKED_REASON = ("trading in the US since 2017; yangschicken.ca serves browsers and hangs on"
                      " programmatic clients — verified from the operator's own terminal"
                      " (21 Sep 2026)")
    RECHECK = ["https://yangschicken.ca/"]


class TaiErAdapter(Adapter):
    """
    Tai Er (太二) — the pickled-cabbage-fish chain of Jiumaojiu (HKEX 9922), trading in the US.

    INVESTIGATED IN FULL ON 21 SEP 2026, AND THE ANSWER IS NO. Recorded in detail because the
    failure is instructive and because the next person should not have to re-derive any of it.

    The lead was real. The parent's English site has a store finder at
    en.jiumaojiu.com/store/taier.html, backed by:

        POST http://en.jiumaojiu.com/AjaxAction/store.ashx?action=list
        nodecode=126005002002   the Tai Er brand node
        page=1, s=100           `s` is the PAGE SIZE, not a search string — sending it empty
                                returns zero rows with a success status, which is how this looks
                                like a dead endpoint when it is really a misuse of it
        area=100000010754661    United States   (New York 100000010797299,
                                China 100000010775853, Guangdong 100000010716265,
                                Beijing 100000010789915)

    It answers, it answers quickly, and its counts look right: 12 stores in total, 5 of them in
    the United States. Every single record it returns is the same restaurant — "TAI ER Suancai &
    Fish Guangzhou Grandview Plaza Branch", the same address, the same Google Maps URL, repeated
    as many times as the count demands. Filter to the United States and it returns five copies of
    a Guangzhou restaurant.

    So the endpoint carries a plausible COUNT and worthless RECORDS. An adapter written against
    it without reading the rows would have reported "12 Tai Er stores, 5 in the US" — a
    well-formed, plausible, entirely wrong answer that would have sat in the archive looking
    exactly like every correct number beside it. A locator that is blocked costs a chain; a
    locator that lies costs the archive's credibility.

    The page is also stamped "Updated: May 1, 2022", so even the counts are four years stale —
    and the company's own filings say 31 restaurants outside China at H1 2025, which this page
    does not reflect. taier.net, the brand site, has no US content at all.

    ALIAS CHECKED 21 SEP 2026: it trades in America as "Tai Er Sichuan Cuisine", which is the
    same brand and not a different one, so the earlier search missed nothing. taierusa.com exists
    and answers 401 "Private Site" — password-protected, not public. The US estate is meanwhile
    growing past what the parent's page admits: a first Bay Area restaurant opened in San Mateo,
    and Flushing and Arcadia are separately attested.

    NEXT: nothing first-party is available. Tai Er will need either the app's store API, or a
    corroborated reconstruction from several third-party sources, which is a different kind of
    product and should be a deliberate decision rather than a quiet fallback. Its parent still
    discloses overseas counts twice a year, which remains the best check on whatever is built.

    LEGAL: robots.txt returns 404 on both jiumaojiu.com and en.jiumaojiu.com, i.e. no
    restriction. The endpoint was queried a handful of times at probe rates, not crawled.
    """
    chain_id, name, name_zh = "taier", "Tai Er", "太二"
    name_us = "Tai Er Sichuan Cuisine"
    parent, format = "Jiumaojiu International (HKEX 9922)", "restaurant"
    ENABLED = False
    # 22 Sep 2026: the store page posts to /AjaxAction/store.ashx?action=list with a
    # nodecode=126005001002 filter. It answers {"status":1,"count":1} — a single record,
    # the Guangzhou Grandview Plaza flagship, for any page/area/keys. The international
    # site simply does not carry the US estate; there is no US endpoint to read here.
    # 22 Sep 2026, app-API hunt: taierusa.com exists but is a password-protected Squarespace
    # "Private Site" — an unlaunched US page — and no jiumaojiu/taier app host resolved. When
    # that site launches it may expose a store list; until then there is nothing to read.
    BLOCKED_REASON = ("in the US; the parent's international store endpoint"
                      " (/AjaxAction/store.ashx) returns a single Guangzhou flagship; taierusa.com"
                      " is an unlaunched private Squarespace (re-confirmed 22 Sep 2026)")
    RECHECK = ["https://www.taierusa.com/", "http://en.jiumaojiu.com/store/taier.html"]


class ChaPandaAdapter(Adapter):
    """
    ChaPanda (茶百道) — entered the US in August 2025, first store in Flushing, Queens.

    IT TRADES IN AMERICA AS **TeaByDo**, not as ChaPanda — a transliteration of Cha-bai-dao. That
    matters more than a footnote: this project searched "ChaPanda" and found nothing, exactly as a
    search for "Juewei" misses "King of Braise" in Singapore. A chain hunted under the wrong name
    looks absent, and the archive would have recorded the absence rather than the name error.

    First US store: 38-03 Main Street, Flushing, Queens — opened 18 August 2025, its first in
    North America. teabydo.us is registered but unconfigured (TLS answers "unrecognized name"),
    teabydo.com has no A record, and chapanda.com does not resolve; the US presence surfaces only
    through delivery platforms. So the conclusion below is unchanged, but the next search should
    run on the right name.

    PROBED 21 SEP 2026: there is nothing to collect yet, and the reason is worth distinguishing
    from every other blocked chain here. Pop Mart is defended, Tai Er's locator is wrong, Cotti
    never built one. ChaPanda simply has not grown enough to need one: chapanda.com is a global
    FRANCHISE-RECRUITMENT site — it sells store formats ("Window stores: 30-45 sqm", "Seating
    stores: 60-80 sqm") to prospective franchisees and lists no shops at all. No US-facing
    domain exists (chapandausa.com, chapanda.us, chapandatea.com, chapandaus.com all fail to
    resolve). chabaidao.com belongs to a Sichuan consulting entity, not the consumer brand.

    THIS IS A TEMPORARY STATE, WHICH IS THE POINT. A chain with one or two American shops has no
    reason to publish a locator; a chain with thirty does. ChaPanda is the clearest case in the
    project of a blocker that will expire on its own, which is why `recheck` exists — the
    interesting moment is the day the locator appears, and nothing but a periodic re-probe will
    notice it.

    Starting the day it does appear would capture essentially the chain's whole US history,
    since it has only been here since August 2025.
    """
    chain_id, name, name_zh = "chabaidao", "ChaPanda", "茶百道"
    name_us = "TeaByDo"
    parent, format = "Sichuan Baicha Baidao (HKEX 2555)", "tea"
    ENABLED = False
    BLOCKED_REASON = ("trades as TeaByDo in the US; first store Flushing 18 Aug 2025, too few to"
                      " publish a locator and teabydo.us is parked (21 Sep 2026)")
    RECHECK = ["https://teabydo.us/", "https://www.chapanda.com/"]


class NaixueAdapter(Adapter):
    """
    Naixue / Nayuki (奈雪的茶) — US entry at American Dream, East Rutherford, New Jersey.

    Announced a US push as early as 2020 and took years to arrive, which is itself the useful
    fact: an announcement is not an opening, and this register has three cases of a chain
    entering a market, leaving and returning. HKEX 2150.

    IT HAS THREE NAMES AND THAT IS THE PROBLEM. 奈雪的茶 at home; Nayuki in its own earlier
    English branding; **NaiSnow** as its current international trade name; and "Nayuki Tea &
    Bakery" on the US shopfront and social accounts. A search under any one of them misses the
    others.

    Checked 21 Sep 2026 under the new name: naisnow.us resolves, answers with 90 KB, allows
    everything in robots.txt — and is a GoDaddy parking page reading "THIS DOMAIN IS FOR SALE".
    A squatter, not the chain. naisnow.com is a 501-byte stub. So the alias did not unlock a
    locator, but it did surface a SECOND US location: press coverage puts a NaiSnow on the Upper
    West Side, alongside the American Dream store in East Rutherford.
    """
    chain_id, name, name_zh = "nayuki", "Naixue", "奈雪的茶"
    name_us = "Naisnow"
    # "Nayuki" is the brand's long-standing international romanization (and HK IPO name); it is
    # neither the US trading name (Naisnow) nor the current pinyin (Naixue), so without it here the
    # chain is unfindable by the name most people know. Flows to the map + register + Chains search.
    aliases = ["Nayuki"]
    parent, format = "Nayuki Holdings (HKEX 2150)", "tea"
    ENABLED = False
    BLOCKED_REASON = ("trades as NaiSnow in the US; at least two stores (American Dream NJ, Upper"
                      " West Side NY) and naisnow.us is a parked domain for sale (21 Sep 2026)")
    RECHECK = ["https://www.naixue.com/", "https://naisnow.us/"]


class JueweiAdapter(Adapter):
    """
    Juewei (绝味鸭脖) — braised snacks, and until 21 Sep 2026 this project recorded its US
    presence as "not established". That was wrong, and the reason is instructive.

    IT TRADES IN AMERICA AS "JUEWEI YABO" (鸭脖 = duck neck), with outlets at the USC campus in
    Los Angeles and in San Gabriel; a San Diego store under "Juewei Food" shows closed. In
    Singapore it sells as **King of Braise**. Three markets, three names, and this project had
    already written down the Singapore trap as a lesson before walking into the American one.
    The register said "no evidence of US presence has been checked", which was true and read as
    absence.

    No first-party US locator: jueweiyabo.com, yabo-us.com and jueweiusa.com do not resolve, and
    the corporate site jueweifood.com/eng/ carries no store list. The US presence surfaces through
    delivery platforms only.

    Shanghai-listed (603517), 16,000+ outlets, so overseas counts may appear in filings.
    """
    chain_id, name, name_zh = "juewei", "Juewei", "绝味鸭脖"
    name_us = "Juewei Yabo"
    aliases = ("Jue Wei Kitchen", "Jue Wei Food")
    parent, format = "Juewei Food (SSE 603517)", "snack"
    ENABLED = False
    BLOCKED_REASON = ("trades as Juewei Yabo in the US (LA, San Gabriel); no first-party locator"
                      " and no US domain resolves (21 Sep 2026)")
    RECHECK = ["https://jueweifood.com/eng/"]


class YangguofuAdapter(Adapter):
    """
    Yangguofu Mala Tang (杨国福麻辣烫) — added 22 Sep 2026, and it arrived by a route none of the
    others did: a franchise disclosure document.

    NOT to be confused with Yang's Braised Chicken (杨铭宇黄焖鸡). Two different "Yang" chains; the
    search for Yang's FDD in Wisconsin turned up this one instead. Yangguofu is one of China's
    largest malatang (spicy-soup) chains — malatang is a build-your-own skewered hotpot-soup — and
    unlike the rest of the blocked cohort it is a REGISTERED US FRANCHISOR, filing through Captain
    Business Management Co., Limited (US arm established 8 Apr 2024, franchisor entity behind YGF /
    ygfus.com).

    WHY IT IS HERE AND WHY IT IS NOT COLLECTED. Its own US site, ygfus.com, publishes no store
    locator — the "LOCATIONS" item is commented out of the site's own navigation, so there is
    nothing to read daily. What exists instead is its FDD, whose Item 20 is a legally-required,
    complete roster: 23 US franchised outlets across nine states as of 31 Dec 2025 (CA 10, WA 4,
    NY 3, and one each in FL, GA, IL, IN, MA, TX), reconciled exactly against Exhibit C's
    addresses. That roster lives in manual/sightings.json as a DATED roster — complete as of a day,
    not monitored — because it is a snapshot from a filing, not something the collector re-reads.
    The same filing projects 37+ new outlets for 2026, so the number is already low.

    THE FDD LESSON, stated plainly: this document is the national roster the Cotti FDD could not
    give (Cotti had just registered, zero outlets) and Yang's Braised Chicken had none of (not a
    registered franchisor). It works only for a chain that genuinely franchises WITH history — and
    the franchise registry doubles as a discovery tool, since this chain was found in it, not
    sought.

    RECHECK ygfus.com: the day it publishes a locations page, this becomes a collected chain and
    the FDD roster is superseded by a daily census.
    """
    chain_id, name, name_zh = "yangguofu", "Yangguofu", "杨国福麻辣烫"
    name_us = "YGF"
    parent, format = "Captain Business Management Co. (Yang Guo Fu Malatang)", "restaurant"
    ENABLED = False
    BLOCKED_REASON = ("registered US franchisor with a complete FDD roster (23 outlets in 9 states"
                      " as of 31 Dec 2025), but ygfus.com publishes no live locator — its"
                      " LOCATIONS nav is commented out. Roster held as a dated manual roster,"
                      " not a daily census (22 Sep 2026)")
    RECHECK = ["https://www.ygfus.com/"]


class FishWithYouAdapter(Adapter):
    """
    Fish With You (鱼你在一起) — added 22 Sep 2026, found by the same franchise-registry sweep that
    surfaced Yangguofu. A Chinese fast-casual chain built on one dish: 酸菜鱼, Sichuan sauerkraut
    (pickled-mustard-green) fish over rice. Founded in Beijing around 2016, it grew to thousands of
    outlets across China and registered a US franchise offering (Wisconsin file 639995, "Fish With
    You (US) Brand Management Inc.", trade names Fish With You / YONNY).

    IN SCOPE, and confirmed first-party: the Flushing storefront's own page, fishwithyouny.com,
    identifies it as 鱼你在一起（法拉盛）Fish With You | Sauerkraut Fish 酸菜鱼 at 135-25A 40th Rd,
    Flushing, NY 11354. Chinese origin, not Taiwan or Hong Kong.

    NO NATIONAL LOCATOR. The web presence is per-store (fishwithyouny.com is the Flushing shop
    alone), so there is nothing to collect daily. Its complete US roster is where Yangguofu's was —
    inside its FDD (Item 20 / Exhibit C). Until that filing is pulled, only the one confirmed
    Flushing location is held, as a single sighting, and the chain is marked present-not-collected.
    RECHECK the site, and pull WI file 639995 to lift the roster the way Yangguofu's was lifted.
    """
    chain_id, name, name_zh = "fishwithyou", "Fish With You", "鱼你在一起"
    name_us = "Fish With You"
    aliases = ("Wei's Fish", "YONNY", "YONNY Mini Hot Pot")
    parent, format = "Fish With You (US) Brand Management / Yu You (Beijing)", "restaurant"
    ENABLED = False
    # 22 Sep 2026: pulled its FDD (WI 639995, effective 23 Nov 2025). Item 20 is EMPTY for the
    # US — 0 franchised and 0 company-owned outlets for 2022-2024, no franchisee-list exhibit,
    # only its 2,500 China outlets shown "for reference". Same as Cotti: a just-registered
    # franchisor whose existing US stores are not franchised, so the FDD does not enumerate
    # them. The web-search-verified sightings are the US data, not the filing.
    BLOCKED_REASON = ("sauerkraut-fish chain (鱼你在一起), registered US franchisor"
                      " (WI 639995) but its FDD Item 20 is empty of US outlets; web presence is"
                      " per-store with no national locator. Tracked via verified sightings"
                      " (Flushing, LA, Ellicott City MD, Irvine + leads) (22 Sep 2026)")
    RECHECK = ["https://www.fishwithyouny.com/"]


class CottiAdapter(Adapter):
    """
    Cotti Coffee US — no first-party US locator found.

    cotticoffee.com serves a global brand site with no /us path (404), us.cotticoffee.com and
    cotticoffeeusa.com do not resolve, and the US presence surfaces through third parties
    instead: individual franchisee sites, a Joe Coffee ordering page per store, and mall
    directories. Third-party aggregators are explicitly out of scope for a first-party census —
    they are someone else's refresh cadence and someone else's mistakes.

    RE-INVESTIGATED 21 SEP 2026. cotticoffee.global, the international corporate site, does have
    a STORES entry in its navigation — and it is a photo carousel of thirty selected shops with
    city captions ("Bay St., Toronto, Canada"), served from a route that 404s on direct request
    because the SPA has no server-side fallback. A gallery, not a locator. For a chain claiming
    18,000+ outlets that is a striking absence, and it is the finding: Cotti does not publish
    where it is.

    SECOND PASS, 21 SEP 2026 — and the wall is now a consent boundary, not a technical one.
    Cotti does run a US store finder: mobile.us.cotticoffee.global/?cnty=US, a Flutter web app.
    It renders to canvas (no DOM to read) and it opens on a **Legal Statement** screen requiring
    acceptance of Terms and Conditions and a Privacy Policy before anything loads. This project
    will not click that on the operator's behalf: accepting an agreement is the operator's to
    give, and no store count is worth having an automated agent enter into one.

    So Cotti is collectable in principle and blocked in practice, pending a decision by a human
    about those terms. That is a better-defined blocker than "no locator exists", and it is the
    one to put to the operator.

    KNOWN LOCATIONS, HELD AS EVIDENCE AND NOT AS A ROSTER. A Cotti marketing graphic supplied on
    21 Sep 2026 lists five New York stores:

        345 7th Ave, New York, NY 10001
        170 W 23rd St, New York, NY 10011
        482 3rd Ave, New York, NY 10016
        135-29 Roosevelt Ave, Flushing, NY 11354      (Roosevelt Ave Flushing)
        41-28 Main St, Flushing, NY 11354             (Golden Mall Flushing)

    They are NOT in the store census, deliberately. The graphic covers New York County and Queens
    County only, while Cotti is separately attested in San Gabriel CA, Pearl City HI, Champaign IL,
    Staten Island and Brooklyn — so five is a floor, not a footprint. Filing a partial roster now
    would mean that the day the real source is read, every store it contains beyond these five
    would be recorded as an OPENING that never happened. `fetch_raw` says a partial result is
    worse than a failed run for exactly this reason, and a partial result supplied by hand is no
    different. These five belong here, as corroboration for whatever is collected later.
    """
    chain_id, name, name_zh = "cotti", "Cotti Coffee", "库迪咖啡"
    parent, format = "Cotti Coffee", "coffee"
    ENABLED = False
    # 22 Sep 2026: the Flutter bundle names its gateway and its endpoints. The US store list
    # is POST /cotti-capi/shop/searchShopList on gateway.us.cotticoffee.global, and it
    # answers 200 with {"code":401,"message":"MD5 signature cannot be verified"}. It is a
    # SIGNED endpoint, not a terms gate: reading it means forging the app's request
    # signature, which is defeating an access control. That is a firmer no than before,
    # not a softer one — the door is not merely inconvenient, it is locked.
    BLOCKED_REASON = ("US store list is POST /cotti-capi/shop/searchShopList on"
                      " gateway.us.cotticoffee.global; it requires the app's MD5 request"
                      " signature (returns 401 \"MD5 signature cannot be verified\"), an"
                      " access control this project will not forge (22 Sep 2026)")
    RECHECK = ["https://mobile.us.cotticoffee.global/?cnty=US", "https://www.cotticoffee.global/"]


class ZhangliangAdapter(Adapter):
    """
    Zhang Liang Malatang (张亮麻辣烫) — added 2026-09-26. With Yangguofu, one of China's two
    dominant self-serve malatang chains, founded in Harbin in 2008, ~6,000 outlets.

    Its own brand news (zlmlt.com, 11 Sep 2026) claims 42 outlets across North America — the US,
    Canada and Mexico — from San Francisco and Los Angeles to Toronto and Vancouver. There is no
    single US locator: US outlets surface through per-region franchisee sites (zhangliangmtv.com),
    an LA-area Instagram (@zhangliangmalatangla), city-government notices and delivery platforms.
    Verified US locations so far cluster in California (Bay Area and LA). Tracked via sightings.
    """
    chain_id, name, name_zh = "zhangliang", "Zhang Liang", "张亮麻辣烫"
    name_us = "Zhang Liang Malatang"
    aliases = ("Zhangliang Malatang", "Zhangliang Spicy Hotpot", "ZhangLiang MalaTang")
    parent, format = "Zhang Liang (张亮餐饮, Harbin)", "restaurant"
    ENABLED = False
    BLOCKED_REASON = ("malatang chain (张亮麻辣烫); its brand news claims 42 North American"
                      " outlets (US/Canada/Mexico, 11 Sep 2026) but there is no single US locator —"
                      " US shops appear on per-region franchisee sites, an LA Instagram and delivery"
                      " apps. Tracked via sightings (26 Sep 2026)")
    RECHECK = ["https://www.zlmlt.com/"]


class ChahaloAdapter(Adapter):
    """
    ChaHalo (茶话弄) — added 2026-09-27. A premium "modern Chinese tea" chain founded in 2016 in
    Xi'an (Shaanxi), parent Xi'an Baamu Tian Catering (西安八亩田餐饮管理), ~1,000 stores across
    170+ Chinese cities. Chinese origin, so in scope.

    Recent US entry with no single US locator: outlets surface through per-store sites, delivery
    apps and review aggregators (City of Industry, Berkeley, NYC so far), and it is expanding into
    Canada (Toronto). Tracked via sightings.
    """
    chain_id, name, name_zh = "chahalo", "ChaHalo", "茶话弄"
    aliases = ("Cha Hua Nong", "Cha Halo")
    parent, format = "Xi'an Baamu Tian Catering (西安八亩田餐饮)", "tea"
    ENABLED = False
    BLOCKED_REASON = ("premium-tea chain (茶话弄, Xi'an; ~1,000 stores in China); recent US"
                      " entry (City of Industry, Berkeley, NYC) with no single US locator, also"
                      " expanding into Canada. Tracked via sightings (27 Sep 2026)")
    RECHECK = ["https://www.chahalo.com/"]


class LelechaAdapter(Adapter):
    """
    Lelecha (乐乐茶) — added 2026-09-28. A premium "modern Chinese tea" chain founded in 2016 in
    Shanghai, known for cheese-foam teas and bread; Chinese origin, so in scope.

    Its US site (lelechaus.com) is an unlaunched Squarespace "Private Site" (noindex), so there is
    no public first-party locator. US presence surfaces through Yelp and delivery apps (Rowland
    Heights so far). Tracked via sightings.
    """
    chain_id, name, name_zh = "lelecha", "Lelecha", "乐乐茶"
    name_us = "Lelecha"
    aliases = ("Le Le Cha", "LELECHA")
    parent, format = "Lelecha (乐乐茶, Shanghai)", "tea"
    ENABLED = False
    BLOCKED_REASON = ("premium-tea chain (乐乐茶, Shanghai); US entry with no public"
                      " locator — lelechaus.com is an unlaunched private Squarespace, so outlets"
                      " surface only on Yelp and delivery apps. Tracked via sightings (28 Sep 2026)")
    RECHECK = ["https://www.lelechaus.com/"]


class NonggengjiAdapter(Adapter):
    """
    Nong Geng Ji (农耕记 · 湖南菜) — added 2026-09-28. A Hunan-cuisine restaurant chain from
    Shenzhen known for countryside-style, wok-charred Hunan cooking; Chinese origin, so in scope.

    First US location opened Flushing, Queens in January 2026; a second is announced for Rockville,
    Maryland (1701 Rockville Pike) with no opening date. Too few US outlets to publish a locator,
    so tracked via sightings; the announced Rockville site is noted but not mapped until it opens.
    """
    chain_id, name, name_zh = "nonggengji", "Nong Geng Ji", "农耕记"
    name_us = "Nong Geng Ji"
    aliases = ("Nonggengji", "Nong Geng Ji Hunan Cuisine")
    parent, format = "Nong Geng Ji (农耕记, Shenzhen)", "restaurant"
    ENABLED = False
    BLOCKED_REASON = ("Hunan-cuisine chain (农耕记, Shenzhen); first US restaurant opened"
                      " Flushing NY Jan 2026, a second announced for Rockville MD. Too few US"
                      " outlets for a locator; tracked via sightings (28 Sep 2026)")
    RECHECK = []


class BaosPastryAdapter(Adapter):
    """
    Bao's Pastry (鲍师傅糕点) — added 2026-09-28. A Beijing-headquartered bakery chain (founder Bao
    Caisheng; 100+ outlets in China) known for pork-floss cakes and cream-filled sponge; Chinese
    origin, so in scope.

    First US store opened Flushing, Queens in late 2025; there is no first-party US site, so it is
    tracked via sightings.
    """
    chain_id, name, name_zh = "baospastry", "Bao's Pastry", "鲍师傅"
    name_us = "Bao's Pastry"
    aliases = ("Bao Shifu", "鲍师傅糕点")
    parent, format = "Bao's Pastry (鲍师傅, Beijing)", "bakery"
    ENABLED = False
    BLOCKED_REASON = ("bakery chain (鲍师傅糕点, Beijing; 100+ China stores); first US store"
                      " opened Flushing NY late 2025, no first-party US site. Tracked via sightings"
                      " (28 Sep 2026)")
    RECHECK = []


class TopToyAdapter(Adapter):
    """
    TOP TOY — added 2026-09-28. A Chinese art-toy / blind-box retailer launched in 2020 by MINISO
    Group (Guangzhou), a direct peer of POP MART and MINISO already tracked here; Chinese origin,
    so in scope.

    Its US site (gotoptoy.com) publishes a "USA Store Locations" page, but it is a JS-rendered
    Shopify page listing a single US store (Times Square) with no plain-HTTP roster, so it is
    tracked via sightings until a second store or a machine-readable locator appears.
    """
    chain_id, name, name_zh = "toptoy", "TOP TOY", "TOP TOY"
    name_us = "TOP TOY"
    aliases = ("TOPTOY",)
    parent, format = "MINISO Group", "toys"
    ENABLED = False
    BLOCKED_REASON = ("art-toy/blind-box retailer (TOP TOY, launched 2020 by MINISO Group);"
                      " its US locator (gotoptoy.com) is a JS-rendered Shopify page listing one US"
                      " store (Times Square). Tracked via sightings (28 Sep 2026)")
    RECHECK = ["https://www.gotoptoy.com/pages/toptoy-usa-store-locations"]


class Toys52Adapter(Adapter):
    """
    52Toys — added 2026-09-28. A Chinese designer-toy / blind-box brand founded 2015 in Beijing
    (乐自天成), a peer of POP MART and TOP TOY; Chinese origin, so in scope.

    Its US site (us.52toys.com) is an online store with no locator; US retail presence surfaces
    through mall directories and aggregators (Mall of Georgia and Doraville GA so far), so it is
    tracked via sightings.
    """
    chain_id, name, name_zh = "toys52", "52Toys", "52TOYS"
    name_us = "52Toys"
    aliases = ("52TOYS",)
    parent, format = "52TOYS (乐自天成, Beijing)", "toys"
    ENABLED = False
    BLOCKED_REASON = ("designer-toy/blind-box brand (52TOYS, founded 2015 in Beijing);"
                      " us.52toys.com is an online store with no locator, so US outlets (Mall of"
                      " Georgia, Doraville GA) surface via mall directories. Tracked via sightings"
                      " (28 Sep 2026)")
    RECHECK = []


# The 2026-09-29 batch: Chinese sit-down / hot-pot chains already trading in the US, found by
# building the internal watchlist of top China chains and checking which had already crossed over.
# Each is present-not-collected — a real US footprint, no first-party national locator to read —
# so each is tracked via hand-verified sightings, with the addresses confirmed open by web search
# (press, the store's own site, recent review activity) rather than assembled from an aggregator.

class DezhuangAdapter(Adapter):
    """
    Dezhuang / De Zhuang Hot Pot (德庄火锅) — added 2026-09-29. A Chongqing hot-pot restaurant and
    seasoning group founded 1999 by Li Dejian (李德建); parent 重庆德庄实业（集团）有限公司, ~900+
    restaurants in China. Chinese origin, so in scope.

    Two US outlets confirmed open: the full "De Zhuang Hot Pot" at 37 St Marks Pl, New York (the
    brand's US arrival, ~early 2025), and a "De Hotpot Mini" (德庄小火锅) express store in Bellevue,
    WA. No first-party national US locator — the English site dezhuangofficial.com is a global
    brand page, not a store list — so tracked via sightings.
    """
    chain_id, name, name_zh = "dezhuang", "Dezhuang", "德庄"
    name_us = "De Zhuang Hot Pot"
    aliases = ("De Zhuang", "De Hotpot Mini", "德庄火锅")
    parent, format = "Chongqing Dezhuang Industrial Group (重庆德庄实业集团)", "hotpot"
    ENABLED = False
    BLOCKED_REASON = ("Chongqing hot-pot chain (德庄, founded 1999); US outlets in NYC"
                      " (37 St Marks Pl) and Bellevue WA, but dezhuangofficial.com is a global brand"
                      " page with no US locator. Tracked via sightings (29 Sep 2026)")
    RECHECK = ["https://dezhuangofficial.com/", "https://www.dezhuanghotpotmini.com/"]


class MeizhouDongpoAdapter(Adapter):
    """
    Meizhou Dongpo (眉州东坡) — added 2026-09-29. A Sichuan-cuisine sit-down chain founded in
    Beijing in 1996 by Wang Gang (王刚) and Liang Di (梁棣); parent Meizhou Dongpo Group; ~114
    outlets in China. One of the earliest Chinese chains in the US — its Century City (Los Angeles)
    flagship opened in 2013. Chinese origin, so in scope.

    Two US outlets confirmed open in 2026 (Century City and Irvine, both CA); three former LA-area
    locations (Universal CityWalk, Arcadia, Baldwin Park) are closed. The former US site
    meizhou.us.com no longer resolves, so there is no first-party locator to read; tracked via
    sightings.
    """
    chain_id, name, name_zh = "meizhoudongpo", "Meizhou Dongpo", "眉州东坡"
    name_us = "Meizhou Dongpo"
    aliases = ("Dongpo Kitchen",)
    parent, format = "Meizhou Dongpo Group (眉州东坡集团, Beijing)", "restaurant"
    ENABLED = False
    BLOCKED_REASON = ("Sichuan-cuisine chain (眉州东坡, founded Beijing 1996); in the US"
                      " since 2013 with two open CA outlets (Century City, Irvine) after three LA-area"
                      " closures, and its US site meizhou.us.com no longer resolves. Tracked via"
                      " sightings (29 Sep 2026)")
    RECHECK = ["https://meizhou.us.com/"]


class ShudaxiaAdapter(Adapter):
    """
    Shu Da Xia (蜀大侠) — added 2026-09-29. A Chengdu, Sichuan hot-pot chain founded 2015; parent
    Chengdu Shu Daxia Catering Management Co., and since January 2023 owned by the Xiaolongkan /
    Shoo Loong Kan group (小龙坎) — the same parent as a chain this project already collects, but a
    distinct Chinese brand, so in scope on its own.

    One US outlet confirmed open: Boston (580 Commonwealth Ave), open since May 2022. A Toronto
    store exists but is Canada, not US. The Boston store runs its own site; there is no national US
    locator, so tracked via sightings.
    """
    chain_id, name, name_zh = "shudaxia", "Shu Da Xia", "蜀大侠"
    name_us = "Shu Da Xia Hotpot"
    aliases = ("Shudaxia", "Shu Daxia")
    parent, format = "Xiaolongkan group (小龙坎; acquired Shu Daxia 2023)", "hotpot"
    ENABLED = False
    BLOCKED_REASON = ("Chengdu hot-pot chain (蜀大侠, founded 2015; owned by the Xiaolongkan"
                      " group since 2023); one US outlet, Boston (580 Commonwealth Ave) open since"
                      " May 2022, with only a per-store site. Tracked via sightings (29 Sep 2026)")
    RECHECK = ["https://www.shudaxiaboston.com/", "https://www.shudaxiaus.com/"]


class XibeiAdapter(Adapter):
    """
    Xibei / Xibei Youmiancun (西贝莜面村) — added 2026-09-29. The flagship brand of Xibei Catering
    Group, founded by Jia Guolong; the business traces to a 1988 snack shop in Linhe, Inner
    Mongolia, opened its first Youmiancun in Beijing in 2002, and now runs ~370+ outlets in China of
    Northwestern-China oat-noodle-and-mutton cuisine. Chinese origin, so in scope.

    Four US outlets confirmed open in 2026, all in Southern California, trading under three US
    sub-labels run by one operator (@xibei.us): the flagship "Xibei" (Arcadia), "Xibei Dumplings"
    (Silver Lake, the Dec 2024 first US store), and "Xibei Eatery" fast-casual (Santa Ana, Westwood).
    No single national US locator — the Arcadia store uses its own ordering site — so tracked via
    sightings. (Corporate ownership vs. licensee is not documented in English sources; treated as
    the Xibei brand's US expansion.)
    """
    chain_id, name, name_zh = "xibei", "Xibei", "西贝莜面村"
    name_us = "Xibei"
    aliases = ("Xibei Youmiancun", "Xibei Dumplings", "Xibei Eatery")
    parent, format = "Xibei Catering Group (西贝餐饮集团)", "restaurant"
    ENABLED = False
    BLOCKED_REASON = ("Northwestern-China chain (西贝莜面村, ~370+ China stores); four open"
                      " SoCal outlets under three US sub-labels (Arcadia flagship, Silver Lake"
                      " dumplings, Santa Ana + Westwood 'Eatery'), first US Dec 2024, no national US"
                      " locator. Tracked via sightings (29 Sep 2026)")
    RECHECK = ["https://www.xibeiarcadia.com/", "https://www.xibei.com.cn/"]


class GrandmasHomeAdapter(Adapter):
    """
    Grandma's Home (外婆家 / Waipojia) — added 2026-09-29. A Hangzhou-cuisine chain founded 1998 in
    Hangzhou by Wu Guoping (吴国平); parent 外婆家餐饮集团, 200+ directly-run restaurants across
    China. Chinese origin, so in scope.

    One US outlet confirmed open: 56 West 22nd St, Manhattan (Flatiron), the chain's first US
    restaurant, opened ~March 2024. The US site lists only this location; no national locator, so
    tracked via sightings. (Care is needed to distinguish the 外婆家 brand from generically-named
    "Grandma's" restaurants.)
    """
    chain_id, name, name_zh = "grandmashome", "Grandma's Home", "外婆家"
    name_us = "Grandma's Home"
    aliases = ("Waipojia",)
    parent, format = "Grandma's Home Catering Group (外婆家餐饮集团, Hangzhou)", "restaurant"
    ENABLED = False
    BLOCKED_REASON = ("Hangzhou-cuisine chain (外婆家, founded 1998; 200+ China outlets);"
                      " one US restaurant, 56 W 22nd St Manhattan, opened ~March 2024 and its only US"
                      " location. Tracked via sightings (29 Sep 2026)")
    RECHECK = ["https://www.grandmashome.us/"]


class XijiadeAdapter(Adapter):
    """
    Xijiade / Dumpling Xi (喜家德) — added 2026-09-29. A Northeastern-China shrimp-dumpling chain
    founded 2002 in Hegang, Heilongjiang by Gao Defu (高德福); parent Xiding Catering (喜鼎餐饮,
    Dalian); all directly-operated, 800+ China stores. Chinese origin, so in scope.

    It trades in the US as "Dumpling Xi". Two US outlets confirmed open, both in New York City:
    Flushing (37-02 Prince St, the first US store, opened 12 Feb 2025) and the East Village (71 4th
    Ave, opened 1 Jul 2025). The Flushing store runs a per-store US site; no national locator, so
    tracked via sightings.
    """
    chain_id, name, name_zh = "xijiade", "Xijiade", "喜家德"
    name_us = "Dumpling Xi"
    aliases = ("Xi Jia De", "喜家德水饺")
    parent, format = "Xiding Catering (喜鼎餐饮, Dalian)", "restaurant"
    ENABLED = False
    BLOCKED_REASON = ("Northeastern dumpling chain (喜家德, founded Hegang 2002); trades in"
                      " the US as Dumpling Xi with two NYC outlets (Flushing, first US 12 Feb 2025;"
                      " East Village), only a per-store site. Tracked via sightings (29 Sep 2026)")
    RECHECK = ["https://dumplingxius.com/", "https://www.xijiade.com.cn/"]


class MalubianbianAdapter(Adapter):
    """
    Malubianbian / Ma Lu Bian Bian (马路边边) — added 2026-09-29. A Chengdu, Sichuan roadside-style
    skewer hot-pot (串串香) chain founded 2015; parent 成都马路边边餐饮管理有限公司, 1,000+ outlets
    claimed globally. Chinese origin, so in scope.

    Heavy US churn: the first US store (San Gabriel CA, Nov 2019) and the early Rowland Heights,
    Houston and Philadelphia outlets are all closed. As of Sep 2026 the clearly-open US outlet is
    Orlando FL (5062 W Colonial Dr); Tustin CA (rebranded "MLBB AYCE Hot Pot") appears open but is
    held as uncertain pending confirmation. Franchised/loosely operated with per-outlet sites and no
    national locator, so tracked via sightings.
    """
    chain_id, name, name_zh = "malubianbian", "Malubianbian", "马路边边"
    name_us = "Ma Lu Bian Bian"
    aliases = ("MLBB", "MLBB AYCE Hot Pot", "Ma Lu Bian Bian Hot Pot")
    parent, format = "Chengdu Ma Lu Bian Restaurant Management (成都马路边边餐饮)", "hotpot"
    ENABLED = False
    BLOCKED_REASON = ("Chengdu skewer-hotpot chain (马路边边, founded 2015); heavy US churn —"
                      " first US store San Gabriel Nov 2019 and several early CA/TX/PA outlets now"
                      " closed; Orlando FL open, Tustin CA (rebranded MLBB AYCE) uncertain. Per-outlet"
                      " sites, no national locator. Tracked via sightings (29 Sep 2026)")
    RECHECK = ["https://www.malubianbianfl.com/", "https://www.malubianbianca.com/"]


class FeidachuAdapter(Adapter):
    """
    Fei Da Chu (费大厨辣椒炒肉) — added 2026-09-29. A Hunan-cuisine chain built on one signature dish,
    辣椒炒肉 (stir-fried pork with chili peppers); founded by Fei Lianghui in Hunan, hundreds of
    restaurants across China, billed in its US marketing as "China's King of Stir-Fry". Chinese
    origin, so in scope.

    It trades in the US as "Chef Fei". Its first US location opened 5 Sep 2026 at Westfield UTC in
    San Diego and is confirmed operating; no national US locator, so tracked via sightings.
    """
    chain_id, name, name_zh = "feidachu", "Fei Da Chu", "费大厨"
    name_us = "Chef Fei"
    aliases = ("Fei Da Chu La Jiao Chao Rou", "费大厨辣椒炒肉")
    parent, format = "Fei Da Chu (费大厨, Hunan)", "restaurant"
    ENABLED = False
    BLOCKED_REASON = ("Hunan-cuisine chain (费大厨辣椒炒肉, 'stir-fried pork with chili"
                      " peppers'); trades in the US as Chef Fei, first US store opened 5 Sep 2026 at"
                      " Westfield UTC, San Diego, with no national locator. Tracked via sightings"
                      " (29 Sep 2026)")
    RECHECK = []


class DalongyiAdapter(Adapter):
    """
    Dalongyi / Da Long Yi (大龙燚) — added 2026-09-29. A Chengdu, Sichuan hot-pot chain founded 2013
    in the Yulin district; parent 成都大龙燚餐饮管理有限公司, a large franchised chain (2,000+ stores
    claimed) with overseas outlets. Chinese origin, so in scope.

    Two US outlets confirmed open (Long Island City NY and Allston/Boston MA), run as independent
    franchise sites. The first US store (San Gabriel CA, Jun 2019) is closed, as is Seattle; a
    Manhattan Canal St outlet appears closed. No authoritative all-US locator, so tracked via
    sightings.
    """
    chain_id, name, name_zh = "dalongyi", "Dalongyi", "大龙燚"
    name_us = "Da Long Yi Hot Pot"
    aliases = ("Da Long Yi", "Dalongyi Hot Pot")
    parent, format = "Chengdu Dalongyi Catering Management (成都大龙燚餐饮)", "hotpot"
    ENABLED = False
    BLOCKED_REASON = ("Chengdu hot-pot chain (大龙燚, founded 2013); two open US outlets (Long"
                      " Island City NY, Allston/Boston MA) on separate franchise sites, after the"
                      " first US store (San Gabriel 2019) and Seattle closed. No all-US locator."
                      " Tracked via sightings (29 Sep 2026)")
    RECHECK = ["https://www.dalongyinyc.com/", "https://www.dlyhotpot.com/"]


class ShuyiAdapter(Adapter):
    """
    Shuyi Tealicious (书亦烧仙草) — added 2026-09-29. A grass-jelly (烧仙草) milk-tea chain founded
    2007 in Chengdu by Wang Bin; parent 四川书亦餐饮管理有限公司; one of China's largest tea chains
    (~5,000+ stores). Chinese origin, so in scope.

    US shops trade as "Shuyi Grass Jelly & Tea", franchise-operated rather than a unified US
    rollout. Three outlets confirmed open (Falls Church VA, Cupertino CA, Fremont CA); the first US
    store (San Mateo CA, ~late 2023) is closed. No first-party US locator, so tracked via sightings.
    """
    chain_id, name, name_zh = "shuyi", "Shuyi Tealicious", "书亦烧仙草"
    name_us = "Shuyi Grass Jelly & Tea"
    aliases = ("Shuyi Shaixiancao", "Shuyi Grass Jelly and Tea")
    parent, format = "Sichuan Shuyi Catering (四川书亦餐饮, Chengdu)", "tea"
    ENABLED = False
    BLOCKED_REASON = ("Chengdu grass-jelly tea chain (书亦烧仙草, founded 2007; ~5,000+ China"
                      " stores); US shops trade as Shuyi Grass Jelly & Tea, three open (Falls Church"
                      " VA, Cupertino + Fremont CA) after the first US store (San Mateo) closed, no"
                      " first-party US locator. Tracked via sightings (29 Sep 2026)")
    RECHECK = ["https://shuyisxc.com/"]


class MoreYogurtAdapter(Adapter):
    """
    More Yogurt (茉酸奶) — added 2026-09-29. A Shanghai yogurt-drink chain; its own English name is
    "More Yogurt" (茉 ≈ "mò"/"more"). Parent 上海茉酸奶餐饮管理有限公司. Chinese origin, so in scope.
    Abroad it operates in Hong Kong, Malaysia and Singapore (see the international register).

    One US outlet confirmed open: The District at Tustin Legacy (2471 Park Ave, Tustin CA), its
    first and only US store, a soft opening ~June 2026. No national US locator, so tracked via
    sightings.
    """
    chain_id, name, name_zh = "moreyogurt", "More Yogurt", "茉酸奶"
    name_us = "More Yogurt"
    aliases = ("Mo Yogurt", "Mosuannai", "茉酸奶")
    parent, format = "Shanghai More Yogurt Catering (上海茉酸奶餐饮管理)", "tea"
    ENABLED = False
    BLOCKED_REASON = ("Shanghai yogurt-drink chain (茉酸奶, 'More Yogurt'); first US store opened"
                      " ~June 2026 at The District at Tustin Legacy (2471 Park Ave, Tustin CA), its"
                      " only US outlet, with no national locator. Tracked via sightings (29 Sep 2026)")
    RECHECK = ["https://www.districttustin.com/"]


class AntaAdapter(Adapter):
    """
    Anta (安踏) — added 2026-09-30 (Phase-1 apparel backfill). China's largest sportswear group;
    the ANTA nameplate runs ~9,900 stores (nearly all in China). Chinese origin, in scope.

    One US outlet: a first US flagship at 330 N Beverly Dr, Beverly Hills CA, opened 13 Feb 2026,
    company-operated. No national US locator, so tracked via sightings. (Group brands FILA,
    Descente, Amer/Arc'teryx etc. are foreign-origin and out of scope — this is the Anta brand only.)
    """
    chain_id, name, name_zh = "anta", "Anta", "安踏"
    name_us = "Anta"
    aliases = ("ANTA",)
    parent, format = "Anta Sports Products (HKEX 2020)", "apparel"
    ENABLED = False
    BLOCKED_REASON = ("China's largest sportswear brand (安踏, ~9,900 stores); first US store opened"
                      " 13 Feb 2026 at 330 N Beverly Dr, Beverly Hills CA, its only US outlet, with no"
                      " national locator. Tracked via sightings (30 Sep 2026)")
    RECHECK = ["https://www.anta.com/"]


class UrbanRevivoAdapter(Adapter):
    """
    Urban Revivo (UR) — added 2026-09-30 (Phase-1 apparel backfill). Guangzhou fast-fashion chain,
    400+ large-format stores (parent FMG). Chinese origin, in scope.

    One US outlet: a first US flagship at 515 Broadway, SoHo NYC (~30,000 sq ft), opened 28 Feb 2025,
    company-operated. No national US locator, so tracked via sightings.
    """
    chain_id, name, name_zh = "urbanrevivo", "Urban Revivo", ""
    name_us = "Urban Revivo"
    aliases = ("UR", "URBAN REVIVO")
    parent, format = "Fashion Momentum Group (FMG, Guangzhou)", "apparel"
    ENABLED = False
    BLOCKED_REASON = ("Guangzhou fast-fashion chain (UR, 400+ stores); first US store opened 28 Feb"
                      " 2025 at 515 Broadway, SoHo NYC (~30,000 sq ft), its only US outlet, with no"
                      " national locator. Tracked via sightings (30 Sep 2026)")
    RECHECK = ["https://www.urbanrevivo.com/"]


class JnbyAdapter(Adapter):
    """
    JNBY (江南布衣) — added 2026-09-30 (Phase-1 apparel backfill). Hangzhou designer-apparel house,
    ~2,118 stores across its brands (HKEX 3306). Chinese origin, in scope.

    Its US arm trades as "AGoodFun", run by a local licensee (Sightclassic LLC). Two US outlets
    open: San Francisco (865 Market St, Westfield SF Centre) and Seattle (600 Pine St, Pacific
    Place); the Bellevue WA and SoHo NYC stores have closed. No national US locator, so tracked via
    sightings.
    """
    chain_id, name, name_zh = "jnby", "JNBY", "江南布衣"
    name_us = "AGoodFun"
    aliases = ("AGoodFun", "JNBY USA", "Sightclassic")
    parent, format = "JNBY Design (HKEX 3306)", "apparel"
    ENABLED = False
    BLOCKED_REASON = ("Hangzhou designer-apparel house (江南布衣, HKEX 3306); US arm trades as AGoodFun"
                      " via licensee Sightclassic LLC, open in San Francisco (865 Market St) and"
                      " Seattle (600 Pine St) — Bellevue and SoHo NYC closed. No national locator."
                      " Tracked via sightings (30 Sep 2026)")
    RECHECK = ["https://www.jnby.com/"]


class MeilleurMomentAdapter(Adapter):
    """
    Meilleur Moment (伊芙丽 / Eifini) — added 2026-09-30 (Phase-1 apparel backfill). Womenswear line
    of Hangzhou's Eifini group (600+ stores group-wide). Chinese origin, in scope.

    One US outlet: a flagship at 257 Elizabeth St, SoHo NYC, opened May 2025, company-operated.
    No national US locator, so tracked via sightings.
    """
    chain_id, name, name_zh = "meilleurmoment", "Meilleur Moment", "伊芙丽"
    name_us = "Meilleur Moment"
    aliases = ("Eifini",)
    parent, format = "Eifini Group (Hangzhou)", "apparel"
    ENABLED = False
    BLOCKED_REASON = ("Womenswear line of Hangzhou's Eifini group (伊芙丽); first US store opened May"
                      " 2025 at 257 Elizabeth St, SoHo NYC, its only US outlet, with no national"
                      " locator. Tracked via sightings (30 Sep 2026)")
    RECHECK = ["https://www.eifini.com/"]


class WallaceAdapter(Adapter):
    """
    Wallace (华莱士 / Wallace Burger & Chicken) — added 2026-10-04. A Western-style fast-food chain
    (burgers, fried chicken, fries) under Fujian Wallace Food Co., founded in Fuzhou in 2001 by the
    Hua brothers; ~20,000 outlets across China, widely billed as "China's KFC". Chinese origin, in
    scope.

    Its first store outside China opened 17 Nov 2024 at 18732 Amar Rd, Walnut, California, with a
    second SoCal outlet in West Covina. A first-party US site (wallace-usa.com) exists but publishes
    no readable national locator yet, so tracked via sightings.
    """
    chain_id, name, name_zh = "wallace", "Wallace", "华莱士"
    name_us = "Wallace Chicken"
    aliases = ("Wallace Burger & Chicken", "Hualaishi", "华莱士炸鸡")
    parent, format = "Fujian Wallace Food Co. (华莱士)", "restaurant"
    ENABLED = False
    BLOCKED_REASON = ("Western-style fast-food chain (华莱士, 'China's KFC'; ~20,000 China stores);"
                      " first overseas store opened 17 Nov 2024 at 18732 Amar Rd, Walnut CA, with a"
                      " second in West Covina. First-party US site but no readable national locator."
                      " Tracked via sightings (4 Oct 2026)")
    # The locator lists its 2 US stores as static HTML (no API). Watch it: launch-watch fires when
    # the address count on this live page rises, i.e. when Wallace opens a third US store.
    RECHECK = ["https://www.wallace-usa.com/locations-order"]


class ZhengxinAdapter(Adapter):
    """
    Zhengxin Chicken Steak (正新鸡排) — added 2026-10-04. A fried-chicken-steak fast-food chain under
    Zhengxin Food (Fujian), founded 2000; its store count passed 20,000 worldwide by 2019, one of
    China's largest F&B chains. Chinese origin, in scope.

    In the US since at least 2024 under its own English name, run by separate regional operators (a
    West-Coast arm at zhengxinca.com; East-Coast NYC stores order via MealKeyway). Open outlets in
    California (San Diego, Milpitas, San Francisco) and New York (Flushing + two in Brooklyn); the
    Chicago store is closed. No single national US locator, so tracked via sightings.
    """
    chain_id, name, name_zh = "zhengxin", "Zhengxin Chicken Steak", "正新鸡排"
    name_us = "Zhengxin Chicken Steak"
    aliases = ("Zheng Xin Chicken Steak", "Zhengxin Chicken", "正新鸡排")
    parent, format = "Zhengxin Food (正新食品, Fujian)", "restaurant"
    ENABLED = False
    BLOCKED_REASON = ("fried-chicken-steak chain (正新鸡排, Fujian, 2000; 20,000+ stores worldwide);"
                      " in the US under its own name via regional operators — open in CA (San Diego,"
                      " Milpitas, San Francisco) and NY (Flushing + two Brooklyn), Chicago closed."
                      " No single national locator. Tracked via sightings (4 Oct 2026)")
    RECHECK = ["https://www.zhengxinca.com/"]


class HiBakeAdapter(Adapter):
    """
    Hi Bake (嗨呗可) — added 2026-10-04. A premium handmade-bakery chain founded in Chengdu in 2012
    (~50 stores, all in Chengdu — IFS, 天府大悦城, 环贸ICD, etc.; a leading Southwest-China bakery).
    Mixed lineage that the Chains tab should note: the founder comes from a Taiwanese baking family
    and a Hong Kong firm (Champs) invested, but the BRAND itself was created and is run in Chengdu, China, and China's trade press counts it as a Chinese brand going abroad (中国烘焙出海) — so it
    is treated as in scope (the operator's call, 4 Oct 2026; cf. Happy Lemon held as Taiwanese-origin).

    First overseas store opened Aug 2025 at 235 N Canon Dr, Beverly Hills, run in partnership with the
    US Chubby Group (The X Pot / Wagyu House / Niku X); IG @HibakeUSA, mascot the rescue dog '大麦'.
    Its only US outlet so far, no national locator, so tracked via sightings.
    """
    chain_id, name, name_zh = "hibake", "Hi Bake", "嗨呗可"
    name_us = "Hi Bake"
    aliases = ("Hibake",)
    parent, format = "Hibake (嗨呗可, Chengdu)", "bakery"
    ENABLED = False
    BLOCKED_REASON = ("Chengdu handmade-bakery chain (嗨呗可, 2012; ~50 stores, all in Chengdu);"
                      " Taiwanese-lineage founder + HK investor but a brand created and run in China, in"
                      " scope per the operator. First US store opened Aug 2025 at 235 N Canon Dr,"
                      " Beverly Hills via US licensee Chubby Group; its only US outlet, no national"
                      " locator. Tracked via sightings (4 Oct 2026)")
    RECHECK = ["https://hibakebakery.com/"]


class BingzAdapter(Adapter):
    """
    Bingz (西少爷 / Bingz Crispy 'Wich) — added 2026-10-05. A Chinese fast-food chain founded 2014 in
    Beijing (Wudaokou) by former tech engineers (Luo Gaojing, Meng Bing, Yuan Zelu); its signature is
    the "crispy 'wich," a modern take on Shaanxi rou jia mo (肉夹馍), plus hot-and-sour hand-pulled
    noodles. Stores across Beijing, Tianjin, Xi'an, Zhengzhou and more; launched its international
    "Bingz" brand in 2018 and entered North America (Canada) in 2021. China origin, in scope.

    First US store opened 2 Oct 2026 at 140 W Valley Blvd Ste 118C (TAWA Gateway), San Gabriel CA —
    its only US outlet so far. bingz.com carries the brand but publishes no readable national US
    locator, so tracked via sightings.
    """
    chain_id, name, name_zh = "bingz", "Bingz", "西少爷"
    name_us = "Bingz Crispy 'Wich"
    aliases = ("Bingz Crispy Burger", "Xishaoye", "西少爷肉夹馍")
    parent, format = "Bingz (西少爷, Beijing)", "restaurant"
    ENABLED = False
    BLOCKED_REASON = ("Shaanxi roujiamo fast-food chain (西少爷, founded Beijing 2014; the 'crispy"
                      " 'wich'); entered North America via Canada in 2021 (~7 stores). First US store"
                      " opened 2 Oct 2026 at 140 W Valley Blvd, San Gabriel CA (TAWA Gateway), its only"
                      " US outlet; bingz.com has no readable national US locator. Tracked via sightings"
                      " (5 Oct 2026)")
    RECHECK = ["https://www.bingz.com/"]


class TeapulseAdapter(Adapter):
    """
    Teapulse (悸动烧仙草 / 悸动 "Jidong") — added 2026-10-06. The US brand of 悸动烧仙草 (Jidong
    Shaoxiancao), a Shanghai-rooted new-tea / grass-jelly (烧仙草) chain ~19 years old with 2,000+
    locations that began expanding abroad in 2019 (UK, Japan, Philippines, Laos, South Korea).
    China origin, in scope. The US arm trades as "Teapulse" (first US store Flushing NY
    ~2022; US HQ Great Neck NY); abroad it trades as "Jidong" / "Jidong Herbal Jelly".

    ~7 NYC outlets (Flushing flagship 37-17 Prince St, plus Doyers St and Canal St in Chinatown,
    Koreatown/65 W 30th, Madison Sq/111 E 23rd, and 1029 & 1375 Sixth Ave), with more announced.
    teapulseusa.com/locations is a dynamic Wix widget whose store list is not in the page HTML (no
    readable feed) — so, like Heytea/Cotti, it is tracked via sightings rather than collected.
    """
    chain_id, name, name_zh = "teapulse", "Teapulse", "悸动烧仙草"
    name_us = "Teapulse"
    aliases = ("悸动", "Jidong", "Jidong Herbal Jelly", "Teapulse 悸动")
    parent, format = "Jidong (悸动烧仙草, Shanghai)", "tea"
    ENABLED = False
    BLOCKED_REASON = ("US brand of 悸动烧仙草 (Jidong, Shanghai; ~2,000 stores, ~19 yrs) — a grass-jelly"
                      " / new-tea chain. ~7 NYC outlets (Flushing flagship + Manhattan), more announced."
                      " teapulseusa.com/locations is a dynamic Wix widget with no readable store feed,"
                      " so tracked via sightings (6 Oct 2026)")
    RECHECK = ["https://www.teapulseusa.com/locations"]


class MakkeeAdapter(Adapter):
    """
    Makkee Dessert (麦记牛奶 / Mak Kee Milk Company) — added 2026-10-07. A Chinese dessert-soup
    (糖水/炖奶) chain founded 2021 in Huzhou, Zhejiang by Xu Kang, built on milk-based takes on
    traditional Chinese tong sui. Despite the Cantonese-style "Mak Kee" branding it is Zhejiang-born,
    not Hong Kong — China origin, in scope. It is now China's largest Chinese dessert-soup chain by
    store count (~1,000 outlets, up from ~53 at the start of 2025) and has begun expanding abroad
    (United States and Australia/Sydney).

    US arm trades as "Makkee Dessert" (IG @makkeedessert_usa). ~6 US outlets open — Rowland Heights,
    San Gabriel, Mountain View and (coming via) downtown LA in CA; Flushing NY; Bellevue WA (Seattle
    metro) — with Irvine CA, San Jose CA and Brooklyn NY announced. No readable national US locator
    (orders run through Chowbus), so tracked via sightings.
    """
    chain_id, name, name_zh = "makkee", "Makkee Dessert", "麦记牛奶"
    name_us = "Makkee Dessert"
    aliases = ("Makkee", "Mak Kee", "Mak Kee Milk Company", "麦记", "麦记牛奶公司", "Maiji Milk")
    parent, format = "Makkee (麦记牛奶, Huzhou, Zhejiang)", "dessert"
    ENABLED = False
    BLOCKED_REASON = ("Chinese dessert-soup chain (麦记牛奶, Huzhou Zhejiang 2021; China's largest"
                      " Chinese-dessert-soup chain, ~1,000 stores). US arm trades as Makkee Dessert"
                      " (~6 outlets: Rowland Heights / San Gabriel / Mountain View / DTLA CA, Flushing"
                      " NY, Bellevue WA; Irvine / San Jose / Brooklyn announced). No readable US"
                      " locator (Chowbus orders), so tracked via sightings (7 Oct 2026)")
    RECHECK = ["https://www.instagram.com/makkeedessert_usa/"]


class DusuAdapter(Adapter):
    """
    Dusu Bakery (读酥世家) — added 2026-10-07. A Shanghai bakery chain (mochi pudding, butter rice
    cakes, egg tarts, burnt cheesecake, sweet/savory buns). China origin, in scope.

    First US location opened 2026 as a SHOP-IN-SHOP counter inside Duo Duo Snacks (a Chinese snack
    market) at 5585 Rosemead Blvd, Temple City CA — its only US outlet, no standalone locator. (The
    host is Duo Duo Snacks, not GW Supermarket.) Tracked via sightings.
    """
    chain_id, name, name_zh = "dusu", "Dusu Bakery", "读酥世家"
    name_us = "Dusu Bakery"
    aliases = ("Dusu", "读酥世家")
    parent, format = "Dusu (读酥世家, Shanghai)", "bakery"
    ENABLED = False
    BLOCKED_REASON = ("Shanghai bakery chain (读酥世家); first US outlet is a shop-in-shop counter"
                      " inside Duo Duo Snacks, 5585 Rosemead Blvd, Temple City CA — its only US"
                      " location, no standalone locator. Tracked via sightings (7 Oct 2026)")
    RECHECK = ["https://www.theinfatuation.com/los-angeles/reviews/dusu-bakery"]


class NanshanAdapter(Adapter):
    """
    Nanshan Hot Pot (南山·熊猫烫火锅) — added 2026-10-10. A Shenzhen-origin "new Chinese-style"
    Sichuan-Chongqing hot-pot chain with a panda mascot/IP (premium imported Wagyu; tops Dianping /
    Douyin hot-pot lists), ~17 outlets in Shenzhen/Dongguan before going abroad. China origin, in scope.

    US entry via New York: first US store opened ~Oct 2024 in Flushing (37-17 Prince St), with a
    second in Bayside (212-12 Northern Blvd). No national US locator, so tracked via sightings.
    """
    chain_id, name, name_zh = "nanshan", "Nanshan Hot Pot", "南山·熊猫烫火锅"
    name_us = "Nanshan Hot Pot"
    # Trades as "Nanshan Hot Pot" in NY; the brand's general English name is "Panda Hot Pot"
    # (storefront 熊猫烫火锅 / PANDA HOT POT). Both are search aliases. (The Melbourne "Panda Hot
    # Pot" is a DIFFERENT brand, Shu Da Xia 蜀大侠 — see cfc-panda-hotpot-namesakes.)
    aliases = ("Nanshan Hotpot", "Nan Shan Hot Pot", "熊猫烫火锅", "Panda Hot Pot")
    parent, format = "Nanshan (南山·熊猫烫火锅, Shenzhen)", "hotpot"
    ENABLED = False
    BLOCKED_REASON = ("Shenzhen Sichuan-Chongqing hot-pot chain (南山·熊猫烫火锅, panda-IP); two US"
                      " outlets open in NY — Flushing (37-17 Prince St) and Bayside (212-12 Northern"
                      " Blvd) — with no national US locator. Tracked via sightings (10 Oct 2026)")
    RECHECK = ["https://www.instagram.com/nanshan.hotpot/"]


class JuqiAdapter(Adapter):
    """
    JUQI (局气) — added 2026-10-10. A Beijing home-style restaurant chain (~20 outlets in China),
    known for playful old-Beijing dishes (Lord-Rabbit mashed potato, honeycomb-briquette fried rice,
    Peking duck). China origin, in scope.

    First US outlet at the Tangram complex, Flushing (133-36 37th Ave G17), open; first-party US site
    juqiusa.com + @juqi_ny. No national US locator, so tracked via sightings. (No Sydney outlet on
    record despite earlier press — not claimed.) Menu/pricing PDF kept for a later Pro pricing catalog.
    """
    chain_id, name, name_zh = "juqi", "JUQI", "局气"
    name_us = "JUQI"
    aliases = ("Ju Qi", "局气")
    parent, format = "JuQi (局气, Beijing)", "restaurant"
    ENABLED = False
    BLOCKED_REASON = ("Beijing home-style restaurant chain (局气, ~20 China outlets); first US outlet"
                      " at Tangram, Flushing (133-36 37th Ave G17), with no national US locator."
                      " Tracked via sightings (10 Oct 2026)")
    RECHECK = ["https://juqiusa.com/",
               "https://website-cdn.menusifu.com/wp-content/uploads/juqiusa.com/2024/01/JuQi-Menu.pdf"]


class LeebaiAdapter(Adapter):
    """
    Lee & Bai (李与白) — added 2026-10-10. A Chengdu buns-and-noodles chain (李与白包子铺; hundreds of
    outlets in China) — fresh-steamed baozi, Chengdu pickled-pork bao and zapu noodles. China origin,
    in scope.

    US footprint growing: open outlets in Flushing (38-09 Union St), Long Island City (42-62 Hunter
    St), Sunnyvale CA (1661 Hollenbeck Ave) and Palisades Park NJ (442 Broad Ave). No national US
    locator, so tracked via sightings (not a complete roster).
    """
    chain_id, name, name_zh = "leebai", "Lee & Bai", "李与白"
    name_us = "Lee & Bai"
    aliases = ("Lee and Bai", "Lee & Bai Buns and Noodles", "Lee & Bai Chinese Bao Shop",
               "Lee & Bai Chinese Buns Shop", "李与白包子铺")
    parent, format = "Lee & Bai (李与白, Chengdu)", "restaurant"
    ENABLED = False
    BLOCKED_REASON = ("Chengdu buns-and-noodles chain (李与白包子铺, hundreds of China outlets); open"
                      " US outlets in NY (Flushing, Long Island City), CA (Sunnyvale) and NJ"
                      " (Palisades Park), with no national US locator. Tracked via sightings (10 Oct 2026)")
    RECHECK = ["https://www.theinfatuation.com/new-york/reviews/lee-and-bai"]


class QuanjudeAdapter(Adapter):
    """
    Quanjude (全聚德) — added 2026-10-10. The Beijing roast-duck institution (since 1864; National
    Intangible Cultural Heritage hanging-oven method), a state-owned chain with 100+ outlets in China.
    China origin, in scope.

    US flagship in NYC at 3 E 52nd St (the former La Grenouille space), run under its upscale "iDEN"
    concept ("iDEN & Quanjude"); soft-opened June 2025, operating. North America began in Vancouver
    (2020, Michelin-starred) — Canada, out of US scope. No US locator, so tracked via sightings.
    """
    chain_id, name, name_zh = "quanjude", "Quanjude", "全聚德"
    name_us = "Quanjude"
    aliases = ("iDEN", "iDEN & Quanjude", "iDEN Fifth", "iDen", "全聚德", "Quanjude Beijing Duck")
    parent, format = "Quanjude (全聚德, Beijing; est. 1864)", "restaurant"
    ENABLED = False
    BLOCKED_REASON = ("Beijing roast-duck chain (全聚德, est. 1864; 100+ China outlets). US flagship"
                      " in NYC — 3 E 52nd St — under its 'iDEN' concept, soft-opened Jun 2025. No US"
                      " locator. Tracked via sightings (10 Oct 2026)")
    RECHECK = ["https://www.quanjude1864.com/", "https://www.cgccusa.org/en/news/iden-quanjude-opens"]


class MamaxitaAdapter(Adapter):
    """
    Mama Xita BBQ (西塔老太太) — added 2026-10-10. A Shenyang-origin Chinese-Korean-style barbecue
    chain (the Xita Korean-BBQ district of Shenyang, Liaoning); 450+ outlets across 31 Asian cities,
    run by the Chubby Group (which also operates Chubby Cattle). China origin, in scope. NOT the same
    as 西塔烧烤 / Xi Top BBQ in Flushing.

    First US outlet open in Bellevue WA (550 106th Ave NE, Ste 101). No US locator, so tracked via
    sightings.
    """
    chain_id, name, name_zh = "mamaxita", "Mama Xita BBQ", "西塔老太太"
    name_us = "Mama Xita BBQ"
    aliases = ("Xita Lao Tai Tai", "Mama Xita", "西塔老太太")
    parent, format = "Chubby Group (Shenyang; also runs Chubby Cattle)", "restaurant"
    ENABLED = False
    BLOCKED_REASON = ("Shenyang Chinese-Korean BBQ chain (西塔老太太, 450+ Asia outlets, Chubby Group);"
                      " first US outlet open in Bellevue WA (550 106th Ave NE). Has a first-party US"
                      " locator (mamaxitabbq.com/locations) — recheck it for new openings."
                      " Tracked via sightings (10 Oct 2026)")
    # First-party US locator — the canonical source to re-crawl for new/closed US outlets.
    RECHECK = ["https://mamaxitabbq.com/locations/"]


class ShanchengLameiziAdapter(Adapter):
    """
    Shancheng Lameizi (山城辣妹子) — added 2026-10-10. A Chongqing hot-pot brand (山城 = Chongqing's
    nickname); has a Beijing outlet and was named by the Chongqing municipal government among regional
    food brands pushed for overseas expansion. China origin, in scope.

    US outlets operate under one group (shared site shanchenglameizi.com) in Southern California:
    Rowland Heights, San Gabriel, Irvine (14130 Culver Dr — in the former Little Sheep area) and San
    Diego. No single US locator page scraped; tracked via sightings.
    """
    chain_id, name, name_zh = "shanchenglameizi", "Shancheng Lameizi", "山城辣妹子"
    name_us = "Shancheng Lameizi"
    aliases = ("Shancheng Lameizhi", "Lameizi", "北京山城辣妹子", "山城辣妹子重庆火锅",
               "Chongqing Spicy Girl Hot Pot")
    parent, format = "Shancheng Lameizi (山城辣妹子, Chongqing)", "hotpot"
    ENABLED = False
    BLOCKED_REASON = ("Chongqing hot-pot brand (山城辣妹子; Beijing outlet + Chongqing-government"
                      " overseas push). US outlets under one operator (shanchenglameizi.com): Rowland"
                      " Heights, San Gabriel, Irvine, San Diego. Tracked via sightings (10 Oct 2026)")
    RECHECK = ["https://www.shanchenglameizi.com/"]


class BingxueAdapter(Adapter):
    """
    Bingxue (冰雪时光) — added 2026-10-12. A mass-market tea-and-ice-cream chain founded 2014 in
    Tai'an, Shandong (operator Jinan Baodao Enterprise Management, Shandong); the budget-priced,
    bear-mascot ("Bobo Bear") rival to Mixue — DISTINCT from Mixue 蜜雪冰城, do not conflate. Fresh
    fruit teas, milk teas, soft serve (it claims the world's best-selling matcha soft serve), yogurt
    smoothies and coffee. The brand reports ~5,000 contracted stores across 18 countries/regions
    (1,500+ operating outside its home market). China origin, in scope.

    Entered the US (and North America) on 2 Oct 2026 with a first store in downtown Davis, CA
    (425 2nd St) — a mayor-attended grand opening; a second US store is in development on Oxnard
    Blvd, CA. No readable US store locator yet (bingxueglobal.com has US/Canada regional sites but no
    machine-readable roster; orders run through Chowbus), so tracked via sightings.
    """
    chain_id, name, name_zh = "bingxue", "BINGXUE", "冰雪时光"
    name_us = None
    aliases = ("Bingxue", "Bingxue Tea & Ice Cream", "Bingxue Shiguang", "冰雪", "冰雪時光")
    parent, format = "Bingxue (冰雪时光, Jinan Baodao, Shandong)", "tea"
    ENABLED = False
    BLOCKED_REASON = ("Shandong tea-and-ice-cream chain (冰雪时光, Tai'an 2014; Mixue's bear-mascot"
                      " budget rival, ~5,000 stores / 18 countries). Entered the US 2 Oct 2026 with a"
                      " first store in Davis, CA; second planned on Oxnard Blvd, CA. No readable US"
                      " locator (Chowbus ordering) — tracked via sightings (12 Oct 2026)")
    RECHECK = ["http://www.bingxueglobal.com/"]


class WalaidaAdapter(Adapter):
    """
    Walaida (蛙来哒) — added 2026-10-14. A Hunan-cuisine restaurant chain built on charcoal / dry-pot
    bullfrog (牛蛙), founded ~2009–2010 in Changsha, Hunan by siblings Luo Hao and Luo Qing (HQ later
    moved to Shenzhen). ~460–500 stores across 90+ Chinese cities, roughly 90% franchised. China
    origin, in scope.

    US presence: one confirmed outlet in Flushing, NY (135-05 Roosevelt Ave, Prince Center), named
    蛙来哒法拉盛店 / WALAIDA FLUSHING and operating per its Google Business listing (4.2 / 140 reviews,
    pickup + delivery). No readable US store locator, so tracked via sightings.
    """
    chain_id, name, name_zh = "walaida", "WALAIDA", "蛙来哒"
    name_us = None
    aliases = ("Walaida", "Wa Lai Da", "蛙來哒", "WALAIDA FLUSHING", "Bullfrog")
    parent, format = "Walaida (蛙来哒, Changsha / Shenzhen)", "restaurant"
    ENABLED = False
    BLOCKED_REASON = ("Hunan bullfrog (牛蛙) restaurant chain (蛙来哒, Changsha ~2009; ~460–500 stores,"
                      " ~90% franchised). Confirmed operating in Flushing, NY (135-05 Roosevelt Ave)"
                      " per its Google listing — no readable US locator, tracked via sightings"
                      " (14 Oct 2026)")
    RECHECK = ["https://www.walaida.net/"]


class JibeichuanAdapter(Adapter):
    """
    JiBeiChuan (季北川花胶鸡汤米粉) — added 2026-10-14. A rice-noodle chain built on fish-maw
    chicken-soup rice noodles (花胶鸡汤米粉); prepared 2018, first direct-operated store 2019;
    HQ in Hangzhou, Zhejiang (Hangzhou Shengli Catering Management Co.). Operates in China
    (Zhejiang, Jiangsu, Hunan, Hubei, Henan) plus North America (US + Canada), via direct-operated
    and partner/franchise stores. China origin, in scope.

    US outlets tracked via sightings from its official US site (jibeichuanny.com) + Google listings:
    three in NYC (Flushing, Manhattan, Brooklyn) and one in San Leandro, CA. No readable US locator.
    """
    chain_id, name, name_zh = "jibeichuan", "JiBeiChuan", "季北川"
    name_us = None
    aliases = ("Ji Bei Chuan", "JBC", "JiBeiChuan Noodles", "季北川花胶鸡汤米粉", "花胶鸡汤米粉")
    parent, format = "JiBeiChuan (季北川, Hangzhou Shengli Catering, Zhejiang)", "restaurant"
    ENABLED = False
    BLOCKED_REASON = ("Hangzhou (Zhejiang) rice-noodle chain (季北川花胶鸡汤米粉, fish-maw chicken-soup"
                      " rice noodles; founded 2018–19, direct + partner stores in China + North"
                      " America). US outlets in NYC (Flushing, Manhattan, Brooklyn) and San Leandro,"
                      " CA — tracked via sightings from its official US site + Google listings"
                      " (14 Oct 2026)")
    RECHECK = ["https://www.jibeichuanny.com/"]


class BabakehouseAdapter(Adapter):
    """
    BA Artisan Bakehouse (BA / BON APPÉTIT) — added 2026-10-14. A French-Asian artisan bakery chain
    founded 2016 in Kunming, Yunnan (first store on 金夏路); operated by Yunnan Bangnaboudi Food
    Development Co. (邦纳博地 = transliteration of "Bon Appétit"). ~45 stores across China (Kunming,
    Chongqing, Xi'an, Chengdu…), plus overseas in Dubai and the US. China origin, in scope. There is
    no formal Chinese brand name — written "BA" / "BA烘焙" / "BA法式烘焙" in Chinese.

    US presence: one outlet, the North America flagship in Bellevue, WA (550 106th Ave NE Ste 102,
    Bellevue Connection), opened Jan 2026, operating (Google 4.0 / 323 reviews). No US store locator,
    so tracked via sightings. Its Dubai store is in the Global register (market AE).
    """
    chain_id, name, name_zh = "babakehouse", "BA Artisan Bakehouse", "BA烘焙"
    name_us = None
    aliases = ("BA", "BA Bakehouse", "Bon Appetit", "BON APPÉTIT", "BA法式烘焙", "邦纳博地")
    parent, format = "Bon Appétit (BA, Yunnan Bangnaboudi Food Development Co., Kunming)", "bakery"
    ENABLED = False
    BLOCKED_REASON = ("Yunnan (Kunming) French-Asian artisan bakery chain (BA / BON APPÉTIT, founded"
                      " 2016; ~45 China stores + Dubai). Its North America flagship operates in"
                      " Bellevue, WA (550 106th Ave NE) — no readable US locator, tracked via"
                      " sightings (14 Oct 2026)")
    RECHECK = ["https://babakery.com/"]


class ChicjocAdapter(Adapter):
    """
    CHICJOC — added 2026-10-14. A Shanghai "minimalist-luxury" (极简极奢) womenswear brand operated by
    Shanghai Jiuci Brand Management Co. (上海玖赐), founded 2015. Began as a Taobao online brand, went
    offline in May 2022 (first store at Nanjing Deji Plaza) and grew to ~40–50 brick-and-mortar stores
    across first- and key second-tier Chinese cities' high-end malls; four own factories (Changzhou,
    Taixing, Wuxi, Anqing). China origin, in scope. No Chinese brand name (uses "CHICJOC").

    US presence: two California outlets — Fashion Island (Newport Beach, its first overseas store,
    Nov 2024) and Beverly Center (Los Angeles). Also a Paris store (in the Global register, market FR).
    Store page at chicjoc.com/store-locator is not machine-readable, so tracked via sightings.
    """
    chain_id, name, name_zh = "chicjoc", "CHICJOC", ""
    name_us = None
    aliases = ("CHICJOC", "玖赐", "上海玖赐", "Journey of Costume")
    parent, format = "CHICJOC (Shanghai Jiuci Brand Management, 上海玖赐)", "apparel"
    ENABLED = False
    BLOCKED_REASON = ("Shanghai minimalist-luxury womenswear brand (CHICJOC, 上海玖赐, founded 2015;"
                      " ~40–50 China stores). US outlets at Fashion Island (Newport Beach) and Beverly"
                      " Center (Los Angeles), CA; Paris store abroad. No machine-readable US locator,"
                      " tracked via sightings (14 Oct 2026)")
    RECHECK = ["https://www.chicjoc.com/store-locator.html"]


class DreameAdapter(Adapter):
    """
    DREAME (追觅科技) — added 2026-10-14. A Suzhou (Jiangsu) smart-home electronics brand
    (Xiaomi-ecosystem origin): robot vacuums, cordless stick vacuums, wet/dry cleaners and hair
    dryers. It runs a growing US BRANDED RETAIL CHAIN of smart-home stores — a chain, not a lone
    flagship. China origin, in scope, sector electronics.

    US permanent stores (from its own dreametech.com "where to buy" list): Westfield Century City
    (Los Angeles), Westfield UTC (San Diego), Westfield Valley Fair (Santa Clara) and Garden State
    Plaza (Paramus, NJ). It also runs temporary pop-ups / a "road show" (NOT counted here). No
    machine-readable US locator, so tracked via sightings. NOT to be confused with "Dreame Mart", a
    SEPARATE art-toy concept (opened Brea Mall May 2025, since renamed Ohku).
    """
    chain_id, name, name_zh = "dreame", "DREAME", "追觅"
    name_us = None
    aliases = ("Dreame", "追觅", "追觅科技", "Dreame Technology")
    parent, format = "Dreame Technology (追觅科技, Suzhou, Jiangsu)", "electronics"
    ENABLED = False
    BLOCKED_REASON = ("Suzhou smart-home electronics brand (追觅科技 Dreame Technology; robot/cordless"
                      " vacuums, hair dryers). Runs a US branded retail chain — 4 permanent stores"
                      " (Century City, San Diego UTC, Valley Fair CA + Garden State Plaza NJ) plus"
                      " pop-ups. Tracked via sightings from its 'where to buy' list (14 Oct 2026)."
                      " NOT 'Dreame Mart' (separate art-toy concept, now Ohku)")
    RECHECK = ["https://www.dreametech.com/pages/where-to-buy"]


class ShowminihotpotAdapter(Adapter):
    """
    Show Mini Hot Pot (秀海福) — added 2026-10-14. A golden-soup MALATANG chain (金汤麻辣烫, branded
    "mini hot pot" in the US — customizable individual-serving malatang), operated by Harbin
    Yuxiangding Catering Management Co. (哈尔滨裕祥鼎), founded 2016 in Harbin, Heilongjiang. ~693
    China stores (June 2025), franchise + central kitchen. China origin, in scope, sector food_drink.

    US: open in Richardson, TX (1251 State St #800, CityLine — Yelp ~4.3, delivery live). A Flushing,
    NY space it lists (136-72 Roosevelt Ave — the former First Lamb Shabu unit) shows CLOSED on Yelp,
    so it is held UNCERTAIN pending re-check. Many US cities are announced "coming soon" (Soho NY,
    Los Angeles, Seattle, Dallas, Houston, Chicago, College Station). No readable US locator, tracked
    via sightings. A San Gabriel, CA (Tawa Gateway) tenant listing is NOT on the brand's own site
    (its only CA entry is LA "coming soon"), so it is not counted.
    """
    chain_id, name, name_zh = "showminihotpot", "Show Mini Hot Pot", "秀海福"
    name_us = None
    aliases = ("Show Mini Hot Pot", "Show Mini Hotpot", "秀海福金汤麻辣烫", "秀海福麻辣烫", "Show Hot Pot")
    parent, format = "Show Mini Hot Pot (秀海福, Harbin Yuxiangding Catering, 哈尔滨裕祥鼎)", "restaurant"
    ENABLED = False
    BLOCKED_REASON = ("Harbin (Heilongjiang) golden-soup malatang chain (秀海福 / Show Mini Hot Pot,"
                      " 哈尔滨裕祥鼎; founded 2016, ~693 China stores). Open in Richardson, TX; a Flushing"
                      " NY space it lists shows closed on Yelp (held uncertain); several US cities"
                      " announced coming-soon. Tracked via sightings (14 Oct 2026)")
    RECHECK = ["https://showminihotpot.com/"]


class RolifeAdapter(Adapter):
    """
    Rolife (若来) — added 2026-10-14. An IP-toy / lifestyle-creative brand of Robotime Group (若态科技,
    Suzhou, Jiangsu; founded 2007, Rolife sub-brand since 2017): DIY miniature dollhouses, 3D wooden
    puzzles and IP art toys (headline character Nanci, sold as blind boxes). China origin, in scope,
    sector lifestyle & toys (like TOP TOY / 52TOYS / Pop Mart).

    It runs a US BRANDED RETAIL CHAIN (a chain, not a lone flagship) — ~12 US stores across 7 states
    per its own rolifeonline.com "where to buy" list, tracked via sightings. It also runs stores
    abroad (China, Thailand, Japan, Netherlands) not tracked here. A Mall of America flagship was
    announced (Sep 2026) but is not yet on the brand's own US store list, so it is not counted yet.
    """
    chain_id, name, name_zh = "rolife", "Rolife", "若来"
    name_us = None
    aliases = ("Rolife", "Robotime", "若来", "若态", "Rolife Robotime")
    parent, format = "Robotime Group (若态科技, Suzhou)", "toys"
    ENABLED = False
    BLOCKED_REASON = ("Suzhou (Jiangsu) IP-toy / lifestyle-creative chain (Rolife by Robotime 若态科技;"
                      " DIY miniatures, 3D wooden puzzles, Nanci art-toy blind boxes). Runs a ~12-store"
                      " US retail chain across 7 states — tracked via sightings from its own 'where to"
                      " buy' list (14 Oct 2026)")
    RECHECK = ["https://www.rolifeonline.com/pages/retail-store"]


class NanhotpotAdapter(Adapter):
    """
    Nan Hotpot (楠火锅) — added 2026-10-14. A Chongqing-style hotpot chain founded 1993, HQ Chengdu
    (成都上纵集团 / Chengdu Shangzong Group, founder Zhang Wenhao); heavy beef-tallow base and a
    "market-stall / old-alley" (巷子里的老火锅) store concept; 590–600+ stores. China origin, in scope,
    sector food_drink.

    It expanded abroad through a North America business division with SIGNED COOPERATIVE / FRANCHISE
    stores (also UK, Italy, NZ). US outlets: its overseas-first store in the Seattle area (Bellevue,
    WA, Mar 2023; Google 4.5/686) and one in Plano, TX (nanhotpottx.com). The US stores use per-market
    operator sites and a navy logo variant (official is orange) and make no explicit "official" claim,
    so they appear AUTHORIZED but identity is not independently confirmed. Tracked via sightings.
    """
    chain_id, name, name_zh = "nanhotpot", "Nan Hotpot", "楠火锅"
    name_us = None
    aliases = ("Nan Hotpot", "Nan Hot Pot", "楠火锅", "巷子里的老火锅")
    parent, format = "Nan Hotpot (楠火锅, Chengdu Shangzong Group 成都上纵集团)", "hotpot"
    ENABLED = False
    BLOCKED_REASON = ("Chongqing-style hotpot chain (楠火锅 Nan Hotpot, founded 1993; HQ Chengdu,"
                      " 成都上纵集团; 590–600+ stores). Overseas-first store Bellevue WA (Seattle, 2023),"
                      " plus Plano TX, via its North America cooperative/franchise program — US outlets"
                      " appear authorized but identity not independently confirmed. Tracked via"
                      " sightings (14 Oct 2026)")
    RECHECK = ["https://www.nanhotpotseattle.com/", "https://www.nanhotpottx.com/"]


class HuaxiaoxiaoAdapter(Adapter):
    """
    Hwa ShooShoo (花小小 新疆炒米粉) — added 2026-10-14. A Xinjiang fried-rice-noodle (新疆炒米粉)
    fast-casual chain founded 2019–2020 (first store Beijing Wangjing); parent 四有青年餐创集团
    (Beijing Siyou Qingnian, est. 2015), slogan 让世界爱上新疆味. ~3,500 stores by end-2025,
    4,000+ claimed by mid-2026. China origin, in scope, sector food_drink.

    Its documented overseas-first store opened in Flushing, NY (Tangram food court) in Feb 2025 —
    the brand bills it as the first Xinjiang fried-rice-noodle brand to reach North America, and the
    storefront carries the genuine brand identity (red plum-blossom chef-girl seal + HWA SHOOSHOO /
    新疆炒米粉). Tracked via sightings; US scale beyond the one store not yet independently confirmed.
    """
    chain_id, name, name_zh = "huaxiaoxiao", "Hwa ShooShoo", "花小小"
    name_us = None
    aliases = ("Hwa ShooShoo", "Hwa Shoo Shoo", "花小小", "花小小新疆炒米粉",
               "Xinjiang Fried Rice Noodles", "新疆炒米粉")
    parent, format = "Hwa ShooShoo (花小小, 四有青年餐创集团 / Beijing Siyou Qingnian)", "fastfood"
    ENABLED = False
    BLOCKED_REASON = ("Xinjiang fried-rice-noodle chain (花小小 Hwa ShooShoo, founded 2019–2020; HQ"
                      " Beijing, 四有青年餐创集团; ~3,500–4,000+ stores). Overseas-first store in"
                      " Flushing NY (Tangram, Feb 2025) — storefront carries the genuine brand"
                      " identity; in scope. Tracked via sightings (14 Oct 2026)")
    RECHECK = ["https://zhuanlan.zhihu.com/p/30284995808"]


class ZhoumapoAdapter(Adapter):
    """
    Zhoumapo / Mrs. Zhou (周麻婆) — added 2026-10-14. A fast-casual Sichuan stir-fry (快餐式小炒) chain
    founded August 2012 by Zhou Hongxia (周红霞); parent 福建省周麻婆餐饮管理有限公司 (Fujian Zhou Mapo
    Catering Management), HQ Fuzhou, Fujian. Signature ¥2 Mapo tofu; ~300 franchised stores (2021).
    China origin, in scope, sector food_drink.

    Its first US store opened at 728 Eighth Avenue, Times Square, NYC (10-year lease signed Jan 2025;
    Commercial Observer), trading as "Mapo Asian Restaurant & Bar — Time Square 周麻婆" — repositioned
    upmarket as a full restaurant & bar but carrying the genuine 周麻婆 / Mrs. Zhou name and grandma
    logo. Confirmed operating (Google 4.5/302). Tracked via sightings.
    """
    chain_id, name, name_zh = "zhoumapo", "Zhoumapo", "周麻婆"
    name_us = None
    aliases = ("Zhoumapo", "Zhou Mapo", "Mrs. Zhou", "Mapo", "Mapo Asian Restaurant & Bar",
               "周麻婆")
    parent, format = "Zhoumapo (周麻婆, Fujian Zhou Mapo Catering 福建省周麻婆餐饮管理有限公司)", "restaurant"
    ENABLED = False
    BLOCKED_REASON = ("Fast-casual Sichuan stir-fry chain (周麻婆 Zhoumapo / Mrs. Zhou, founded 2012;"
                      " HQ Fuzhou, Fujian; ~300 stores). First US store at 728 Eighth Ave, Times"
                      " Square NYC (lease Jan 2025, Commercial Observer), trading as 'Mapo Asian"
                      " Restaurant & Bar — Time Square 周麻婆'; confirmed operating. In scope, tracked"
                      " via sightings (14 Oct 2026)")
    RECHECK = ["https://www.mapoasianbartimesquare.com/", "https://www.mapousa.com/"]


class LittleSheepAdapter(Adapter):
    """
    Little Sheep (小肥羊) — added 2026-10-17. A Mongolian hot-pot chain founded 1999 in Baotou, Inner
    Mongolia; owned by Yum China since 2012 (China origin, in scope, sector food_drink). A global
    franchise across East/Southeast Asia and Oceania, tracked for those markets in the Global register.

    Its earlier US outlets (e.g. Irvine) closed, but it RE-ENTERED the US in 2026: its self-described
    first US location is at American Dream, East Rutherford, NJ (1 American Dream Way, Unit A320),
    confirmed operating (Google 4.8/1,654; littlesheepusa.com). No first-party national US locator —
    the US site lists the one store — so tracked via sightings; the mall address is a Census no-match,
    placed by a manual OSM/Nominatim centroid override.
    """
    chain_id, name, name_zh = "littlesheep", "Little Sheep", "小肥羊"
    name_us = "Little Sheep Hot Pot"
    aliases = ("Little Sheep", "Little Sheep Hot Pot", "Little Sheep Hot Pot & Bar", "小肥羊")
    parent, format = "Little Sheep (小肥羊; Yum China)", "hotpot"
    ENABLED = False
    BLOCKED_REASON = ("Mongolian hot-pot chain (小肥羊 Little Sheep, founded 1999 in Baotou, Inner"
                      " Mongolia; owned by Yum China since 2012). Earlier US outlets closed, but it"
                      " re-entered the US in 2026 with its first new location at American Dream, East"
                      " Rutherford NJ (littlesheepusa.com); confirmed operating (Google 4.8/1,654). In"
                      " scope (China origin), tracked via sightings (17 Oct 2026)")
    RECHECK = ["https://littlesheepusa.com/where-we-are"]


class YaoyaoAdapter(Adapter):
    """
    YAOYAO (姚姚酸菜鱼) — added 2026-10-18. A China-origin Sichuan pickled-fish (酸菜鱼) chain
    founded in Shenzhen in Aug 2016 (founder Yao Minxi 姚旻汐, ex-Huawei); Tiffany-blue bear-fish
    branding, ~50-70 China stores, repeatedly a Top-10 China pickled-fish brand. Franchises since
    2019. Overseas in Singapore (VivoCity) and the US; it fully exited Hong Kong (4 stores closed),
    tracked for HK/SG in the Global register.

    US presence = 3 operating outlets: Chicago, IL (230 W Cermak Rd — Michelin Bib Gourmand 2024 &
    2025), San Leandro, CA (699 Lewelling Blvd, Greenhouse Marketplace) and San Bruno, CA (1212 El
    Camino Real, co-branded 'Jin Gege & Yao Yao'). No first-party national US locator, so tracked
    via sightings; San Leandro is a Census no-match placed by a manual OSM/Nominatim override.
    """
    chain_id, name, name_zh = "yaoyao", "YAOYAO", "姚姚酸菜鱼"
    name_us = "Yao Yao"
    aliases = ("YAOYAO", "Yao Yao", "姚姚酸菜鱼", "姚姚酸菜魚", "Yao Yao Suan Cai Yu", "Jin Gege & Yao Yao")
    parent, format = "YAOYAO (姚姚酸菜鱼; Shenzhen)", "restaurant"
    ENABLED = False
    BLOCKED_REASON = ("China-origin Sichuan pickled-fish chain (姚姚酸菜鱼 YAOYAO, founded Shenzhen"
                      " 2016). 3 operating US outlets — Chicago IL (Michelin Bib Gourmand 2024/2025),"
                      " San Leandro CA and San Bruno CA (co-branded Jin Gege & Yao Yao). No first-party"
                      " US locator, so tracked via sightings (18 Oct 2026). In scope (China origin)")
    RECHECK = ["https://yaoyaochicago.com/"]

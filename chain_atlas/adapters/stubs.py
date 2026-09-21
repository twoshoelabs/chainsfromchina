"""
Chains in scope that cannot be collected yet, and exactly why.

These are not placeholders to be tidied away. A tracker that silently omits Pop Mart because
Pop Mart was inconvenient is a tracker that will one day report "Chinese retail is all tea
shops". Each stub carries the evidence from the 21 Sep 2026 probe so the next attempt starts
where this one stopped, and `status` prints the reason beside the chains that do collect.
"""
from .base import Adapter


class PopMartAdapter(Adapter):
    """
    POP MART US — https://www.popmart.com/us/store-list

    The page is Next.js with a static data document at
    /_next/data/<buildId>/us/store-list.json, and the buildId is readable from the page, so
    the shape of the collector is obvious. The obstacle is Cloudflare bot management: from this
    host both the page and the data document return an interstitial (HTTP 200, ~25 KB of
    challenge HTML) to a plain client, while a real browser gets the data. The store list IS
    rendered server-side and was read successfully through the browser pane on 21 Sep 2026
    (South Coast Plaza, American Dream, Valley Fair, ... with addresses, phone and hours).

    SITE-WIDE, not US-specific: the Hong Kong store list (popmart.com/hk/store-list) was probed on
    21 Sep 2026 and returns the same challenge, so there is no friendlier national site to collect
    instead. Pop Mart is unavailable in every market until either a real browser session is budgeted
    or they grant access.

    NOT a reason to route around the protection. The next step is to ask Pop Mart for access,
    or to drive one real browser session a day, which is a different politeness budget and
    needs a deliberate decision rather than a quiet workaround.
    """
    chain_id, name, name_zh = "popmart", "POP MART", "泡泡玛特"
    parent, format = "Pop Mart International Group", "toys"
    ENABLED = False
    BLOCKED_REASON = ("Cloudflare bot management returns a challenge to non-browser clients in every"
                      " market probed, US and HK (21 Sep 2026)")
    RECHECK = ["https://www.popmart.com/us/store-list"]


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
    BLOCKED_REASON = ("site's /api/v1/page key=stores is a 13-store global showcase, not a US"
                      " locator; no US subdomain resolves (21 Sep 2026)")
    RECHECK = ["https://www.heytea.com/en-us/store"]


class YangsAdapter(Adapter):
    """
    Yang's Braised Chicken Rice (杨铭宇黄焖鸡) — trading in the US since September 2017.

    In the archive because it is HERE, not because it is easy. It opened in Tustin, California in
    2017, franchised through Orange County and beyond, and the trade press counts roughly a
    hundred locations across the US, Australia, Japan and Singapore — making it one of the
    earliest and least-covered mainland chains in America, operating for eight years while the
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

    NEXT: nothing first-party is available. Tai Er will need either the app's store API, or a
    corroborated reconstruction from several third-party sources, which is a different kind of
    product and should be a deliberate decision rather than a quiet fallback. Its parent still
    discloses overseas counts twice a year, which remains the best check on whatever is built.

    LEGAL: robots.txt returns 404 on both jiumaojiu.com and en.jiumaojiu.com, i.e. no
    restriction. The endpoint was queried a handful of times at probe rates, not crawled.
    """
    chain_id, name, name_zh = "taier", "Tai Er", "太二"
    parent, format = "Jiumaojiu International (HKEX 9922)", "restaurant"
    ENABLED = False
    BLOCKED_REASON = ("in the US; the parent's store endpoint returns plausible counts but repeats"
                      " one Guangzhou record for every row, and is stamped May 2022 (21 Sep 2026)")
    RECHECK = ["http://en.jiumaojiu.com/store/taier.html"]


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
    """
    chain_id, name, name_zh = "nayuki", "Naixue", "奈雪的茶"
    parent, format = "Nayuki Holdings (HKEX 2150)", "tea"
    ENABLED = False
    BLOCKED_REASON = ("US entry reported at American Dream NJ; naixue.com is a 505-byte shell and"
                      " no US domain resolves (21 Sep 2026)")
    RECHECK = ["https://www.naixue.com/"]


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
    BLOCKED_REASON = ("a US store finder exists (mobile.us.cotticoffee.global, Flutter) but opens"
                      " on a Terms and Conditions gate this project will not accept for you"
                      " (21 Sep 2026)")
    RECHECK = ["https://mobile.us.cotticoffee.global/?cnty=US", "https://www.cotticoffee.global/"]

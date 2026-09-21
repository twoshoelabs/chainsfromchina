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


class HeyteaAdapter(Adapter):
    """
    HEYTEA US — https://www.heytea.com/en-us/store

    The site has a clean CMS API — POST /api/v1/page with {"key":"stores", "region":"DEFAULT",
    "lang":"English"} returns 200 — but what it returns is a curated showcase of flagship
    design stores worldwide (13 entries across heytea / lab / teabar / craft, of which exactly
    one is American). It is a brand page, not a locator, and using it as one would report
    HEYTEA as a single-store chain when the trade press counts roughly 28 US locations.

    Next step: the ordering app's shop endpoint, which is where the real US list lives.
    """
    chain_id, name, name_zh = "heytea", "HEYTEA", "喜茶"
    parent, format = "Heytea (Shenzhen Meixixi)", "tea"
    ENABLED = False
    BLOCKED_REASON = "site's /api/v1/page key=stores is a 13-store global showcase, not a US locator (21 Sep 2026)"


class YangsAdapter(Adapter):
    """
    Yang's Braised Chicken Rice (杨铭宇黄焖鸡) — trading in the US since September 2017.

    In the archive because it is HERE, not because it is easy. It opened in Tustin, California in
    2017, franchised through Orange County and beyond, and the trade press counts roughly a
    hundred locations across the US, Australia, Japan and Singapore — making it one of the
    earliest and least-covered mainland chains in America, operating for eight years while the
    attention went to the tea shops that arrived in 2023.

    No first-party US locator has been identified. The franchise network appears to run through
    individual operators, and yangsbraisedchickenrice.com did not resolve when probed on
    21 Sep 2026. Next step is to find whether a national franchisor page exists; if it does not,
    this becomes the first chain here that needs a corroborated multi-source count rather than a
    single locator read.
    """
    chain_id, name, name_zh = "yangs", "Yang's Braised Chicken Rice", "杨铭宇黄焖鸡"
    parent, format = "Yang's Braised Chicken Rice", "restaurant"
    ENABLED = False
    BLOCKED_REASON = "trading in the US since 2017; no first-party US locator found yet (21 Sep 2026)"


class TaiErAdapter(Adapter):
    """
    Tai Er (太二) — the pickled-cabbage-fish chain of Jiumaojiu (HKEX 9922), trading in the US.

    Unlike most of this roster, its parent is listed and discloses: 31 restaurants outside China
    at H1 2025, up from 22, across Canada, Indonesia, Malaysia, Singapore, Thailand and the US.
    That makes it the best corroboration target in the project — a locator count checkable against
    a filing.

    Promising lead, not yet parsed: en.jiumaojiu.com/store/taier.html answered 200 on
    21 Sep 2026 with store-shaped markup in it. It needs a proper look to see whether the US
    restaurants are listed there and in what form.
    """
    chain_id, name, name_zh = "taier", "Tai Er", "太二"
    parent, format = "Jiumaojiu International (HKEX 9922)", "restaurant"
    ENABLED = False
    BLOCKED_REASON = "trading in the US; parent's store page is a promising unparsed lead (21 Sep 2026)"


class HaidilaoAdapter(Adapter):
    """
    Haidilao (海底捞) — hotpot, trading in the US since 2013 and the longest-established mainland
    chain on this roster by a decade.

    Its overseas arm Super Hi International is listed twice (HKEX 9658, Nasdaq HDL) and discloses
    restaurant counts, which makes it the second-best corroboration target here after Tai Er.
    A dozen-plus US restaurants across California, Washington, Texas, New York, Illinois and
    Arizona. Several .us domains carry outlet lists but their provenance is unverified — the
    first-party source to find is Super Hi's own site or the app.
    """
    chain_id, name, name_zh = "haidilao", "Haidilao", "海底捞"
    parent, format = "Super Hi International (HKEX 9658 / Nasdaq HDL)", "restaurant"
    ENABLED = False
    BLOCKED_REASON = "in the US since 2013; first-party US locator not yet identified (21 Sep 2026)"


class ChaPandaAdapter(Adapter):
    """
    ChaPanda (茶百道) — entered the US in August 2025, first store in Flushing, Queens.

    The newest arrival on this roster, which makes it the most valuable to start watching early:
    a chain caught in its first months leaves a complete opening history rather than a partial
    one. HKEX-listed (2555), 38 overseas stores by end-2025.
    """
    chain_id, name, name_zh = "chabaidao", "ChaPanda", "茶百道"
    parent, format = "Sichuan Baicha Baidao (HKEX 2555)", "tea"
    ENABLED = False
    BLOCKED_REASON = "entered the US Aug 2025; chapanda.com not yet probed for a locator (21 Sep 2026)"


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
    BLOCKED_REASON = "US entry reported at American Dream NJ; extent and locator unverified (21 Sep 2026)"


class CottiAdapter(Adapter):
    """
    Cotti Coffee US — no first-party US locator found.

    cotticoffee.com serves a global brand site with no /us path (404), us.cotticoffee.global
    does not resolve, and the US presence surfaces through third parties instead: individual
    franchisee sites, a Joe Coffee ordering page per store, and mall directories. Third-party
    aggregators are explicitly out of scope for a first-party census — they are someone else's
    refresh cadence and someone else's mistakes.

    Next step: the app's store API, or accept Cotti as uncollectable and say so on the map.
    """
    chain_id, name, name_zh = "cotti", "Cotti Coffee", "库迪咖啡"
    parent, format = "Cotti Coffee", "coffee"
    ENABLED = False
    BLOCKED_REASON = "no first-party US locator exists; only per-franchisee and aggregator pages (21 Sep 2026)"

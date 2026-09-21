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

    NOT a reason to route around the protection. The next step is to ask Pop Mart for access,
    or to drive one real browser session a day, which is a different politeness budget and
    needs a deliberate decision rather than a quiet workaround.
    """
    chain_id, name, name_zh = "popmart", "POP MART", "泡泡玛特"
    parent, format = "Pop Mart International Group", "toys"
    ENABLED = False
    BLOCKED_REASON = "Cloudflare bot management returns a challenge to non-browser clients (21 Sep 2026)"


class MinisoAdapter(Adapter):
    """
    MINISO US — https://www.miniso-us.com/store-locator

    A Wix site. robots.txt allows the path. The locator page is 1.5 MB of Wix Thunderbolt and
    the store list did not appear in the HTML, in an iframe, or in any XHR captured during an
    8-second browser load on 21 Sep 2026 — no third-party locator vendor (Stockist, StoreRocket,
    Yext and the usual others) is referenced either, which points at a Wix Data collection
    queried only after the visitor picks a state or grants location.

    Next step: drive the widget in a browser once, capture the /_api/cloud-data query with its
    collection id, then call that directly. Roughly 400 US stores are at stake, the largest
    footprint in scope, so this is the most valuable stub here.
    """
    chain_id, name, name_zh = "miniso", "MINISO", "名创优品"
    parent, format = "MINISO Group Holding", "lifestyle"
    ENABLED = False
    BLOCKED_REASON = "Wix Data query not yet identified; list is not in the HTML (21 Sep 2026)"


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

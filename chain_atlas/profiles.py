"""
Who each company is.

EDITORIAL, AND KEPT SEPARATE FROM THE COLLECTOR ON PURPOSE. Everything else in this project is
something the collector saw for itself and can show you the raw capture for. Nothing here is:
these are facts from published sources — company filings, exchange announcements and the trade
press — typed in by hand on the date in `as_of`. They go stale, and the map labels them as
background rather than as data.

`global_stores` is the number that rots fastest, so it always travels with the date it was
reported. A US store count is deliberately NOT recorded here: that is the one number this
project measures itself, and having a hand-typed copy of it beside the measured one is how a
tracker ends up quoting its own stale note back at itself.
"""

AS_OF = "2026-09-21"

PROFILES = {
    "mixue": {
        "name": "MIXUE", "name_zh": "蜜雪冰城",
        "founded": 1997, "founder": "Zhang Hongchao", "hq": "Zhengzhou, Henan",
        "listing": "HKEX (listed 3 March 2025)",
        "global_stores": "59,823 worldwide at 31 Dec 2025",
        "us_entry": "Los Angeles, 19 December 2025",
        "blurb": (
            "The largest food-and-beverage chain on earth by number of outlets — more units than "
            "McDonald's or Starbucks — built on ¥1 soft serve and cheap cheese-foam tea in China's "
            "smaller cities. Zhang Hongchao started it in 1997 with 3,000 yuan borrowed from his "
            "grandmother. Almost every store is a franchise, and the company earns less from drinks "
            "than from selling ingredients, equipment and packaging to its own franchisees, which is "
            "why it can open so many so fast. Its March 2025 Hong Kong listing was the year's most "
            "heavily subscribed."),
        "why_watch": (
            "The only chain here that publishes its pipeline: US stores appear as 'coming soon' "
            "weeks before they trade, so its expansion is visible in advance rather than in hindsight."),
    },
    "chagee": {
        "name": "CHAGEE", "name_zh": "霸王茶姬",
        "founded": 2017, "founder": "Zhang Junjie", "hq": "Kunming, Yunnan",
        "listing": "Nasdaq: CHA (IPO 17 April 2025)",
        "global_stores": "about 7,500 in 2026, from 6,400+ in March 2025",
        "us_entry": "Los Angeles, 2025",
        "blurb": (
            "A premium 'modern teahouse' chain selling original-leaf tea with fresh milk, pitched at "
            "the space Starbucks occupies rather than at the bubble-tea price war. Zhang Junjie "
            "founded it in Yunnan in 2017 at twenty-three, after dropping out of school and working "
            "in a Taiwanese-style tea shop; the April 2025 Nasdaq IPO raised $411m and made him a "
            "billionaire. Its US stores are mall flagships — Century City, Brea, Del Amo — not "
            "street counters."),
        "why_watch": (
            "The only chain in this archive that publishes coordinates for every US store, and the "
            "one making the most deliberate bet on American mall real estate."),
    },
    "luckin": {
        "name": "Luckin Coffee", "name_zh": "瑞幸咖啡",
        "founded": 2017, "founder": "Lu Zhengyao and Qian Zhiya (both since ousted)",
        "hq": "Xiamen, Fujian",
        "listing": "delisted from Nasdaq July 2020; OTC, with a US relisting reported as being prepared",
        "global_stores": "approaching 30,000 after Q3 2025",
        "us_entry": "New York City, mid-2025",
        "blurb": (
            "China's biggest coffee chain, and bigger there than Starbucks. It is also the most "
            "notorious company in this group: after a 2019 Nasdaq IPO it admitted in April 2020 to "
            "fabricating more than $300m of sales, paid a $180m SEC penalty, was delisted, and went "
            "through Chapter 15. It then rebuilt under new management into a roughly 30,000-store "
            "app-first operation — order on the phone, collect at a counter, little seating — and is "
            "reported to be preparing a return to a US listing."),
        "why_watch": (
            "The fraud makes its own numbers worth checking against something independent, which is "
            "exactly what a locator census is. Its US stores publish no coordinates, so they are "
            "counted here by state but cannot be mapped."),
    },
    "popmart": {
        "name": "POP MART", "name_zh": "泡泡玛特",
        "founded": 2010, "founder": "Wang Ning", "hq": "Beijing",
        "listing": "HKEX (listed 2020)",
        "global_stores": "530+ stores worldwide at Dec 2024, plus roboshops",
        "us_entry": "2020s; now in malls nationwide",
        "blurb": (
            "Designer toys sold in blind boxes — you pay before you know which figure you get. Wang "
            "Ning founded it in 2010 as a Beijing variety store and turned it into an IP company: the "
            "Labubu character, designed by Kasing Lung, became a global craze that put Pop Mart bags "
            "on celebrities and queues outside its US malls. It is the one chain in scope selling "
            "objects rather than drinks."),
        "why_watch": (
            "The clearest test of whether the Chinese chain wave in America is only tea and coffee. "
            "Its locator is behind bot management, so it is not collected here yet."),
    },
    "miniso": {
        "name": "MINISO", "name_zh": "名创优品",
        "founded": 2013, "founder": "Ye Guofu", "hq": "Guangzhou, Guangdong",
        "listing": "NYSE: MNSO (2020) and HKEX: 9896 (dual primary, July 2022)",
        "global_stores": "8,485 worldwide at 31 Dec 2025 — 4,568 in mainland China, 3,583 overseas",
        "us_entry": "Pasadena, California, 2017",
        "blurb": (
            "A cheap-and-cheerful variety chain — homeware, stationery, cosmetics, plush toys — that "
            "long presented itself with Japanese-styled branding despite being founded in Guangzhou "
            "in 2013. It has since leaned into licensed character goods (Disney, Sanrio, Barbie) and "
            "its own IP, and opened its 400th US store in August 2026, by far the largest American "
            "footprint of any chain in scope."),
        "why_watch": (
            "The biggest prize and the biggest gap: roughly 400 US stores, and a locator this "
            "collector cannot read yet."),
    },
    "heytea": {
        "name": "HEYTEA", "name_zh": "喜茶",
        "founded": 2012, "founder": "Nie Yunchen (Neo Nie)", "hq": "Shenzhen, Guangdong",
        "listing": "private",
        "global_stores": "4,000+ in 2026",
        "us_entry": "New York City, December 2023",
        "blurb": (
            "The chain credited with inventing cheese-foam tea, which Nie Yunchen began selling from "
            "a small shop in Jiangmen in 2012 under the name Royal Tea. It built its reputation on "
            "design-led flagship stores and fruit teas at premium prices, and was the first of this "
            "mainland wave to open in the United States, in New York at the end of 2023."),
        "why_watch": (
            "The earliest mover of the current wave, which makes it the closest thing to a control "
            "case for how these US expansions mature."),
    },
    "cotti": {
        "name": "Cotti Coffee", "name_zh": "库迪咖啡",
        "founded": 2022, "founder": "Lu Zhengyao and Qian Zhiya", "hq": "Beijing",
        "listing": "private",
        "global_stores": "18,000+ in 28 countries as of April 2026",
        "us_entry": "2023-24, via franchisees",
        "blurb": (
            "Founded in 2022 by the two executives ousted from Luckin over the accounting fraud, and "
            "aimed squarely at the company they used to run: Cotti undercuts Luckin on price and has "
            "expanded at extraordinary speed on a franchise model. Its US presence has grown quietly "
            "through individual franchisees near universities and in Chinese-American suburbs rather "
            "than through a national rollout."),
        "why_watch": (
            "The purest example of the price war that is pushing these chains abroad. It publishes no "
            "first-party US locator at all, which is itself the finding."),
    },
}

#!/usr/bin/env python3
"""
name:      build_zh.py
purpose:   Generate the Simplified-Chinese mirror tree (/zh/...) of the site inside the publish dir,
           from the already-stamped English pages, on every deploy. English is always the fallback,
           so an untranslated string shows English rather than breaking.
arguments: argv[1] = pubdir (the staged copy of map/, e.g. the deploy $TMP). Defaults to "map".
returns:   exit 0.
effects:   Writes <pubdir>/zh-strings.js and <pubdir>/zh/<page> for each top-level page; adds
           reciprocal hreflang alternates to the English pages in place. (Chinese chain pages are
           emitted by prerender_chains.py in its zh pass.)
other:     Runs AFTER the deploy's cache-bust stamping and BEFORE/with prerender. Shares ONE data set
           with the English tree: /zh/ pages carry <base href="/"> so they fetch the same /data,
           /icons, /photos. The only per-tree differences are lang, the string catalog, the baked
           [data-i18n] text, the <head> alternates/canonical, and /zh/-prefixed in-page links.
"""
import hashlib
import json
import re
import sys
from pathlib import Path

DOMAIN = "https://chainsfromchina.com"

# Top-level pages that get a /zh/ twin. (Chain pages are handled by the prerender zh pass.)
PAGES = ["index.html", "intro.html", "register.html", "states.html",
         "centers.html", "method.html", "contribute.html"]

# Known internal page link targets (relative or root-absolute); everything else (css/js/png/jpg/
# json/geojson/svg/webp, https:, mailto:, #...) is an asset or external and stays root-shared.
_PAGE_BASENAMES = {p for p in PAGES} | {"classic.html", "states.html"}
_LINK_RE = re.compile(r'(href=")(/)?((?:[\w.-]+\.html(?:[#?][^"]*)?)|(?:chain/[^"]*)|)(")')


def canon_path(page: str) -> str:
    """Site path for a page under /zh/ (index.html → /zh/)."""
    return "/zh/" if page == "index.html" else "/zh/" + page


def en_path(page: str) -> str:
    return "/" if page == "index.html" else "/" + page


def _zh_link(m: re.Match) -> str:
    pre, slash, body, post = m.group(1), m.group(2), m.group(3), m.group(4)
    if not body:                                   # href="/" (root) or href="" → root becomes /zh/
        if slash:
            return pre + "/zh/" + post
        return m.group(0)
    base = body.split("#")[0].split("?")[0]
    is_page = base.endswith(".html") and base in _PAGE_BASENAMES
    is_chain = base.startswith("chain/")
    if is_page or is_chain:
        return pre + "/zh/" + body + post
    return m.group(0)                              # leave assets/other untouched


def rewrite_links(html: str) -> str:
    # href="/" → /zh/ ; href="intro.html"/"/intro.html"/"chain/x/" → /zh/... ; assets untouched.
    html = re.sub(r'href="/"', 'href="/zh/"', html)
    return _LINK_RE.sub(_zh_link, html)


def bake_i18n(html: str, cat: dict) -> str:
    """Replace the text of leaf elements annotated data-i18n="key" with the Chinese string."""
    def rep(m: re.Match) -> str:
        tag, attrs, key = m.group(1), m.group(2), m.group(3)
        zh = cat.get(key)
        if zh is None:
            return m.group(0)
        return "<" + tag + attrs + ">" + zh + "</" + tag + ">"
    # <tag ...data-i18n="key"...>TEXT</tag> — leaf elements only (no nested same-tag).
    return re.sub(r'<([a-zA-Z0-9]+)([^>]*\sdata-i18n="([^"]+)"[^>]*)>(.*?)</\1>', rep, html, flags=re.S)


def head_alternates(page: str) -> str:
    en = DOMAIN + en_path(page)
    zh = DOMAIN + canon_path(page)
    return ('<link rel="alternate" hreflang="en" href="%s">'
            '<link rel="alternate" hreflang="zh-Hans" href="%s">'
            '<link rel="alternate" hreflang="x-default" href="%s">') % (en, zh, en)


def transform_zh(html: str, page: str, cat: dict, strings_ref: str) -> str:
    # 1. locale on <html>
    html = re.sub(r'<html lang="en">', '<html lang="zh-Hans">', html, count=1)
    # (base href is inserted LAST, after link rewriting, so it isn't itself rewritten)
    # 3. Chinese string catalog loads synchronously BEFORE i18n.js (sets CFC_LANG + CFC_STRINGS)
    html = re.sub(r'(<script src="i18n\.js)', '<script src="%s"></script>\n\\1' % strings_ref, html, count=1)
    # 4. head: og:locale, JSON-LD inLanguage, canonical → /zh/, + reciprocal alternates
    html = html.replace('content="en_US"', 'content="zh_CN"')
    html = html.replace('"inLanguage":"en-US"', '"inLanguage":"zh-CN"')
    html = html.replace('"inLanguage": "en-US"', '"inLanguage": "zh-CN"')
    zh_url = DOMAIN + canon_path(page)
    html = re.sub(r'(<link rel="canonical" href=")[^"]*(">)', r'\g<1>' + zh_url + r'\2', html, count=1)
    html = re.sub(r'(<meta property="og:url" content=")[^"]*(">)', r'\g<1>' + zh_url + r'\2', html, count=1)
    html = html.replace('<link rel="canonical"', head_alternates(page) + '<link rel="canonical"', 1)
    # 5. optional zh <title>/description/OG from the catalog (English stays if a key is absent)
    pkey = page[:-5] if page.endswith(".html") else page
    t = cat.get("head.%s.title" % pkey)
    if t:
        html = re.sub(r'<title>.*?</title>', '<title>' + t + '</title>', html, count=1, flags=re.S)
        html = re.sub(r'(<meta property="og:title" content=")[^"]*(">)', r'\g<1>' + t + r'\2', html, count=1)
        html = re.sub(r'(<meta name="twitter:title" content=")[^"]*(">)', r'\g<1>' + t + r'\2', html, count=1)
    d = cat.get("head.%s.desc" % pkey)
    if d:
        html = re.sub(r'(<meta name="description" content=")[^"]*(">)', r'\g<1>' + d + r'\2', html, count=1)
        html = re.sub(r'(<meta property="og:description" content=")[^"]*(">)', r'\g<1>' + d + r'\2', html, count=1)
        html = re.sub(r'(<meta name="twitter:description" content=")[^"]*(">)', r'\g<1>' + d + r'\2', html, count=1)
    # 6. bake static copy + rewrite in-page links to the /zh/ tree
    html = bake_i18n(html, cat)
    html = rewrite_links(html)
    # 7. <base href="/"> LAST so /zh/ shares the root's assets + data and the base isn't rewritten
    if "<base " not in html:
        html = html.replace('<meta charset="utf-8">',
                            '<meta charset="utf-8">\n<base href="/">', 1)
    return html


def add_en_alternates(html: str, page: str) -> str:
    if 'hreflang="zh-Hans"' in html:
        return html
    return html.replace('<link rel="canonical"', head_alternates(page) + '<link rel="canonical"', 1)


def main() -> int:
    pub = Path(sys.argv[1] if len(sys.argv) > 1 else "map")
    cat_path = pub / "i18n.zh.json"
    if not cat_path.exists():
        print("build_zh: no i18n.zh.json found, skipping")
        return 0
    cat = {k: v for k, v in json.loads(cat_path.read_text(encoding="utf-8")).items()
           if not k.startswith("_")}

    # Runtime catalog for the /zh/ tree: sets the locale + overrides before i18n.js runs.
    strings_js = "window.CFC_LANG='zh';window.CFC_STRINGS=" + json.dumps(cat, ensure_ascii=False) + ";\n"
    (pub / "zh-strings.js").write_text(strings_js, encoding="utf-8")
    ver = hashlib.sha1(strings_js.encode("utf-8")).hexdigest()[:10]
    strings_ref = "/zh-strings.js?v=" + ver

    zdir = pub / "zh"
    zdir.mkdir(exist_ok=True)
    n = 0
    for page in PAGES:
        src = pub / page
        if not src.exists():
            continue
        html = src.read_text(encoding="utf-8")
        (zdir / page).write_text(transform_zh(html, page, cat, strings_ref), encoding="utf-8")
        # reciprocal alternates on the English page, in place
        src.write_text(add_en_alternates(html, page), encoding="utf-8")
        n += 1
    print("built /zh/ for %d pages" % n)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

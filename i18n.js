/*
 * name:      i18n.js
 * purpose:   One tiny locale runtime shared by every page and the /zh/ Simplified-Chinese mirror.
 * arguments: window.CFC_LANG ('en' | 'zh'), optional; else inferred from <html lang>.
 *            window.CFC_STRINGS — a { key: "中文" } map of Chinese overrides, loaded (synchronously,
 *            before this file) only on the /zh/ tree via /zh-strings.js. Absent on the English site.
 * returns:   nothing.
 * effects:   Exposes globals: t(), secLabel(), stateName(), dfmt(), cfcLocale(), CFC_LANG. On the zh
 *            tree, fills any [data-i18n] element the build left unbaked (a safety net).
 * other:     English is the inline default EVERYWHERE — in code (the 2nd arg to t) and in the HTML
 *            (the element's own text). This file only supplies Chinese overrides, so the English site
 *            is unaffected and the Chinese site falls back to English for anything not yet translated.
 */
(function () {
  var lang = window.CFC_LANG;
  if (!lang) {
    var l = (document.documentElement.getAttribute('lang') || 'en').toLowerCase();
    lang = l.indexOf('zh') === 0 ? 'zh' : 'en';
  }
  window.CFC_LANG = lang;
  var S = window.CFC_STRINGS || {};               // key -> Chinese string (only present on /zh/)

  function interp(s, vars) {
    return vars ? String(s).replace(/\{(\w+)\}/g, function (m, k) {
      return vars[k] != null ? vars[k] : m; }) : s;
  }

  // t(key, en, vars): the Chinese override when on zh and present, else the English default.
  function t(key, en, vars) {
    var s = (lang === 'zh' && S[key] != null) ? S[key] : en;
    return interp(s, vars);
  }

  // Canonical English label maps (the single source these used to be copy-pasted from). Chinese
  // lives in the catalog under sector.<code> / state.<CODE>.
  var SEC_EN = { tea: 'Tea', coffee: 'Coffee', food_drink: 'Food & drink', bakery: 'Bakery',
    grocery_convenience: 'Grocery', snacks: 'Snacks', apparel: 'Apparel', beauty: 'Beauty',
    lifestyle_variety: 'Lifestyle & toys', electronics: 'Electronics', home: 'Home' };
  function secLabel(code) { return t('sector.' + code, SEC_EN[code] || code); }

  var STATE_EN = {
    AL: 'Alabama', AK: 'Alaska', AZ: 'Arizona', AR: 'Arkansas', CA: 'California', CO: 'Colorado',
    CT: 'Connecticut', DE: 'Delaware', DC: 'District of Columbia', FL: 'Florida', GA: 'Georgia',
    HI: 'Hawaii', ID: 'Idaho', IL: 'Illinois', IN: 'Indiana', IA: 'Iowa', KS: 'Kansas', KY: 'Kentucky',
    LA: 'Louisiana', ME: 'Maine', MD: 'Maryland', MA: 'Massachusetts', MI: 'Michigan', MN: 'Minnesota',
    MS: 'Mississippi', MO: 'Missouri', MT: 'Montana', NE: 'Nebraska', NV: 'Nevada', NH: 'New Hampshire',
    NJ: 'New Jersey', NM: 'New Mexico', NY: 'New York', NC: 'North Carolina', ND: 'North Dakota',
    OH: 'Ohio', OK: 'Oklahoma', OR: 'Oregon', PA: 'Pennsylvania', RI: 'Rhode Island',
    SC: 'South Carolina', SD: 'South Dakota', TN: 'Tennessee', TX: 'Texas', UT: 'Utah', VT: 'Vermont',
    VA: 'Virginia', WA: 'Washington', WV: 'West Virginia', WI: 'Wisconsin', WY: 'Wyoming' };
  function stateName(code) { return t('state.' + code, STATE_EN[code] || code); }

  function cfcLocale() { return lang === 'zh' ? 'zh-CN' : 'en-US'; }
  // Locale-aware date formatting; same options object the pages already pass to toLocaleDateString.
  function dfmt(d, opts) { try { return d.toLocaleDateString(cfcLocale(), opts); } catch (e) { return ''; } }

  // Safety net: on the zh tree, fill any [data-i18n] element the build did not bake. (The build bakes
  // these server-side so crawlers see Chinese; this only covers anything missed.)
  function fillStatic() {
    if (lang !== 'zh') return;
    var els = document.querySelectorAll('[data-i18n]');
    for (var i = 0; i < els.length; i++) {
      var k = els[i].getAttribute('data-i18n');
      if (S[k] != null) els[i].textContent = S[k];
    }
  }
  if (document.readyState !== 'loading') fillStatic();
  else document.addEventListener('DOMContentLoaded', fillStatic);

  window.t = t;
  window.secLabel = secLabel;
  window.stateName = stateName;
  window.dfmt = dfmt;
  window.cfcLocale = cfcLocale;
  window.CFC_SEC_EN = SEC_EN;       // for any call site that still wants the raw English map
  window.CFC_STATE_EN = STATE_EN;
})();

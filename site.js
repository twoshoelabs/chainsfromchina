/*
 * name:      site.js
 * purpose:   Inject the one shared header on every page, mark the current page, fill each page's
 *            census eyebrow line, and provide the ⌘K search (Places / Shopping centers / Chains).
 * arguments: body[data-page] — map | chains | cotenancy | global (optional).
 * returns:   nothing.
 * effects:   Prepends <header class="site-nav">; hides legacy .masthead; fills [data-census];
 *            builds a hidden search overlay opened by ⌘K or the header Search button.
 * other:     No framework. One row at every width ≥768 px (60 px desktop, 56 px tablet). The home
 *            page keeps its own hero search, so there ⌘K focuses that box instead of the overlay.
 */
(function () {
  // i18n.js loads first (in <head>); be defensive if it somehow didn't.
  var LANG = window.CFC_LANG || 'en';
  var P = LANG === 'zh' ? 'zh/' : '';                 // internal-link prefix for the /zh/ tree (base=/)
  var tt = window.t || function (k, en) { return en; };
  var secLbl = window.secLabel || function (c) { return c; };

  var PAGES = [
    ['map', 'index.html', tt('nav.map', 'Map')],
    ['chains', 'intro.html', tt('nav.chains', 'Chains')],
    ['cotenancy', 'centers.html', tt('nav.cotenancy', 'Co-tenancy')],
    ['global', 'register.html', tt('nav.global', 'Global')],
    ['method', 'method.html', tt('nav.method', 'Method')],
    ['pro', 'index.html#pro', tt('nav.pro', 'Pro')],
  ];
  var cur = (document.body.getAttribute('data-page') || '').trim();

  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) {
    return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }

  // ---- Language switcher: link to the counterpart page in the other locale --------------------
  var _path = location.pathname, _inZh = /^\/zh(\/|$)/.test(_path);
  var _enHref = (_inZh ? (_path.replace(/^\/zh/, '') || '/') : _path) + location.search + location.hash;
  var _zhHref = (_inZh ? _path : ('/zh' + (_path === '/' ? '/' : _path))) + location.search + location.hash;
  var langSw = '<span class="np-lang">' +
    '<a href="' + esc(_enHref) + '"' + (!_inZh ? ' aria-current="true"' : '') + '>EN</a>' +
    '<span class="np-langsep" aria-hidden="true">·</span>' +
    '<a href="' + esc(_zhHref) + '" lang="zh-Hans"' + (_inZh ? ' aria-current="true"' : '') + '>中文</a></span>';

  // ---- Header: newspaper nameplate (shared with the home page) ------------------------------
  var nav = PAGES.map(function (p) {
    return '<a href="' + P + p[1] + '"' + (p[0] === cur ? ' aria-current="page"' : '') + '>' + p[2] + '</a>';
  }).join('');

  var header = document.createElement('header');
  header.className = 'site-nav';
  var sub = tt('np.sub', 'The daily census of China-origin retail in the United States');
  header.innerHTML =
    '<div class="np-issue"><span id="cfc-issue">' + esc(sub) + '</span>' +
      '<span class="np-sub">' + esc(sub) + '</span></div>' +
    '<div class="np-row">' +
      '<a class="np-wm" href="' + P + 'index.html">' +
        '<span class="np-mark">Chains From China</span>' +
        '<span class="np-zh" lang="zh-Hans">中国连锁在美门市</span></a>' +
      '<nav class="np-nav" aria-label="Primary">' + nav + langSw + '</nav>' +
    '</div>';

  var olds = document.querySelectorAll('.masthead');
  for (var i = 0; i < olds.length; i++) olds[i].style.display = 'none';
  document.body.insertBefore(header, document.body.firstChild);

  // Search icon, reused by the ⌘K overlay below (the nameplate itself carries no search button).
  var searchIcon = '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="7"/><path d="m21 21-4.3-4.3"/></svg>';

  // All site times are New York time. Render the census's finish time in ET from meta.generated
  // (an ISO stamp the pipeline writes in NY time); if absent, fall back to a plain zone tag.
  function etClock(iso) {
    if (!iso) return '';
    try {
      return new Date(iso).toLocaleTimeString(window.cfcLocale ? cfcLocale() : 'en-US',
        { timeZone: 'America/New_York', hour: 'numeric', minute: '2-digit' }) + tt('census.et', ' ET');
    } catch (e) { return ''; }
  }

  // ---- Census meta: fill the nameplate issue line + any [data-census] eyebrow -----------------
  fetch('data/meta.json' + ((window.CFC_DATA_V) || '')).then(function (r) { return r.json(); }).then(function (m) {
    if (!m) return;
    var d = m.last_collected, shortLabel = d, issue = '', et = etClock(m.generated);
    try {
      var dt = new Date(d + 'T00:00:00');
      if (LANG === 'zh') {
        shortLabel = dt.toLocaleDateString('zh-CN', { year: 'numeric', month: 'short', day: 'numeric' });
        issue = dt.toLocaleDateString('zh-CN', { year: 'numeric', month: 'long', day: 'numeric', weekday: 'long' });
      } else {
        shortLabel = dt.toLocaleDateString('en-US', { day: 'numeric', month: 'short', year: 'numeric' });
        issue = dt.toLocaleDateString('en-US', { weekday: 'long' }) + ' ' + dt.getDate() + ' ' +
          dt.toLocaleDateString('en-US', { month: 'long' }) + ' ' + dt.getFullYear();
      }
    } catch (e) {}
    var issueEl = document.getElementById('cfc-issue');
    if (issueEl && issue) issueEl.textContent = issue;
    var tail = et ? ((LANG === 'zh' ? ' · ' : ', ') + et) : tt('census.nytime', ', New York time');
    var text = tt('census.updated', 'Daily census · Updated {date}{tail}', { date: shortLabel, tail: tail });
    document.querySelectorAll('[data-census]').forEach(function (el) { el.textContent = text; });
  }).catch(function () {});

  // ---- ⌘K search overlay ---------------------------------------------------------------------
  var SEC_COLOR = { tea:'#5E8C3A', coffee:'#7A4E2D', food_drink:'#B5462E', bakery:'#C08A2B',
    grocery_convenience:'#2F8C8C', snacks:'#D0702A', apparel:'#6B4FA0', beauty:'#C4577A',
    lifestyle_variety:'#2F5FA8', electronics:'#3C7A9A', home:'#7A8C3A' };
  // (sector labels now come from i18n.js secLabel(); SEC_COLOR above stays local.)

  var overlay = null, idxP = null, opts = [], sel = -1;

  function heroSearch() { return document.getElementById('hero-search'); }

  function buildOverlay() {
    overlay = document.createElement('div');
    overlay.className = 'cfc-searchmodal'; overlay.hidden = true;
    overlay.innerHTML =
      '<div class="cfc-sm-box" role="dialog" aria-label="Search">' +
        '<div class="cfc-sm-top">' + searchIcon +
          '<input id="cfc-sm-input" type="search" autocomplete="off" placeholder="' + esc(tt('search.placeholder', 'Search chains, cities or shopping centers…')) + '" aria-label="Search" aria-controls="cfc-sm-list" aria-expanded="true">' +
          '<kbd>Esc</kbd></div>' +
        '<div class="cfc-sm-list" id="cfc-sm-list" role="listbox"></div>' +
      '</div>';
    document.body.appendChild(overlay);
    overlay.addEventListener('click', function (e) { if (e.target === overlay) closeModal(); });
    var input = overlay.querySelector('#cfc-sm-input');
    input.addEventListener('input', function () { renderModal(input.value); });
    input.addEventListener('keydown', function (e) {
      if (e.key === 'ArrowDown') { e.preventDefault(); if (opts.length) { sel = Math.min(sel + 1, opts.length - 1); hi(); } }
      else if (e.key === 'ArrowUp') { e.preventDefault(); if (opts.length) { sel = Math.max(sel - 1, 0); hi(); } }
      else if (e.key === 'Enter') { if (sel >= 0) { e.preventDefault(); choose(sel); } }
      else if (e.key === 'Escape') { closeModal(); }
    });
  }

  function loadIndex() {
    if (idxP) return idxP;
    idxP = Promise.all([
      fetch('data/stores.geojson' + ((window.CFC_DATA_V) || '')).then(function (r) { return r.json(); }),
      // Co-tenancy is a Pro feature — centers.json is not published publicly, so don't request it.
      Promise.resolve({ co_tenancy: [] }),
    ]).then(function (res) {
      var gj = res[0], cen = res[1];
      var chainMap = {}, cityMap = {};
      gj.features.forEach(function (f) {
        var p = f.properties;
        if (!chainMap[p.chain]) chainMap[p.chain] = { type: 'chain', id: p.chain, name: p.name, sector: p.sector };
        else if (p.status === 'open') chainMap[p.chain].name = p.name;
        if (p.city && p.state) {
          var k = p.city + ', ' + p.state, c = cityMap[k] || (cityMap[k] = { type: 'place', name: p.city, state: p.state, n: 0, x: 0, y: 0 });
          c.n++; c.x += f.geometry.coordinates[0]; c.y += f.geometry.coordinates[1];
        }
      });
      var places = Object.keys(cityMap).map(function (k) { var c = cityMap[k]; return { type: 'place', name: c.name, state: c.state, n: c.n, lng: c.x / c.n, lat: c.y / c.n }; });
      var centers = (cen.co_tenancy || []).filter(function (c) { return c.center && c.center.name && c.lat != null; })
        .map(function (c) { return { type: 'center', name: c.center.name, city: c.city, state: c.state, lng: c.lon, lat: c.lat }; });
      return { chains: Object.keys(chainMap).map(function (k) { return chainMap[k]; }), places: places, centers: centers };
    });
    return idxP;
  }

  function renderModal(raw) {
    var list = overlay.querySelector('#cfc-sm-list');
    var q = raw.trim().toLowerCase();
    opts = []; sel = -1;
    if (!q) { list.innerHTML = '<div class="cfc-sm-none">' + esc(tt('search.empty', 'Type to search across chains, cities and shopping centers.')) + '</div>'; return; }
    loadIndex().then(function (idx) {
      if (overlay.querySelector('#cfc-sm-input').value.trim().toLowerCase() !== q) return;
      var m = function (arr) { return arr.filter(function (o) { return o.name.toLowerCase().indexOf(q) >= 0; })
        .sort(function (a, b) { return a.name.toLowerCase().indexOf(q) - b.name.toLowerCase().indexOf(q); }); };
      var places = m(idx.places).slice(0, 5), centers = m(idx.centers).slice(0, 5), chains = m(idx.chains).slice(0, 6);
      var html = '';
      if (!chains.length && (places.length || centers.length)) html += '<div class="cfc-sm-note">' + tt('search.nochain', 'No chain names match <b>{q}</b> — try a place or center:', { q: esc(raw.trim()) }) + '</div>';
      function grp(label, arr, make) { if (!arr.length) return; html += '<div class="cfc-sm-grp">' + label + '</div>';
        arr.forEach(function (o) { var i = opts.length; opts.push(o); html += '<div class="cfc-sm-opt" role="option" data-i="' + i + '">' + make(o) + '</div>'; }); }
      grp(tt('search.g.places', 'Places'), places, function (o) { return '<span class="ic">◉</span><span class="nm">' + esc(o.name) + ', ' + esc(o.state) + '</span><span class="meta">' + tt('search.outlets', o.n + ' outlet' + (o.n > 1 ? 's' : ''), { n: o.n }) + '</span>'; });
      grp(tt('search.g.centers', 'Shopping centers'), centers, function (o) { return '<span class="ic">▣</span><span class="nm">' + esc(o.name) + '</span><span class="meta">' + esc([o.city, o.state].filter(Boolean).join(', ')) + '</span>'; });
      grp(tt('search.g.chains', 'Chains'), chains, function (o) { return '<span class="ring" style="border-color:' + (SEC_COLOR[o.sector] || '#888') + '"></span><span class="nm">' + esc(o.name) + '</span><span class="meta">' + esc(secLbl(o.sector) || '') + '</span>'; });
      if (!opts.length) html = '<div class="cfc-sm-none">' + tt('search.nomatch', 'No matches for <b>{q}</b>.', { q: esc(raw.trim()) }) + '</div>';
      list.innerHTML = html;
      list.querySelectorAll('.cfc-sm-opt').forEach(function (el) { el.addEventListener('mousedown', function (e) { e.preventDefault(); choose(+el.dataset.i); }); });
    });
  }

  function hi() { overlay.querySelectorAll('.cfc-sm-opt').forEach(function (el, i) { el.setAttribute('aria-selected', String(i === sel)); });
    var c = overlay.querySelector('.cfc-sm-opt[aria-selected="true"]'); if (c) c.scrollIntoView({ block: 'nearest' }); }

  function choose(i) {
    var o = opts[i]; if (!o) return;
    if (o.type === 'chain') location.href = P + 'chain/' + encodeURIComponent(o.id) + '/';
    else location.href = P + 'index.html#c=' + o.lng.toFixed(4) + ',' + o.lat.toFixed(4) + '&z=' + (o.type === 'center' ? 15 : 10);
  }

  function openModal() {
    var hs = heroSearch();
    if (hs) { hs.focus(); hs.select(); return; }   // home: use its own hero search
    if (!overlay) buildOverlay();
    overlay.hidden = false;
    var input = overlay.querySelector('#cfc-sm-input'); input.value = ''; renderModal('');
    setTimeout(function () { input.focus(); }, 0);
  }
  function closeModal() { if (overlay) overlay.hidden = true; }

  var sbtn = document.getElementById('cfc-searchbtn');
  if (sbtn) sbtn.addEventListener('click', openModal);   // nameplate has no button; ⌘K still opens it
  document.addEventListener('keydown', function (e) {
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
      e.preventDefault(); openModal();
    }
  });
})();

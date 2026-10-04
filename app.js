/*
 * Two views of the same archive.
 *
 *   Stores    every store the collector can place, as a dot. Precise, and incomplete: a chain
 *             that publishes no coordinates is missing from it entirely.
 *   By state  counts per state, taken from the roster rather than from the dots, so the stores
 *             that cannot be drawn are still counted. This view is the more complete one, and
 *             the legend says so rather than leaving a reader to assume the dots are everything.
 *
 * The projection is the same Lambert azimuthal equal-area formula the collector keys cells with
 * (geo.py), so a dot here and a cell in the database are the same piece of ground.
 *
 * No map library, no tile server, no API key: sixty dots on fifty outlines need none of it, and
 * a page that fetches nothing third-party keeps working when a CDN does not.
 */
const R = 6370997.0;
const MAINLAND = [45, -100];          // the centre the collector keys its cells with (geo.py)

/*
 * Lambert azimuthal equal-area about a given centre. The mainland uses 45N 100W, matching
 * geo.py exactly, so a dot on that part of the map and a cell in the database are the same
 * ground. Each inset uses its OWN centre instead: Guam sits 97 degrees of arc from 45N 100W,
 * where this projection is still valid but visibly shears anything drawn in it, and an inset
 * is its own little map anyway — nothing is compared across the frame.
 */
function project(lat, lon, centre) {
  const [c0, l0] = centre || MAINLAND;
  const lat0 = c0 * Math.PI / 180, lon0 = l0 * Math.PI / 180;
  const phi = lat * Math.PI / 180, lam = lon * Math.PI / 180;
  const cosc = Math.sin(lat0) * Math.sin(phi) + Math.cos(lat0) * Math.cos(phi) * Math.cos(lam - lon0);
  const k = Math.sqrt(Math.max(0, 2 / (1 + cosc)));
  return [
    R * k * Math.cos(phi) * Math.sin(lam - lon0),
    -(R * k * (Math.cos(lat0) * Math.sin(phi) - Math.sin(lat0) * Math.cos(phi) * Math.cos(lam - lon0))),
  ];
}

const COLOR = { mixue: 'var(--mixue)', chagee: 'var(--chagee)',
                luckin: 'var(--luckin)', miniso: 'var(--miniso)',
                popmart: 'var(--popmart)', haidilao: 'var(--haidilao)' };
const colorOf = c => COLOR[c] || 'var(--other)';
const SVG = 'http://www.w3.org/2000/svg';
const el = (n, a = {}) => { const e = document.createElementNS(SVG, n); for (const k in a) e.setAttribute(k, a[k]); return e; };
/*
 * How a chain is named, everywhere it is named. These are Chinese companies trading under
 * English names, and several trade under a DIFFERENT English name in America — ChaPanda sells
 * as TeaByDo, Juewei as King of Braise elsewhere. Showing the original alongside is not
 * decoration: it is how a reader connects what is on the shopfront here to the company that
 * owns it, and how the next person searching avoids the mistake of hunting the wrong name.
 */
const chainLabel = (c, opts = {}) => {
  const trading = c.name_us || c.name;
  const alias = c.name_us && c.name_us !== c.name ? c.name : null;
  const zh = c.name_zh ? `<span class="zh">${esc(c.name_zh)}</span>` : '';
  const also = alias && !opts.short ? `<span class="zh">(${esc(alias)})</span>` : '';
  // Extra US trading names for the same shops (Fish With You also trades as Wei's Fish, YONNY).
  const aka = (c.aliases && c.aliases.length && !opts.short)
    ? `<span class="zh">also: ${c.aliases.map(esc).join(', ')}</span>` : '';
  return `${esc(trading)}${zh}${also}${aka}`;
};

// Resolve a chain id to its record, whether it is collected (meta.chains) or blocked
// (meta.blocked). Used so every tooltip can lead with the chain, not just the shopfront name.
const chainObj = id =>
  (DATA.meta.chains && DATA.meta.chains[id]) ||
  ((DATA.meta.blocked || []).find(b => b.chain_id === id)) ||
  { name: id };

// The location line under the chain heading should be just the branch. A label may repeat the
// chain ("HEYTEA (Flushing)", "MIXUE-Union Square", "Tai Er Sichuan Cuisine (Valley Fair)"), so
// strip a leading copy of the chain name and unwrap the "(X)" it leaves behind.
function branchOf(chainName, name) {
  let n = (name || '').trim();
  if (!n) return '';
  const rx = new RegExp('^' + chainName.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '[\\s\\-\u2013\u2014:]*', 'i');
  n = n.replace(rx, '').trim();
  const m = n.match(/^\((.*)\)$/);
  if (m) n = m[1].trim();
  return n.toLowerCase() === chainName.toLowerCase() ? '' : n;
}

const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

let view, home, mode = 'stores';
const statePaths = {}, stateLabels = [];

/*
 * Alaska and Hawaii are drawn as insets, the way every US map does it, because fitting the
 * view to include them would shrink the lower 48 to a smear. They are NOT optional: MINISO
 * has two stores in Hawaii, and before these insets existed they were projected to their true
 * position, drawn correctly, and left permanently outside the viewport — collected every day
 * and impossible to see. Hawaii matters for this subject in particular.
 *
 * Each inset is its own <g> with a transform, so the geometry, the label and the dots inside it
 * move together and stay honest relative to one another. The scale differs from the mainland's,
 * which is why each inset is framed and captioned rather than quietly abutted.
 */
const INSETS = {
  AK: { boxW: 0.150, boxH: 0.24, at: [0.010, 0.70], centre: [63, -152] },
  HI: { boxW: 0.075, boxH: 0.12, at: [0.175, 0.82], centre: [20.6, -157.3] },
  PR: { boxW: 0.070, boxH: 0.07, at: [0.268, 0.88], centre: [18.2, -66.5] },
  GU: { boxW: 0.035, boxH: 0.07, at: [0.355, 0.88], centre: [13.45, 144.78] },
};
const insetCaptions = [];
const insetGroups = {};
const hidden = new Set();
let DATA = null;

async function main() {
  const [states, data] = await Promise.all([
    fetch('us-states.geojson').then(r => r.json()),
    fetch('data/stores.json').then(r => r.json()),
  ]);
  DATA = data;
  computeBreaks(data.meta.by_state);

  const svg = document.getElementById('map');
  const gLand = el('g'), gInsets = el('g'), gLabels = el('g'), gDots = el('g');
  svg.append(gLand, gInsets, gLabels, gDots);

  // Outlines. CONUS sets the view; Alaska and Hawaii are drawn but left outside it, because
  // fitting to them would shrink the lower 48 to a smear for the sake of two empty states.
  const CONUS = f => !INSETS[f.id];
  let bb = [Infinity, Infinity, -Infinity, -Infinity];
  const ownBox = {};
  for (const f of states.features) {
    const polys = f.geometry.type === 'Polygon' ? [f.geometry.coordinates] : f.geometry.coordinates;
    let d = '';
    const own = [Infinity, Infinity, -Infinity, -Infinity];
    for (const poly of polys) for (const ring of poly) {
      // Alaska's Aleutians cross the antimeridian, which inflates its bounding box to 2,800 km
      // wide and would shrink the inset to nothing. Drop the rings that sit past 180°, as
      // printed US maps do.
      if (f.id === 'AK' && ring.reduce((a, p) => a + p[0], 0) / ring.length > 0) continue;
      d += ring.map(([lon, lat], i) => {
        const [x, y] = project(lat, lon, INSETS[f.id] && INSETS[f.id].centre);
        own[0] = Math.min(own[0], x); own[1] = Math.min(own[1], y);
        own[2] = Math.max(own[2], x); own[3] = Math.max(own[3], y);
        if (CONUS(f)) {
          bb[0] = Math.min(bb[0], x); bb[1] = Math.min(bb[1], y);
          bb[2] = Math.max(bb[2], x); bb[3] = Math.max(bb[3], y);
        }
        return (i ? 'L' : 'M') + x.toFixed(0) + ' ' + y.toFixed(0);
      }).join('') + 'Z';
    }
    ownBox[f.id] = own;
    const p = el('path', { d, class: 'state', 'data-state': f.id });
    const t = el('title');
    t.textContent = f.properties.name;
    p.append(t);
    p.addEventListener('pointerenter', e => { if (mode === 'states') showStateTip(e, f.id, f.properties.name); });
    p.addEventListener('pointerleave', hideTip);
    gLand.append(p);
    statePaths[f.id] = p;

    // Label anchored at the outline's own centre. Crude for a hooked state like Florida, and
    // good enough for a number that only has to sit inside its own shape.
    const st = data.meta.by_state[f.id];
    if (st && (st.open || st.coming_soon)) {
      // Drawn at an ordinary font size and scaled into place. Setting font-size in viewBox
      // units instead would ask for ~115,000px of type, which browsers silently clamp (to
      // 5000px in Chrome) and the label comes out three pixels wide.
      const label = el('text', {
        x: 0, y: 0, 'font-size': 14, 'stroke-width': 3.1,
        class: 'slabel', 'text-anchor': 'middle', 'dominant-baseline': 'central',
      });
      label.dataset.x = ((own[0] + own[2]) / 2).toFixed(0);
      label.dataset.y = ((own[1] + own[3]) / 2).toFixed(0);
      label.textContent = st.open + (st.coming_soon ? '+' + st.coming_soon : '');
      label.dataset.state = f.id;
      gLabels.append(label);
      stateLabels.push(label);
    }
  }

  const pad = (bb[2] - bb[0]) * 0.03;
  home = { x: bb[0] - pad, y: bb[1] - pad, w: bb[2] - bb[0] + 2 * pad, h: bb[3] - bb[1] + 2 * pad };
  view = { ...home };

  // Each inset: fit that state's own bounding box into a reserved rectangle of the CONUS view.
  for (const [id, cfg] of Object.entries(INSETS)) {
    const own = ownBox[id];
    if (!own || !isFinite(own[0])) continue;
    const tw = home.w * cfg.boxW, th = home.h * cfg.boxH;
    const k = Math.min(tw / (own[2] - own[0]), th / (own[3] - own[1]));
    const tx = home.x + home.w * cfg.at[0] - own[0] * k;
    const ty = home.y + home.h * cfg.at[1] - own[1] * k;
    const g = el('g', { class: 'inset', 'data-state': id, transform: `translate(${tx} ${ty}) scale(${k})` });
    g.dataset.k = k;
    insetGroups[id] = g;
    gInsets.append(g);
    // The state's own outline and label move into the group so they travel with it.
    if (statePaths[id]) g.append(statePaths[id]);
    const frame = el('rect', {
      class: 'insetframe', x: own[0], y: own[1],
      width: own[2] - own[0], height: own[3] - own[1],
    });
    frame.dataset.k = k;
    g.insertBefore(frame, g.firstChild);
    const cap = el('text', { class: 'icap', x: 0, y: 0, 'font-size': 10 });
    cap.textContent = id;
    cap.dataset.x = own[0];
    cap.dataset.y = own[1];
    cap.dataset.k = k;
    g.append(cap);
    insetCaptions.push(cap);
  }

  // Biggest chain first, so it ends up at the BOTTOM. SVG paints in document order, and the
  // archive's natural order put MINISO's 430 dots last: they covered all 11 CHAGEE stores
  // completely, because both are mall chains and sit in the same malls. A chain with a tenth
  // of the footprint has to win the overlap or it reads as absent.
  const size = {};
  for (const s of data.stores) size[s.chain] = (size[s.chain] || 0) + 1;
  const ordered = [...data.stores].sort((a, b) =>
    (size[b.chain] - size[a.chain]) || a.chain.localeCompare(b.chain));

  for (const s of ordered) {
    const ins = INSETS[s.state];
    const [x, y] = project(s.lat, s.lon, ins && ins.centre);
    const open = s.status === 'active';
    const c = el('circle', {
      cx: x.toFixed(0), cy: y.toFixed(0), r: 1,
      class: 'store' + (s.coord_src === 'geocoded' || s.coord_src === 'manual' ? ' geo' : ''), 'data-chain': s.chain,
      fill: open ? colorOf(s.chain) : 'none',
      stroke: open ? 'var(--surface)' : colorOf(s.chain),
    });
    c.addEventListener('pointerenter', e => showStoreTip(e, s));
    c.addEventListener('pointerleave', hideTip);
    const g = insetGroups[s.state];
    if (g) { c.dataset.k = g.dataset.k; g.append(c); } else { gDots.append(c); }
  }

  // Sightings: known locations of chains that are NOT counted. Squares, not dots, because they
  // are a different kind of claim and must not read as one more store in the census.
  for (const g of (data.meta.sightings || [])) {
    if (g.lat == null || g.lon == null) continue;
    // Low-confidence sightings are held out of the map and the count, waiting in the submit-info
    // queue until a human confirms them, so everything drawn here is confirmed.
    if (g.confidence === 'uncertain') continue;
    const [sx, sy] = project(g.lat, g.lon, INSETS[g.state] && INSETS[g.state].centre);
    // Every drawn sighting is a hand-verified location, so all are solid — the only distinction the
    // map makes is open vs not-yet-open, the same as the census pins.
    const q = el('rect', {
      class: 'sight',
      'data-chain': g.chain, x: sx.toFixed(0), y: sy.toFixed(0), width: 1, height: 1,
      fill: colorOf(g.chain), stroke: 'var(--surface)' });
    q.addEventListener('pointerenter', e => {
      const c = chainObj(g.chain);
      const chainName = c.name_us || c.name || g.chain;
      const loc = branchOf(chainName, g.name);
      tipAt(e,
        `<b>${chainLabel(c, { short: true })}</b>` +
        (loc && loc !== g.address ? `<div class="loc">${esc(loc)}</div>` : '') +
        (g.address ? `<div class="addr">${esc(g.address)}</div>` : '') +
        `<div class="meta">` +
        `A hand-verified location — counted in the total, but not part of the daily census: `
        + `this chain publishes no roster this project can read.`
        + (g.verified_by ? `<br>Verified: ${esc(g.verified_by)}` : '') +
        `<br>${esc(g.source || '')}</div>`);
    });
    q.addEventListener('pointerleave', hideTip);
    gDots.append(q);
  }

  offMapCheck(data);

  applyView(svg);
  drawTally(data);
  drawPanels(data);
  drawCoverage(data);
  drawProfiles(data);
  wireModes(svg);
  wireZoom(svg);
  const sa = document.getElementById('show-all'), sn = document.getElementById('show-none');
  if (sa) sa.onclick = () => setAllChains(true);
  if (sn) sn.onclick = () => setAllChains(false);
  setMode('stores');
  document.getElementById('asof').textContent =
    `Collected ${data.meta.last_collected} · ${data.meta.days_collected} day(s) of archive.`;
}

function applyView(svg) {
  svg.setAttribute('viewBox', `${view.x} ${view.y} ${view.w} ${view.h}`);
  const r = view.w / 170;
  for (const c of svg.querySelectorAll('.store')) {
    const hollow = c.getAttribute('fill') === 'none';
    // Anything living inside an inset is already scaled by that group's transform, so its own
    // size is divided back out — otherwise Alaska's dots would be a third the size of Ohio's
    // and would read as smaller stores rather than as a smaller map.
    const ik = Number(c.dataset.k) || 1;
    // An announced store reads as an absence of fill, which only works if the ring stays thin.
    c.setAttribute('r', (hollow ? r * 0.92 : r) / ik);
    c.setAttribute('stroke-width', (hollow ? r / 3.4 : r / 5) / ik);
  }
  const k = view.w / 42 / 14;          // glyphs are 14 units; scale carries them to map size
  const sr = (view.w / 170) * 1.5;
  for (const q of svg.querySelectorAll('.sight')) {
    q.setAttribute('width', sr); q.setAttribute('height', sr);
    q.setAttribute('transform', `translate(${-sr / 2} ${-sr / 2})`);
    q.setAttribute('stroke-width', sr / 6);
  }
  for (const t of stateLabels)
    t.setAttribute('transform',
      `translate(${t.dataset.x} ${t.dataset.y}) scale(${k / (Number(t.dataset.k) || 1)})`);
  for (const f of svg.querySelectorAll('.insetframe'))
    f.setAttribute('stroke-width', (view.w / 700) / (Number(f.dataset.k) || 1));
  const ck = view.w / 78 / 10;
  for (const c of insetCaptions) {
    const s2 = ck / (Number(c.dataset.k) || 1);
    c.setAttribute('transform',
      `translate(${c.dataset.x} ${c.dataset.y}) scale(${s2}) translate(2 11)`);
  }
}

/*
 * A store the map cannot show must say so. Hawaii spent a day drawn correctly and permanently
 * outside the viewport, which no test caught because nothing was wrong with the data — so the
 * page now checks its own coverage and reports anything it failed to place, the same way the
 * archive counts stores with no coordinates rather than dropping them.
 */
function offMapCheck(data) {
  const off = {};
  for (const s of data.stores) {
    if (INSETS[s.state]) continue;
    const [x, y] = project(s.lat, s.lon);
    if (x < home.x || x > home.x + home.w || y < home.y || y > home.y + home.h)
      off[s.state || '(no state)'] = (off[s.state || '(no state)'] || 0) + 1;
  }
  const n = Object.values(off).reduce((a, b) => a + b, 0);
  const box = document.getElementById('offmap');
  if (!n) { box.hidden = true; return; }
  box.hidden = false;
  box.textContent = `${n} store(s) fall outside the mapped area and are not in an inset (` +
    Object.entries(off).map(([k, v]) => `${k} ${v}`).join(', ') +
    `). They are counted in every total on this page; the map needs an inset for them.`;
}

/* ---- the state choropleth ------------------------------------------------------------- */

// Four steps, not a continuous ramp: a smooth scale would imply a precision these counts do
// not have. The thresholds are quantiles of the states that actually have stores, so the map
// keeps working as the archive grows — hard-coded breaks were already wrong once, when adding
// one chain moved the top of the range from 28 to 118.
let BREAKS = [3, 10, 30];

function computeBreaks(byState) {
  const v = Object.values(byState).map(s => s.open).filter(n => n > 0).sort((a, b) => a - b);
  if (v.length < 4) return;
  const q = f => v[Math.min(v.length - 1, Math.floor(v.length * f))];
  const raw = [q(0.4), q(0.7), q(0.9)];
  // Strictly increasing, or two steps of the ramp would mean the same thing.
  BREAKS = raw.map((n, i) => Math.max(n, (raw[i - 1] || 0) + 1));
}

const stepOf = n => n <= 0 ? -1 : n < BREAKS[0] ? 0 : n < BREAKS[1] ? 1 : n < BREAKS[2] ? 2 : 3;
const breakLabels = () => [
  BREAKS[0] > 2 ? `1\u2013${BREAKS[0] - 1}` : '1',
  BREAKS[1] - 1 > BREAKS[0] ? `${BREAKS[0]}\u2013${BREAKS[1] - 1}` : `${BREAKS[0]}`,
  BREAKS[2] - 1 > BREAKS[1] ? `${BREAKS[1]}\u2013${BREAKS[2] - 1}` : `${BREAKS[1]}`,
  `${BREAKS[2]}+`,
];

function paintStates(on) {
  const by = DATA.meta.by_state;
  for (const [id, p] of Object.entries(statePaths)) {
    const st = by[id];
    p.classList.toggle('lit', on && !!st && st.open > 0);
    p.classList.toggle('pending', on && !!st && st.open === 0 && st.coming_soon > 0);
    p.setAttribute('data-step', on && st ? stepOf(st.open) : -1);
  }
  for (const t of stateLabels) t.style.display = on ? '' : 'none';
}

// Chain visibility on the map. `hidden` holds the chains switched off; every dot AND sighting
// square carries data-chain, so one function draws the lot — which is what lets a reader isolate a
// chain, or a handful, by switching the rest off, starting from all-shown.
function applyChainVisibility() {
  const statesMode = mode === 'states';
  for (const el of document.querySelectorAll('.store, .sight'))
    el.style.display = statesMode || hidden.has(el.dataset.chain) ? 'none' : '';
}
function refreshChips() {
  for (const chip of document.querySelectorAll('.chip[data-chain]'))
    chip.setAttribute('aria-pressed', String(!hidden.has(chip.dataset.chain)));
}
function toggleChain(id) {
  hidden.has(id) ? hidden.delete(id) : hidden.add(id);
  applyChainVisibility();
  refreshChips();
}
function setAllChains(show) {         // show=true → all on; false → all off (then pick a few)
  hidden.clear();
  if (!show)
    for (const chip of document.querySelectorAll('.chip[data-chain]')) hidden.add(chip.dataset.chain);
  applyChainVisibility();
  refreshChips();
}
function showOnlyChain(id) {          // isolate one chain; others can still be clicked back on after
  for (const chip of document.querySelectorAll('.chip[data-chain]')) hidden.add(chip.dataset.chain);
  hidden.delete(id);
  applyChainVisibility();
  refreshChips();
}
// Shared wiring for every chip (collected or blocked). Clicking the CHIP shows/hides that chain on
// the map (a checkbox, in effect) — that is the primary action a legend chip should have. Two
// small trailing controls do the rest: "ⓘ" opens the chain's "Who they are" profile, and "only"
// isolates the chain (leaving the others clickable, so a reader can start from one and add more).
function wireChip(el, id) {
  el.dataset.chain = id;
  el.setAttribute('role', 'button');
  el.tabIndex = 0;
  el.setAttribute('aria-pressed', String(!hidden.has(id)));
  el.title = 'Click to show or hide this chain on the map. ' + (el.title || '');
  const prof = document.createElement('a');
  prof.className = 'prof';
  prof.href = `intro.html#${id}`;
  prof.textContent = 'ⓘ';
  prof.setAttribute('aria-label', 'About this chain (Who they are)');
  prof.title = 'Who they are — about this chain';
  prof.addEventListener('click', e => e.stopPropagation());
  const only = document.createElement('button');
  only.type = 'button';
  only.className = 'only';
  only.textContent = 'only';
  only.title = 'Show only this chain (you can click others to add them)';
  only.addEventListener('click', e => { e.stopPropagation(); showOnlyChain(id); });
  el.append(prof, only);
  const isControl = t => t.closest('.prof') || t.closest('.only');
  el.addEventListener('click', e => { if (!isControl(e.target)) toggleChain(id); });
  el.addEventListener('keydown', e => {
    if ((e.key === 'Enter' || e.key === ' ') && !isControl(e.target)) { e.preventDefault(); toggleChain(id); }
  });
  return el;
}

function setMode(m) {
  mode = m;
  document.getElementById('map').classList.toggle('statemode', m === 'states');
  for (const b of document.querySelectorAll('.modebtn'))
    b.setAttribute('aria-pressed', String(b.dataset.mode === m));
  applyChainVisibility();
  paintStates(m === 'states');
  document.getElementById('legend').hidden = m !== 'states';
  document.getElementById('tally').hidden = m === 'states';
  const ctl = document.getElementById('tallyctl');
  if (ctl) ctl.hidden = m === 'states';
  hideTip();
}

function wireModes(svg) {
  for (const b of document.querySelectorAll('.modebtn')) b.onclick = () => setMode(b.dataset.mode);
  const lg = document.getElementById('legend');
  const labels = breakLabels();
  lg.innerHTML = '<span class="lgl">Stores trading</span>' +
    labels.map((t, i) => `<span class="sw" data-step="${i}"></span><span class="lgt">${t}</span>`).join('') +
    '<span class="sw pend"></span><span class="lgt">announced only</span>' +
    `<span class="lgn">Counts include ${DATA.meta.unlocated.luckin || 0} stores with no published
     coordinates, which the Stores view cannot draw.</span>`;
}

/* ---- panels --------------------------------------------------------------------------- */

function perChain(data) {
  const per = {};
  for (const s of data.stores) (per[s.chain] ||= { open: 0, soon: 0 })[s.status === 'active' ? 'open' : 'soon']++;
  return per;
}

// The roster of chains has grown past the point where one flat row reads well, so the chips are
// grouped by what the chain actually sells. Category comes from each chain's `format`, with one
// override: MIXUE is the ice-cream-and-tea chain, filed under its defining product.
const CAT_ORDER = ['Tea', 'Coffee', 'Ice Cream', 'Restaurants', 'Bakery',
                   'Toys & Pop Culture', 'Other'];
const CAT_BY_FORMAT = {
  tea: 'Tea', coffee: 'Coffee', restaurant: 'Restaurants', hotpot: 'Restaurants',
  snack: 'Restaurants', bakery: 'Bakery', toys: 'Toys & Pop Culture', lifestyle: 'Toys & Pop Culture',
};
const CAT_OVERRIDE = { mixue: 'Ice Cream' };
function categoryOf(id, fmt) { return CAT_OVERRIDE[id] || CAT_BY_FORMAT[fmt] || 'Other'; }

function drawTally(data) {
  const box = document.getElementById('tally'), per = perChain(data);

  const collectedChip = (id, meta) => {
    const p = per[id] || { open: 0, soon: 0 };
    const un = data.meta.unlocated[id] || 0;
    // The chip carries counts only. Whether a chain's pins are published or geocoded is a
    // provenance detail, shown where it reads clearly — the "Chains collected" table note and the
    // fainter geocoded dots — not as a cryptic suffix here.
    const n = un && !p.open ? `${un} unplaced`
      : `${p.open}${un ? '+' + un + ' unplaced' : ''}${p.soon ? ' +' + p.soon + ' soon' : ''}`;
    // A span, not a button, so the chain name inside can be a real link to its profile without
    // nesting interactive elements. Clicking the name goes to "Who they are"; clicking anywhere
    // else on the chip still toggles the chain on the map.
    const b = document.createElement('span');
    b.className = 'chip' + (meta.provenance && meta.provenance !== 'collected' ? ' supplied' : '');
    if (meta.provenance && meta.provenance !== 'collected')
      b.title = `Supplied, not collected — ${meta.provenance_detail || ''}. `
        + 'These rows do not refresh; no change tomorrow means nobody looked.';
    b.innerHTML = `<span class="dot" style="background:${colorOf(id)}"></span>` +
      `<span class="chipnm">${chainLabel(meta, { short: true })}</span>` +
      `<span class="n">${n}</span>`;
    if (un && !p.open) b.title = 'No coordinates published — counted, but nothing to draw';
    if (meta.aliases && meta.aliases.length)
      b.title = `Also trades in the US as: ${meta.aliases.join(', ')}. ` + (b.title || '');
    return wireChip(b, id);
  };

  // Chains with known locations but no roster get a count of what is KNOWN, never of what is.
  // Low-confidence sightings are held out (they wait in the submit-info queue), so they are not counted.
  const sightBy = {};
  for (const g of (data.meta.sightings || [])) {
    if (g.confidence === 'uncertain') continue;
    sightBy[g.chain] = (sightBy[g.chain] || 0) + 1;
  }
  // A hand-assembled roster with a dated completeness claim gets a real count — clearly
  // marked hand-made and unmonitored, so it never reads as a collected total.
  const rosterBy = {};
  for (const r of (data.meta.manual_rosters || [])) rosterBy[r.chain] = r;

  // Chains that are HERE and cannot be drawn. A reader looking for Haidilao looks here first;
  // finding nothing, they conclude it is not in America. It is — there is simply no store-level
  // data for it, and the chip has to say that rather than not exist.
  const blockedChip = (b) => {
    const el = document.createElement('span');
    const kc = b.known_count;
    const rr = rosterBy[b.chain_id];
    const ns = sightBy[b.chain_id] || 0;
    // Every hand-verified location counts; the map makes no confirmed/unconfirmed distinction.
    const known = !!(rr || kc || ns > 0);
    el.className = 'chip off' + (known ? ' known' : ' pending');
    // This page counts the US only, so a roster complete for the whole country is simply
    // "complete"; a sub-national scope (Cotti's New York City) keeps its qualifier.
    const usWide = /^\s*(united states|u\.?s\.?a?\.?)\b/i.test((rr && rr.complete_scope) || '');
    const knownN = ns;                                        // hand-verified locations held
    const scopeShort = ((rr && rr.complete_scope) || '').split('(')[0].trim();
    const toCfm = '';
    let n;
    // If the live count of hand-verified locations EXCEEDS a dated roster, the roster is stale
    // (newer outlets found since it was filed), so show the current count rather than claiming
    // "complete" at the old number — this keeps the chip equal to the by-state hand total. Otherwise
    // a roster complete for the whole US reads simply "complete"; a sub-scope keeps its qualifier.
    if (rr && knownN > rr.count) n = `${knownN} known${toCfm}`;
    else if (rr && usWide) n = `${rr.count} — complete`;
    else if (rr) n = `${rr.count} — complete for ${esc(scopeShort || 'a defined area')}`;
    else if (kc) n = `${kc.stores} — no locations published`;
    else if (ns) n = `${knownN} known${toCfm}`;
    else n = 'not counted yet';
    el.innerHTML = `<span class="dot" style="background:${known ? colorOf(b.chain_id) : 'var(--muted)'}"></span>` +
      `<span class="chipnm">${chainLabel(b, { short: true })}</span>` +
      `<span class="n">${n}</span>`;
    // Alias line first, so hovering any chip shows every US name the chain trades under.
    const akaTitle = (b.aliases && b.aliases.length)
      ? `Also trades in the US as: ${b.aliases.join(', ')}. ` : '';
    el.title = akaTitle + (rr
      ? `Hand-assembled and operator-verified. `
        + (usWide
          ? `Complete for the US as of ${rr.complete_as_of}. `
          : `${rr.count} confirmed and complete for ${scopeShort || 'a defined area'} as of `
            + `${rr.complete_as_of}` + (knownN > rr.count ? `, plus ${knownN - rr.count} known elsewhere. ` : `. `))
        + `Not monitored: this count does not update on its own and is not part of the collected census.`
      : (b.reason || ''));
    // Blocked chains draw squares (and count-only chains draw nothing), but their chip is still a
    // filter toggle like the collected ones, so a reader can isolate, say, only HEYTEA's sightings.
    return wireChip(el, b.chain_id);
  };

  // Bucket every chip by category — collected (drawable) first, then blocked, within each group.
  const buckets = {};
  for (const [id, meta] of Object.entries(data.meta.chains)) {
    const cat = categoryOf(id, meta.format);
    (buckets[cat] = buckets[cat] || []).push(collectedChip(id, meta));
  }
  for (const b of data.meta.blocked || []) {
    const cat = categoryOf(b.chain_id, b.format);
    (buckets[cat] = buckets[cat] || []).push(blockedChip(b));
  }

  // Render in a fixed order, each group under its own full-width label.
  const cats = [...CAT_ORDER.filter(c => buckets[c]),
                ...Object.keys(buckets).filter(c => !CAT_ORDER.includes(c))];
  for (const cat of cats) {
    const label = document.createElement('div');
    label.className = 'tallygroup';
    label.textContent = cat;
    box.append(label);
    for (const chip of buckets[cat]) box.append(chip);
  }
}

function drawPanels(data) {
  const per = perChain(data);

  const tb = document.querySelector('#chains tbody');
  for (const [id, meta] of Object.entries(data.meta.chains)) {
    const p = per[id] || { open: 0, soon: 0 }, un = data.meta.unlocated[id] || 0;
    const tr = document.createElement('tr');
    const supplied = meta.provenance && meta.provenance !== 'collected';
    const gc2 = (data.meta.geocoded || {})[id] || 0;
    const co = ((data.meta.companies || {}).companies || {})[id] || {};
    tr.innerHTML = `<td>${chainLabel(meta)}` +
      (co.us_since ? `<br><span class="csince">US since ${esc(co.us_since)}</span>` : '') +
      (gc2 ? `<br><span class="zh">${gc2} placed by geocoding its addresses,` +
             ` not by published coordinates</span>` : '') +
      (supplied ? `<br><span class="zh warnzh">supplied ${esc(meta.provenance_detail || '')}` +
                  ` — not fetched daily</span>` : '') +
      (un ? `<br><span class="zh">${un} unplaced — locator publishes no coordinates</span>` : '') +
      `</td><td class="n">${p.open + un}${p.soon ? ' +' + p.soon : ''}</td>`;
    tb.append(tr);
  }

  const sb = document.querySelector('#states tbody');
  // The census counts (by_state) and the hand-confirmed locations (by_state_hand) are held apart
  // in the data — the collector's total is never polluted by hand entries — but for the reader one
  // confirmed outlet is one confirmed outlet, so the table shows a single combined total (census +
  // hand), with only the announced "+N" kept separate. This is also how a jurisdiction whose only
  // outlet is a sighting (Washington DC) earns a row at all.
  const hand = data.meta.by_state_hand || {};
  const nameOf = c => (data.meta.chains[c] && data.meta.chains[c].name)
    || ((data.meta.blocked || []).find(b => b.chain_id === c) || {}).name || c;
  const allSt = new Set([...Object.keys(data.meta.by_state), ...Object.keys(hand)]);
  const rows = [...allSt].map(st => {
    const v = data.meta.by_state[st] || { open: 0, coming_soon: 0, chains: {} };
    const h = hand[st] || { count: 0, chains: {} };
    return { st, v, h, total: (v.open || 0) + (h.count || 0) };
  }).sort((a, b) => (b.total - a.total) || ((b.v.coming_soon || 0) - (a.v.coming_soon || 0)) || a.st.localeCompare(b.st));
  const SHOWN = 12;
  for (const { st, v, h } of rows) {
    const tot = {};                                   // per-chain: census open+soon plus hand
    for (const [c, n] of Object.entries(v.chains || {})) tot[c] = (tot[c] || 0) + (n.open || 0) + (n.coming_soon || 0);
    for (const [c, n] of Object.entries(h.chains || {})) tot[c] = (tot[c] || 0) + n;
    const who = Object.entries(tot).sort((a, b) => b[1] - a[1])
      .map(([c, n]) => `${esc(nameOf(c))} ${n}`).join(', ');
    const confirmed = (v.open || 0) + (h.count || 0), soon = v.coming_soon || 0;
    const cnt = `${confirmed}${soon ? ` +${soon}` : ''}`;
    const tr = document.createElement('tr');
    tr.innerHTML = `<td>${esc(st)}<br><span class="statewho">${who}</span></td>` +
      `<td class="n">${cnt}</td>`;
    sb.append(tr);
  }
  // Every state stays in the DOM — the count in the "more" row has to be the real remainder,
  // not a number that drifts from the table it summarises.
  const extra = [...sb.rows].slice(SHOWN);
  if (extra.length) {
    for (const tr of extra) tr.hidden = true;
    const more = document.createElement('tr');
    more.className = 'more';
    more.innerHTML = `<td colspan="2"><button class="morebtn" type="button">` +
      `Show ${extra.length} more state${extra.length > 1 ? 's' : ''}</button></td>`;
    sb.append(more);
    more.querySelector('button').onclick = e => {
      const open = extra[0].hidden;
      for (const tr of extra) tr.hidden = !open;
      e.target.textContent = open ? 'Show fewer' :
        `Show ${extra.length} more state${extra.length > 1 ? 's' : ''}`;
    };
  }
  if (data.meta.no_state)
    document.getElementById('nostate').textContent =
      `${data.meta.no_state} store(s) have an address this project could not read a state from.`;

  document.getElementById('pipeline').textContent = data.meta.counts.coming_soon
    ? `${data.meta.counts.coming_soon} store(s) are listed by their chain as announced but not yet ` +
      `trading. They show as hollow rings on the map and after a + in the state counts. We don't ` +
      `count one as an opening until its listing changes to trading.`
    : 'No chain currently publishes a pipeline of announced stores.';


  // The headline number for a US reader is not 468 stores, it is how much of the category those
  // stores represent. Four chains rendered prominently and eight buried two screens down reads
  // as "this is the category" — so the ratio goes at the top, where the claim is made.
  const nCounted = Object.keys(data.meta.chains).length;
  const nBlocked = (data.meta.blocked || []).length;
  const supplied = Object.values(data.meta.chains)
    .filter(c => c.provenance && c.provenance !== 'collected');
  const names = (data.meta.blocked || []).slice(0, 3).map(b => b.name);
  const cover = document.getElementById('coverline');
  if (cover) {
    // Coverage in 50-state terms, computed from the data so it stays true as the map fills in.
    const STATES = new Set(('AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN ' +
      'MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY').split(' '));
    // The 50 states plus DC as its own jurisdiction, counting outlets of any kind (collected or
    // hand-confirmed) so DC — whose only outlet is a sighting — is included.
    const covJur = new Set([...Object.keys(data.meta.by_state || {}),
      ...Object.keys(data.meta.by_state_hand || {})]);
    const total = STATES.size + 1;                      // 50 states + DC
    const covered = [...STATES].filter(s => covJur.has(s)).length + (covJur.has('DC') ? 1 : 0);
    const missing = total - covered;
    const stateLine = missing <= 0
      ? 'Every one of the 50 states and D.C. now has at least one outlet of a Chinese chain.'
      : `All but <b>${missing}</b> of the 50 states and D.C. now have at least one outlet of a Chinese chain.`;
    cover.innerHTML =
      `We pair AI with careful manual research and confirmation to build the most complete picture ` +
      `we can of outlets of Chinese chains in the US and where they are &mdash; monitoring both openings ` +
      `and closings. Today we follow <b>${nCounted + nBlocked}</b> chains across tea, coffee, hot ` +
      `pot, restaurants, bakeries, toys and more, and the number is growing. ${stateLine}`;
  }

  const totalEl = document.getElementById('ustotal');
  const T = data.meta.totals;
  if (totalEl && T) {
    // One canonical total, shared with the homepage (meta.totals.outlets). The by-state table
    // below carries the breakdown, so the headline stays a single plain number.
    totalEl.innerHTML = `<b>${T.outlets.toLocaleString()}</b> outlets of Chinese chains open in the US` +
      (T.unmapped > 0 ? ` <span class="dim">${T.unmapped} not yet mapped.</span>` : '');
  }
}

function drawCoverage(data) {
  // The scorecard: what we hold against what the trade press says exists. Collected chains are
  // complete; sighted chains show a rough ratio against a dated trade-press estimate — a yardstick,
  // never a measurement. The point is to be honest about the gap, in numbers, on the page itself.
  const c = data.meta.coverage;
  if (!c || !c.rows) return;
  const t = c.totals;
  // An estimate is a rumour with a date, so holding more than it is possible; coverage is capped at
  // 100% rather than claiming we found more than exists.
  const covPct = t.sighted_estimated
    ? Math.min(100, Math.round(100 * t.sighted_estimable_confirmed / t.sighted_estimated)) : null;
  document.getElementById('coverintro').innerHTML =
    `<b>${t.collected}</b> chains are counted in full from their own locators ` +
    `(<b>${t.collected_stores}</b> stores). The other <b>${t.sighted}</b> publish no roster we can ` +
    `read. For the <b>${t.sighted_estimable}</b> of them with a published trade-press estimate, we hold ` +
    `<b>${t.sighted_estimable_confirmed}</b> of about <b>${t.sighted_estimated}</b> locations` +
    (covPct != null ? ` — roughly <b>${covPct}%</b> of what is thought to exist` : '') + `.` +
    (t.sighted_no_benchmark
      ? ` The remaining <b>${t.sighted_no_benchmark}</b> have no published estimate to measure against yet ` +
        `(a further <b>${t.sighted_confirmed - t.sighted_estimable_confirmed}</b> confirmed locations).`
      : '');

  const tb = document.querySelector('#coverage tbody');
  tb.innerHTML = '';
  // Cap at 100%: when we hold at least as many as the estimate, say so plainly rather than
  // printing an impossible figure like 200%.
  const pct = r => r.ratio == null ? '' : (r.ratio >= 1 ? 'exceeds est.' : `${Math.round(r.ratio * 100)}%`);
  const bar = r => {
    if (r.kind === 'collected') return '<span class="cbar full"></span>';
    const w = r.ratio == null ? 0 : Math.min(100, Math.round(r.ratio * 100));
    return `<span class="cbar" style="--w:${w}%" data-status="${esc(r.status)}"></span>`;
  };
  for (const r of c.rows) {
    const meta = (data.meta.chains && data.meta.chains[r.chain]) ||
                 (data.meta.blocked || []).find(b => b.chain_id === r.chain) || { name: r.name };
    const held = `<b>${r.held}</b>`;   // all hand-verified locations count; no confirmed/unconfirmed split
    const est = r.kind === 'collected' ? '<span class="dim">— complete —</span>'
      : esc(String(r.estimate_text || r.estimate || 'no est.'));
    const title = r.kind === 'collected'
      ? 'Counted in full from the chain\'s own locator.'
      : `Estimate: ${esc(String(r.estimate_text || r.estimate || 'none'))}` +
        (r.source ? ` — ${esc(r.source)}` : '') + (r.as_of ? ` (${esc(r.as_of)})` : '') +
        (r.confidence ? `, ${esc(r.confidence)} confidence` : '') +
        (r.note ? `. ${esc(r.note)}` : '');
    const tr = document.createElement('tr');
    tr.className = 'cov ' + (r.kind === 'collected' ? 'covfull' : 'cov-' + r.status);
    tr.title = title;
    tr.innerHTML = `<td>${chainLabel(meta, { short: true })}</td>` +
      `<td class="num">${held}</td><td class="num dim">${est}</td>` +
      `<td class="covcell">${bar(r)}<span class="cpct">${pct(r) || (r.kind==='collected'?'✓':'')}</span></td>`;
    tb.append(tr);
  }
  document.getElementById('covernote').textContent =
    `Estimates are drawn from the trade press, dated, and never added to any count on this ` +
    `page. They only show how big the gap is, as of ${c.as_of}. Hover a row for its source. ` +
    `"Complete" means the chain's own locator is the count, not that its growth has stopped.`;
}

function drawProfiles(data) {
  const box = document.getElementById('profiles');
  const collected = new Set(Object.keys(data.meta.chains));
  const order = [...Object.keys(data.meta.chains), ...data.meta.blocked.map(b => b.chain_id)];
  for (const id of order) {
    const p = data.meta.profiles[id];
    if (!p) continue;
    const d = document.createElement('details');
    d.innerHTML =
      `<summary><span class="dot" style="background:${collected.has(id) ? colorOf(id) : 'var(--muted)'}"></span>` +
      `<span class="nm">${esc(p.name)}</span><span class="zh">${esc(p.name_zh)}</span>` +
      `</summary>` +
      `<p>${esc(p.blurb)}</p>` +
      `<p class="why"><b>Why it is in this archive.</b> ${esc(p.why_watch)}</p>` +
      `<dl>` +
      `<dt>Founded</dt><dd>${esc(p.founded)}, ${esc(p.hq)}</dd>` +
      `<dt>Founder</dt><dd>${esc(p.founder)}</dd>` +
      `<dt>Listing</dt><dd>${esc(p.listing)}</dd>` +
      `<dt>Worldwide</dt><dd>${esc(p.global_stores)}</dd>` +
      `<dt>US since</dt><dd>${esc(p.us_entry)}</dd>` +
      `</dl>`;
    box.append(d);
  }
  document.getElementById('profnote').textContent =
    `These are fixed background profiles, written by hand from published sources as of ` +
    `${data.meta.profiles_as_of} — descriptions, not live figures, so they can go out of date. ` +
    `The live US counts are on the map above.`;
}

/* ---- interaction ---------------------------------------------------------------------- */

function wireZoom(svg) {
  let drag = null;
  svg.addEventListener('pointerdown', e => {
    drag = { x: e.clientX, y: e.clientY, vx: view.x, vy: view.y };
    svg.classList.add('drag'); svg.setPointerCapture(e.pointerId);
  });
  svg.addEventListener('pointermove', e => {
    if (!drag) return;
    const sc = view.w / svg.clientWidth;
    view.x = drag.vx - (e.clientX - drag.x) * sc;
    view.y = drag.vy - (e.clientY - drag.y) * sc;
    applyView(svg);
  });
  const end = () => { drag = null; svg.classList.remove('drag'); };
  svg.addEventListener('pointerup', end);
  svg.addEventListener('pointercancel', end);
  svg.addEventListener('wheel', e => {
    e.preventDefault();
    const r = svg.getBoundingClientRect();
    const fx = (e.clientX - r.left) / r.width, fy = (e.clientY - r.top) / r.height;
    const k = e.deltaY > 0 ? 1.18 : 1 / 1.18;
    const nw = Math.min(home.w * 1.6, Math.max(home.w / 400, view.w * k));
    const nh = nw * (view.h / view.w);
    view.x += (view.w - nw) * fx; view.y += (view.h - nh) * fy;
    view.w = nw; view.h = nh;
    applyView(svg);
  }, { passive: false });
  svg.addEventListener('dblclick', () => { view = { ...home }; applyView(svg); });
}

function tipAt(e, html) {
  const t = document.getElementById('tip');
  t.innerHTML = html;
  t.hidden = false;
  t.style.left = Math.min(e.clientX + 14, innerWidth - 300) + 'px';
  t.style.top = (e.clientY + 14) + 'px';
}

function showStoreTip(e, s) {
  const when = s.status === 'active'
    ? (s.opened_on ? `open, first seen trading ${s.opened_on}` : `open, in the locator since ${s.first_seen}`)
    : `announced ${s.first_seen}, not yet trading`;
  const c = chainObj(s.chain);
  const chainName = c.name_us || c.name || s.chain;
  // A POP MART "ROBO SHOP" is Pop Mart's unmanned vending kiosk, not a chain of its own, so the
  // lead stays POP MART with "Robo Shop" in parentheses. Every other store leads with its chain
  // too, then the shopfront/mall name, so the tooltip always says who is trading there.
  const isRobo = /robo\s*shop/i.test(s.name || '');
  let head, locLine;
  if (isRobo) {
    head = `${esc(chainName)} <span class="zh">(Robo Shop)</span>`;
    locLine = (s.name || '').replace(/^\s*robo\s*shop\s*/i, '').trim();
  } else {
    head = chainLabel(c, { short: true });
    locLine = branchOf(chainName, s.name);
  }
  tipAt(e,
    `<b>${head}</b>` +
    (locLine ? `<div class="loc">${esc(locLine)}</div>` : '') +
    (s.addr ? `<div class="addr">${esc(s.addr)}</div>` : '') +
    `<div class="meta">${when}</div>`);
}

function showStateTip(e, id, name) {
  const st = DATA.meta.by_state[id];
  if (!st) { tipAt(e, `<b>${esc(name)}</b><div class="meta">no stores in this archive</div>`); return; }
  const who = Object.entries(st.chains).sort((a, b) => b[1].open - a[1].open).map(([c, n]) =>
    `${esc(DATA.meta.chains[c]?.name || c)} ${n.open}${n.coming_soon ? ' +' + n.coming_soon : ''}`).join('<br>');
  tipAt(e, `<b>${esc(name)}</b>${st.open} trading${st.coming_soon ? `, ${st.coming_soon} announced` : ''}` +
    `<div class="meta">${who}</div>`);
}

const hideTip = () => { document.getElementById('tip').hidden = true; };

main();

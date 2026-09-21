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
                luckin: 'var(--luckin)', miniso: 'var(--miniso)' };
const colorOf = c => COLOR[c] || 'var(--other)';
const SVG = 'http://www.w3.org/2000/svg';
const el = (n, a = {}) => { const e = document.createElementNS(SVG, n); for (const k in a) e.setAttribute(k, a[k]); return e; };
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
      cx: x.toFixed(0), cy: y.toFixed(0), r: 1, class: 'store', 'data-chain': s.chain,
      fill: open ? colorOf(s.chain) : 'none',
      stroke: open ? 'var(--surface)' : colorOf(s.chain),
    });
    c.addEventListener('pointerenter', e => showStoreTip(e, s));
    c.addEventListener('pointerleave', hideTip);
    const g = insetGroups[s.state];
    if (g) { c.dataset.k = g.dataset.k; g.append(c); } else { gDots.append(c); }
  }

  offMapCheck(data);

  applyView(svg);
  drawTally(data);
  drawPanels(data);
  drawProfiles(data);
  wireModes(svg);
  wireZoom(svg);
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

function setMode(m) {
  mode = m;
  document.getElementById('map').classList.toggle('statemode', m === 'states');
  for (const b of document.querySelectorAll('.modebtn'))
    b.setAttribute('aria-pressed', String(b.dataset.mode === m));
  for (const c of document.querySelectorAll('.store'))
    c.style.display = m === 'states' || hidden.has(c.dataset.chain) ? 'none' : '';
  paintStates(m === 'states');
  document.getElementById('legend').hidden = m !== 'states';
  document.getElementById('tally').hidden = m === 'states';
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

function drawTally(data) {
  const box = document.getElementById('tally'), per = perChain(data);
  for (const [id, meta] of Object.entries(data.meta.chains)) {
    const p = per[id] || { open: 0, soon: 0 };
    const un = data.meta.unlocated[id] || 0;
    // A chain whose locator publishes no coordinates would otherwise read as a zero here,
    // which is the one number it definitely is not.
    const n = un && !p.open ? `${un} unplaced`
      : `${p.open}${un ? '+' + un + ' unplaced' : ''}${p.soon ? ' +' + p.soon + ' soon' : ''}`;
    const b = document.createElement('button');
    b.className = 'chip' + (meta.provenance && meta.provenance !== 'collected' ? ' supplied' : '');
    b.setAttribute('aria-pressed', 'true');
    if (meta.provenance && meta.provenance !== 'collected')
      b.title = `Supplied, not collected — ${meta.provenance_detail || ''}. `
        + 'These rows do not refresh; no change tomorrow means nobody looked.';
    b.innerHTML = `<span class="dot" style="background:${colorOf(id)}"></span>${esc(meta.name)}<span class="n">${n}</span>`;
    if (un && !p.open) b.title = 'No coordinates published — counted, but nothing to draw';
    b.onclick = () => {
      hidden.has(id) ? hidden.delete(id) : hidden.add(id);
      b.setAttribute('aria-pressed', String(!hidden.has(id)));
      for (const c of document.querySelectorAll(`.store[data-chain="${id}"]`))
        c.style.display = hidden.has(id) || mode === 'states' ? 'none' : '';
    };
    box.append(b);
  }

  // Then the chains that are HERE and cannot be drawn. A reader looking for Haidilao looks at
  // this row first; finding nothing, they conclude it is not in America. It is — there is simply
  // no store-level data for it, and the chip has to say that rather than not exist.
  for (const b of data.meta.blocked || []) {
    const el = document.createElement('span');
    el.className = 'chip off';
    const kc = b.known_count;
    const n = kc ? `${kc.stores} — no locations published` : 'not counted yet';
    el.innerHTML = `<span class="dot"></span>${esc(b.name)}<span class="n">${esc(n)}</span>`;
    el.title = b.reason || '';
    box.append(el);
  }
}

function drawPanels(data) {
  const per = perChain(data);

  const tb = document.querySelector('#chains tbody');
  for (const [id, meta] of Object.entries(data.meta.chains)) {
    const p = per[id] || { open: 0, soon: 0 }, un = data.meta.unlocated[id] || 0;
    const tr = document.createElement('tr');
    const supplied = meta.provenance && meta.provenance !== 'collected';
    tr.innerHTML = `<td>${esc(meta.name)}<span class="zh">${esc(meta.name_zh || '')}</span>` +
      (supplied ? `<br><span class="zh warnzh">supplied ${esc(meta.provenance_detail || '')}` +
                  ` — not fetched daily</span>` : '') +
      (un ? `<br><span class="zh">${un} unplaced — locator publishes no coordinates</span>` : '') +
      `</td><td class="n">${p.open + un}${p.soon ? ' +' + p.soon : ''}</td>`;
    tb.append(tr);
  }

  const sb = document.querySelector('#states tbody');
  const rows = Object.entries(data.meta.by_state).sort((a, b) =>
    (b[1].open - a[1].open) || (b[1].coming_soon - a[1].coming_soon));
  const SHOWN = 12;
  for (const [st, v] of rows) {
    const who = Object.entries(v.chains)
      .sort((a, b) => b[1].open - a[1].open)
      .map(([c, n]) => `${esc(data.meta.chains[c]?.name || c)} ${n.open + n.coming_soon}`).join(', ');
    const tr = document.createElement('tr');
    tr.innerHTML = `<td>${esc(st)}<br><span class="zh">${who}</span></td>` +
      `<td class="n">${v.open}${v.coming_soon ? ' +' + v.coming_soon : ''}</td>`;
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
      `trading. They are drawn as hollow rings, shown after a + in state counts, and are never ` +
      `counted as openings — the opening is the day the listing flips.`
    : 'No chain currently publishes a pipeline of announced stores.';

  // Markets the collector covers that this map deliberately does not draw. Saying so is the
  // point: a collected market that no page mentions is a collected market nobody knows about.
  const om = data.meta.other_markets || {};
  const lines = [];
  for (const [country, rows] of Object.entries(om))
    for (const r of rows)
      lines.push(`${esc(r.name)} — ${r.stores} stores in ${esc(country)}` +
        (r.located ? '' : ', none with published coordinates'));
  if (lines.length) {
    document.getElementById('othersec').hidden = false;
    document.getElementById('other').innerHTML = lines.join('<br>') +
      `<br><br>This is a map of the United States, so they are counted but not drawn. They appear
       in the <a href="register.html">international register</a>.`;
  }

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
    cover.innerHTML =
      `Counting <b>${nCounted}</b> of the <b>${nCounted + nBlocked}</b> mainland-China-origin ` +
      `chains known to trade in the United States` +
      (supplied.length
        ? ` — though ${supplied.map(c => esc(c.name)).join(', ')} ` +
          `${supplied.length === 1 ? 'was' : 'were'} <b>supplied by hand, not collected</b>, and ` +
          `${supplied.length === 1 ? 'does' : 'do'} not refresh`
        : '') +
      `. The other ${nBlocked}${names.length ? ' — including ' + names.join(', ') + ' —' : ''} ` +
      `are here and not yet countable; <a href="#notcounted">each is listed with the reason</a>.`;
  }

  const ul = document.getElementById('blocked');
  for (const b of data.meta.blocked) {
    const li = document.createElement('li');
    li.innerHTML = `<b>${esc(b.name)}</b> — ${esc(b.reason)}`;
    ul.append(li);
  }
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
      `${collected.has(id) ? '' : '<span class="tagoff">not collected</span>'}</summary>` +
      `<p>${esc(p.blurb)}</p>` +
      `<p class="why"><b>Why it is in this archive.</b> ${esc(p.why_watch)}</p>` +
      `<dl>` +
      `<dt>Founded</dt><dd>${esc(p.founded)}, ${esc(p.hq)}</dd>` +
      `<dt>Founder</dt><dd>${esc(p.founder)}</dd>` +
      `<dt>Listing</dt><dd>${esc(p.listing)}</dd>` +
      `<dt>Worldwide</dt><dd>${esc(p.global_stores)}</dd>` +
      `<dt>US debut</dt><dd>${esc(p.us_entry)}</dd>` +
      `</dl>`;
    box.append(d);
  }
  document.getElementById('profnote').textContent =
    `Background from published sources as of ${data.meta.profiles_as_of}, typed in by hand — not ` +
    `collected, and it goes stale. The US counts above are the collector's own and are not repeated here.`;
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
    ? (s.opened_on ? `open — first seen trading ${s.opened_on}` : `open — in the locator since ${s.first_seen}`)
    : `announced ${s.first_seen} — not yet trading`;
  tipAt(e, `<b>${esc(s.name || '(unnamed)')}</b>${esc(s.addr || '')}<div class="meta">${when}</div>`);
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

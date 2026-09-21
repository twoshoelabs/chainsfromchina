/*
 * The map draws the same projection the collector keys cells with — Lambert azimuthal
 * equal-area about 45N 100W (geo.py). Keeping them identical means a dot on this map and a
 * cell in the database are the same piece of ground, not two approximations of it.
 *
 * No map library and no tile server: sixty dots on fifty state outlines do not need either,
 * and a page that fetches nothing third-party keeps working when a CDN or an API key does not.
 */
const R = 6370997.0, LAT0 = 45 * Math.PI / 180, LON0 = -100 * Math.PI / 180;

function project(lat, lon) {
  const phi = lat * Math.PI / 180, lam = lon * Math.PI / 180;
  const cosc = Math.sin(LAT0) * Math.sin(phi) + Math.cos(LAT0) * Math.cos(phi) * Math.cos(lam - LON0);
  const k = Math.sqrt(Math.max(0, 2 / (1 + cosc)));
  return [
    R * k * Math.cos(phi) * Math.sin(lam - LON0),
    -(R * k * (Math.cos(LAT0) * Math.sin(phi) - Math.sin(LAT0) * Math.cos(phi) * Math.cos(lam - LON0))),
  ];
}

const COLOR = { mixue: 'var(--mixue)', chagee: 'var(--chagee)', luckin: 'var(--luckin)' };
const colorOf = c => COLOR[c] || 'var(--other)';
const SVG = 'http://www.w3.org/2000/svg';
const el = (n, a = {}) => { const e = document.createElementNS(SVG, n); for (const k in a) e.setAttribute(k, a[k]); return e; };

let view = { x: 0, y: 0, w: 1, h: 1 };     // current viewBox
let home = null;                            // the fitted CONUS view, for reset
const hidden = new Set();

async function main() {
  const [states, data] = await Promise.all([
    fetch('us-states.geojson').then(r => r.json()),
    fetch('data/stores.json').then(r => r.json()),
  ]);

  const svg = document.getElementById('map');
  const gLand = el('g'), gDots = el('g');
  svg.append(gLand, gDots);

  // Outlines. CONUS sets the view; Alaska and Hawaii are drawn but left outside it, because
  // fitting to them would shrink the lower 48 to a smear for the sake of two empty states.
  const CONUS = f => f.id !== 'AK' && f.id !== 'HI';
  let bb = [Infinity, Infinity, -Infinity, -Infinity];
  for (const f of states.features) {
    const polys = f.geometry.type === 'Polygon' ? [f.geometry.coordinates] : f.geometry.coordinates;
    let d = '';
    for (const poly of polys) for (const ring of poly) {
      d += ring.map(([lon, lat], i) => {
        const [x, y] = project(lat, lon);
        if (CONUS(f)) {
          bb[0] = Math.min(bb[0], x); bb[1] = Math.min(bb[1], y);
          bb[2] = Math.max(bb[2], x); bb[3] = Math.max(bb[3], y);
        }
        return (i ? 'L' : 'M') + x.toFixed(0) + ' ' + y.toFixed(0);
      }).join('') + 'Z';
    }
    const p = el('path', { d, class: 'state' });
    const t = el('title');
    t.textContent = f.properties.name;
    p.append(t);
    gLand.append(p);
  }

  const pad = (bb[2] - bb[0]) * 0.03;
  home = { x: bb[0] - pad, y: bb[1] - pad, w: bb[2] - bb[0] + 2 * pad, h: bb[3] - bb[1] + 2 * pad };
  view = { ...home };
  applyView(svg);

  // Dots, largest-first so a dense corner still shows its smaller neighbours on top.
  for (const s of data.stores) {
    const [x, y] = project(s.lat, s.lon);
    const open = s.status === 'active';
    const c = el('circle', {
      cx: x.toFixed(0), cy: y.toFixed(0), r: 7000, class: 'store', 'data-chain': s.chain,
      fill: open ? colorOf(s.chain) : 'none',
      stroke: open ? 'var(--surface)' : colorOf(s.chain),
      'fill-opacity': 1,
    });
    c.addEventListener('pointerenter', e => showTip(e, s));
    c.addEventListener('pointerleave', hideTip);
    gDots.append(c);
  }

  applyView(svg);      // again, now that the dots exist: applyView sizes them to the view
  drawTally(data);
  drawPanels(data);
  wireZoom(svg, gDots);
  document.getElementById('asof').textContent =
    `Collected ${data.meta.last_collected} · ${data.meta.days_collected} day(s) of archive.`;
}

function applyView(svg) {
  svg.setAttribute('viewBox', `${view.x} ${view.y} ${view.w} ${view.h}`);
  // Dots keep a constant screen size as the view scales.
  const r = view.w / 170;
  for (const c of svg.querySelectorAll('.store')) {
    const hollow = c.getAttribute('fill') === 'none';
    // An announced store is drawn as an outline, not as a thinner dot: the eye should read
    // "not there yet" as an absence of fill, which only works if the ring stays thin.
    c.setAttribute('r', hollow ? r * 0.92 : r);
    c.setAttribute('stroke-width', hollow ? r / 3.4 : r / 5);
  }
}

function drawTally(data) {
  const box = document.getElementById('tally');
  const per = {};
  for (const s of data.stores) {
    (per[s.chain] ||= { open: 0, soon: 0 })[s.status === 'active' ? 'open' : 'soon']++;
  }
  for (const [id, meta] of Object.entries(data.meta.chains)) {
    const p = per[id] || { open: 0, soon: 0 };
    const b = document.createElement('button');
    b.className = 'chip';
    b.setAttribute('aria-pressed', 'true');
    // A chain whose locator publishes no coordinates would otherwise read as a zero here,
    // which is the one number it definitely is not. Say "unplaced" on the chip itself.
    const un = data.meta.unlocated[id] || 0;
    const n = un && !p.open ? `${un} unplaced`
      : `${p.open}${un ? '+' + un + ' unplaced' : ''}${p.soon ? ' +' + p.soon + ' soon' : ''}`;
    b.innerHTML = `<span class="dot" style="background:${colorOf(id)}"></span>${meta.name}` +
      `<span class="n">${n}</span>`;
    if (un && !p.open) b.title = 'No coordinates published — counted, but nothing to draw';
    b.onclick = () => {
      hidden.has(id) ? hidden.delete(id) : hidden.add(id);
      b.setAttribute('aria-pressed', String(!hidden.has(id)));
      for (const c of document.querySelectorAll(`.store[data-chain="${id}"]`))
        c.style.display = hidden.has(id) ? 'none' : '';
    };
    box.append(b);
  }
}

function drawPanels(data) {
  const per = {};
  for (const s of data.stores) (per[s.chain] ||= { open: 0, soon: 0 })[s.status === 'active' ? 'open' : 'soon']++;

  const tb = document.querySelector('#chains tbody');
  for (const [id, meta] of Object.entries(data.meta.chains)) {
    const p = per[id] || { open: 0, soon: 0 };
    const un = data.meta.unlocated[id] || 0;
    const tr = document.createElement('tr');
    tr.innerHTML = `<td>${meta.name}<span class="zh">${meta.name_zh || ''}</span>` +
      (un ? `<br><span class="zh">${un} unplaced — locator publishes no coordinates</span>` : '') +
      `</td><td class="n">${p.open + un}${p.soon ? ' +' + p.soon : ''}</td>`;
    tb.append(tr);
  }

  const soon = data.meta.counts.coming_soon;
  document.getElementById('pipeline').textContent = soon
    ? `${soon} store(s) are listed by their chain as announced but not yet trading. They are drawn ` +
      `as hollow rings and are never counted as openings — the opening is the day the listing flips.`
    : 'No chain currently publishes a pipeline of announced stores.';

  const ul = document.getElementById('blocked');
  for (const b of data.meta.blocked) {
    const li = document.createElement('li');
    li.innerHTML = `<b>${b.name}</b> — ${b.reason}`;
    ul.append(li);
  }
}

function wireZoom(svg, gDots) {
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

function showTip(e, s) {
  const t = document.getElementById('tip');
  const when = s.status === 'active'
    ? (s.opened_on ? `open — first seen trading ${s.opened_on}` : `open — in the locator since ${s.first_seen}`)
    : `announced ${s.first_seen} — not yet trading`;
  t.innerHTML = `<b>${s.name || '(unnamed)'}</b>${s.addr || ''}<div class="meta">${when}</div>`;
  t.hidden = false;
  t.style.left = Math.min(e.clientX + 14, innerWidth - 300) + 'px';
  t.style.top = (e.clientY + 14) + 'px';
}
const hideTip = () => { document.getElementById('tip').hidden = true; };

main();

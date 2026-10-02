// Vector map (MapLibre GL JS). Our pins come from data/stores.geojson; the basemap is a separate,
// swappable style. 'use strict' kept off so top-level await is not needed.

// ---- Basemap config -------------------------------------------------------------------------
// TWO ways to supply a clean, keyless basemap — set BASEMAP.pmtiles to switch:
//   • pmtiles: ''  (default) -> CARTO Positron, a hosted keyless light style. Renders immediately.
//   • pmtiles: 'https://<your-r2-bucket>/us.pmtiles'  -> the project's self-hosted Protomaps basemap
//        (no tile server, no API fees). Build/upload it with scripts/build_basemap.sh, which prints
//        exactly this URL. When set, the Protomaps light theme loads from a US PMTiles file on R2.
// (To use MapTiler instead, set BASEMAP.style to a MapTiler style URL with your key.)
const BASEMAP = {
  pmtiles: 'https://pub-7dec9caf8d7e4d4e9f4ab6dea7bb8005.r2.dev/us.pmtiles',  // self-hosted US Protomaps (R2)
  style: 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json',     // fallback if pmtiles is cleared
};
let GLYPH_FONT = 'Open Sans Regular';   // a font the active style's glyph server provides
let LOGO_PRESENT = {};                   // chain -> whether a logo badge (vs monogram) was used
let MAP_REF = null, FULL_FC = null;      // the map + full FeatureCollection, for the chain filter
let HIDDEN = new Set();                  // chains currently hidden from the map
let ALL_CHAINS = [], GROUP_CHAINS = {};  // all chain ids; chains grouped by sector

// Sector → color. Keep in sync with the register's sectors.
const SECTOR = {
  tea: '#5E8C3A', coffee: '#7A4E2D', food_drink: '#B5462E', bakery: '#C08A2B',
  grocery_convenience: '#2F8C8C', snacks: '#D0702A', apparel: '#6B4FA0', beauty: '#C4577A',
  lifestyle_variety: '#2F5FA8', electronics: '#3C7A9A', home: '#7A8C3A',
};
const OTHER = '#6b7280';
const SECTOR_LABEL = {
  tea: 'Tea', coffee: 'Coffee', food_drink: 'Food & drink', bakery: 'Bakery',
  grocery_convenience: 'Grocery', snacks: 'Snacks', apparel: 'Apparel', beauty: 'Beauty',
  lifestyle_variety: 'Lifestyle / toys', electronics: 'Electronics', home: 'Home',
};
const sectorColor = ['match', ['get', 'sector'],
  ...Object.entries(SECTOR).flatMap(([k, v]) => [k, v]), OTHER];

// Short monograms, used for the pin badge ONLY when a brand has no logo file in icons/.
const MONOGRAM = {
  mixue: 'MX', chagee: 'CG', luckin: 'LK', miniso: 'MO', popmart: 'PM', haidilao: 'HD',
  heytea: 'HT', cotti: 'CT', taier: 'TE', chabaidao: 'CB', nayuki: 'NX', juewei: 'JW',
  yangguofu: 'YG', fishwithyou: 'FW', yangs: 'YS', zhangliang: 'ZL', chahalo: 'CH',
  xiaolongkan: 'XL', liuyishou: 'LY', aunteajenny: 'AJ', mollytea: 'MT', lelecha: 'LL',
  toptoy: 'TT', toys52: '52', dezhuang: 'DZ', shudaxia: 'SX', xibei: 'XB', grandmashome: 'GH',
  xijiade: 'XJ', feidachu: 'FC', dalongyi: 'DL', shuyi: 'SY', anta: 'AN', urbanrevivo: 'UR',
  jnby: 'JN', meilleurmoment: 'MM', meizhoudongpo: 'MD', nonggengji: 'NG', malubianbian: 'ML',
  moge: 'MG', moreyogurt: 'MG', baospastry: 'BP',
};

// Brands with a logo file in icons/ (first-party, nominative use). Any brand not listed falls back
// to a sector-colored monogram badge. Keep in sync with the files in map/icons/.
const LOGO_CHAINS = new Set([
  'anta', 'aunteajenny', 'baospastry', 'chabaidao', 'chagee', 'chahalo', 'cotti', 'dalongyi', 'dezhuang',
  'feidachu', 'fishwithyou', 'grandmashome', 'haidilao', 'heytea', 'jnby', 'juewei', 'lelecha', 'liuyishou',
  'luckin', 'malubianbian', 'meilleurmoment', 'meizhoudongpo', 'miniso', 'mixue', 'moge', 'mollytea', 'moreyogurt',
  'nayuki', 'nonggengji', 'popmart', 'shudaxia', 'shuyi', 'taier', 'toptoy', 'toys52', 'urbanrevivo', 'xiaolongkan',
  'xibei', 'xijiade', 'yangguofu', 'yangs', 'zhangliang',
]);

const DPR = 2;            // render badges at 2× for crisp icons on retina
const BADGE = 64;         // logical badge diameter (px); device size = BADGE * DPR

// Load a brand's logo PNG (icons/<chain>.png). Resolves to an Image, or null if there is none.
function loadLogo(chain) {
  return new Promise((resolve) => {
    const img = new Image();
    img.crossOrigin = 'anonymous';
    img.onload = () => resolve(img);
    img.onerror = () => resolve(null);
    img.src = 'icons/' + chain + '.png';
  });
}

// Compose a circular pin badge. With a logo: a white chip + sector-colored ring + the logo inside.
// Without one: a solid sector-colored disc with the brand's monogram. `soft` (announced / coming
// soon, not yet open) draws a dashed ring and a hollow, faded treatment, matching the legend.
function makeBadge(logo, color, mono, soft) {
  const S = BADGE * DPR;
  const cv = document.createElement('canvas');
  cv.width = S; cv.height = S;
  const ctx = cv.getContext('2d');
  const cx = S / 2, cy = S / 2;
  const ring = Math.round(4 * DPR);
  const r = cx - ring / 2 - DPR;          // ring centerline radius

  // soft drop in opacity for the whole mark
  ctx.globalAlpha = soft ? 0.82 : 1;

  if (logo) {
    // white chip
    ctx.beginPath(); ctx.arc(cx, cy, r, 0, 2 * Math.PI);
    ctx.fillStyle = soft ? 'rgba(255,255,255,0.92)' : '#ffffff'; ctx.fill();
    // logo, contained within the inner circle's bounding square
    ctx.save();
    ctx.beginPath(); ctx.arc(cx, cy, r - ring * 0.6, 0, 2 * Math.PI); ctx.clip();
    const inset = (r - ring) * 1.42;       // side of the square that fits inside the inner circle
    const scale = Math.min(inset / logo.width, inset / logo.height);
    const w = logo.width * scale, h = logo.height * scale;
    ctx.drawImage(logo, cx - w / 2, cy - h / 2, w, h);
    ctx.restore();
  } else {
    // monogram: solid disc (open) or white disc (soft)
    ctx.beginPath(); ctx.arc(cx, cy, r, 0, 2 * Math.PI);
    ctx.fillStyle = soft ? '#ffffff' : color; ctx.fill();
    ctx.fillStyle = soft ? color : '#ffffff';
    ctx.font = `600 ${Math.round(S * 0.34)}px "Libre Franklin", system-ui, sans-serif`;
    ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    ctx.fillText(mono || '•', cx, cy + S * 0.02);
  }

  // ring
  ctx.beginPath(); ctx.arc(cx, cy, r, 0, 2 * Math.PI);
  ctx.lineWidth = ring; ctx.strokeStyle = color;
  if (soft) ctx.setLineDash([ring * 1.4, ring * 1.1]);
  ctx.stroke();
  ctx.setLineDash([]);

  return { width: S, height: S, data: ctx.getImageData(0, 0, S, S).data };
}

// Resolve the basemap style: a hosted URL (CARTO/MapTiler) or a built Protomaps style over PMTiles.
async function resolveStyle() {
  if (!BASEMAP.pmtiles) return BASEMAP.style;      // a style URL string
  // Protomaps path: register the pmtiles:// protocol and build the light theme over our US file.
  const [pm, bm] = await Promise.all([
    import('https://cdn.jsdelivr.net/npm/pmtiles@4/+esm'),
    import('https://cdn.jsdelivr.net/npm/@protomaps/basemaps@5/+esm'),
  ]);
  maplibregl.addProtocol('pmtiles', new pm.Protocol().tile);
  GLYPH_FONT = 'Noto Sans Regular';                // Protomaps' glyph server provides this
  return {
    version: 8,
    glyphs: 'https://protomaps.github.io/basemaps-assets/fonts/{fontstack}/{range}.pbf',
    sprite: 'https://protomaps.github.io/basemaps-assets/sprites/v4/light',
    sources: {
      protomaps: { type: 'vector', url: 'pmtiles://' + BASEMAP.pmtiles,
                   attribution: '© OpenStreetMap contributors' },
    },
    layers: bm.layers('protomaps', bm.namedFlavor('light'), { lang: 'en' }),
  };
}

async function init() {
  // Fetch our data once; we reuse it for the source, the per-brand icons, and the count line.
  const fc = await fetch('data/stores.geojson').then((r) => r.json());
  const chainSector = {};
  for (const f of fc.features) chainSector[f.properties.chain] = f.properties.sector;

  const style = await resolveStyle();
  const map = new maplibregl.Map({
    container: 'map', style, center: [-96, 38], zoom: 3.3,
    attributionControl: { compact: true },
  });
  map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right');
  map.addControl(new maplibregl.ScaleControl({ unit: 'imperial' }));
  map.on('error', (e) => console.warn('map error', e && e.error && e.error.message));
  MAP_REF = map; FULL_FC = fc;            // for the chain-filter panel

  // Load each brand's logo (icons/<chain>.png; null when absent) before the layer is built so
  // every icon-image reference resolves to either a logo badge or a monogram badge.
  const chains = Object.keys(chainSector);
  const logos = await Promise.all(chains.map((c) => (LOGO_CHAINS.has(c) ? loadLogo(c) : Promise.resolve(null))));
  chains.forEach((c, i) => { LOGO_PRESENT[c] = !!logos[i]; });

  map.on('load', () => {
    // Register a per-brand badge (solid "open" + dashed "soft" variant). addImage requires the
    // style to be loaded, so it happens here, not before.
    chains.forEach((c, i) => {
      const color = SECTOR[chainSector[c]] || OTHER;
      const mono = MONOGRAM[c] || c.slice(0, 2).toUpperCase();
      if (!map.hasImage('ic-' + c)) map.addImage('ic-' + c, makeBadge(logos[i], color, mono, false), { pixelRatio: DPR });
      if (!map.hasImage('ic-' + c + '-s')) map.addImage('ic-' + c + '-s', makeBadge(logos[i], color, mono, true), { pixelRatio: DPR });
    });

    // Turn OFF the basemap's own points of interest, so only our pins read as data.
    for (const l of map.getStyle().layers) {
      if (/poi|place.?of.?interest/i.test(l.id)) {
        try { map.setLayoutProperty(l.id, 'visibility', 'none'); } catch (e) { /* non-symbol layer */ }
      }
    }

    map.addSource('stores', {
      type: 'geojson', data: fc,
      cluster: true, clusterRadius: 48, clusterMaxZoom: 11,
    });

    map.addLayer({
      id: 'clusters', type: 'circle', source: 'stores', filter: ['has', 'point_count'],
      paint: {
        'circle-color': ['step', ['get', 'point_count'], '#f0a0a0', 10, '#e06666', 50, '#cc3333', 200, '#a11'],
        'circle-opacity': 0.9,
        'circle-radius': ['step', ['get', 'point_count'], 15, 10, 19, 50, 24, 200, 30],
        'circle-stroke-width': 2, 'circle-stroke-color': '#fff',
      },
    });
    map.addLayer({
      id: 'cluster-count', type: 'symbol', source: 'stores', filter: ['has', 'point_count'],
      layout: {
        'text-field': ['get', 'point_count_abbreviated'],
        'text-font': [GLYPH_FONT], 'text-size': 12, 'text-allow-overlap': true,
      },
      paint: { 'text-color': '#fff' },
    });

    // Individual outlets: a per-brand logo/monogram badge. The dashed "soft" variant marks an outlet
    // that isn't open yet (announced / coming soon); every confirmed location, census or sighting, is
    // a solid pin.
    const soft = ['==', ['get', 'status'], 'coming_soon'];
    map.addLayer({
      id: 'pts', type: 'symbol', source: 'stores', filter: ['!', ['has', 'point_count']],
      layout: {
        'icon-image': ['case', soft,
          ['concat', 'ic-', ['get', 'chain'], '-s'],
          ['concat', 'ic-', ['get', 'chain']]],
        'icon-size': ['interpolate', ['linear'], ['zoom'], 3, 0.34, 8, 0.5, 12, 0.72],
        'icon-allow-overlap': true, 'icon-ignore-placement': true,
      },
    });

    map.on('click', 'clusters', (e) => {
      const f = map.queryRenderedFeatures(e.point, { layers: ['clusters'] })[0];
      map.getSource('stores').getClusterExpansionZoom(f.properties.cluster_id).then((z) => {
        map.easeTo({ center: f.geometry.coordinates, zoom: z });
      });
    });
    map.on('click', 'pts', (e) => {
      const p = e.features[0].properties;
      const sec = SECTOR_LABEL[p.sector] || 'Other';
      const state = p.status === 'coming_soon' ? 'Announced / coming soon' : 'Open';
      const logo = LOGO_PRESENT[p.chain]
        ? `<img src="icons/${esc(p.chain)}.png" alt="" style="width:34px;height:34px;object-fit:contain;border-radius:50%;background:#fff;border:1px solid #eee;flex:0 0 auto">`
        : '';
      const addr = p.address ? `${esc(p.address)}<br>` : '';
      const cityState = `${esc(p.city || '')}${p.city && p.state ? ', ' : ''}${esc(p.state || '')}`;
      new maplibregl.Popup({ closeButton: false })
        .setLngLat(e.features[0].geometry.coordinates)
        .setHTML(`<div style="display:flex;gap:.55rem;align-items:center">${logo}<div>` +
                 `<b>${esc(p.name)}</b><br>${addr}${cityState}` +
                 `<br><span style="color:#666">${sec} · ${state}</span></div></div>`)
        .addTo(map);
    });
    for (const id of ['clusters', 'pts']) {
      map.on('mouseenter', id, () => { map.getCanvas().style.cursor = 'pointer'; });
      map.on('mouseleave', id, () => { map.getCanvas().style.cursor = ''; });
    }

    buildLegend();
    buildTally(fc);
  });
}

// ---- Chain filter panel ---------------------------------------------------------------------
// The homepage lists every brand on the map, grouped by sector, and lets a reader show/hide a brand,
// a whole group, or all of them — and jump to each one's "Who they are" profile. Toggling re-sets the
// GeoJSON source so clusters recount from only the visible brands.
function applyFilter() {
  if (MAP_REF && FULL_FC) {
    const src = MAP_REF.getSource('stores');
    if (src) src.setData({ type: 'FeatureCollection',
      features: FULL_FC.features.filter((f) => !HIDDEN.has(f.properties.chain)) });
  }
  for (const chip of document.querySelectorAll('.chip[data-chain]'))
    chip.setAttribute('aria-pressed', String(!HIDDEN.has(chip.dataset.chain)));
  for (const h of document.querySelectorAll('button.tallygroup[data-sector]')) {
    const on = (GROUP_CHAINS[h.dataset.sector] || []).filter((c) => !HIDDEN.has(c)).length;
    const total = (GROUP_CHAINS[h.dataset.sector] || []).length;
    h.setAttribute('aria-pressed', String(on > 0));
    h.classList.toggle('partial', on > 0 && on < total);
    h.style.opacity = on ? '' : '.5';
  }
}
function toggleChain(id) { HIDDEN.has(id) ? HIDDEN.delete(id) : HIDDEN.add(id); applyFilter(); }
function setAllChains(show) { HIDDEN = show ? new Set() : new Set(ALL_CHAINS); applyFilter(); }
function toggleGroup(sector) {
  const chains = GROUP_CHAINS[sector] || [];
  const anyOn = chains.some((c) => !HIDDEN.has(c));
  for (const c of chains) { if (anyOn) HIDDEN.add(c); else HIDDEN.delete(c); }
  applyFilter();
}
function onlyChain(id) { HIDDEN = new Set(ALL_CHAINS); HIDDEN.delete(id); applyFilter(); }

// Free-text search over brand names, for the hero search box. Empty query restores every brand.
// It also shows/hides the matching chips so the panel and the map stay in step.
window.filterChains = function (q) {
  q = (q || '').toLowerCase().trim();
  const names = window.CHAIN_META || {};
  HIDDEN = !q ? new Set() : new Set(ALL_CHAINS.filter((c) => {
    const nm = (names[c] && names[c].name ? names[c].name : c).toLowerCase();
    return !(nm.includes(q) || c.includes(q));
  }));
  applyFilter();
  for (const chip of document.querySelectorAll('.chip[data-chain]')) {
    const nm = (chip.querySelector('.chipnm')?.textContent || '').toLowerCase();
    chip.style.display = (!q || nm.includes(q) || chip.dataset.chain.includes(q)) ? '' : 'none';
  }
};

function buildTally(fc) {
  const box = document.getElementById('tally');
  if (!box) return;
  const meta = {};
  for (const f of fc.features) {
    const p = f.properties;
    const m = meta[p.chain] || (meta[p.chain] = { name: p.name, sector: p.sector, n: 0 });
    m.n++;
    if (p.status === 'open') m.name = p.name;   // prefer an open outlet's display name
  }
  ALL_CHAINS = Object.keys(meta);
  window.CHAIN_META = meta;                // let the hero search map chain id -> display name
  GROUP_CHAINS = {};
  for (const id of ALL_CHAINS) (GROUP_CHAINS[meta[id].sector] || (GROUP_CHAINS[meta[id].sector] = [])).push(id);
  const order = Object.keys(SECTOR);
  const sectors = [...order.filter((s) => GROUP_CHAINS[s]),
                   ...Object.keys(GROUP_CHAINS).filter((s) => !order.includes(s))];
  box.innerHTML = '';
  for (const s of sectors) {
    const head = document.createElement('button');
    head.type = 'button'; head.className = 'tallygroup'; head.dataset.sector = s;
    head.textContent = SECTOR_LABEL[s] || 'Other';
    head.title = 'Show or hide this whole group';
    head.addEventListener('click', () => toggleGroup(s));
    box.append(head);
    for (const id of GROUP_CHAINS[s].sort((a, b) => meta[b].n - meta[a].n)) {
      const m = meta[id];
      const chip = document.createElement('span');
      chip.className = 'chip'; chip.dataset.chain = id;
      chip.setAttribute('role', 'button'); chip.tabIndex = 0;
      chip.title = 'Click to show or hide this chain on the map.';
      chip.innerHTML = `<span class="chiplogo" style="border-color:${SECTOR[s] || OTHER}">` +
        `<img src="icons/${esc(id)}.png" alt="" loading="lazy"></span>` +
        `<span class="chipnm">${esc(m.name)}</span><span class="n">${m.n}</span>`;
      const prof = document.createElement('a');
      prof.className = 'prof'; prof.href = 'intro.html#' + id; prof.textContent = 'ⓘ';
      prof.title = 'Who they are — about this chain';
      prof.setAttribute('aria-label', 'About this chain (Who they are)');
      prof.addEventListener('click', (e) => e.stopPropagation());
      const only = document.createElement('button');
      only.type = 'button'; only.className = 'only'; only.textContent = 'only';
      only.title = 'Show only this chain (click others to add them back)';
      only.addEventListener('click', (e) => { e.stopPropagation(); onlyChain(id); });
      chip.append(prof, only);
      const isCtl = (t) => t.closest('.prof') || t.closest('.only');
      chip.addEventListener('click', (e) => { if (!isCtl(e.target)) toggleChain(id); });
      chip.addEventListener('keydown', (e) => {
        if ((e.key === 'Enter' || e.key === ' ') && !isCtl(e.target)) { e.preventDefault(); toggleChain(id); }
      });
      box.append(chip);
    }
  }
  const sa = document.getElementById('show-all'), sn = document.getElementById('show-none');
  if (sa) sa.onclick = () => setAllChains(true);
  if (sn) sn.onclick = () => setAllChains(false);
  applyFilter();
}

init().catch((e) => {
  console.error('map init failed', e);
  const el = document.getElementById('method');
  if (el) el.textContent = 'The map could not load its basemap. ' + (el.textContent || '');
});

function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"]/g, (c) =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
}

function buildLegend() {
  const el = document.getElementById('legend');
  const sectors = Object.keys(SECTOR).map((k) =>
    `<span class="k"><span class="dot" style="border-color:${SECTOR[k]};background:#fff"></span>${SECTOR_LABEL[k]}</span>`).join('');
  el.innerHTML = '<span class="k" style="font-weight:600">Pin ring = sector:</span>' + sectors +
    `<span class="k"><span class="dot hollow" style="border-color:#888;border-style:dashed"></span>announced / coming soon</span>`;
}

fetch('data/stores.geojson').then((r) => r.json()).then((fc) => {
  const open = fc.features.filter((f) => f.properties.status === 'open').length;
  const soon = fc.features.filter((f) => f.properties.status === 'coming_soon').length;
  const sight = fc.features.filter((f) => f.properties.kind === 'sighting' && f.properties.status !== 'coming_soon').length;
  // One grand total, with its additive parts spelled out — the open count and the hand-verified
  // sightings are DISJOINT sets (a sighting is a chain the daily census doesn't cover), so they sum.
  const located = open + sight;
  const ut = document.getElementById('ustotal');
  if (ut) ut.innerHTML = `<b>${located.toLocaleString()}</b> outlets of Chinese chains located in the US` +
    `<span class="dim">— ${open.toLocaleString()} open outlets counted daily from the chains’ own ` +
    `lists, plus ${sight} hand-verified sightings. ${soon} more announced / coming soon.</span>`;
  const asof = document.getElementById('asof');
  if (asof && fc.meta && fc.meta.collected) asof.textContent = `Collected ${fc.meta.collected}.`;
}).catch(() => {});

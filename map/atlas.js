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
let CO_TENANCY = [];                     // named co-tenancy clusters, for search + place panel
let SHOW_ANNOUNCED = true;               // the map toolbar's "show announced" status toggle
let FRANCHISE_ONLY = false;              // "Franchise" filter: show only chains open to a US franchisee
let FRANCHISERS = new Set();             // chains with franchise_available_us === 1 (from feature .fr)

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
function roundRect(ctx, x, y, w, h, rad) {
  ctx.moveTo(x + rad, y);
  ctx.arcTo(x + w, y, x + w, y + h, rad);
  ctx.arcTo(x + w, y + h, x, y + h, rad);
  ctx.arcTo(x, y + h, x, y, rad);
  ctx.arcTo(x, y, x + w, y, rad);
  ctx.closePath();
}

// A circular badge for census outlets, or a rounded SQUARE one for hand-verified sightings, so the
// legend's two shapes read apart. `soft` = announced / coming soon (dashed, faded).
function makeBadge(logo, color, mono, soft, square) {
  const S = BADGE * DPR;
  const cv = document.createElement('canvas');
  cv.width = S; cv.height = S;
  const ctx = cv.getContext('2d');
  const cx = S / 2, cy = S / 2;
  const ring = Math.round(4 * DPR);
  const r = cx - ring / 2 - DPR;          // ring centerline "radius" (half-side for the square)
  const corner = r * 0.42;
  const trace = (rr) => {
    ctx.beginPath();
    if (square) roundRect(ctx, cx - rr, cy - rr, rr * 2, rr * 2, Math.min(corner, rr * 0.6));
    else ctx.arc(cx, cy, rr, 0, 2 * Math.PI);
  };

  ctx.globalAlpha = soft ? 0.82 : 1;

  if (logo) {
    trace(r);
    ctx.fillStyle = soft ? 'rgba(255,255,255,0.92)' : '#ffffff'; ctx.fill();
    ctx.save();
    trace(r - ring * 0.6); ctx.clip();
    const inset = (r - ring) * 1.42;
    const scale = Math.min(inset / logo.width, inset / logo.height);
    const w = logo.width * scale, h = logo.height * scale;
    ctx.drawImage(logo, cx - w / 2, cy - h / 2, w, h);
    ctx.restore();
  } else {
    trace(r);
    ctx.fillStyle = soft ? '#ffffff' : color; ctx.fill();
    ctx.fillStyle = soft ? color : '#ffffff';
    ctx.font = `600 ${Math.round(S * 0.34)}px "Libre Franklin", system-ui, sans-serif`;
    ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    ctx.fillText(mono || '•', cx, cy + S * 0.02);
  }

  trace(r);
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

// US extents: the opening view frames the lower 48, and panning/zooming is clamped to the US and
// its territories so a stray scroll never drifts into the empty grey world beyond the tiles.
const US_BOUNDS = [[-125, 24.2], [-66.5, 49.6]];
const MAX_BOUNDS = [[-179.5, 13], [-63, 72]];

// A one-tap "frame the United States" button, sitting under the zoom control.
class FitUSControl {
  onAdd(map) {
    this._map = map;
    const d = document.createElement('div');
    d.className = 'maplibregl-ctrl maplibregl-ctrl-group';
    const b = document.createElement('button');
    b.type = 'button'; b.title = 'Fit the United States';
    b.setAttribute('aria-label', 'Fit the United States');
    b.style.cssText = 'font:700 11px/29px "Libre Franklin",system-ui,sans-serif';
    b.textContent = 'US';
    b.onclick = () => map.fitBounds(US_BOUNDS, { padding: 40 });
    d.appendChild(b); this._c = d; return d;
  }
  onRemove() { this._c.remove(); this._map = undefined; }
}

async function init() {
  // Loading state: the basemap and the badge icons take a moment, so the map and the brand list get
  // a skeleton instead of sitting blank and grey.
  const mapEl = document.getElementById('map');
  let loadingEl = null;
  if (mapEl) {
    mapEl.style.position = 'relative';
    loadingEl = document.createElement('div');
    loadingEl.className = 'map-loading';
    loadingEl.textContent = 'Loading the map…';
    mapEl.appendChild(loadingEl);
  }
  const tallyEl = document.getElementById('tally');
  if (tallyEl) tallyEl.innerHTML = '<div class="tally-skel">' + '<div class="skelrow"></div>'.repeat(7) + '</div>';

  // Fetch our data once; we reuse it for the source, the per-brand icons, and the count line.
  const fc = await fetch('data/stores.geojson').then((r) => r.json());
  if (loadingEl) {
    const n = (fc.meta && fc.meta.totals && fc.meta.totals.mapped) || fc.features.length;
    loadingEl.textContent = `Loading ${n.toLocaleString()} outlets…`;
  }
  const chainSector = {};
  for (const f of fc.features) chainSector[f.properties.chain] = f.properties.sector;

  const style = await resolveStyle();
  const map = new maplibregl.Map({
    container: 'map', style,
    bounds: US_BOUNDS, fitBoundsOptions: { padding: 40 },
    maxBounds: MAX_BOUNDS, minZoom: 2.6, maxZoom: 17,
    cooperativeGestures: true,          // page scroll no longer zooms the map; ⌘/Ctrl+scroll or two fingers does
    attributionControl: { compact: true },
  });
  map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right');
  map.addControl(new maplibregl.GeolocateControl({
    positionOptions: { enableHighAccuracy: false }, trackUserLocation: false }), 'top-right');
  map.addControl(new FitUSControl(), 'top-right');
  map.addControl(new maplibregl.ScaleControl({ unit: 'imperial' }));
  map.on('error', (e) => console.warn('map error', e && e.error && e.error.message));
  MAP_REF = map; FULL_FC = fc;            // for the chain-filter panel
  // Named co-tenancy clusters feed the "Shopping centers" search group and the place panel.
  fetch('data/centers.json').then((r) => r.json()).then((d) => { CO_TENANCY = d.co_tenancy || []; }).catch(() => {});

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
      if (!map.hasImage('ic-' + c)) map.addImage('ic-' + c, makeBadge(logos[i], color, mono, false, false), { pixelRatio: DPR });
      if (!map.hasImage('ic-' + c + '-s')) map.addImage('ic-' + c + '-s', makeBadge(logos[i], color, mono, true, false), { pixelRatio: DPR });
    });

    // Turn OFF the basemap's own points of interest, so only our pins read as data.
    for (const l of map.getStyle().layers) {
      if (/poi|place.?of.?interest/i.test(l.id)) {
        try { map.setLayoutProperty(l.id, 'visibility', 'none'); } catch (e) { /* non-symbol layer */ }
      }
    }

    map.addSource('stores', {
      type: 'geojson', data: fc,
      cluster: true, clusterRadius: 48, clusterMaxZoom: 14,
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

    // Individual outlets: a per-brand badge. Every outlet we draw is confirmed to exist, so they
    // share one shape (a circle) — the only variation is solid (open) vs dashed ("soft", announced
    // / coming soon). We do not distinguish how we learned of a store on the map.
    const soft = ['==', ['get', 'status'], 'coming_soon'];
    map.addLayer({
      id: 'pts', type: 'symbol', source: 'stores', filter: ['!', ['has', 'point_count']],
      layout: {
        'icon-image': ['case',
          soft, ['concat', 'ic-', ['get', 'chain'], '-s'],
          ['concat', 'ic-', ['get', 'chain']]],
        'icon-size': ['interpolate', ['linear'], ['zoom'], 3, 0.34, 8, 0.5, 12, 0.72],
        'icon-allow-overlap': true, 'icon-ignore-placement': true,
      },
    });

    map.on('click', 'clusters', (e) => {
      const f = map.queryRenderedFeatures(e.point, { layers: ['clusters'] })[0];
      const src = map.getSource('stores');
      const id = f.properties.cluster_id;
      src.getClusterExpansionZoom(id).then((z) => {
        // A cluster that only breaks apart beyond the clustering max is effectively one place —
        // the outlets share an address (Tangram's nine). Don't zoom into nothing; list them so
        // every outlet at a shared address is one click away. Otherwise jump in hard (at least a
        // couple of levels) so the US view reaches street level in two clicks, not six.
        if (z > 14) {
          src.getClusterLeaves(id, 100, 0, (err, leaves) => {
            if (!err && leaves) openPlacePanel(f.geometry.coordinates, leaves);
          });
        } else {
          map.easeTo({ center: f.geometry.coordinates, zoom: Math.max(z, map.getZoom() + 2.5) });
        }
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
    setupSearch(map);
    setupToolbar(map);
    restoreFromURL(map);
    map.once('idle', () => { if (loadingEl) { loadingEl.remove(); loadingEl = null; } });
  });
}

// ---- Place panel ----------------------------------------------------------------------------
// Opened from a same-address cluster (or a center search result): the brands at one spot, with its
// center name/owner when known, directions and a copy-link. Every outlet here is one click away.
function closePlacePanel() {
  const el = document.getElementById('place-panel');
  if (el) { el.hidden = true; el.innerHTML = ''; }
}

// The named co-tenancy center within ~250 m of a point, so a cluster can show its name and owner.
function nearestCenter(lng, lat) {
  let best = null, bestD = 0.0035;
  for (const c of CO_TENANCY) {
    if (c.lat == null || c.lon == null || !c.center || !c.center.name) continue;
    const d = Math.hypot(c.lon - lng, c.lat - lat);
    if (d < bestD) { bestD = d; best = c; }
  }
  return best;
}

function openPlacePanel(coords, leaves) {
  const el = document.getElementById('place-panel');
  if (!el || !leaves || !leaves.length) return;
  const [lng, lat] = coords;
  const center = nearestCenter(lng, lat);
  const brands = new Set(leaves.map((l) => l.properties.chain));
  const sectors = new Set(leaves.map((l) => l.properties.sector));
  const addr = (leaves.find((l) => l.properties.address) || { properties: {} }).properties.address;
  const title = center ? center.center.name : (addr || 'This location');
  const owner = center && center.center.owner_reit ? center.center.owner_reit
    : center ? [center.city, center.state].filter(Boolean).join(', ') : '';
  const dest = encodeURIComponent(lat + ',' + lng);
  const rows = leaves.slice().sort((a, b) => a.properties.name.localeCompare(b.properties.name)).map((l) => {
    const p = l.properties;
    const sq = '';                              // one shape for every outlet (no counted/hand split)
    const st = p.status === 'coming_soon' ? 'coming soon' : 'open';
    return `<a class="pp-row" href="chain.html?c=${esc(p.chain)}">` +
      `<span class="ring${sq}" style="border-color:${SECTOR[p.sector] || OTHER}"></span>` +
      `<span>${esc(p.name)}</span><span class="st">${st}</span></a>`;
  }).join('');
  // Nearby named clusters, by rough distance, so a reader can hop between centers.
  const near = CO_TENANCY
    .filter((c) => c.center && c.center.name && c.lat != null && Math.hypot(c.lon - lng, c.lat - lat) > 0.0006)
    .map((c) => ({ c, d: milesBetween(lat, lng, c.lat, c.lon) }))
    .sort((a, b) => a.d - b.d).slice(0, 3);
  const nearHtml = near.length
    ? '<div class="pp-list" style="flex:0 0 auto;border-top:1px solid var(--rule)"><div class="lbl">Nearby clusters</div>' +
      near.map((n) => `<a class="pp-row" href="#" onclick="cfcGoCenter('${esc(n.c.key)}');return false;">` +
        `<span>${esc(n.c.center.name)}</span><span class="st">${n.d < 10 ? n.d.toFixed(1) : Math.round(n.d)} mi</span></a>`).join('') +
      '</div>'
    : '';
  el.dataset.lng = lng; el.dataset.lat = lat;
  el.innerHTML =
    '<div class="pp-head"><button class="pp-x" aria-label="Close place panel" onclick="closePlacePanel()">×</button>' +
    `<h3>${esc(title)}</h3>` + (owner ? `<div class="pp-owner">${esc(owner)}</div>` : '') + '</div>' +
    '<div class="pp-stats">' +
      `<div class="s"><b>${brands.size}</b><span>brand${brands.size > 1 ? 's' : ''}</span></div>` +
      `<div class="s"><b>${leaves.length}</b><span>outlets</span></div>` +
      `<div class="s"><b>${sectors.size}</b><span>sector${sectors.size > 1 ? 's' : ''}</span></div></div>` +
    '<div class="pp-btns">' +
      `<a href="https://www.google.com/maps/dir/?api=1&destination=${dest}" target="_blank" rel="noopener">Directions</a>` +
      '<button type="button" onclick="cfcCopyPlace(this)">Copy link</button>' +
      '<button type="button" class="pro" title="Follow this place — Pro, in development">Follow</button></div>' +
    `<div class="pp-list"><div class="lbl">Chinese brands here</div>${rows}</div>` + nearHtml;
  el.hidden = false;
}

function milesBetween(lat1, lng1, lat2, lng2) {
  const dy = (lat2 - lat1) * 69;
  const dx = (lng2 - lng1) * 69 * Math.cos(lat1 * Math.PI / 180);
  return Math.sqrt(dx * dx + dy * dy);
}

function cfcGoCenter(key) {
  const c = CO_TENANCY.find((x) => x.key === key);
  if (!c || !MAP_REF) return;
  MAP_REF.flyTo({ center: [c.lon, c.lat], zoom: 15 });
  openCenterPanel(c);
}

function cfcCopyPlace(btn) {
  const el = document.getElementById('place-panel');
  if (!el) return;
  const u = location.origin + location.pathname + '#c=' + (+el.dataset.lng).toFixed(4) +
    ',' + (+el.dataset.lat).toFixed(4) + '&z=15';
  if (navigator.clipboard) navigator.clipboard.writeText(u).catch(() => {});
  const o = btn.textContent; btn.textContent = 'Copied'; setTimeout(() => { btn.textContent = o; }, 1200);
}

// ---- Search: grouped suggestions (Places / Shopping centers / Chains) ------------------------
function buildSearchIndex() {
  const meta = window.CHAIN_META || {};
  const chains = Object.keys(meta).map((id) => ({ type: 'chain', id, name: meta[id].name, sector: meta[id].sector }));
  const cityMap = {};
  for (const f of FULL_FC.features) {
    const p = f.properties; if (!p.city || !p.state) continue;
    const k = p.city + ', ' + p.state;
    const c = cityMap[k] || (cityMap[k] = { name: p.city, state: p.state, n: 0, x: 0, y: 0 });
    c.n++; c.x += f.geometry.coordinates[0]; c.y += f.geometry.coordinates[1];
  }
  const places = Object.values(cityMap).map((c) => ({ type: 'place', name: c.name, state: c.state, n: c.n, lng: c.x / c.n, lat: c.y / c.n }));
  const centers = CO_TENANCY.filter((c) => c.center && c.center.name && c.lat != null)
    .map((c) => ({ type: 'center', name: c.center.name, city: c.city, state: c.state, lng: c.lon, lat: c.lat, cluster: c }));
  return { chains, places, centers };
}

function fitChain(id) {
  const pts = FULL_FC.features.filter((f) => f.properties.chain === id &&
    (SHOW_ANNOUNCED || f.properties.status !== 'coming_soon'));
  if (!pts.length || !MAP_REF) return;
  let minx = 180, miny = 90, maxx = -180, maxy = -90;
  for (const f of pts) { const [x, y] = f.geometry.coordinates; minx = Math.min(minx, x); maxx = Math.max(maxx, x); miny = Math.min(miny, y); maxy = Math.max(maxy, y); }
  if (minx === maxx && miny === maxy) MAP_REF.flyTo({ center: [minx, miny], zoom: 13 });
  else MAP_REF.fitBounds([[minx, miny], [maxx, maxy]], { padding: 70, maxZoom: 13 });
}

function openCenterPanel(cluster) {
  const lng = cluster.lon, lat = cluster.lat;
  const leaves = FULL_FC.features.filter((f) => {
    const [x, y] = f.geometry.coordinates; return Math.hypot(x - lng, y - lat) < 0.004;
  });
  if (leaves.length) openPlacePanel([lng, lat], leaves);
}

function setupSearch(map) {
  const box = document.getElementById('hero-search');
  const panel = document.getElementById('search-suggest');
  if (!box || !panel) return;
  let opts = [], sel = -1;

  const close = () => { panel.hidden = true; box.setAttribute('aria-expanded', 'false'); sel = -1; };
  const matchIn = (arr, q) => arr.filter((o) => o.name.toLowerCase().includes(q))
    .sort((a, b) => a.name.toLowerCase().indexOf(q) - b.name.toLowerCase().indexOf(q));

  function render(raw) {
    const q = raw.trim().toLowerCase();
    if (!q) { close(); return; }
    const idx = buildSearchIndex();
    const places = matchIn(idx.places, q).slice(0, 5);
    const centers = matchIn(idx.centers, q).slice(0, 5);
    const chains = matchIn(idx.chains, q).slice(0, 6);
    opts = [];
    let html = '';
    const grp = (label, arr, make) => {
      if (!arr.length) return;
      html += `<div class="grp">${label}</div>`;
      for (const o of arr) { const i = opts.length; opts.push(o); html += `<div class="opt" role="option" data-i="${i}">${make(o)}</div>`; }
    };
    if (!chains.length && (places.length || centers.length)) {
      html += `<div class="none">No chain names match <b>${esc(raw.trim())}</b> — try a place or center:</div>`;
    }
    grp('Places', places, (o) => `<span class="ic">◉</span><span class="nm">${esc(o.name)}, ${esc(o.state)}</span><span class="meta">${o.n} outlet${o.n > 1 ? 's' : ''}</span>`);
    grp('Shopping centers', centers, (o) => `<span class="ic">▣</span><span class="nm">${esc(o.name)}</span><span class="meta">${esc([o.city, o.state].filter(Boolean).join(', '))}</span>`);
    grp('Chains', chains, (o) => `<span class="ring" style="border-color:${SECTOR[o.sector] || OTHER}"></span><span class="nm">${esc(o.name)}</span><span class="meta">${esc(SECTOR_LABEL[o.sector] || '')}</span>`);
    if (!opts.length) html = `<div class="none">No matches for <b>${esc(raw.trim())}</b>.</div>`;
    panel.innerHTML = html; panel.hidden = false; box.setAttribute('aria-expanded', 'true'); sel = -1;
    panel.querySelectorAll('.opt').forEach((elt) => {
      elt.addEventListener('mousedown', (e) => { e.preventDefault(); choose(+elt.dataset.i); });
    });
  }

  function highlight() {
    panel.querySelectorAll('.opt').forEach((elt, i) => elt.setAttribute('aria-selected', String(i === sel)));
    const cur = panel.querySelector('.opt[aria-selected="true"]');
    if (cur) cur.scrollIntoView({ block: 'nearest' });
  }

  function choose(i) {
    const o = opts[i]; if (!o) return;
    close(); box.value = o.name;
    if (o.type === 'chain') { onlyChain(o.id); fitChain(o.id); }
    else if (o.type === 'place') { map.flyTo({ center: [o.lng, o.lat], zoom: 10 }); }
    else if (o.type === 'center') { map.flyTo({ center: [o.lng, o.lat], zoom: 15 }); openCenterPanel(o.cluster); }
  }

  box.addEventListener('input', () => render(box.value));
  box.addEventListener('focus', () => { if (box.value.trim()) render(box.value); });
  box.addEventListener('keydown', (e) => {
    if (e.key === 'ArrowDown') { e.preventDefault(); if (opts.length) { sel = Math.min(sel + 1, opts.length - 1); highlight(); } }
    else if (e.key === 'ArrowUp') { e.preventDefault(); if (opts.length) { sel = Math.max(sel - 1, 0); highlight(); } }
    else if (e.key === 'Enter') { if (sel >= 0) { e.preventDefault(); choose(sel); } }
    else if (e.key === 'Escape') { close(); box.blur(); }
  });
  document.addEventListener('click', (e) => { if (!panel.contains(e.target) && e.target !== box) close(); });
  document.addEventListener('keydown', (e) => {
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); box.focus(); box.select(); }
  });
}

// ---- Toolbar: status toggle + Share view ----------------------------------------------------
function shareURL(map) {
  const c = map.getCenter();
  const parts = ['c=' + c.lng.toFixed(4) + ',' + c.lat.toFixed(4), 'z=' + map.getZoom().toFixed(2)];
  const hide = [...HIDDEN]; if (hide.length) parts.push('hide=' + hide.join(','));
  if (!SHOW_ANNOUNCED) parts.push('open=1');
  return location.origin + location.pathname + '#' + parts.join('&');
}

function setupToolbar(map) {
  const share = document.getElementById('share-view');
  if (share) share.addEventListener('click', () => {
    const u = shareURL(map);
    if (navigator.clipboard) navigator.clipboard.writeText(u).catch(() => {});
    share.classList.add('copied'); const o = share.textContent; share.textContent = 'Link copied';
    setTimeout(() => { share.classList.remove('copied'); share.textContent = o; }, 1400);
  });
  const ann = document.getElementById('show-announced');
  if (ann) ann.addEventListener('change', () => { SHOW_ANNOUNCED = ann.checked; applyFilter(); });
  const fr = document.getElementById('only-franchise');
  if (fr) fr.addEventListener('click', () => {
    FRANCHISE_ONLY = !FRANCHISE_ONLY;
    fr.setAttribute('aria-pressed', String(FRANCHISE_ONLY));
    applyFilter();
  });
}

function restoreFromURL(map) {
  const h = location.hash.replace(/^#/, ''); if (!h) return;
  const p = new URLSearchParams(h);
  if (p.get('hide')) HIDDEN = new Set(p.get('hide').split(',').filter(Boolean));
  if (p.get('open') === '1') { SHOW_ANNOUNCED = false; const ann = document.getElementById('show-announced'); if (ann) ann.checked = false; }
  if (p.get('hide') || p.get('open')) applyFilter();
  const c = p.get('c'), z = p.get('z');
  if (c) { const [lng, lat] = c.split(',').map(Number); if (isFinite(lng) && isFinite(lat)) map.jumpTo({ center: [lng, lat], zoom: z ? parseFloat(z) : 11 }); }
}

// ---- Chain filter panel ---------------------------------------------------------------------
// The homepage lists every brand on the map, grouped by sector, and lets a reader show/hide a brand,
// a whole group, or all of them — and jump to each one's "Who they are" profile. Toggling re-sets the
// GeoJSON source so clusters recount from only the visible brands.
function applyFilter() {
  if (MAP_REF && FULL_FC) {
    const src = MAP_REF.getSource('stores');
    if (src) src.setData({ type: 'FeatureCollection',
      features: FULL_FC.features.filter((f) =>
        !HIDDEN.has(f.properties.chain) &&
        (SHOW_ANNOUNCED || f.properties.status !== 'coming_soon') &&
        (!FRANCHISE_ONLY || FRANCHISERS.has(f.properties.chain))) });
  }
  for (const chip of document.querySelectorAll('.chip[data-chain]')) {
    const id = chip.dataset.chain;
    chip.setAttribute('aria-pressed', String(!HIDDEN.has(id)));
    chip.style.display = (FRANCHISE_ONLY && !FRANCHISERS.has(id)) ? 'none' : '';
  }
  for (const h of document.querySelectorAll('button.tallygroup[data-sector]')) {
    const chains = GROUP_CHAINS[h.dataset.sector] || [];
    const on = chains.filter((c) => !HIDDEN.has(c)).length;
    h.setAttribute('aria-pressed', String(on > 0));
    h.classList.toggle('partial', on > 0 && on < chains.length);
    h.style.opacity = on ? '' : '.5';
    h.style.display = (FRANCHISE_ONLY && !chains.some((c) => FRANCHISERS.has(c))) ? 'none' : '';
  }
}
function toggleChain(id) { HIDDEN.has(id) ? HIDDEN.delete(id) : HIDDEN.add(id); applyFilter(); }
function setAllChains(show) {
  HIDDEN = show ? new Set() : new Set(ALL_CHAINS);
  FRANCHISE_ONLY = false;                                  // "All"/"None" also clear the franchise filter
  const fr = document.getElementById('only-franchise');
  if (fr) fr.setAttribute('aria-pressed', 'false');
  applyFilter();
}
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
    const m = meta[p.chain] || (meta[p.chain] = { name: p.name, sector: p.sector, n: 0, fr: 0, fdd: 0 });
    m.n++;
    if (p.fr === 1) m.fr = 1;                   // chain is open to a US franchisee
    if (p.fdd === 1) m.fdd = 1;                 // ...backed by a registered US FDD (stronger tier)
    if (p.status === 'open') m.name = p.name;   // prefer an open outlet's display name
  }
  ALL_CHAINS = Object.keys(meta);
  FRANCHISERS = new Set(ALL_CHAINS.filter((id) => meta[id].fr));
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
        `<span class="chipnm">` +
        (m.fr
          ? `<span class="frbox${m.fdd ? '' : ' page'}" title="${m.fdd ? 'Open to a US franchisee — registered US FDD on file' : 'Open to a US franchisee via a first-party US franchise page (FDD not confirmed)'}">${esc(m.name)}</span>`
          : esc(m.name)) +
        `</span><span class="n">${m.n}</span>`;
      const prof = document.createElement('a');
      prof.className = 'prof'; prof.href = 'chain.html?c=' + id; prof.textContent = 'ⓘ';
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
    '<span class="k"><span class="dot" style="border-color:#888;background:#fff"></span>open</span>' +
    '<span class="k"><span class="dot hollow" style="border-color:#888;border-style:dashed"></span>announced / coming soon</span>' +
    '<span class="k" style="margin-left:.4rem"><span class="frbox">name</span> franchise (US FDD)</span>' +
    '<span class="k"><span class="frbox page">name</span> franchise (first-party page)</span>';
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

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

// Sector → color. Keep in sync with the register's sectors.
const SECTOR = {
  tea: '#16a34a', coffee: '#92400e', food_drink: '#dc2626', bakery: '#d97706',
  grocery_convenience: '#0891b2', snacks: '#ea580c', apparel: '#7c3aed', beauty: '#db2777',
  lifestyle_variety: '#2563eb', electronics: '#0d9488', home: '#65a30d',
};
const OTHER = '#6b7280';
const SECTOR_LABEL = {
  tea: 'Tea', coffee: 'Coffee', food_drink: 'Food & drink', bakery: 'Bakery',
  grocery_convenience: 'Grocery', snacks: 'Snacks', apparel: 'Apparel', beauty: 'Beauty',
  lifestyle_variety: 'Lifestyle / toys', electronics: 'Electronics', home: 'Home',
};
const sectorColor = ['match', ['get', 'sector'],
  ...Object.entries(SECTOR).flatMap(([k, v]) => [k, v]), OTHER];

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
  const style = await resolveStyle();
  const map = new maplibregl.Map({
    container: 'map', style, center: [-96, 38], zoom: 3.3,
    attributionControl: { compact: true },
  });
  map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right');
  map.addControl(new maplibregl.ScaleControl({ unit: 'imperial' }));
  map.on('error', (e) => console.warn('map error', e && e.error && e.error.message));

  map.on('load', () => {
    // Turn OFF the basemap's own points of interest, so only our pins read as data.
    for (const l of map.getStyle().layers) {
      if (/poi|place.?of.?interest/i.test(l.id)) {
        try { map.setLayoutProperty(l.id, 'visibility', 'none'); } catch (e) { /* non-symbol layer */ }
      }
    }

    map.addSource('stores', {
      type: 'geojson', data: 'data/stores.geojson',
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

    map.addLayer({
      id: 'pts', type: 'circle', source: 'stores', filter: ['!', ['has', 'point_count']],
      paint: {
        'circle-radius': ['interpolate', ['linear'], ['zoom'], 3, 3.5, 8, 6, 12, 7.5],
        'circle-color': ['case', ['==', ['get', 'status'], 'open'], sectorColor, '#ffffff'],
        'circle-stroke-width': 2, 'circle-stroke-color': sectorColor, 'circle-opacity': 0.95,
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
      const state = p.status === 'open' ? 'Open'
        : p.status === 'coming_soon' ? 'Announced / coming soon' : 'Reported sighting';
      const prov = p.kind === 'sighting' ? ' · hand-verified sighting' : ' · counted from its own locator';
      new maplibregl.Popup({ closeButton: false })
        .setLngLat(e.features[0].geometry.coordinates)
        .setHTML(`<b>${esc(p.name)}</b><br>${esc(p.city || '')}${p.city ? ', ' : ''}${esc(p.state || '')}` +
                 `<br><span style="color:#666">${sec} · ${state}${prov}</span>`)
        .addTo(map);
    });
    for (const id of ['clusters', 'pts']) {
      map.on('mouseenter', id, () => { map.getCanvas().style.cursor = 'pointer'; });
      map.on('mouseleave', id, () => { map.getCanvas().style.cursor = ''; });
    }

    buildLegend();
  });
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
    `<span class="k"><span class="dot" style="border-color:${SECTOR[k]};background:${SECTOR[k]}"></span>${SECTOR_LABEL[k]}</span>`).join('');
  el.innerHTML = sectors +
    `<span class="k"><span class="dot hollow" style="border-color:#888"></span>coming soon / unconfirmed</span>`;
}

fetch('data/stores.geojson').then((r) => r.json()).then((fc) => {
  const open = fc.features.filter((f) => f.properties.status === 'open').length;
  const soon = fc.features.filter((f) => f.properties.status === 'coming_soon').length;
  const sight = fc.features.filter((f) => f.properties.kind === 'sighting' && f.properties.status !== 'coming_soon').length;
  document.getElementById('count').textContent =
    `${open.toLocaleString()} open outlets, ${sight} hand-verified sightings, ${soon} coming soon.`;
}).catch(() => {});

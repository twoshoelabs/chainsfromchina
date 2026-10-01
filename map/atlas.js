// Vector map (MapLibre GL JS). Our pins come from data/stores.geojson; the basemap is a separate,
// swappable style. 'use strict' kept off so top-level await is not needed.

// ---- Basemap config -------------------------------------------------------------------------
// Default: a keyless, clean light/grayscale vector style that renders with no account and no fees.
// SWAP OPTIONS (change BASEMAP.style):
//   • Protomaps (project's end goal — keyless, self-hostable): add the pmtiles script + a
//     @protomaps/basemaps theme in atlas.html, host a US extract as .pmtiles on R2/S3, and point a
//     'pmtiles://<url>' vector source at it. No tile server, no API fees.
//   • MapTiler: 'https://api.maptiler.com/maps/dataviz-light/style.json?key=YOUR_KEY'
const BASEMAP = {
  style: 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json',
  glyphFont: 'Open Sans Regular',   // a font the chosen style's glyph server provides
};

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
// A MapLibre 'match' expression: sector -> color, default OTHER.
const sectorColor = ['match', ['get', 'sector'],
  ...Object.entries(SECTOR).flatMap(([k, v]) => [k, v]), OTHER];

const map = new maplibregl.Map({
  container: 'map',
  style: BASEMAP.style,
  center: [-96, 38],
  zoom: 3.3,
  attributionControl: { compact: true },
});
map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right');
map.addControl(new maplibregl.ScaleControl({ unit: 'imperial' }));

map.on('load', () => {
  // Turn OFF the basemap's own points of interest, so only our pins read as data.
  for (const l of map.getStyle().layers) {
    if (/poi|place.?of.?interest/i.test(l.id)) {
      try { map.setLayoutProperty(l.id, 'visibility', 'none'); } catch (e) { /* layer may be non-symbol */ }
    }
  }

  map.addSource('stores', {
    type: 'geojson',
    data: 'data/stores.geojson',
    cluster: true,
    clusterRadius: 48,
    clusterMaxZoom: 11,
  });

  // Clusters: red bubbles sized + shaded by how many outlets they hold.
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
      'text-font': [BASEMAP.glyphFont], 'text-size': 12, 'text-allow-overlap': true,
    },
    paint: { 'text-color': '#fff' },
  });

  // Individual outlets: sector color; filled = open, hollow = coming-soon / unconfirmed sighting.
  map.addLayer({
    id: 'pts', type: 'circle', source: 'stores', filter: ['!', ['has', 'point_count']],
    paint: {
      'circle-radius': ['interpolate', ['linear'], ['zoom'], 3, 3.5, 8, 6, 12, 7.5],
      'circle-color': ['case', ['==', ['get', 'status'], 'open'], sectorColor, '#ffffff'],
      'circle-stroke-width': 2,
      'circle-stroke-color': sectorColor,
      'circle-opacity': 0.95,
    },
  });

  // Click a cluster → zoom to expand it.
  map.on('click', 'clusters', (e) => {
    const f = map.queryRenderedFeatures(e.point, { layers: ['clusters'] })[0];
    map.getSource('stores').getClusterExpansionZoom(f.properties.cluster_id).then((z) => {
      map.easeTo({ center: f.geometry.coordinates, zoom: z });
    });
  });
  // Click a pin → popup.
  map.on('click', 'pts', (e) => {
    const p = e.features[0].properties;
    const sec = SECTOR_LABEL[p.sector] || 'Other';
    const state = p.status === 'open' ? 'Open'
      : p.status === 'coming_soon' ? 'Announced / coming soon'
      : 'Reported sighting';
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

map.on('error', (e) => { console.warn('map error', e && e.error && e.error.message); });

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

// Count line from the GeoJSON itself.
fetch('data/stores.geojson').then((r) => r.json()).then((fc) => {
  const open = fc.features.filter((f) => f.properties.status === 'open').length;
  const soon = fc.features.filter((f) => f.properties.status === 'coming_soon').length;
  const sight = fc.features.filter((f) => f.properties.kind === 'sighting' && f.properties.status !== 'coming_soon').length;
  document.getElementById('count').textContent =
    `${open.toLocaleString()} open outlets, ${sight} hand-verified sightings, ${soon} coming soon.`;
}).catch(() => {});

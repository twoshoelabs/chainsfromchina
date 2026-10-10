// By-state list — a clean, sortable breakdown of where China-origin chains are open, built from the
// same data/stores.geojson the map uses (no map here; the main "Map" tab owns that). Each state lists
// its chains by outlet count as brand-logo chips, with the long tail behind an expandable "+N more".
// Counts an outlet under the state it sits in; "opening soon" (announced) is shown separately.
const ICONV = window.CFC_ICON_V || '';
const DATAV = window.CFC_DATA_V || '';   // per-deploy data cache-bust
const OTHER = '#6b7280';
const SECTOR = {
  tea: '#5E8C3A', coffee: '#7A4E2D', food_drink: '#B5462E', bakery: '#C08A2B',
  grocery_convenience: '#2F8C8C', snacks: '#D0702A', apparel: '#6B4FA0', beauty: '#C4577A',
  lifestyle_variety: '#2F5FA8', electronics: '#3C7A9A', home: '#7A8C3A',
};
const STATE_NAME = {
  AL: 'Alabama', AK: 'Alaska', AZ: 'Arizona', AR: 'Arkansas', CA: 'California', CO: 'Colorado',
  CT: 'Connecticut', DE: 'Delaware', DC: 'District of Columbia', FL: 'Florida', GA: 'Georgia',
  HI: 'Hawaii', ID: 'Idaho', IL: 'Illinois', IN: 'Indiana', IA: 'Iowa', KS: 'Kansas', KY: 'Kentucky',
  LA: 'Louisiana', ME: 'Maine', MD: 'Maryland', MA: 'Massachusetts', MI: 'Michigan', MN: 'Minnesota',
  MS: 'Mississippi', MO: 'Missouri', MT: 'Montana', NE: 'Nebraska', NV: 'Nevada', NH: 'New Hampshire',
  NJ: 'New Jersey', NM: 'New Mexico', NY: 'New York', NC: 'North Carolina', ND: 'North Dakota',
  OH: 'Ohio', OK: 'Oklahoma', OR: 'Oregon', PA: 'Pennsylvania', RI: 'Rhode Island',
  SC: 'South Carolina', SD: 'South Dakota', TN: 'Tennessee', TX: 'Texas', UT: 'Utah', VT: 'Vermont',
  VA: 'Virginia', WA: 'Washington', WV: 'West Virginia', WI: 'Wisconsin', WY: 'Wyoming',
};
const TOP_N = 6;
let STATES = [];
let SORT = 'most';

const esc = (s) => String(s == null ? '' : s).replace(/[&<>"]/g,
  (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const plural = (n) => (n === 1 ? 'outlet' : 'outlets');

// One brand chip: a sector-ringed logo, the chain NAME and its outlet count. Clicking it opens that
// chain's ADDRESSES in this state (not the generic profile) — what a reader actually wants after
// drilling into a state. The name sits next to the logo so nothing has to be guessed. The logo falls
// back to a sector-colored monogram when a chain has no icon file.
function chip(c, extra, abbr) {
  const col = SECTOR[c.sector] || OTHER;
  return `<button type="button" class="bchip${extra ? ' extra' : ''}"${extra ? ' hidden' : ''} ` +
    `data-chain="${esc(c.chain)}" data-state="${esc(abbr)}" ` +
    `title="${esc(c.name)} — ${c.n} ${plural(c.n)} in this state; click for addresses">` +
    `<span class="blogo" data-chain="${esc(c.chain)}" data-col="${col}" style="border-color:${col}">` +
    `<img src="icons/${esc(c.chain)}.png${ICONV}" alt="" loading="lazy"></span>` +
    `<span class="bnm">${esc(c.name)}</span><span class="bn">${c.n}</span></button>`;
}

function render() {
  const box = document.getElementById('statelist');
  const rows = [...STATES];
  if (SORT === 'alpha') rows.sort((a, b) => a.name.localeCompare(b.name));
  else if (SORT === 'fewest') rows.sort((a, b) => a.total - b.total || a.name.localeCompare(b.name));
  else rows.sort((a, b) => b.total - a.total || a.name.localeCompare(b.name));

  box.innerHTML = rows.map((s) => {
    const top = s.chains.slice(0, TOP_N).map((c) => chip(c, false, s.abbr)).join('');
    const rest = s.chains.slice(TOP_N);
    const restChips = rest.map((c) => chip(c, true, s.abbr)).join('');
    const more = rest.length
      ? `<button type="button" class="st-more" aria-expanded="false">+${rest.length} more</button>` : '';
    const soon = s.soon ? `<span class="st-soon">${s.soon} opening soon</span>` : '';
    const total = s.total
      ? `${s.total.toLocaleString()} <span class="st-unit">${plural(s.total)}</span>`
      : '<span class="st-none">No outlets yet</span>';
    return `<div class="statecard${s.total ? '' : ' empty'}">` +
      `<div class="st-head"><span class="st-name">${esc(s.name)}<span class="st-abbr">${s.abbr}</span></span>` +
      `<span class="st-total">${total}${soon}</span></div>` +
      (s.total ? `<div class="st-chains">${top}${restChips}${more}</div>` : '') +
      '</div>';
  }).join('');

  // Logo fallback: a missing icon file becomes a sector-colored monogram.
  box.querySelectorAll('.blogo img').forEach((img) => {
    img.addEventListener('error', function () {
      const span = this.parentNode;
      this.remove();
      span.textContent = (span.dataset.chain || '').slice(0, 2).toUpperCase();
      span.style.background = span.dataset.col; span.style.color = '#fff';
    });
  });
  // Expand / collapse the long tail.
  box.querySelectorAll('.st-more').forEach((btn) => {
    btn.addEventListener('click', () => {
      const extras = btn.parentNode.querySelectorAll('.bchip.extra');
      const opening = btn.getAttribute('aria-expanded') !== 'true';
      extras.forEach((e) => { e.hidden = !opening; });
      btn.setAttribute('aria-expanded', String(opening));
      btn.textContent = opening ? 'show less' : `+${extras.length} more`;
    });
  });
}

async function init() {
  let fc;
  try { fc = await fetch('data/stores.geojson' + DATAV).then((r) => r.json()); } catch (e) { return; }
  const agg = {};
  for (const f of fc.features) {
    const p = f.properties, st = p.state;
    if (!st) continue;
    const a = agg[st] || (agg[st] = { chains: {}, soon: 0 });
    if (p.status === 'coming_soon') { a.soon++; continue; }
    if (p.kind !== 'store' && p.kind !== 'sighting') continue;
    const c = a.chains[p.chain] || (a.chains[p.chain] = { chain: p.chain, name: p.name || p.chain, sector: p.sector, n: 0, items: [] });
    c.n++;
    if (p.name) c.name = p.name;
    const g = f.geometry && f.geometry.coordinates;
    c.items.push({ address: p.address || '', city: p.city || '',
                   lat: g ? g[1] : null, lon: g ? g[0] : null });
  }
  STATES = Object.keys(STATE_NAME).map((abbr) => {
    const a = agg[abbr] || { chains: {}, soon: 0 };
    const chains = Object.values(a.chains).sort((x, y) => y.n - x.n || x.name.localeCompare(y.name));
    return { abbr, name: STATE_NAME[abbr], chains, total: chains.reduce((s, c) => s + c.n, 0), soon: a.soon };
  });

  const covered = STATES.filter((s) => s.total > 0).length;
  const outlets = STATES.reduce((s, x) => s + x.total, 0);
  const nChains = new Set(fc.features.filter((f) => {
    const p = f.properties;
    return p.state && p.status !== 'coming_soon' && (p.kind === 'store' || p.kind === 'sighting');
  }).map((f) => f.properties.chain)).size;
  const gap = 51 - covered;
  const none = STATES.filter((s) => !s.total).map((s) => s.abbr);
  const intro = document.getElementById('intro');
  if (intro) {
    intro.textContent = `${outlets.toLocaleString()} outlets of ${nChains} chains, across ${covered} of the 50 states and D.C. ` +
      (gap === 0 ? 'Every state and D.C. now has at least one China-origin chain.'
                 : `Still none in ${none.join(', ')}.`);
  }

  render();
  setupModal();
  document.querySelectorAll('.sortbtn').forEach((b) => b.addEventListener('click', () => {
    SORT = b.dataset.sort;
    document.querySelectorAll('.sortbtn').forEach((x) => x.setAttribute('aria-pressed', String(x === b)));
    render();
  }));
}

// ---- Address modal: one chain's outlets in one state --------------------------------------------
// Clicking a chip answers "where is this chain in THIS state" with a scrollable address list, a
// "Show on map" deep link (the main US map, this chain only, centred on the state's outlets) and a
// link to the chain's profile for anyone who still wants "who they are".
let MODAL, M_TITLE, M_LIST, M_MAP, M_PROFILE;

function openAddresses(abbr, chain) {
  const s = STATES.find((x) => x.abbr === abbr); if (!s) return;
  const c = s.chains.find((x) => x.chain === chain); if (!c) return;
  const items = [...(c.items || [])].sort((x, y) =>
    (x.city || '').localeCompare(y.city || '') || (x.address || '').localeCompare(y.address || ''));

  M_TITLE.innerHTML = `<span class="m-name">${esc(c.name)}</span> in ${esc(s.name)}` +
    ` <span class="m-count">${c.n} ${plural(c.n)}</span>`;
  // City leads (the readable line), with the street address below it and lighter. The panel header
  // already says which state, so the row shows the city name alone, not "City, ST".
  M_LIST.innerHTML = items.length
    ? items.map((i) => {
        const city = i.city ? esc(i.city) : '';
        const addr = i.address ? esc(i.address) : '';
        const head = city || addr || '—';      // city leads; fall back to the address, then a dash
        const sub = city ? addr : '';           // the street address sits beneath, in the muted style
        return `<li><span class="m-city">${head}</span>` +
          (sub ? `<span class="m-addr">${sub}</span>` : '') + `</li>`;
      }).join('')
    : '<li class="m-empty">No street addresses on file for these outlets.</li>';

  const pts = items.filter((i) => isFinite(i.lat) && isFinite(i.lon));
  let href = `index.html#only=${encodeURIComponent(chain)}`;
  if (pts.length) {
    const lat = pts.reduce((t, i) => t + i.lat, 0) / pts.length;
    const lon = pts.reduce((t, i) => t + i.lon, 0) / pts.length;
    href += `&c=${lon.toFixed(4)},${lat.toFixed(4)}&z=${pts.length === 1 ? 11 : 6}`;
  }
  M_MAP.href = href;
  M_PROFILE.href = `chain.html?c=${encodeURIComponent(chain)}`;

  MODAL.hidden = false;
  document.body.classList.add('modal-open');
  document.getElementById('smodal-close').focus();
}

function closeAddresses() {
  MODAL.hidden = true;
  document.body.classList.remove('modal-open');
}

function setupModal() {
  MODAL = document.getElementById('smodal');
  if (!MODAL) return;
  M_TITLE = document.getElementById('smodal-title');
  M_LIST = document.getElementById('smodal-list');
  M_MAP = document.getElementById('smodal-map');
  M_PROFILE = document.getElementById('smodal-profile');
  MODAL.querySelectorAll('[data-close]').forEach((el) => el.addEventListener('click', closeAddresses));
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && !MODAL.hidden) closeAddresses(); });
  // Delegated so it survives re-render and the "+N more" expansion.
  document.getElementById('statelist').addEventListener('click', (e) => {
    const btn = e.target.closest('.bchip'); if (!btn) return;
    openAddresses(btn.dataset.state, btn.dataset.chain);
  });
}

init();

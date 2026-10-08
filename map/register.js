/*
 * Renders register.json. Deliberately plain: this is a table of claims, and any chart drawn
 * over it would imply a completeness the underlying research does not have.
 */
const esc = s => String(s ?? '').replace(/[&<>"]/g, c =>
  ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const chainLabel = (c, opts = {}) => {
  const trading = c.name_us || c.name;
  const alias = c.name_us && c.name_us !== c.name ? c.name : null;
  const zh = c.name_zh ? `<span class="zh">${esc(c.name_zh)}</span>` : '';
  // Only show the alternate romanization when it is a genuinely different name used elsewhere
  // (e.g. "ChaPanda" for the US "TeaByDo"), not when it is merely a shorter form of the trading
  // name ("Tai Er" within "Tai Er Sichuan Cuisine"). When shown, it reads in the same font as the
  // rest of the label — not the Hans face the Chinese name uses.
  const norm = s => s.toLowerCase().replace(/[^a-z0-9]/g, '');
  const redundant = alias && (norm(trading).includes(norm(alias)) || norm(alias).includes(norm(trading)));
  const also = alias && !redundant && !opts.short ? ` (${esc(alias)})` : '';
  return `${esc(trading)}${zh}${also}`;
};

const REGION_ORDER = ['East Asia', 'Southeast Asia', 'Central Asia', 'Gulf', 'Oceania', 'North America', 'Europe'];
// The same retail-type buckets the landing page groups its chains by, so the matrix reads the
// same way — tea with tea, toys with toys — and every chain (US or only-abroad) lands in its type.
const CAT_ORDER = ['Tea', 'Coffee', 'Ice Cream', 'Restaurants', 'Snacks & Delis', 'Bakery',
  'Grocery & Convenience', 'Apparel & Accessories', 'Beauty', 'Electronics', 'Toys & Pop Culture', 'Other'];
const CAT_BY_FORMAT = { tea: 'Tea', coffee: 'Coffee', restaurant: 'Restaurants', hotpot: 'Restaurants',
  snack: 'Snacks & Delis', bakery: 'Bakery', toys: 'Toys & Pop Culture', lifestyle: 'Toys & Pop Culture',
  convenience: 'Grocery & Convenience', supermarket: 'Grocery & Convenience', grocery: 'Grocery & Convenience',
  apparel: 'Apparel & Accessories', beauty: 'Beauty', electronics: 'Electronics' };
const CAT_OVERRIDE = { mixue: 'Ice Cream' };
let D = null;
const catOf = c => CAT_OVERRIDE[c] || CAT_BY_FORMAT[(D.chains[c] || {}).format] || 'Other';

async function main() {
  D = await fetch('data/register.json').then(r => r.json());
  const cells = {};
  for (const e of D.entries) cells[e.chain + '/' + e.market] = e;

  const markets = Object.keys(D.markets).sort((a, b) =>
    (REGION_ORDER.indexOf(D.markets[a].region) - REGION_ORDER.indexOf(D.markets[b].region))
    || a.localeCompare(b));
  const chains = Object.keys(D.chains).sort((a, b) =>
    (D.derived.markets_present[b] || 0) - (D.derived.markets_present[a] || 0) || a.localeCompare(b));

  // Region headers span their markets, so Europe reads as one block.
  const spans = [];
  for (const m of markets) {
    const r = D.markets[m].region;
    if (spans.length && spans[spans.length - 1].r === r) spans[spans.length - 1].n++;
    else spans.push({ r, n: 1 });
  }

  let h = '<table class="reg"><thead><tr><th class="corner"></th>' +
    spans.map(s => `<th class="region" colspan="${s.n}">${esc(s.r)}</th>`).join('') +
    '</tr><tr><th class="corner"></th>' +
    markets.map(m => `<th title="${esc(D.markets[m].name)}">${esc(m)}</th>`).join('') +
    '</tr></thead><tbody>';
  // Rows grouped by retail type; within each type the most-widely-expanded chain leads (chains is
  // already sorted by markets present). A category band spans the whole width above its chains.
  const byCat = {};
  for (const c of chains) (byCat[catOf(c)] = byCat[catOf(c)] || []).push(c);
  const cats = [...CAT_ORDER.filter(c => byCat[c]), ...Object.keys(byCat).filter(c => !CAT_ORDER.includes(c))];
  for (const cat of cats) {
    h += `<tr class="catrow"><th class="catcell" colspan="${markets.length + 1}">${esc(cat)}</th></tr>`;
    for (const c of byCat[cat]) {
      h += `<tr><th class="chain">${chainLabel(D.chains[c])}</th>`;
      for (const m of markets) {
        const e = cells[c + '/' + m];
        h += `<td class="${cellClass(e)}" data-key="${esc(c + '/' + m)}">${cellText(e)}</td>`;
      }
      h += '</tr>';
    }
  }
  h += '</tbody></table>';
  document.getElementById('matrix').innerHTML = h;

  for (const td of document.querySelectorAll('.reg td')) {
    td.addEventListener('pointerenter', ev => tip(ev, cells[td.dataset.key], td.dataset.key));
    td.addEventListener('pointerleave', () => { document.getElementById('tip').hidden = true; });
  }

  // Per-chain US store counts, taken from the SAME stores.geojson the map draws and tallied by the
  // SAME rule the map uses: OPEN outlets only (open + hand-verified sighting), with announced /
  // coming-soon held out — the governing US count for the whole site. So the register's "In the US"
  // column is identical to the US tab by construction, and updates with every deploy. See atlas.js
  // buildTally and the homepage isLocated predicate.
  const usCount = {};
  try {
    const sg = await fetch('data/stores.geojson').then(r => r.json());
    for (const f of (sg.features || [])) {
      const p = f.properties || {};
      if (p.chain && (p.status === 'open' || (p.kind === 'sighting' && p.status !== 'coming_soon')))
        usCount[p.chain] = (usCount[p.chain] || 0) + 1;
    }
  } catch (e) { /* no map data: US column falls back to em-dashes */ }

  usView(chains, markets, cells, usCount);
  document.getElementById('asof').textContent = `Last updated ${D.as_of}.`;
}

/*
 * The reader is American, so the first thing the page answers is "is it here yet?".
 * Chains already trading in the US sit above the ones that have only gone elsewhere — the
 * second group being the actual watchlist.
 */
function usView(chains, markets, cells, usCount) {
  const us = D.derived.us_status || {};
  const ww = (D.derived && D.derived.worldwide) || {};
  const metaOf = c => D.chains[c] || us[c] || { name: c };
  // "Here" is every chain that trades in the US, drawn from us_status (which now covers all US
  // adapters), not just the register's own international chains — so the map's US chains all show.
  // Ordered alphabetically by the name shown, so a reader can scan for one.
  const nameKey = c => String(metaOf(c).name_us || metaOf(c).name || c).toLowerCase();
  const here = Object.keys(us)
    .filter(c => us[c].status === 'collected' || us[c].status === 'present_not_collected')
    .sort((a, b) => nameKey(a).localeCompare(nameKey(b)));
  const notHere = Object.keys(D.chains).filter(c => (us[c] || {}).status === 'not_established')
    .sort((a, b) => nameKey(a).localeCompare(nameKey(b)));

  const num = n => (n != null ? Number(n).toLocaleString('en-US') : null);
  // US cell: the live count from the map (em-dash when a chain has no mapped US outlet).
  const usCell = c => {
    const n = usCount[c];
    return n ? `<td class="num">${num(n)}</td>` : `<td class="num dash">&mdash;</td>`;
  };
  // Worldwide cell: latest reported company-wide total + its as-of (blank where unknown). China
  // and overseas splits are Pro-only and never reach this page.
  const wwCell = c => {
    const w = ww[c];
    if (!w || w.n == null) return `<td class="num dash">&mdash;</td>`;
    return `<td class="num">${num(w.n)}` +
      (w.as_of ? `<span class="asof">as of ${esc(w.as_of)}</span>` : '') + `</td>`;
  };
  const body = list => list.map(c =>
    `<tr><td class="name"><b>${chainLabel(metaOf(c))}</b></td>${usCell(c)}${wwCell(c)}</tr>`).join('');
  const table = list =>
    `<table class="ustable"><thead><tr><th>Chain</th>` +
    `<th class="num">In the US</th><th class="num">Worldwide</th></tr></thead>` +
    `<tbody>${body(list)}</tbody></table>`;

  document.getElementById('usview').innerHTML =
    `<section class="usbox"><h2>Already in the United States</h2>` +
    `<p class="note small">Every Chinese chain this project tracks on the US map, A&ndash;Z. ` +
    `The <strong>In the US</strong> column is collected daily and matches the ` +
    `<a href="index.html">US map</a> exactly; <strong>Worldwide</strong> is the latest company-wide ` +
    `store total reported in filings or the press, with the date it was reported.</p>` +
    table(here) + `</section>` +
    (notHere.length ? `<section class="usbox watch"><h2>Expanding abroad, not yet in the US</h2>` +
      `<p class="note small">The watchlist &mdash; Chinese chains that have opened outside China but ` +
      `that we have not found in the United States. If one reaches America, it moves up to the list ` +
      `above.</p>` + table(notHere) + `</section>` : '');
}

function cellClass(e) {
  if (!e) return 'c-none';
  if (e.collected) return 'c-yes c-high c-collected';
  if (e.status === 'no_evidence') return 'c-noev';
  if (e.status === 'exited') return 'c-exit';
  return 'c-yes c-' + e.confidence;
}

function cellText(e) {
  if (!e) return '<span class="dotmark">·</span>';
  if (e.status === 'no_evidence') return '–';
  if (e.status === 'exited') return '×';
  if (e.collected) return `${e.locations}<span class="conf c-collected">\u2605</span>`;
  const mark = e.confidence === 'high' ? '' :
    `<span class="conf c-${e.confidence}">${e.confidence === 'low' ? '??' : '?'}</span>`;
  return (e.locations != null ? e.locations : 'Y') + mark;
}

function tip(ev, e, key) {
  const t = document.getElementById('tip');
  const [c, m] = key.split('/');
  if (!e) {
    t.innerHTML = `<b>${chainLabel(D.chains[c], { short: true })} · ${esc(D.markets[m].name)}</b>` +
      `<div class="meta">Not looked at yet. This is not a claim of absence.</div>`;
  } else {
    const bits = [];
    if (e.first_opened) bits.push(`first opened ${esc(e.first_opened)} (${esc(e.precision)})`);
    if (e.locations != null) bits.push(`${e.locations} locations as of ${esc(e.locations_as_of)}`);
    bits.push(e.collected ? 'collected daily, not typed' : `${esc(e.confidence)} confidence`);
    t.innerHTML = `<b>${chainLabel(D.chains[c], { short: true })} · ${esc(D.markets[m].name)}</b>` +
      `${esc(e.status)}: ${bits.join('; ')}` +
      (e.note ? `<div class="meta">${esc(e.note)}</div>` : '') +
      (e.sources && e.sources.length ? `<div class="meta">${e.sources.length} source(s)</div>`
        : `<div class="meta">no source cited</div>`);
  }
  t.hidden = false;
  t.style.left = Math.min(ev.clientX + 14, innerWidth - 320) + 'px';
  t.style.top = (ev.clientY + 14) + 'px';
}

main();

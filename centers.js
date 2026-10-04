// Co-tenancy view: render the clusters where two or more China-origin chains trade together.
// Data is data/centers.json, produced by `chain_atlas export` (chain_atlas/centers.py).
'use strict';

const esc = s => String(s == null ? '' : s).replace(/[&<>"]/g, c =>
  ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

const SECTOR_LABEL = {
  food_drink: 'Food & drink', tea: 'Tea', coffee: 'Coffee', bakery: 'Bakery',
  grocery_convenience: 'Grocery', snacks: 'Snacks', apparel: 'Apparel', beauty: 'Beauty',
  lifestyle_variety: 'Lifestyle', electronics: 'Electronics', home: 'Home',
};

function placeCell(c) {
  const named = c.center && c.center.name;
  const owner = c.center && c.center.owner_reit;
  const where = `${esc(c.city || '—')}, ${esc(c.state || '—')}`;
  const title = named ? esc(c.center.name) : where;
  const sub = named ? `${where}${owner ? ' · ' + esc(owner) : ''}` : `${c.lat}, ${c.lon}`;
  return `<span class="place">${title}</span><br><small>${sub}</small>`;
}

function chainChips(c) {
  return c.brands.map(b => {
    const soon = (b.statuses || []).length === 1 && b.statuses[0] === 'pre_opening';
    const sec = b.sector ? `<span class="sec"> ${esc(SECTOR_LABEL[b.sector] || b.sector)}</span>` : '';
    const n = b.count > 1 ? ` ×${b.count}` : '';
    return `<span class="chip"><b>${esc(b.name)}</b>${n}${sec}${soon ? ' <span class="sec">(coming)</span>' : ''}</span>`;
  }).join(' ');
}

function renderLandlords(roll) {
  if (!roll || !roll.length) return;
  document.getElementById('landlordsec').hidden = false;
  document.querySelector('#reit tbody').innerHTML = roll.map(r => `
    <tr>
      <td class="place">${esc(r.owner_reit)}</td>
      <td><span class="sec">${r.is_reit ? 'REIT' : 'private'}</span></td>
      <td class="num">${r.centers}</td>
      <td class="num">${r.brands}</td>
    </tr>`).join('');
}

fetch('data/centers.json?cb=' + Date.now())
  .then(r => r.json())
  .then(data => {
    renderLandlords(data.reit_rollup);
    const rows = data.co_tenancy || [];
    const tb = document.querySelector('#cot tbody');
    tb.innerHTML = rows.map((c, i) => `
      <tr class="${c.brand_count >= 3 ? 'top' : ''}">
        <td class="num">${i + 1}</td>
        <td>${placeCell(c)}</td>
        <td class="num">${c.brand_count}</td>
        <td class="num">${c.sector_count}</td>
        <td>${chainChips(c)}</td>
      </tr>`).join('');

    const three = rows.filter(c => c.brand_count >= 3).length;
    const named = rows.filter(c => c.center).length;
    const states = new Set(rows.map(c => c.state).filter(Boolean)).size;
    document.getElementById('summary').textContent =
      `${rows.length} places where 2+ Chinese chains trade together` +
      (three ? `, ${three} with 3 or more` : '') +
      `, across ${states} states — ${named} in a named shopping center.`;
    document.getElementById('method').textContent =
      'A cluster is chains geocoded within about 100 m of each other. ' +
      'Counts are distinct brands and distinct sectors; “×N” marks more than one outlet of a brand ' +
      'in the same cluster. Named centers and owners are added where known.';

    const total = (data.clusters || []).length;
    const as = document.getElementById('asof');
    if (as) as.textContent = `From ${total.toLocaleString()} located storefronts.`;
  })
  .catch(() => {
    document.getElementById('summary').textContent = 'Could not load the co-tenancy data.';
  });

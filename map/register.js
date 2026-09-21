/*
 * Renders register.json. Deliberately plain: this is a table of claims, and any chart drawn
 * over it would imply a completeness the underlying research does not have.
 */
const esc = s => String(s ?? '').replace(/[&<>"]/g, c =>
  ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const REGION_ORDER = ['East Asia', 'Southeast Asia', 'Gulf', 'Oceania', 'North America', 'Western Europe'];
let D = null;

async function main() {
  D = await fetch('data/register.json').then(r => r.json());
  const cells = {};
  for (const e of D.entries) cells[e.chain + '/' + e.market] = e;

  const markets = Object.keys(D.markets).sort((a, b) =>
    (REGION_ORDER.indexOf(D.markets[a].region) - REGION_ORDER.indexOf(D.markets[b].region))
    || a.localeCompare(b));
  const chains = Object.keys(D.chains).sort((a, b) =>
    (D.derived.markets_present[b] || 0) - (D.derived.markets_present[a] || 0) || a.localeCompare(b));

  // Region headers span their markets, so Western Europe reads as one block.
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
  for (const c of chains) {
    h += `<tr><th class="chain">${esc(D.chains[c].name)}` +
      `<span class="zh">${esc(D.chains[c].name_zh)}</span></th>`;
    for (const m of markets) {
      const e = cells[c + '/' + m];
      h += `<td class="${cellClass(e)}" data-key="${esc(c + '/' + m)}">${cellText(e)}</td>`;
    }
    h += '</tr>';
  }
  h += '</tbody></table>';
  document.getElementById('matrix').innerHTML = h;

  for (const td of document.querySelectorAll('.reg td')) {
    td.addEventListener('pointerenter', ev => tip(ev, cells[td.dataset.key], td.dataset.key));
    td.addEventListener('pointerleave', () => { document.getElementById('tip').hidden = true; });
  }

  detail(chains, markets, cells);
  coverage(chains);
  document.getElementById('asof').textContent = `Compiled ${D.as_of}.`;
  document.getElementById('gaps').textContent =
    `${D.derived.gaps} of ${chains.length * markets.length} chain/market pairs have not been ` +
    `checked at all. They are blank on purpose — an unchecked pair is not an absence.`;
}

function cellClass(e) {
  if (!e) return 'c-none';
  if (e.status === 'no_evidence') return 'c-noev';
  if (e.status === 'exited') return 'c-exit';
  return 'c-yes c-' + e.confidence;
}

function cellText(e) {
  if (!e) return '<span class="dotmark">·</span>';
  if (e.status === 'no_evidence') return '–';
  if (e.status === 'exited') return '×';
  const mark = e.confidence === 'high' ? '' :
    `<span class="conf c-${e.confidence}">${e.confidence === 'low' ? '??' : '?'}</span>`;
  return (e.locations != null ? e.locations : 'Y') + mark;
}

function tip(ev, e, key) {
  const t = document.getElementById('tip');
  const [c, m] = key.split('/');
  if (!e) {
    t.innerHTML = `<b>${esc(D.chains[c].name)} · ${esc(D.markets[m].name)}</b>` +
      `<div class="meta">Not looked at yet — not a claim of absence.</div>`;
  } else {
    const bits = [];
    if (e.first_opened) bits.push(`first opened ${esc(e.first_opened)} (${esc(e.precision)})`);
    if (e.locations != null) bits.push(`${e.locations} locations as of ${esc(e.locations_as_of)}`);
    bits.push(`${esc(e.confidence)} confidence`);
    t.innerHTML = `<b>${esc(D.chains[c].name)} · ${esc(D.markets[m].name)}</b>` +
      `${esc(e.status)} — ${bits.join('; ')}` +
      (e.note ? `<div class="meta">${esc(e.note)}</div>` : '') +
      (e.sources && e.sources.length ? `<div class="meta">${e.sources.length} source(s)</div>`
        : `<div class="meta">no source cited</div>`);
  }
  t.hidden = false;
  t.style.left = Math.min(ev.clientX + 14, innerWidth - 320) + 'px';
  t.style.top = (ev.clientY + 14) + 'px';
}

function detail(chains, markets, cells) {
  let h = '';
  for (const c of chains) {
    const rows = markets.filter(m => cells[c + '/' + m]).map(m => [m, cells[c + '/' + m]]);
    if (!rows.length) continue;
    h += `<section class="chainblock"><h3>${esc(D.chains[c].name)}` +
      `<span class="zh">${esc(D.chains[c].name_zh)}</span></h3>` +
      `<p class="note small">${esc(D.chains[c].global)}</p><dl class="rows">`;
    for (const [m, e] of rows) {
      const bits = [];
      if (e.first_opened) bits.push(`first ${esc(e.first_opened)}`);
      if (e.locations != null) bits.push(`${e.locations} locations (${esc(e.locations_as_of)})`);
      h += `<dt>${esc(D.markets[m].name)}</dt><dd>` +
        `<span class="status s-${esc(e.status)}">${esc(e.status.replace('_', ' '))}</span> ` +
        bits.join(' · ') +
        (e.note ? `<div class="rnote">${esc(e.note)}</div>` : '') +
        (e.sources || []).map(u =>
          `<a class="src" href="${esc(u)}" target="_blank" rel="noopener">source</a>`).join(' ') +
        `</dd>`;
    }
    h += '</dl></section>';
  }
  document.getElementById('detail').innerHTML = h;
}

function coverage(chains) {
  const tb = document.querySelector('#coverage tbody');
  for (const c of chains) {
    const n = D.derived.markets_present[c] || 0;
    tb.insertAdjacentHTML('beforeend',
      `<tr><td>${esc(D.chains[c].name)}</td><td class="n">${n}</td></tr>`);
  }
  document.getElementById('covnote').textContent =
    `Markets in this register where each chain is recorded as present. Not a ranking of size — ` +
    `MIXUE has more stores abroad than everyone here combined, in countries this register does ` +
    `not yet cover.`;
}

main();

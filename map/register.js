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
  const also = alias && !opts.short ? `<span class="zh">(${esc(alias)})</span>` : '';
  return `${esc(trading)}${zh}${also}`;
};

const REGION_ORDER = ['Greater China', 'East Asia', 'Southeast Asia', 'Gulf', 'Oceania', 'North America', 'Western Europe'];
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
    h += `<tr><th class="chain">${chainLabel(D.chains[c])}</th>`;
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

  usView(chains, markets, cells);
  detail(chains, markets, cells);
  coverage(chains);
  document.getElementById('asof').textContent = `Compiled ${D.as_of}.`;
  document.getElementById('gaps').textContent =
    `${D.derived.gaps} of ${chains.length * markets.length} chain/market pairs have not been ` +
    `checked at all. They are blank on purpose — an unchecked pair is not an absence.`;
}

/*
 * The reader is American, so the first thing the page answers is "is it here yet?".
 * Chains already trading in the US sit above the ones that have only gone elsewhere — the
 * second group being the actual watchlist.
 */
function usView(chains, markets, cells) {
  const us = D.derived.us_status || {};
  const abroad = c => markets.filter(m => (cells[c + '/' + m] || {}).status === 'present').length;
  const here = chains.filter(c => (us[c] || {}).status !== 'not_established');
  const notHere = chains.filter(c => (us[c] || {}).status === 'not_established');
  const row = c => {
    const st = us[c] || {};
    const badge = st.status === 'collected'
      ? '<span class="status s-collected">counted daily</span>'
      : st.status === 'present_not_collected'
        ? '<span class="status s-present">here, not yet counted</span>' : '';
    return `<li><b>${chainLabel(D.chains[c])}</b> ` +
      `${badge}<span class="abroad">${abroad(c)} market${abroad(c) === 1 ? '' : 's'} abroad</span>` +
      (st.detail ? `<div class="rnote">${esc(st.detail)}</div>` : '') + `</li>`;
  };
  document.getElementById('usview').innerHTML =
    `<section class="usbox"><h2>Already in the United States</h2>` +
    `<p class="note small">Every one of these is on the US roster. "Counted daily" means this ` +
    `project reads its store locator every morning; the rest are here and not yet countable, ` +
    `with the reason stated.</p><ul class="uslist">${here.map(row).join('')}</ul></section>` +
    (notHere.length ? `<section class="usbox watch"><h2>Expanding abroad, US presence not established</h2>` +
      `<p class="note small">The watchlist. These have crossed at least one border; whether they ` +
      `have reached America has not been checked or the evidence was ambiguous. Not a claim of ` +
      `absence.</p><ul class="uslist">${notHere.map(row).join('')}</ul></section>` : '');
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

function detail(chains, markets, cells) {
  let h = '';
  for (const c of chains) {
    const rows = markets.filter(m => cells[c + '/' + m]).map(m => [m, cells[c + '/' + m]]);
    if (!rows.length) continue;
    h += `<section class="chainblock"><h3>${chainLabel(D.chains[c])}</h3>` +
      `<p class="note small">${esc(D.chains[c].global)}</p><dl class="rows">`;
    for (const [m, e] of rows) {
      const bits = [];
      if (e.first_opened) bits.push(`first ${esc(e.first_opened)}`);
      if (e.locations != null) bits.push(`${e.locations} locations (${esc(e.locations_as_of)})`);
      h += `<dt>${esc(D.markets[m].name)}</dt><dd>` +
        `<span class="status s-${esc(e.status)}">${esc(e.status.replace('_', ' '))}</span> ` +
        (e.collected ? '<span class="status s-collected">collected</span> ' : '') +
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
      `<tr><td>${chainLabel(D.chains[c], { short: true })}</td><td class="n">${n}</td></tr>`);
  }
  document.getElementById('covnote').textContent =
    `Markets in this register where each chain is recorded as present. This is not a ranking of ` +
    `size: MIXUE has more stores abroad than everyone here combined, in countries this register ` +
    `does not yet cover.`;
}

main();

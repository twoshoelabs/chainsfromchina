// Method page: render the "how complete is this?" coverage scorecard from the public data
// (data/stores.json → meta.coverage), the same figures the detailed data view used. The rest of the
// page is static prose; site.js fills the nameplate + census line.
async function initMethod() {
  let d;
  try { d = await fetch('data/stores.json').then((r) => r.json()); } catch (e) { return; }
  const cov = (d.meta && d.meta.coverage) || {};
  const T = cov.totals || {};
  const rows = cov.rows || [];
  const esc = (s) => String(s == null ? '' : s).replace(/[&<>"]/g,
    (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

  const sum = document.getElementById('covsum');
  if (sum && T.chains) {
    sum.innerHTML =
      `We track <strong>${T.chains}</strong> chains. <strong>${T.collected}</strong> are collected daily ` +
      `from their own store locator (${(T.collected_stores || 0).toLocaleString()} outlets); ` +
      `<strong>${T.sighted}</strong> are hand-verified (${(T.sighted_confirmed || 0).toLocaleString()} outlets). ` +
      `For ${T.sighted_estimable || 0} of the hand-tracked chains a parent company or the trade press states a ` +
      `US figure, which we show beside ours.`;
  }

  const tb = document.querySelector('#covtable tbody');
  if (tb) {
    const sorted = [...rows].sort((a, b) => (b.held || 0) - (a.held || 0) || String(a.name).localeCompare(b.name));
    tb.innerHTML = sorted.map((r) => {
      const how = r.kind === 'collected' ? 'Collected daily' : 'Hand-verified';
      const held = (r.held != null ? r.held : (r.held_confirmed || 0)).toLocaleString();
      const reality = r.estimate_text
        ? esc(r.estimate_text)
        : (r.kind === 'collected' ? '<span class="how">its own list</span>' : '<span class="how">&mdash;</span>');
      return `<tr><td>${esc(r.name)}</td><td class="how">${how}</td>` +
        `<td class="num">${held}</td><td>${reality}</td></tr>`;
    }).join('');
  }

  const note = document.getElementById('covnote');
  if (note) {
    note.textContent = 'Coverage assessed ' + (cov.as_of || '') +
      '. “Reality” is a company or press figure for a chain’s US footprint, shown only where one exists; ' +
      'it is a check on our hand count, not part of the headline total.';
  }
}
initMethod();

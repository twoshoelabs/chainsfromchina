/*
 * name:      site.js
 * purpose:   Inject the one universal header on every page, mark the current page, and hide any
 *            page's old masthead, so every page shares identical chrome from a single source.
 * arguments: body[data-page] — one of map | chains | cotenancy | global (optional).
 * returns:   nothing.
 * effects:   Prepends <header class="site-nav"> to <body>; hides legacy .masthead; fetches
 *            data/meta.json for the "Updated …" line.
 * other:     No framework; pairs with site.css. The four primary links match the v4 brief.
 */
(function () {
  var PAGES = [
    ['map', 'index.html', 'US map'],
    ['chains', 'intro.html', 'Chains'],
    ['cotenancy', 'centers.html', 'Co-tenancy'],
    ['global', 'register.html', 'Global'],
  ];
  var cur = (document.body.getAttribute('data-page') || '').trim();

  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) {
    return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }

  var nav = PAGES.map(function (p) {
    var on = p[0] === cur ? ' aria-current="page"' : '';
    return '<a href="' + p[1] + '"' + on + '>' + p[2] + '</a>';
  }).join('');

  var header = document.createElement('header');
  header.className = 'site-nav';
  header.innerHTML =
    '<a class="wm" href="index.html">Chains From China</a>' +
    '<span class="beta" title="In beta — coverage is still being built and figures may change.">Beta</span>' +
    '<nav class="primary" aria-label="Primary">' + nav + '</nav>' +
    '<div class="right">' +
      '<span class="updated" id="site-updated"></span>' +
      '<a class="txt" href="contribute.html">Submit a sighting</a>' +
      '<a class="txt" href="index.html#pro">Sign in</a>' +
      '<a class="pro" href="index.html#pro">Pro</a>' +
    '</div>';

  // Hide any page's old in-page masthead so there is exactly one header.
  var olds = document.querySelectorAll('.masthead');
  for (var i = 0; i < olds.length; i++) olds[i].style.display = 'none';

  document.body.insertBefore(header, document.body.firstChild);

  // "Updated <date>" from the tiny shared meta file (cheap on every page).
  fetch('data/meta.json').then(function (r) { return r.json(); }).then(function (m) {
    var up = document.getElementById('site-updated');
    if (!up || !m || !m.last_collected) return;
    var d = m.last_collected, label = d;
    try {
      label = new Date(d + 'T00:00:00').toLocaleDateString('en-US',
        { day: 'numeric', month: 'short', year: 'numeric' });
    } catch (e) { /* keep ISO */ }
    up.innerHTML = '<span class="dot"></span>Updated ' + esc(label) + ', 06:00 UTC';
  }).catch(function () {});
})();

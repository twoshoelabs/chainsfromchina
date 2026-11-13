# CFC backlog / todo

Project follow-ups not yet done. Newest first.

---

## Puerto Rico sweep (added 2026-11-13)

**Context:** Puerto Rico was brought into scope on 2026-11-13 (owner decision — PR is a US territory, so China-origin chain outlets there count toward the US totals). So far only **2 Miniso PR stores** are covered (Plaza Carolina, Carolina; Puerto Rico Premium Outlets, Barceloneta), hand-added from Simon's brand page with manual coordinates.

**What's left — a proper PR sweep across all tracked chains:**

1. **Extend the locator adapters to keep PR rows.** The adapters (Miniso, Pop Mart, Mixue, etc.) currently filter to the 50 states + DC and discard PR rows their own feeds already carry. Flipping each adapter's US filter to include `PR` would pull in every PR outlet automatically — Miniso's own locator has more PR stores than the 2 Simon-listed ones, and other chains (Pop Mart roboshops, tea brands, apparel) likely have PR presence too.
2. **PR geocoding.** The Census geocoder returns nothing for PR addresses (`geocode_one` → None), so PR stores need **manual coordinates** (mall centroids), same pattern as other geocode gaps. A reusable PR geocode source (e.g., a PR address dataset or a fallback geocoder) would help.
3. **Verify `geo.py` point-in-state handles PR.** Confirm the state-shapes file includes a PR polygon before trusting coordinate-validation for adapter-pulled PR rows (Pop Mart's adapter drops rows that land in no US state — PR rows could be silently dropped).
4. **Sweep PR malls/directories by hand** for chains without good locators (the Simon/Premium-Outlets PR centers — Plaza Carolina, Puerto Rico Premium Outlets, Plaza Las Américas, etc. — plus the big SJ-metro malls).
5. **Confirm totals/count logic** fold PR into the governing US count (verified working for sightings on 2026-11-13; re-check after adapter changes).

**Notes:** `usaddr.STATES` already recognizes `PR` (and GU/VI/AS/MP). See memory `cfc-puerto-rico-scope`.

---

## Other known pending items (from memory, for visibility)

- **Geo-watch feature** — users subscribe to new-opening alerts within a zip+radius, filtered by chain type (requested 2026-10-19, not built). See `cfc-geo-watch-feature`.
- **Franchisee section** — "What it takes to be a franchisee" on chain pages for the 12 US-franchise chains (6 with FDDs → fdd.py numbers; 6 from brand pages). See `cfc-franchisee-section`.
- **closings.json surfacing** — closures are held internal for now; must be surfaced on the site later. See `cfc-closings-internal`.
- **Miniso Gurnee IL / Smith Haven NY, HeyTea Florida Mall, Molly Tea Ala Moana** — coming-soon sightings held as `uncertain`; flip to confirmed when they open.

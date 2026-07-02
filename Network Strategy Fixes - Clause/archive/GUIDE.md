# Network Strategy Builder — How It Works

A plain-English walkthrough of the tool: what each page does, what's
happening behind the scenes, and where the data comes from. Suitable for
explaining to a non-technical audience in a meeting.

---

## 1. What the tool does

Three pages under `/network-strategy`:

| Page | URL | Purpose |
|---|---|---|
| **Territory Overview** | `/network-strategy` | Map of every existing dealer's 60-min and 90-min drive-time catchment, plus heat-map of McLaren-relevant registrations and "open-point" white-space areas. |
| **Volume Planning** | `/network-strategy/volume-planning` | Edit the target annual volumes per segment (Core Supercar, GT, SUV, …). A CAGR slider grows the total addressable market for the forecast year. Saved plan drives every projection on the Impact page. |
| **Impact Analysis** | `/network-strategy/impact-analysis` | "What if?" lab. Remove existing dealers and/or add new ones on the map; see per-dealer unit deltas, a gain/loss summary banner, and a new catchment hull around any added dealer. |

---

## 2. Data sources (where numbers come from)

1. **Registration data** — `McLaren Registration Segment.xlsx`: every UK supercar/luxury reg for the last few years, tagged by postcode sector, brand, segment, sub-model, year, units.
2. **Dealer list** — `Network_Database (2).xlsx`: UK Full Sales & Service dealers with lat/lon.
3. **Postcode sector boundaries** — `SHARED-CODE/DRAFT_DATA/extracted/network_strategy/postcode_sectors.geojson`: the shape of every ~9,500 UK postcode sectors. Downloaded once.
4. **Population-weighted centroids** — derived per sector from the OS CodePoint-Open "Longair" postcode-unit file (`scripts/import_longair_sectors.py`) and cached to `sector_points.parquet`. We use these centroids for drive-time queries and for tight, tendril-free catchment polygons.

Everything else is computed from those four inputs.

---

## 3. The pipeline, in five stages

```
(raw excel + geojson)                    ┌────────────────────────────┐
           │                             │   pre-computed parquet +    │
           ▼                             │    geojson caches in:       │
┌────────────────────┐                   │  SHARED-CODE/DRAFT_DATA/   │
│  Stage 1 — Sector  │ ───► points ──►   │    extracted/              │
│  centroids         │                   │      network_strategy/     │
└────────────────────┘                   │        _cache/             │
┌────────────────────┐                   │                            │
│ Stage 2 — Drive-   │ ───► matrix ──►   │  sector_points.parquet     │
│ time matrix        │                   │  drive_time_matrix.parquet │
│ (Graphhopper)      │                   │  sector_assignment.parquet │
└────────────────────┘                   │  catchments.geojson        │
┌────────────────────┐                   │                            │
│ Stage 3 — Sector   │ ───► assigns ──►  └────────────────────────────┘
│ → dealer assign    │
│ (≤60 min, ≤90 min) │
└────────────────────┘
┌────────────────────┐
│ Stage 4 — Dissolve │ ───► catchments GeoJSON
│ catchments per     │       (one polygon per dealer × band)
│ (dealer, band)     │
└────────────────────┘
┌────────────────────┐
│ Stage 5 — Live app │ ◄─── reads every cache file, never rebuilds
│ (Flask + Leaflet)  │       on request — everything is pre-baked.
└────────────────────┘
```

The heavy pipeline (stages 1–4) is scripted in:

- `scripts/build_network_strategy_caches.py` — orchestrator
- `scripts/import_longair_sectors.py` — centroid build
- The dissolve step uses `SHARED-CODE/network_strategy_service.py → dissolve_catchments()`.

It takes ~40 minutes to run end-to-end. You only re-run it when dealers change, boundaries change, or registration data changes.

---

## 4. What Graphhopper actually is (and why we ever say "live")

**Graphhopper** is an open-source routing engine (like Google Directions, but self-hosted). It answers "how many minutes does it take to drive from A to B over the UK road network?". It's a Java process listening on `http://localhost:8989`.

**When we build the matrix** (stage 2): for every (dealer × sector centroid) pair (≈ 7 dealers × 9,500 sectors = 66,500 queries), we ask Graphhopper for the drive time and stash it in `drive_time_matrix.parquet`.

**After that, the live app does NOT normally talk to Graphhopper.** It just reads the parquet. This is why the Territory Overview and the baseline of Impact Analysis are instant.

**The one time it comes back to life: adding a new dealer on Impact Analysis.** When you drop a pin in London we need drive times from *that new location* to every sector (~9,500 fresh routing queries not in the cache). Scenario routing queries sector **centroids only** (one point per sector, not the 5-point baseline sample), so the whole row lands in a few seconds.

**Graphhopper is mandatory for adding a dealer.** There is no great-circle fallback for new locations — if the routing engine is offline the Impact Analysis refuses to compute the "add dealer" scenario and shows an error. Existing dealers' drive times were baked into the parquet months ago and never need Graphhopper again, so removal scenarios always work regardless.

**Auto-start.** `dev_app.py` tries to launch Graphhopper itself when the Flask server boots (it checks `http://127.0.0.1:8989/health` first, skips if already up). End-users don't run anything manually. Bootstrap/manual scripts still exist for first-time setup and debugging:

```powershell
powershell -File scripts/bootstrap_graphhopper.ps1  # one-off download + UK map import
powershell -File scripts/start_graphhopper.ps1     # manual start (rarely needed)
powershell -File scripts/stop_graphhopper.ps1      # kill the Java process
```

A fully warm Graphhopper answers a single query in ~5 ms; a whole network-wide matrix rebuild comes back in 60–100 seconds on a laptop.

---

## 5. How "projected units" work (Volume Planning → Impact Analysis)

1. Volume Planning lets you set a target volume per segment (e.g. "Core Supercar = 660 units/year"). Optionally a CAGR for market growth over the forecast horizon.
2. For every postcode sector we know McLaren-relevant **market registrations** per segment from the Excel file. We compute each sector's *share* of the segment's total market (e.g. SW1 takes 1.4% of Core Supercar).
3. We spread the Volume Planning target across sectors by that share. Result: every sector has a projected McLaren unit number for each segment, summed to `projected_units` per sector.
4. On Impact Analysis, we assign each sector to its nearest dealer (≤60 min first, ≤90 min fallback, otherwise "open point") and roll the projected units up:
   - per dealer → the "Baseline" column
   - open points → units the network can't capture today

When you remove or add a dealer, we re-assign the sectors, re-roll up, and show deltas.

### Open-point revaluation (band-aware)

Sectors that fall outside every dealer's 90-min catchment still generate *some* McLaren sales (rich buyers travel), but at a much lower realised market share. We measure two empirical averages per segment from the registrations file:

- **60-min-derived open-point share** — applied if the sector was previously inside someone's 60-min ring and has now fallen out of coverage entirely.
- **90-min-derived open-point share** — applied if the sector was previously only in a 90-min band.

When removal causes a sector to drop out, we *re-value* (not zero out) its units at the share matching its previous band. This keeps volume conserved — nothing is "lost to rounding" — while being realistic about how little white-space sectors actually capture.

### Reassigned sectors — receiving-dealer average share (dealer removal)

When a removed dealer's sectors are absorbed by a neighbouring dealer (still within 60 or 90 min), we **do not** carry forward the historical per-sector McLaren figure from the old dealer's territory. Instead, we project using the **receiving dealer's own average McLaren market share** in their current band:

```
projected_units = total_market_units_in_sector
                × (Σ McLaren units across receiving dealer's existing band sectors
                   ÷ Σ market units across receiving dealer's existing band sectors)
```

60-min and 90-min averages are computed and applied independently. If New Forest absorbs a sector with 50 market units and achieves 5% share across their current 60-min zone, that sector projects 2.5 McLaren units.

**Capped at baseline.** If the receiving dealer's average share is *higher* than the sector's own historical share, we clip the new value at the sector's baseline. Removing a dealer must never manufacture extra network volume in a sector that is now further from any dealer — so a reassigned sector can only stay flat or drop, never rise.

### New dealer — UK network-average share

A newly-added dealer has no history. Sectors it absorbs are projected using the **UK-wide network average McLaren market share** across the full current network, computed separately for the 60-min and 90-min bands:

```
projected_units = total_market_units_in_sector
                × (Σ McLaren units across all UK 60-min [or 90-min] sectors
                   ÷ Σ market units across all UK 60-min [or 90-min] sectors)
```

Only sectors that were **previously uncovered open points** get re-shared with this network average — sectors already covered by another dealer keep their existing projection, so adding a dealer doesn't inflate the network total by re-basing in-network sectors.

**Graphhopper is mandatory** for adding a dealer. We no longer fall back to a great-circle estimate for new locations; if the routing engine is offline the Impact Analysis returns an error. Scenario routing uses sector centroids only (one query per sector, ~0.5 s for all sectors) so the UI stays responsive.

---

## 6. Impact Analysis: what you see when you add/remove

The per-dealer table has four numeric columns:

| Column | Meaning |
|---|---|
| **Baseline** | Units this dealer captures today. |
| **Absolute** | Units the dealer would capture if the changed sectors simply moved across at their *current* per-sector value — no share recalibration, no open-point revaluation. Isolates the pure reassignment effect. |
| **Scenario** | Units with all share logic applied: receiving-dealer share for reassigned sectors (capped at baseline), UK network share for new-dealer white-space absorptions, band-aware open-point share for dropped sectors. |
| **Δ** | Scenario − Baseline. Coloured red if it worsens open points. |

Comparing **Absolute vs Scenario** tells you how much of a dealer's delta is raw geography (sectors moving between catchments) versus market-share recalibration.

Bottom rows of the table:

- **In 90-min band** *(60-min view only)* — units captured by some dealer only in their outer 90-min band. Mutually exclusive with Open Points, so the table sums to the full network volume.
- **Open Points** — strict white space: units from sectors outside every dealer's 90-min catchment, re-valued at the band-aware open-point share. Adding a dealer can only shrink this number; if it ever grows (share-recalibration artefact) the row is flagged red.

Summary banner at the top:

- **New dealer captures** (positive): units from sectors now closer to the new pin than to any existing dealer.
- **Shifted from existing** (negative): losses on existing dealers *plus* the full volume of any removed dealer.
- **Net network change**: Σ dealer scenario − Σ dealer baseline + (scenario open points − baseline open points). For a pure removal this is always ≤ 0; for an add in genuine white space it's > 0; for an add that only redistributes coverage it's ≈ 0.
- **Map visual**: the new dealer's 60-min and 90-min catchment is drawn as a convex-hull polygon around the sector centroids it actually won, filled in its colour.

A blocking loading overlay is shown whenever a scenario is being recomputed (adding a dealer requires live Graphhopper routing and can take several seconds).

---

## 7. Architecture at a glance

```
┌────────────────────┐   Jinja templates
│ Flask (dev_app.py) │   FRONTEND/templates/*.html
│  routes /network-  │ → base.html, network_strategy.html,
│  strategy/*        │   volume_planning.html, impact_analysis.html,
└────────────────────┘   _ns_subnav.html (shared sub-nav)
         │
         ▼
┌────────────────────────────────┐
│ SHARED-CODE/                   │
│   network_strategy_api.py      │ ← thin API layer, returns dicts
│   network_strategy_service.py  │ ← heavy compute + caching
│   data_loader.py               │ ← all DB/Excel reads
│   db_connection.py             │ ← SQL Server pooled client
└────────────────────────────────┘
         │
         ▼
┌────────────────────────────────┐
│ FRONTEND/static/network_strategy/ │
│   territory.{js,css}            │
│   volume_planning.{js,css}      │
│   impact.{js,css}               │
│   leaflet-heat.js               │
└────────────────────────────────┘
```

Conventions:

- Templates extend `base.html`, use `{% block title/content/scripts %}`.
- All shared sub-nav comes from `_ns_subnav.html` — pass `active` ∈ `{'territory','volume','impact'}`.
- New JS uses vanilla ES5, no build step. CSS classes use `ns-` (shared) or `ia-` / `vp-` (page-local) prefixes and the McLaren dark-theme CSS variables.
- Map tiles: `https://{s}.basemaps.cartocdn.com/{light_all|dark_all}/{z}/{x}/{y}{r}.png`.
- Default UK view: centre `[53.5, -2.5]`, zoom 6.

Prod vs dev:

- `dev_app.py` runs standalone on port 5050 — used during development.
- `ROUTES_TO_ADD_TO_APP.py` contains the route snippets to paste into the production `app.py` (this repo is a feature module inside the main McLaren flask app).

---

## 8. Cheat-sheet of cache files

All under `SHARED-CODE/DRAFT_DATA/extracted/network_strategy/_cache/`:

| File | Built by | Read by |
|---|---|---|
| `sector_points.parquet` | `import_longair_sectors.py` | everything |
| `drive_time_matrix.parquet` | `build_network_strategy_caches.py` (Graphhopper) | assignment, add-dealer |
| `sector_assignment.parquet` | assignment step | summary, projections, scenarios |
| `catchments.geojson` | `dissolve_catchments()` | `/api/catchments` (Territory map) |
| `volume_plan.json` | Volume Planning `POST /api/volume-plan` | Impact baseline + scenario |

Delete any of these and the app degrades gracefully to "cache not found — run the build script".

---

## 9. One-minute talking-points for the meeting

- "The map shows every UK postcode sector coloured by the nearest dealer within 60 or 90 minutes of real road time."
- "Drive times are computed once with Graphhopper — an open-source routing engine — and cached. The app is instant because nothing is recalculated on page load."
- "Volume Planning lets the business set a target per segment; the tool spreads that target across every postcode sector by its share of historic registrations."
- "Impact Analysis then says: if you remove this dealer, which sectors fall out of 90-min coverage? If you add one here, which sectors move, which dealers lose units, and how much extra the network captures vs. just redistributes."
- "When a sector is reassigned from a removed dealer to a neighbour, projected units use the neighbour's own average McLaren share in that band — not the removed dealer's history, and capped at the sector's baseline so removals can never manufacture extra volume. For a brand-new dealer with no history, we use the UK network-wide average share, applied only to previously-open-point sectors it pulls into coverage."
- "Sectors that fall out of network coverage entirely are re-valued at a band-aware open-point share (separate averages for sectors previously inside a 60-min ring vs. only a 90-min band) — nothing vanishes, but white-space retention is realistic."
- "The Impact table shows **Baseline | Absolute | Scenario | Δ**. Absolute = pure geography (sectors move at current value); Scenario = full share recalibration; Scenario − Absolute isolates the market-share impact."
- "Adding a brand-new dealer is the only place the app touches Graphhopper live — and if the routing engine isn't running, we fall back to a calibrated straight-line estimate and flag the dealer as 'estimated'."

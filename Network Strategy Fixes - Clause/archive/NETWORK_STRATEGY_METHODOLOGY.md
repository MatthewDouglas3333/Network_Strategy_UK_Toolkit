# Network Strategy Toolkit — Methodology

This document explains, in plain English, exactly how the Network Strategy Toolkit
computes dealer catchments, allocates postcode sectors, and produces
impact-analysis results. It is designed so that anyone — commercial, IT, a
network committee member — can understand the mechanics without reading Python.

---

## 1. Scope

- **Geography:** United Kingdom (England, Wales, Scotland, Northern Ireland).
  Channel Islands and Isle of Man are explicitly excluded.
- **Mode of transport:** Private car, using the OpenStreetMap road network.
  No live traffic; free-flow times only.
- **Time bands:** 60 minutes and 90 minutes. A sector is "60-min covered" if
  any dealer reaches it in ≤60 min, "90-min covered" if ≤90 min but >60 min,
  otherwise "white space".

---

## 2. Data sources

| Source                                      | What we use it for                         |
|---------------------------------------------|--------------------------------------------|
| ONS Postcode Directory (ONSPD)              | Every live UK full postcode + its lat/lon  |
| ONS Postcode Sector Boundaries (GeoJSON)    | Drawing sector polygons on the map         |
| Industry Registrations file (2024–2025)     | Market volume by sector × sub-model × year |
| Segment lookup file                         | Mapping each sub-model to a market segment |
| OpenStreetMap Great Britain extract (`.pbf`)| The road graph used for drive times        |
| Network Database (internal)                 | List of current McLaren retail sites       |

---

## 3. Postcode sector = full postcode minus the last two characters

UK postcodes have two parts separated by a space:

- **Outward code** (2–4 chars): e.g. `SL6`, `M1`, `AB10`
- **Inward code** (3 chars): e.g. `8AB`, `1AA`

The **sector** is the outward code plus the first digit of the inward code —
equivalently, the full postcode minus the last two letters.

```
SL6 8AB  →  SL6 8
M1 1AA   →  M1 1
AB10 1AB →  AB10 1
```

There are approximately 12,000 populated sectors in the UK.

---

## 4. From a sector (an area) to a single drive-time number

A sector is a polygon, not a point. A dealer's drive time to "the sector"
depends on which bit of it you pick. We use a multi-point approach (Tier 2)
so the answer is robust for both small urban sectors and large rural ones.

### 4.1 Tier 2 sampling (default, always on)

For every sector, we sample **five representative points**:

1. **Population-weighted centroid** — the mean of all live full-postcode
   lat/lons within the sector. Because Royal Mail issues more postcodes
   where more households exist, this centroid naturally falls in the
   inhabited part of the sector.
2–5. **Four quartile points** — the full postcodes at the extreme north,
   south, east, and west of the sector. These catch cases where a large
   rural sector has customers along its edges rather than at its centre.

We ask the routing engine for the drive time from the dealer to each of the
five points and take the **median**. This is robust to one weird point
(e.g. a postcode on a motorway junction) and accurate for both tiny urban
sectors and wide rural sectors.

### 4.2 Tier 1 (diagnostic only)

A single-centroid drive time per sector. Faster but less accurate for wide
rural sectors. Not used in production; Tier 2 is always on.

### 4.3 Sectors with no live full postcodes

These are **excluded**. In practice they cover industrial estates or
decommissioned areas with zero households and therefore zero sales
potential.

---

## 5. The routing engine — Graphhopper, OpenStreetMap, no live traffic

- **Engine:** Graphhopper (open-source), running as a local Java service on
  the user's machine. No internet, no API keys, no admin rights required.
- **Road graph:** Great Britain extract from OpenStreetMap (Geofabrik).
  Updated manually every few months by replacing the extract file.
- **Profile:** Car, free-flow speeds from the OSM `maxspeed` tag where
  present, default speed limits by road class otherwise. No traffic model.
- **Speed-up:** Contraction Hierarchies (CH) pre-computed once; individual
  route queries take under a millisecond.

This matches the methodology used by commercial providers (HERE, TomTom,
Mapbox) minus the live-traffic layer. For **strategic network planning**,
free-flow is the conventional choice because it's the same for every
dealer on every day of the week — a fair comparison.

---

## 6. Drive-time matrix — one number for every (dealer, sector) pair

We compute a matrix of shape `N_dealers × N_sectors` containing the
Tier-2-median drive time in minutes.

- **Size:** ~20 × ~12,000 = ~240,000 numbers, but each requires 5 routing
  queries (Tier 2), so ~1.2 M queries per full rebuild.
- **Time:** ~1–3 minutes on a modern laptop, multi-threaded.
- **Cache:** stored as a Parquet file alongside the data. Rebuilt only
  when (a) the dealer list changes, or (b) the user clicks
  "Recompute drive times".

---

## 7. Sector → dealer assignment

For each sector, the assigned dealer is simply the dealer with the
**minimum drive time** to that sector, provided the drive time is ≤90 min.
The band is determined by the same minimum:

- `min ≤ 60 min` → band = **60-min**, dealer = argmin
- `60 < min ≤ 90` → band = **90-min**, dealer = argmin
- `min > 90 min` → **unassigned** (white space)

A sector is **always assigned to exactly one dealer** — ties are broken by
the lower `Site_Code` alphabetically, which is deterministic and invisible
in practice (exact ties are extremely rare at minute-level granularity).

---

## 8. Dealer catchments on the map

For each dealer and each band (60, 90), we take the sector polygons
assigned to that (dealer, band) and compute their geometric **union**
(dissolve). The result is one multi-polygon per (dealer, band) — this is
what you see coloured on the map.

Because the input polygons are administrative boundaries, the result:

- **Never extends into the sea.**
- **Never overlaps between dealers.**
- **Hugs islands and peninsulas naturally.**

We simplify the outline to ~50-metre tolerance before sending it to the
browser, so rendering is fast.

---

## 9. Registration overlays

The registrations file gives `Units` per `(Sector, Sub Model, Year)`.

- **Segment assignment:** each `Sub Model` is mapped to one `Segment` via
  the segment lookup file (e.g. `Porsche Macan` → `SUV`). Unmapped
  sub-models are logged and shown in an "Unmapped" bucket so the lookup
  can be corrected.
- **Aggregation:** choose a year (2024 or 2025), choose a segment. We sum
  `Units` per sector across matching rows → a single value per sector.
- **Visualisation:** a choropleth layer — each sector polygon is shaded
  by its value. The scale is quantile-based so that outliers (central
  London) don't wash out the rest of the country.

---

## 10. Impact Analysis — the three scenario modes

Every mode starts from the same **baseline state**: current dealers,
current assignment, current registration distribution.

### 10.1 No change — volume forecast slider

User sets a target UK annual volume for each segment (e.g. Core Supercar:
700 units, GT: 300, SUV: 400).

- **Segments McLaren already sells in** (Core Supercar, GT, etc.):
  Each sector's share = McLaren units in that sector ÷ McLaren UK total,
  taken from the registrations file filtered to the McLaren rows.
  Projected sector volume = `sector_share × user_target`. Roll up by
  assigned dealer to get each dealer's projected volume.

- **Segments McLaren does not yet sell** (e.g. SUV):
  We have no McLaren distribution to copy. Fall back to the market
  distribution for that segment instead: sector share = total units of
  that segment in that sector ÷ UK total of that segment. Same roll-up.

All share overrides operate on the **target-scaled per-segment unit
grid** (each segment's sector value = `market_units × sector_share × (target / total_McLaren)`)
so they stay consistent with the Volume Plan and with baseline totals.
Non-McLaren segments retain their market-distribution baseline and are
not re-shared.

### 10.2 Remove a dealer point (cascade reassignment)

Dealer X is removed from the active list:

1. The drive-time matrix column for X is dropped.
2. Assignment is **re-computed**. Sectors that had X as their nearest
   dealer are automatically **reassigned to their next-nearest dealer** —
   provided that dealer is within 90 min.
3. Sectors that **are** absorbed by a neighbouring dealer use that
   neighbour's **own average McLaren market share** for the relevant
   band, not the historical per-sector figure from X's old territory:

   ```
   projected_units(sector, seg) =
       market_units(sector, seg)
       × Σ McLaren units(neighbour, seg, band)
         / Σ market units(neighbour, seg, band)
       × target_scale(seg)
   ```

   60-min and 90-min averages are computed and applied independently,
   per McLaren segment. *Example:* New Forest absorbs a Core Supercar
   sector with 50 market units and achieves 5% Core Supercar share
   across their 60-min zone → 2.5 × target-scale projected units.

   **Capped at baseline.** The rewritten value is clipped to be ≤ the
   sector's original projected value in that segment. Removing a dealer
   must never manufacture extra volume in a sector that is now further
   from any dealer — a reassigned sector can only stay flat or drop.

4. Sectors with no remaining dealer within 90 min become **open
   points**. They are not zeroed — they are **re-valued at the
   band-aware open-point share**, empirically measured from today's
   uncovered sectors in the registrations file:

   - if the sector was previously inside someone's 60-min ring, apply
     the **60-min-derived open-point share** (average McLaren share
     across sectors outside every dealer's 60-min ring);
   - if the sector was previously only at 90 min, apply the
     **90-min-derived open-point share** (average across strict white
     space — sectors outside every dealer's 90-min ring).

   Shares are computed per segment. This gives a realistic, volume-
   conserving revaluation: nothing disappears, but white-space retention
   rates reflect reality.

5. Neighbouring dealers therefore see a **volume uplift** (they just
   inherited some of X's sectors) and open points pick up the re-valued
   residual. Summed across dealers + open points the change is always
   ≤ 0 for a pure removal.

### 10.3 Add a dealer point

New dealer Y is added at a lat/lon:

1. A single row is added to the drive-time matrix — Graphhopper computes
   Y's drive time to all ~12,000 sector centroids. Scenario routing uses
   centroids only (one query per sector, not the 5-point baseline
   sample) so the whole row lands in a few seconds.
2. **Graphhopper is mandatory.** There is no great-circle fallback for
   new dealers; if the routing engine is offline the scenario endpoint
   returns an error. Removal scenarios still work because they only use
   the cached matrix.
3. Assignment is re-computed. Sectors where Y is now the nearest dealer
   and within 90 min are **reassigned** from whichever dealer (or open
   point) previously held them.
4. **Only sectors that were previously open points** are re-shared. Y
   absorbs them using the **UK-wide network average McLaren share**,
   computed separately for the 60-min and 90-min bands and per segment:

   ```
   projected_units(sector, seg) =
       market_units(sector, seg)
       × Σ McLaren units(all covered sectors, seg, band)
         / Σ market units(all covered sectors, seg, band)
       × target_scale(seg)
   ```

   Sectors already covered by another dealer keep their existing
   projection — they simply move across under their current value.
   This prevents adding a dealer from inflating the network total by
   re-basing in-network sectors.

5. Volume shifts: Y's catchment gains its projected units; each
   affected existing dealer loses the contribution from sectors that
   moved to Y; open points shrinks by whatever Y pulled in from white
   space.

### 10.4 Absolute vs Scenario rollup

The Impact Analysis payload returns **two per-dealer rollups** against
the same scenario assignments:

- **Absolute** — runs the *original* baseline per-sector projection
  through the *scenario* assignments. No share recalibration, no open-
  point revaluation. Shows the pure geographic effect: "what each
  dealer captures if sectors just move across at their current value."
- **Scenario** — the full computation described in §10.2 / §10.3 with
  receiving-dealer share, UK network share, band-aware open-point
  share and the cap-at-baseline rule applied.

The UI shows both side by side. `Scenario − Absolute` is the
**market-share impact** — how much a dealer's delta comes from share
recalibration versus pure reassignment.

---

## 11. Live recalculation

Every scenario interaction — dragging a pin, moving a slider, toggling a
dealer — triggers an **in-memory recompute** against the cached matrix.
No routing API is hit unless a brand-new dealer location is added or
moved, and even then only a single row of sector centroids is fetched
(a few seconds end-to-end). The UI shows a blocking loading overlay
during add-dealer scenarios so the user never sees a half-rendered
state.

`dev_app.py` auto-starts Graphhopper in the background on boot (if it
isn't already listening on `http://127.0.0.1:8989`) so the tool is
self-contained for end-users.

---

## 12. Known limitations

- **Free-flow drive times only.** Morning rush-hour near London will be
  noticeably slower in reality.
- **Car profile only.** No consideration of train / plane journeys for
  edge-case Scottish island sectors.
- **Segment mapping depends entirely on the segment lookup file** being
  kept up to date as new sub-models launch.
- **Volume forecasts assume customer behaviour scales proportionally**
  with market distribution. A disruptive product launch (e.g. a
  first-ever SUV) could have a distribution that differs from the
  competitor baseline we borrow.
- **Northern Irish postcodes (BT) may be sparse** in the registrations
  file; check coverage before publishing NI-specific conclusions.
- **The OSM extract is a snapshot.** The first build used the
  `great-britain-260421.osm.pbf` extract (April 2021). GB motorway /
  A-road network changes very little year-to-year, so this is fine for
  strategic planning. To refresh, replace the `.pbf` file and run
  `scripts/recompute_drive_times.ps1`.

---

## 13. How to regenerate everything from scratch

If data files change, re-run in this order:

1. Update the raw file(s) in
   `SHARED-CODE/DRAFT_DATA/extracted/network_strategy/`.
2. Run `scripts/recompute_drive_times.ps1`. This rebuilds:
   - `_cache/sector_points.parquet` (from ONSPD)
   - `_cache/drive_time_matrix.parquet` (from Graphhopper)
   - `_cache/sector_assignment.parquet`
3. Restart the Flask app. The Territory Overview map will reflect the
   new data.

---

## 14. Glossary

| Term                | Meaning                                                         |
|---------------------|-----------------------------------------------------------------|
| Sector              | First 5–6 chars of a UK postcode, e.g. `SL6 8`. ~12,000 in UK.  |
| Outward code        | First half of a postcode, e.g. `SL6`.                           |
| Inward code         | Second half of a postcode, e.g. `8AB`.                          |
| ONSPD               | ONS Postcode Directory — the master list of UK postcodes.       |
| Isochrone           | Polygon showing "everywhere you can reach in X minutes".        |
| Dissolve            | Merging many small polygons into one big one by removing shared borders. |
| Contraction Hierarchies (CH) | A graph pre-processing technique that makes shortest-path queries ~1000x faster. |
| Cannibalisation     | When a new dealer takes sales from an existing one nearby.      |
| White space         | UK area not reachable by any dealer within 90 min.              |

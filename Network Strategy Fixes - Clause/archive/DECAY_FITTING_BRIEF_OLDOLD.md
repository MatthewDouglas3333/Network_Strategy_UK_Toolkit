# Competitive Share Model — Decay Curve Fitting Brief

**Audience:** Coding agent executing the analysis end-to-end.

**Deliverable:** A validated, per-segment decay curve configuration plus a cleaned registrations dataset, ready to plug into the Network Strategy Toolkit as the input to a new Competitive Share model.

**Context.** The existing Network Strategy Toolkit uses a "territory share" model where every sector inside a dealer's drive-time catchment is projected at the same share. This produces known artefacts — removals looking positive in isolated regions, adds looking equivalent in very different competitive contexts, dealer type ignored, hard cliffs at band boundaries. We are replacing it with a model that uses a smooth distance-decay function per segment, combined with a competitor-accessibility term. This brief is **step 1** of that replacement: fitting the decay curves from real market data. Once the output of this brief is validated, a separate rebuild plan will integrate the curves into the tool.

---

## 1. Objective

For every supercar / luxury segment in the competitive universe, produce a **distance-decay function** that describes how market share realises as drive time to the nearest relevant dealer increases.

The decay curve shape will be exponential:

```
accessibility(t) = exp(-t / k)
```

where `t` is drive time in minutes and `k` is the characteristic distance — the free parameter being fitted. A low `k` means share collapses quickly with distance (steep decay, typical of daily-driver products); a high `k` means share is robust to distance (flat decay, typical of destination purchases).

Output is a single YAML / JSON configuration file the toolkit can load at runtime.

**One `k` per segment. Where data supports it, one `k` per (segment × urban/rural) combination.** No global curve. No brand-specific curve.

---

## 2. Decisions already taken (do not re-open)

These were debated and settled before this brief was written. The agent should not re-derive them:

| Decision | Resolution |
|---|---|
| Curve family | Exponential decay (`exp(-t/k)`), not inverse, not step-bands |
| Who fits the curves | Per-segment fit from **full competitive segment market**, not McLaren-only. McLaren data is validation-only |
| Scope of competitor network for SUV | **Use the competitor dealer file as-is.** SUV competitor dealer set = the brands listed in the SUV row of the segment lookup. Do **not** widen to include Porsche, Range Rover, BMW, Mercedes G-Class, etc. — user's explicit call |
| Time horizon of registrations data | **2020–2025** first pass. User can supply 2012 onwards; we do not request the full history unless segments fail to fit |
| Model architecture | **Replace** the existing share model entirely — no parallel "territory vs competitive" dual-display. One number per sector, which the user understands and owns |
| Tool applicability by segment | Hypercar is **excluded** from the decay model — volume too low (33 UK units in 2024–25) and purchase mechanism (allocation, not retail) doesn't fit the framework |
| Committee framing | Not a goal. The tool must work for the user as a network-strategy manager; committee usability is downstream |

---

## 3. Inputs

### 3.1 Files the agent should expect on disk

| Path | Role |
|---|---|
| `SHARED-CODE/DRAFT_DATA/extracted/network_strategy/registrations_2020_2025.csv` | Competitor & McLaren registrations by sector × sub-model × year. User will extend beyond current 2024–2025 file before this brief is run |
| `McLaren_Registration_Segment.xlsx` | Sub-model → segment lookup |
| `Network_Database.xlsx` | McLaren dealer locations, types (Full Sales & Service / Sales Only / Service Only), lat/lon |
| `Competitor_Dealer_Database.xlsx` | Competitor dealer locations: brand, Dealer Format, lat/lon |
| `_cache/drive_time_matrix.parquet` | McLaren dealer → sector drive-time matrix (existing) |
| `_cache/sector_points.parquet` | Sector centroids |
| ONS sector-level rural/urban classification | See §6.4 — may need sourcing |

### 3.2 Files the agent must build

| Path | Role |
|---|---|
| `_cache/competitor_drive_time_matrix.parquet` | Competitor dealer → sector drive-time matrix. New build, same Graphhopper instance as the McLaren matrix |
| `_cache/registrations_cleaned.parquet` | Cleaned, in-segment, de-distorted registrations dataset (§4) |
| `_cache/exclusions_audit.csv` | Every row removed from registrations during cleaning, with reason |
| `config/decay_curves.yaml` | Final fitted `k` per segment, plus rural/urban variants where supported. The deliverable |

---

## 4. Data cleaning — run before anything else

The raw registrations file contains distortions that will wreck the decay fit if left in. Cleaning is a first-class step, not a preamble.

### 4.1 Filter to in-segment rows only

The raw file contains volume product (Porsche Macan, Cayenne, Taycan, 911 Carrera, 718 etc.) that is **not** in the segment lookup. These rows must be excluded. The filter:

```python
df_segmented = df.merge(
    segment_lookup[['Sub Model', 'Segment']].drop_duplicates(),
    on='Sub Model',
    how='inner'   # inner join drops unmatched rows
)
```

**Sanity check the agent must run:** log pre-filter and post-filter unit totals. Expect roughly an 80% reduction in units after filtering (2024–2025 sample: 47,763 raw units → 9,650 in-segment units). If the reduction is much smaller, the segment lookup has silently gained rows and the fit will include volume product. Halt and investigate.

### 4.2 Strip HQ / factory / head-office registrations

Manufacturer self-registrations (press fleet, demo pool, employee cars, pre-delivery stock) concentrate at factory and UK head-office postcodes. Left in, they distort the decay curve at the zero-distance end and artificially steepen every fitted `k`.

**Observed in 2024–2025 data alone:**

- McLaren: 132 of 404 UK McLaren units (33%) sit in a single sector, GU21 4 (Woking HQ)
- Aston Martin: 112 units in CV35 0 (Gaydon HQ)
- Bentley: 259 units across CW1 postcodes (Crewe HQ and factory)
- Rolls-Royce: 53 units in PO18 0 (Goodwood HQ)
- Ferrari / Aston / Lambo / Bentley / Porsche: combined 187 units in the SL area (Slough — multi-brand UK head-office cluster)

**Cleaning procedure:**

**(a) Hard exclusion list (provided by user + agent research, verified by user before use):**

User to provide from their knowledge:
- McLaren — GU21 4 (Woking)
- [user to complete for any others they know directly]

Agent to research from public sources (OEM UK websites, Companies House registered addresses, press materials) and present for user verification before applying:
- Aston Martin UK HQ / Gaydon factory postcodes
- Bentley Crewe factory and UK HQ postcodes
- Rolls-Royce Goodwood postcodes
- Ferrari UK head office (Slough area — specific postcode)
- Lamborghini UK (Pangbourne area — specific postcode)
- Maserati UK
- Any other manufacturer head offices visible in the data

The agent presents a table of proposed exclusions (brand, postcode sector, rationale, source URL) and waits for user sign-off before applying them. Once signed off, the list lives in `config/hq_exclusions.yaml` and is version-controlled.

**(b) Statistical outlier detection:** for each brand, compute the distribution of units across sectors. Flag any sector holding more than **5% of a brand's total UK registrations in any single year** as a candidate for exclusion. These are typically press fleets, demo pools, or corporate leasing concentrations that aren't obvious HQ sectors. The agent produces a second list of candidates with brand, sector, units, % of brand total — user reviews each one and marks keep / exclude / needs more investigation.

**(c) Scope of the exclusion:** HQ sectors are excluded **only for the brand whose HQ it is**, not for all brands. Ferrari sales in CV35 0 (Gaydon) are retained; only Aston Martin sales in CV35 0 are stripped. The cleaning is brand-scoped.

**(d) Apply per-year, not aggregate.** A sector that was a press-fleet hub in 2014 may not be in 2024. For each year of data, apply detection independently. HQ/factory exclusions are stable year to year; statistical-outlier exclusions are not.

**(e) Keep raw totals for volume forecasting.** The cleaned dataset is used for **share calibration and decay fitting only**. The raw dataset (with HQ sectors included) remains the source for market volume totals, because factory registrations are real economic activity even if they don't represent retail purchase behaviour. The agent maintains two parquet outputs: `registrations_raw.parquet` (in-segment filter only) and `registrations_cleaned.parquet` (in-segment filter + HQ/outlier exclusions).

### 4.3 Handle Northern Ireland explicitly

NI (BT postcodes) has 191 competitor units across 63 sectors in 2024–25, zero McLaren, and the nearest McLaren dealer is on the GB mainland requiring a ferry or flight. "Drive time" is not a meaningful concept for NI → GB.

**Rule:** NI sectors are **excluded from the decay fitting step** for every segment. NI retains its own handling in the downstream model (effectively always white-space, served by the GB network opportunistically). This needs to be documented as an assumption, not hidden.

### 4.4 Time-period consistency

Confirm 2024 vs 2025 volumes are both complete-year. Sample check already done: in-segment market is down ~7% YoY (5,008 → 4,642), McLaren specifically down 29% (236 → 168). McLaren's drop is larger than market and is likely product-cycle (late 720S life, Artura ramp). Proceed as though both years are complete unless the agent finds evidence otherwise in the extended 2020–2023 data.

---

## 5. Build the competitor drive-time matrix

### 5.1 Why this is needed

The existing `drive_time_matrix.parquet` covers McLaren dealers → sectors only. The competitive share model needs competitor accessibility — which means drive times from **every competitor dealer** to every sector.

### 5.2 Method

Using the same Graphhopper instance that produces the McLaren matrix:

- 100 competitor dealers × ~9,500 UK sectors = ~950,000 queries
- One query per (dealer, sector centroid) pair — centroids only, not the 5-point Tier-2 sampling, same as the "add a dealer" live-routing path
- At ~5 ms per query warm, this is ~80 minutes single-threaded, well under 10 minutes multi-threaded
- Cache to `_cache/competitor_drive_time_matrix.parquet` with columns `dealer_id`, `sector`, `drive_time_minutes`

### 5.3 Data structure

```
competitor_drive_time_matrix
├── dealer_id      (FK to competitor dealer table)
├── brand          (denormalised for filter speed — Ferrari, Lamborghini, etc.)
├── dealer_format  (Sales & Service / Sales Only / Service Only)
├── sector         (postcode sector, e.g. "SW1A 1")
└── drive_time_min (float, minutes)
```

### 5.4 Dealer-type weighting

Not every competitor dealer contributes equally to a sector's competitive pressure. A Sales & Service point is fully competitive; a Service Only point doesn't help the customer buy a new car.

Apply these multipliers when summing accessibility:

| Dealer Format | Acquisition weight | Ownership weight |
|---|---|---|
| Sales & Service | 1.0 | 1.0 |
| Sales Only | 0.9 | 0.2 |
| Service Only | 0.0 | 1.0 |

The decay-curve fit uses **acquisition weights** (we're modelling purchase share). The ownership weights are logged for future use by the retention module but not applied in this brief.

These weights are starting values — see §7.3 for the sensitivity check.

---

## 6. The fit — segment by segment

### 6.1 Segment scope

| Segment | 2024–25 market units | Fitting approach | McLaren status |
|---|---|---|---|
| Core Supercar | 2,337 | Fit from full segment | McLaren competes |
| GT | 3,147 | Fit from full segment | McLaren competes |
| Upper GT | 595 | Fit from full segment | McLaren does not yet compete |
| Upper Supercar | 328 | Fit from full segment | McLaren does not yet compete |
| SUV | 3,210 | Fit from full segment | McLaren does not yet compete |
| Hypercar | 33 | **Excluded from model** | Allocation-driven, not drive-time-driven |

### 6.2 The fitting procedure per segment

For each segment independently:

**Step 1 — Build the per-sector share series.**

```
For each sector s:
    segment_market_units[s]   = sum of in-segment competitor+McLaren units in sector s
    nearest_dealer_distance[s] = min drive time from s to any dealer in the
                                  segment's dealer set (see §6.3)
```

The dealer set is the union of McLaren dealers and competitor dealers whose brand sells in that segment. Use acquisition weights (§5.4) when computing "nearest": a Sales Only dealer at 20 minutes is equivalent for acquisition to a Sales & Service dealer at 20 minutes, but Service Only points do not count toward nearest-dealer distance because they don't sell cars.

**Step 2 — Normalise for market size.**

We cannot fit "units vs distance" directly because rural sectors have fewer people. Instead fit **realised share per sector** relative to an expected baseline:

```
expected_units[s]  = total_segment_units × (total_population[s] / UK_population)
realised_share[s]  = actual_segment_units[s] / expected_units[s]
```

A realised_share of 1.0 means the sector bought its population-proportionate share of the segment. Above 1.0: over-indexed. Below 1.0: under-indexed.

Use the per-sector household count from the ONS sector boundary data (or sector_points.parquet's point count as a proxy if households aren't joinable) as the population denominator.

**Step 3 — Bin by drive time, fit the curve.**

Group sectors into 5-minute drive-time bins: [0–5), [5–10), [10–15), ... [85–90), [90+).

For each bin, compute the mean `realised_share` weighted by `expected_units[s]` (so high-population bins don't get dominated by one low-volume sector). This gives an empirical decay curve: average share at each drive-time distance.

Fit `realised_share(t) = A × exp(-t / k) + C` by non-linear least squares, where:
- `k` is the characteristic distance we care about
- `A` is the near-dealer peak share (sanity check: should be > 1)
- `C` is the asymptotic floor (sanity check: should be ≥ 0, typically 0.05–0.15 for supercar segments — the "determined buyer" tail)

Report `k`, `A`, `C`, R², and a residuals plot for each segment.

**Step 4 — Bootstrap for confidence intervals.**

Given sample sizes are modest (Upper GT: 595 units), fit with bootstrap resampling (1,000 iterations, sampling sectors with replacement). Report the 5th and 95th percentile of `k` per segment. If the 90% CI spans a factor of 2× or more (e.g. k = [20, 50]), the fit is fragile and the agent flags it — may need to extend the time series backwards.

### 6.3 Segment-specific dealer sets

For each segment, the dealer set is built from the segment lookup. Check which brands appear in that segment's row and include their dealers:

| Segment | Brands included (from segment lookup) |
|---|---|
| Core Supercar | McLaren, Ferrari, Porsche (911 GT-cars only), Lamborghini, Maserati |
| GT | McLaren, Porsche (911 Turbo only), Mercedes-Benz AMG, Ferrari, Bentley, Aston Martin, Maserati, Ford |
| Upper GT | Ferrari, Rolls-Royce, Aston Martin |
| Upper Supercar | Lamborghini, Ferrari |
| SUV | Bentley, Rolls-Royce, Aston Martin, Ferrari, Lamborghini |
| Hypercar | (excluded) |

**Important for Porsche:** the competitor dealer file has no Porsche dealers. This is correct — a Porsche Centre primarily sells Macans and Cayennes and does not meaningfully serve a supercar buyer, even though the GT3/Turbo is on-site. For segments where Porsche is listed as a competitor (Core Supercar, GT), the agent **uses Porsche sales data** in the market-volume term but **does not count Porsche dealer locations** in the competitor accessibility term. User's explicit decision — do not re-open.

**For SUV specifically:** the competitor dealer set is the five brands in the SUV row of the segment lookup (Bentley, Rolls-Royce, Aston Martin, Ferrari, Lamborghini). Do **not** add Porsche, Range Rover, BMW or Mercedes. User's explicit decision — this is a known limitation on SUV calibration and is accepted.

### 6.4 Urban / rural split

For each segment, additionally fit `k` separately on urban vs rural sectors using the ONS Rural-Urban Classification (RUC11). Sectors classified A1/B1/C1/C2 (urban major / urban minor / urban in sparse / urban in sparse settlement) are urban; everything else is rural.

Fit the split only if each subset has ≥200 in-segment units. Otherwise report segment-level `k` only.

Expected pattern to sanity-check against:
- Core Supercar, GT, Upper GT, Upper Supercar: urban and rural `k` should be similar (flat decay either way — destination purchases)
- SUV: rural `k` should be meaningfully higher than urban `k`. Rural SUV buyers are used to travelling; urban SUV buyers have more alternatives within short drives

If SUV comes back with similar urban/rural `k`, investigate — either the data is too thin, the urban/rural classifier is too coarse, or the expected pattern isn't real. Don't just accept the number.

---

## 7. Validation

The fitted curves must survive these checks before being written to the config file.

### 7.1 Hold out McLaren data and predict it

McLaren registrations were excluded from the fit. Now use the fitted Core Supercar and GT curves to predict McLaren's sector-level volumes, and compare to actuals.

For each McLaren-active sector:
```
predicted_McLaren_share[s] = national_McLaren_share 
                           × accessibility_from_McLaren_network[s]
                           / (accessibility_from_McLaren_network[s] 
                              + accessibility_from_competitor_network[s])
```

Report mean absolute error and correlation at sector level (for sectors with ≥2 McLaren units — singletons are too noisy). Target: correlation > 0.5. Below that, the model isn't capturing reality well enough to trust.

### 7.2 Historical dealer-change validation

If the user can supply details of any dealer open / close / relocation in the last 5 years with pre/post volume data, run that scenario through the fitted model and compare projected to actual change. Three historical cases would be enough for a credibility check.

If the user cannot supply any, this validation is skipped — note it as a gap to fill later.

### 7.3 Sensitivity checks

Re-fit each segment with these perturbations and report how `k` changes:

- Include HQ/factory sectors (confirms the cleaning matters)
- Drop 2020–2021 data (tests COVID distortion)
- Halve the Sales Only / Service Only weights to 0.5 / 0.0 (tests weighting assumptions)
- Use all registrations including volume product (confirms the in-segment filter matters — `k` should shift dramatically; if it doesn't, something is wrong)

Any segment whose fitted `k` changes by more than 30% under any of these perturbations is **flagged as fragile**. The config file records the fragility flag so the downstream tool can surface it to the user.

### 7.4 Regional sanity check

Predict share for five very different regions using the fitted curves and eyeball the results:
- Central London (SW1, SW3, W1)
- Cheshire (WA16, SK9)
- Edinburgh (EH10, EH12)
- Highlands (IV2, PH1)
- Cornwall (TR1, PL1)

If the Highlands or Cornwall come back projecting meaningful McLaren share despite being 90+ minutes from any dealer, something is wrong with the floor term `C`. If central London comes back below network average, something is wrong with the near-dealer peak `A`. These are just gut-checks — but flagrant failures here mean the fit needs redoing.

---

## 8. Output — what the agent delivers

### 8.1 `config/decay_curves.yaml`

Single source of truth for the downstream tool:

```yaml
# Generated by decay fitting pipeline
# Source: registrations_2020_2025.csv (cleaned)
# Fit date: <date>
# McLaren holdout correlation: <value>

segments:
  core_supercar:
    k: 47.2                      # minutes
    k_ci_low: 38.1               # 5th percentile bootstrap
    k_ci_high: 56.8              # 95th percentile
    A: 1.85                      # near-dealer peak multiplier
    C: 0.08                      # asymptotic share floor
    r_squared: 0.74
    fragile: false
    urban:
      k: 45.1
      A: 1.82
      C: 0.07
    rural:
      k: 49.4
      A: 1.88
      C: 0.09
    brands: [McLaren, Ferrari, Porsche, Lamborghini, Maserati]
    n_units_fitted: <int>

  gt:
    # ... same structure ...

  upper_gt:
    # ... same structure ...

  upper_supercar:
    # ... same structure ...

  suv:
    k: 28.5                      # expected steeper than supercar
    # ... same structure ...
    mclaren_status: not_yet_selling
    calibration_notes: |
      Competitor dealer set limited to 5 brands in SUV segment lookup.
      Does not include Porsche, Range Rover, BMW, Mercedes G-Class.
      Known under-estimate of true SUV competitive density.

  hypercar:
    excluded: true
    reason: "Allocation-driven purchase. 33 UK units in 2024-25 insufficient to fit."

dealer_type_weights:
  acquisition:
    full_sales_and_service: 1.0
    sales_only: 0.9
    service_only: 0.0
  ownership:
    full_sales_and_service: 1.0
    sales_only: 0.2
    service_only: 1.0
```

### 8.2 Supporting files

- `_cache/registrations_cleaned.parquet` — in-segment rows with HQ/outlier exclusions applied
- `_cache/registrations_raw.parquet` — in-segment rows only (for volume totals downstream)
- `_cache/exclusions_audit.csv` — every row removed, with brand, sector, year, units, reason
- `_cache/competitor_drive_time_matrix.parquet` — new drive-time matrix
- `config/hq_exclusions.yaml` — user-signed-off HQ postcode list

### 8.3 Analysis report

A single markdown report `DECAY_FIT_REPORT.md` containing:

1. Data volumes pre/post cleaning (the sanity-check numbers)
2. HQ exclusion list as applied, with user sign-off date
3. Fitted `k` per segment with bootstrap CI
4. The decay curves plotted (one chart per segment, all segments on one chart for comparison)
5. Urban vs rural comparison where fit
6. Validation results (McLaren holdout correlation, regional sanity check, any historical dealer-change backtests)
7. Sensitivity checks table
8. Fragility flags and recommended next steps

---

## 9. Sequencing and stop-points

The agent does **not** execute end-to-end without user checkpoints. Three mandatory stops:

**Stop 1 — After §4.2(a) HQ list research.** Agent presents the researched HQ postcode table to the user for sign-off before applying exclusions. User reviews, confirms, and the cleaning proceeds.

**Stop 2 — After §4.2(b) statistical-outlier detection.** Agent presents the flagged sectors for user review. User marks keep / exclude / investigate per row. Only after sign-off does the cleaning proceed.

**Stop 3 — After §7 validation, before writing `decay_curves.yaml`.** Agent presents the full report to the user. User accepts, rejects, or requests re-fit with different parameters. Only after sign-off does the config file become authoritative.

---

## 10. Known limitations (document in the final report)

- Dealer allocation constraints on McLaren sales mean the fitted curve partially reflects supply patterns, not just demand. Cannot be fixed from this data alone.
- Dealer-relationship loyalty (existing customers returning to the same dealer group regardless of distance) is invisible in the data and adds noise.
- 2020–2021 may be COVID-distorted; agent tests this in sensitivity checks but cannot fully isolate the effect.
- Northern Ireland excluded from fit; retained as separate downstream handling.
- SUV competitor dealer set limited by user decision — calibration will be revisited post-launch with McLaren's own SUV registrations as they accumulate.
- Hypercar segment not modelled.
- Free-flow drive times only (same as existing toolkit). No traffic, no time-of-day.

---

## 11. What happens next (out of scope for this brief)

Once `decay_curves.yaml` is validated and signed off:

1. A separate rebuild plan will integrate the curves into `network_strategy_api.py`, replacing the existing share calculation.
2. The new model computes `competitive_position(sector, segment)` per sector per segment per scenario, and uses that as the projected share.
3. Add-dealer and remove-dealer scenarios both use the same function — no asymmetry, no cap-at-baseline, no band artefacts.
4. The volume planner gains a per-segment toggle: when the user switches McLaren into SUV / Upper GT / Upper Supercar, the tool picks up the already-fitted curve for that segment automatically. No code change required to enter a new segment — it's a config flip.

That rebuild is written separately once this brief's output is in hand.

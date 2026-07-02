# Issue 2 — Wealth-Based Normalisation

**Status:** In progress (substantive decisions agreed; minor sensitivity-test specification and McLaren holdout structure still open)
**Date:** 1 May 2026
**Relates to:** `DECAY_FITTING_BRIEF.md` §6.2 Step 2, §7.1, §10

---

## The problem

§6.2 Step 2 of the brief normalises sector-level sales by population:

```
expected_units[s]  = total_segment_units × (total_population[s] / UK_population)
realised_share[s]  = actual_segment_units[s] / expected_units[s]
```

The decay fit then attributes the gap between expected and realised share to drive-time accessibility.

This is the right approach for mass-market products. For supercars it is structurally wrong because supercar buyers are not evenly distributed across the population. They are heavily concentrated in high-wealth sectors — central London, Surrey, Cheshire, Edinburgh, the Cotswolds, Hertfordshire commuter belt. A £200k car purchase isn't constrained by population; it is constrained by household wealth.

### How the bias enters the fit

Population-normalisation produces systematic geographic errors that propagate into the decay parameters:

- **Wealthy near-dealer sectors** (e.g. SW1) — population-normalisation expects very few sales; reality shows many. The fit reads this as "share peaks dramatically near dealers" → inflates `A`
- **Wealthy far-from-dealer sectors** (e.g. wealthy rural Cheshire) — population-normalisation expects average sales; reality shows above average. The fit reads this as "share is robust to distance" → inflates `k`
- **Poor near-dealer sectors** (e.g. urban Birmingham) — population expects average, reality is below. The fit reads this as evidence of decay → deflates `k`

These errors are *not* random noise. UK dealer locations are strongly correlated with wealth — Ferrari, McLaren, Lamborghini and Aston Martin all locate near where their customers live. Wealthy areas are dealer-near areas, on average. This means the population-normalisation errors are *correlated with the variable being fitted* (drive time), which biases the decay parameters in a specific direction rather than averaging out.

Net effect: the fit will conclude the network is more powerful than it is and decay is gentler than it is. Downstream, remove-dealer scenarios will under-estimate share loss, and add-dealer scenarios in wealthy white-space will under-estimate gains.

### Why a single wealth measure isn't enough

No single publicly available wealth measure captures supercar buyer geography cleanly:

| Measure | What it captures | Blind spot |
|---|---|---|
| Council Tax Band H proportion | Stock concentration of "valuable homes" | Cannot distinguish £1m homes from £5m homes — both are Band H. Also based on 1991 valuations, geographically biased |
| ONS MSOA income | Working-age earning power | Misses retirees, business owners, capital-wealth households. Modelled not measured at MSOA level |
| Land Registry property prices | Current values, with right-tail discrimination | Only sees traded homes; misses long-held high-value stock |

Each measure has a structural blind spot that another covers. A composite combining them is sharper than any individual measure.

---

## Why right-tail concentration matters specifically — embedded in the design

A £200k purchase represents a meaningfully different fraction of disposable wealth for a household with a £1m home versus a £10m home. The £1m homeowner stretches; the £10m homeowner doesn't notice. This means supercar demand should *not* scale linearly with wealth — sectors with concentrations of *very* high property values should be expected to over-index disproportionately.

This insight is embedded in the Land Registry banded score (Decision G below). Three bands (£1–2m / £2–4m / £4m+) with weights 1/2/4 explicitly say "a £4m+ home contributes 4× the expected supercar demand of a £1–2m home." This is a substantive prior baked into the model and is sensitivity-tested rather than assumed correct.

---

## The agreed solution

### Decision E — Replace population normalisation with a wealth-based composite

The §6.2 Step 2 formula changes from:

```
expected_units[s] = total_segment_units × (population[s] / UK_population)
```

to:

```
expected_units[s] = total_segment_units × (wealth_composite[s] / UK_wealth_composite_total)
```

Where `wealth_composite[s]` is a weighted combination of three measures (Decision F).

This is the substantive correction to the brief. The decay fit will subsequently attribute residual share variation to drive time, against a baseline that reflects where supercar buyers actually live rather than where the general population lives.

### Decision F — Composite structure: Land Registry / Band H / ONS income, weights 0.50 / 0.35 / 0.15

Three measures, each normalised to a 0–1 scale across UK sectors, then combined via weighted average:

```
wealth_composite[s] = 0.50 × land_reg_norm[s]
                    + 0.35 × band_h_norm[s]
                    + 0.15 × income_norm[s]
```

**Reasoning for weights:**

- **Land Registry banded score (0.50)** — most direct measure of what we care about. Built from current (post-indexation) property values, with explicit right-tail discrimination via the £1m/£2m/£4m bands. The strongest single proxy for supercar buying capacity is owning a home worth several million pounds, and this measure captures that directly.

- **Band H proportion (0.35)** — captures stock that Land Registry can't see. A wealthy retiree in a £4m home that hasn't traded since 1985 doesn't appear in Land Registry but does appear in Band H. Useful as broad-coverage support, but blunter than Land Registry because it can't distinguish between value tiers within Band H.

- **ONS MSOA income (0.15)** — lowest weight. Three reasons. (i) Income is structurally a weaker signal of supercar buying than housing wealth — supercar buyers are predominantly retirees with capital, business owners with patchy income, equity-comp executives, and inheritors, none of whom show cleanly in PAYE-dominated income data. (ii) The MSOA income figure is modelled, not measured (regression projection from census variables), with wide CIs in the tail. (iii) Income is partly redundant with the housing measures because the ONS income model uses housing-tenure variables as predictors. Income still adds *something* (catches working-age high-earner sectors the housing measures miss; dampens the 1991-valuation bias of Band H by introducing current data) — hence not zero — but clearly tertiary.

**Sensitivity testing:** Because the weights are a judgement, the §7.3 sensitivity step adds a composite-weight bracket: re-fit with weights (0.50, 0.35, 0.15), (0.60, 0.30, 0.10) [stronger Land Registry lead], (0.40, 0.40, 0.20) [Land Registry and Band H tied as primary]. If `k` is robust across these, the precise weights don't matter much. If `k` swings, the composite is sensitive and the final report flags it.

### Decision G — Land Registry banded score: 10-year window, LA-level indexation, weighted-sum aggregation

For each sector, the Land Registry score is constructed as follows:

1. **Source:** HMLR Price Paid file (full UK transactions since 1995)
2. **Filter:** Transactions in the last 10 years
3. **Index to today's value:** Each transaction's sold-price is uplifted using the LA-level UK House Price Index (HMLR), so a £1.8m transaction from 2018 becomes its today-equivalent value before band assignment
4. **Band assignment** (using indexed value):
   - Band 1: £1m – £2m
   - Band 2: £2m – £4m
   - Band 3: £4m+
5. **Aggregate per sector:** Count transactions in each band
6. **Weighted-sum score:**

   ```
   land_reg_score[s] = 1 × count_band1[s]
                     + 2 × count_band2[s]
                     + 4 × count_band3[s]
   ```

7. **Volume check:** If total transactions in sector < 20, mark Land Registry score as missing — fall back to Band H + income only with proportional reweighting (see Decision H)

8. **UK-wide thresholds** — same £1m / £2m / £4m bands across England, Scotland, Wales. Scotland will look thinner across all bands by absolute terms; this is broadly consistent with absolute supercar demand patterns.

**Why 10-year window:** more transactions per sector, especially in the £4m+ band where activity is sparse. Indexation methodology is reliable over this span. Trade-off acknowledged: 10 years includes periods where geography of wealth itself shifted (Brexit aftermath, COVID re-rating of out-of-London markets). Indexation handles price-level changes but cannot undo geographic shifts. We are effectively assuming today's geography of wealth is the right baseline — same assumption the rest of the model makes — but it is documented.

**Why LA-level indexation:** national-level over-corrects for some areas and under-corrects for others. LA-level is the best free-data option. Specialist prime-property indices (Knight Frank, Savills) would be slightly better at the very top of the market but are paid products.

**Why band weights 1/2/4:** embeds the right-tail concentration hypothesis (£4m+ home contributes 4× the expected supercar demand of a £1–2m home). Sensitivity tested at §7.3 with alternative weights (1/2/4) [default], (1/3/9) [steeper], (1/1.5/2) [flatter], (1/1/1) [no right-tail effect].

### Decision H — Low-volume sector fallback

For any sector with fewer than 20 transactions in the indexed 10-year window:

- Mark Land Registry component as missing for that sector
- Composite uses only Band H + ONS income, with weights renormalised:
  - Band H: 0.35 / (0.35 + 0.15) ≈ 0.70
  - Income: 0.15 / (0.35 + 0.15) ≈ 0.30
- Log every sector hitting the fallback in an audit file (`_cache/wealth_fallback_audit.csv`)

**Why 20:** judgement threshold chosen so that the £4m+ band has a reasonable chance of containing at least one transaction in any genuinely high-end sector. Could be tested at 10 / 20 / 30 as a sensitivity but unlikely to materially change `k`.

**Expected fallback rate:** likely 5–15% of UK sectors will fall below the threshold (mostly rural Scotland, parts of rural Wales, low-density industrial sectors). The audit file lets us spot-check that the fallback isn't being mis-applied to sectors where it'd matter for the fit.

### Decision I — Within-nation normalisation for Band H; UK-wide for ONS income

**Band H — within-nation:**
Scotland's council tax bands are based on 1991 valuations of Scottish properties, which were systematically lower than English values for equivalent homes. Scottish Band H is broadly equivalent to "very valuable for Scotland" rather than "very valuable in absolute terms." Within-nation normalisation treats Scottish sectors against the Scottish Band H distribution and English sectors against the English distribution before combining into the composite. Wales follows the same logic.

**ONS income — UK-wide:**
ONS income figures are current and produced on a consistent methodology UK-wide. No 1991-style bias to correct. Within-nation normalisation here would actually distort by treating "high-income for Scotland" and "high-income for England" as equivalent, which they aren't in absolute terms — and absolute-wealth signal is what supercar demand tracks.

**Land Registry — UK-wide thresholds (already noted above):** £1m / £2m / £4m apply uniformly. Scotland looks thinner, which is broadly correct in absolute terms.

### Decision J — Land Registry banded score as McLaren §7.1 holdout cross-check

The §7.1 validation step (predict McLaren sector volumes using the fitted curve, compare to actuals) becomes a *comparison across normalisation choices*:

1. Predict McLaren sector volumes using the fitted curve under the agreed composite (0.50/0.35/0.15)
2. Re-predict using Land Registry banded score *alone* as the normalisation
3. Re-predict using Band H *alone* as the normalisation
4. Compare correlation with McLaren actuals across the three

Whichever normalisation predicts McLaren actuals best gives the strongest validation evidence. If the agreed composite wins (or ties), composite is confirmed. If single-measure normalisations beat it, the composite needs revisiting before sign-off.

This adds value beyond the standard §7.1 holdout because it lets the McLaren data speak to the *normalisation choice itself*, not just to the curve parameters.

---

## Geographic plumbing — what needs building

The brief assumed the population-normalisation step was straightforward because population data is already available at sector level. Wealth-proxy data isn't. A small geographic pipeline is added to scope:

| Dataset | Source | Native granularity | Join needed? |
|---|---|---|---|
| VOA Council Tax stock by Band | gov.uk (VOA "Council Tax: stock of properties") | LSOA | LSOA → sector via ONSPD, weighted by household count |
| Scottish Band H counts | Scottish Assessors Association / Scottish Government | Local Authority (less standardised) | Per-LA aggregation then join via ONSPD |
| ONS MSOA net household income | ONS Open Geography Portal | MSOA | MSOA → sector via ONSPD |
| Land Registry Price Paid | gov.uk Land Registry | Full unit postcode | None — direct aggregation up to sector |
| LA-level UK HPI | HMLR | Local Authority | Per-LA monthly index, joined to transactions by LA + date |
| ONS Postcode Directory (ONSPD) | ONS Open Geography Portal | Per-postcode | Reference file for all the above |

All free, all public, all stable formats. Realistic build effort: a day or two of pipeline work. Files are sourced and processed by Claude (per user decision).

---

## What you (the user) need to provide

Nothing for Issue 2 directly. All data sourcing and pipeline work is on Claude. The only confirmation needed:

- **Confirm**: that downstream forecasting tools (volume planner, etc) don't depend on the existing population-based expected-units calculation in a way that would break when this changes. If they do, replacing the normalisation will require a coordinated update beyond the decay fit. *Suggestion: keep the old population-based calculation alongside the new wealth-based one as a separate column for a transition period; cut over downstream tools deliberately.*

---

## What I (Claude) will produce

### Pipeline outputs

| File | Role |
|---|---|
| `_cache/sector_band_h.parquet` | Band H proportion per sector, with within-nation normalised score |
| `_cache/sector_msoa_income.parquet` | ONS income per sector, UK-wide normalised score |
| `_cache/sector_land_reg_score.parquet` | Land Registry banded score per sector (10-year, indexed, weighted), with low-volume flag |
| `_cache/sector_wealth_composite.parquet` | Final composite score per sector, including fallback handling |
| `_cache/wealth_fallback_audit.csv` | Sectors where Land Registry component was dropped due to low transaction volume |
| `_cache/land_registry_indexation_log.csv` | For audit: indexation factors applied per LA per period |

### Documentation

The composite construction is documented in the final fitting report (§8.3 of the brief), including:

- Distribution plots of each normalised measure per sector (UK-wide)
- The composite score distribution
- Sectors hitting the low-volume fallback (count and geographic distribution)
- Sensitivity check results (composite weight bracket; Land Registry band weight bracket)
- McLaren §7.1 holdout comparison across normalisation choices

---

## Brief edits required when Issue 2 is applied

These join the queued batch already accumulated for Issue 1:

| Brief location | Current text / structure | Updated text / structure |
|---|---|---|
| §6.2 Step 2 — Normalise for market size | Population-based formula | Replace with composite wealth-based formula. Add explanation of the composite construction (Decisions F, G, H, I) |
| §7.1 — McLaren holdout validation | Single prediction vs actuals | Add: comparison across normalisation choices (composite / Land Registry alone / Band H alone). Use comparison to validate the composite (Decision J) |
| §7.3 — Sensitivity checks | Three perturbation tests | Add two more: (a) composite weight bracket — three-way variation around 0.50/0.35/0.15; (b) Land Registry band weights — variation around 1/2/4 |
| §10 — Known limitations | (add three entries) | (a) Wealth proxy assumes geographic *distribution* of supercar buyers tracks current wealth concentration. Does not capture rapid temporal shifts in this distribution (e.g. gentrifying sectors will be misjudged for some years). (b) ONS MSOA income is a modelled estimate, not a direct measurement; the income component of the composite carries wider confidence than the other two measures. (c) Land Registry banded score's 1/2/4 weights and £1m/£2m/£4m thresholds are judgement-based priors about right-tail concentration; sensitivity-tested but not derived from data |

---

## Open items still to confirm

- **Sensitivity test specification details** — bracket values for composite weights and Land Registry band weights are written above but worth a final sense-check before they're locked into the brief
- **§7.1 holdout comparison structure** — the three-way comparison (composite / Land Registry alone / Band H alone) is the proposed structure; worth confirming this is what we want before locking it in
- **Downstream impact** — confirm that volume planner and other Toolkit components won't break when the expected-units calculation changes
- **§6.2 formula text** — the actual text replacement in the brief will be drafted as part of the batch update at the end

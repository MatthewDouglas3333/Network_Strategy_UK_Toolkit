# Issue 1 — Fit Window, Competitor Locations, Segment Composition, and Dealer-Type Weights

**Status:** Resolved (pending data sourcing and confirmations)
**Date:** 1 May 2026
**Relates to:** `DECAY_FITTING_BRIEF.md` §3.1, §4.4, §5.4, §6.1, §6.3, §7.2, §7.3, §7.5 (new), §10

---

## The problems

This decision record covers four closely-linked issues with the brief as written. They are grouped because they share a single root cause — the brief makes assumptions about *what data to fit on, how to weight inputs,* and *which brands to count* that don't survive scrutiny once the actual data sources and McLaren's network shape are examined.

### Problem 1A — Competitor location data is current-snapshot only

Competitor location data is sourced from a market data provider and represents a single 2025/2026 snapshot. Fitting a 5-year decay curve against current-only competitor locations implicitly assumes the competitor network was static across the window. It wasn't — luxury dealer networks have churned, particularly through and after COVID. Using current locations against historical sales mis-attributes accessibility: a sector that gained a Ferrari dealer in 2023 looks like it was always close to one. The fit will systematically under-estimate `k` (decay looks shallower than it really is) for any segment with meaningful network change.

### Problem 1B — 2020 and 2021 are COVID-distorted

Those two years bend the geographic pattern of luxury sales specifically. Lockdowns, lead-time blowouts, the unusual 2021 second-hand market, and dealer-access restrictions changed how affluent buyers engaged with the network — including more sight-unseen and close-to-home purchasing. Decay curves fitted on 2020–2021 will be steeper than reality. The two timing problems compound: the years where competitor-location uncertainty bites hardest are also the years where buyer behaviour was abnormal.

### Problem 1C — Segment composition includes brands that don't share supercar buyer behaviour

The brief's segment lookup includes Mercedes-AMG, Ford, Maserati and Porsche in segments where their buyers don't meaningfully cross-shop with McLaren. The decay fit assumes every sale in the dataset is responding to the same underlying relationship — drive time to a relevant dealer drives share of segment sales. That assumption breaks when the dataset mixes buyers following genuinely different geographies.

The brief also has an internal inconsistency on Porsche: §6.3 instructs the agent to count Porsche 911 Turbo/GT *sales* in Core Supercar and GT, but to exclude Porsche dealer *locations* from the accessibility term. This is incoherent — including sales but not dealers means the fit attributes Porsche buyers' geographic pattern to other brands' dealer networks.

### Problem 1D — Dealer-type weights cannot be derived from this dataset, only assumed

The brief's §5.4 specifies acquisition weights of 1.0 / 0.9 / 0.0 for Sales & Service / Sales Only / Service Only. These were originally framed as "starting values" with a sensitivity check at §7.3 to test them. On closer examination, this framing is misleading in two ways:

1. **The weights are inputs to the fit, not outputs of it.** The fit produces `k`, `A`, and `C` — the curve parameters. The dealer-type weights are applied *upstream* of the fit, when computing each sector's effective distance to the nearest dealer. A sector's effective distance to a Sales Only point at 15 minutes with weight 0.9 is treated as 15/0.9 ≈ 16.7 minutes — slightly worse than its raw distance, reflecting that SO is slightly less useful than full S&S. The fit then sees one distance per sector and produces a curve. The weights never re-enter the fit itself. They are prior assumptions, not posterior findings. (In principle they could be jointly fitted alongside `k`, `A`, `C`, but this requires a network geometry that this dataset does not have — see point 2.)

2. **The McLaren UK network geometry does not let us learn the SO or Sales Only weights from the data.**
   - **Service Only** — only 3 SO points exist across all in-scope brands (2 McLaren, 1 Ferrari). The number of sectors where an SO point is the nearest dealer is at most 10–30 nationwide. That's not enough to fit a weight as a free parameter, and not enough to test sensitivity meaningfully — the weight value barely changes any sector's effective distance because SO points appear in so few "nearest" calculations.
   - **Sales Only** — almost all McLaren UK Sales Only sites are co-located with or near a Sales & Service site (per user's confirmation). For nearly every UK sector, the nearest S&S point is at roughly the same distance as the nearest SO point — meaning S&S wins the "nearest dealer" calculation regardless of the SO weight. Varying the weight from 0.7 to 1.0 barely changes any sector's input distance.

The consequence: running sensitivity checks on either weight would produce a misleading "doesn't matter" finding. Stakeholders reading "sensitivity check showed Sales Only weight is robust" would reasonably conclude the model has tested SO strategy and found it well-calibrated. It hasn't. The robustness is an artefact of network geometry, not evidence about SO accessibility.

---

## Why segment composition matters — the mechanism

The decay fit learns a single relationship: as drive time to a relevant dealer increases, what happens to share of segment sales? It works backwards from observed share patterns to find the curve that explains them. This only produces a meaningful answer if every sale in the dataset is responding to the same dealer network and the same buyer behaviour.

The moment sales from a different geography are mixed in, the fit isn't measuring one curve any more — it's averaging two underlying patterns, and the answer becomes "the supercar curve smeared with whatever the volume-brand sales do."

**Mercedes-AMG GT in the GT segment.** AMG GT volumes follow Mercedes-Benz dealer density, which is uniformly distributed across mid-sized UK towns. AMG GT sales are therefore much more evenly spread than DB12 or Roma sales. From the fit's perspective, AMG sales look like share that doesn't decay with distance from supercar dealers — because of course it doesn't, those buyers aren't using those dealers. The fit reads this as evidence the decay is shallow, and `k` is biased upward.

**Ford Mustang in the GT segment.** Same mechanism, more extreme. Ford has hundreds of UK dealers. Mustang sales are essentially uniformly distributed relative to supercar dealer locations. Including them is the cleanest possible way to flatten the decay curve toward meaninglessness.

**Maserati across Core Supercar and GT.** Subtler. Maserati's UK position is closer to "premium" than "supercar" — Ghibli and Levante outsell GranTurismo and MC20 several times over, and the dealer network reflects that. Maserati sales geography looks more like a premium brand than a supercar brand. Including them pulls the fit toward the wrong shape. Volumes are also small enough that signal-to-noise is poor.

**Porsche entirely.** A Turbo S buyer does cross-shop a 720S, so the case for keeping Porsche isn't trivial. But the brief excludes Porsche dealer locations correctly — a Porsche Centre is a Macan/Cayenne shop with a 911 corner. Including Porsche sales without Porsche dealers makes the model logically inconsistent. Cleaner to drop entirely.

### Expected magnitude of the segment-composition fix

Hard to predict precisely without running the fit, but order of magnitude: removing volume-brand contamination from the GT segment will likely reduce fitted `k` by 15–35%. Translation — the decay will look meaningfully steeper, which means the model will project bigger share losses for remote sectors and bigger share gains for close-to-dealer sectors. That's a real change in tool behaviour, not a cosmetic one.

### Cost of the segment-composition fix

GT segment unit volumes drop substantially. Using 2024–25 figures (3,147 units), stripping AMG GT, Mustang, Maserati GranTurismo, and 911 Turbo/GT3 takes the segment to roughly 800–1,200 units across 4 brands (McLaren, Ferrari, Aston Martin, Bentley). Over the 4-year fit window (2022–25), that's 1,600–2,400 units. Still enough to fit, but GT becomes the most data-thin segment after Upper Supercar. Bootstrap confidence intervals will be wider, and the GT segment is more likely to be flagged `fragile` in the final config.

This is a price worth paying — a wider CI on a cleanly-defined segment is more useful than a narrow CI on a muddy one.

---

## The agreed solution

### Decision A — Primary fit window: 2022–2025

This window:

- Doubles the sample size relative to the 2024–2025 baseline. Concretely (using 2024–25 unit volumes as a guide): Core Supercar ~2,300 → ~4,600; GT ~3,150 → ~6,300 *before segment narrowing*; Upper GT ~595 → ~1,200; Upper Supercar ~328 → ~660; SUV ~3,200 → ~6,400. Upper GT and Upper Supercar most need the additional data.
- Excludes the COVID-distorted 2020–2021 period from the primary fit. Those years remain available as a sensitivity check.
- Keeps the competitor location assumption tractable. Competitor networks have been relatively stable since 2022, so a "current locations + small deltas file" approach is realistic without a full historical reconstruction.

### Decision B — Competitor location strategy: current snapshot + deltas file from Jan 2022

Rather than reconstructing complete historical networks, source only what *changed* between Jan 2022 and the current snapshot date. Each change event (open / close / relocate / brand-swap) is recorded with date and location, and time-varying accessibility is applied for affected sectors. Sectors not near any change in the window — the vast majority — use the current snapshot directly.

Realistic completeness target: 5–15 change events total across in-scope brands.

**Out of scope:** historical competitor locations pre-2022; dealer ownership / parent group history; Mercedes-AMG and Ford networks (no longer relevant after segment narrowing — see Decision C).

### Decision C — Segment composition narrowed

Tighten segment lookup to brands whose buyers genuinely cross-shop McLaren product:

| Segment | Brands kept | Brands removed |
|---|---|---|
| **Core Supercar** | McLaren, Ferrari, Lamborghini | Maserati, Porsche (911 GT cars) |
| **GT** | McLaren, Ferrari, Aston Martin, Bentley | Mercedes-AMG, Ford, Maserati, Porsche (911 Turbo) |
| **Upper GT** | Ferrari, Rolls-Royce, Aston Martin | (no change — already clean) |
| **Upper Supercar** | Lamborghini, Ferrari | (no change — already clean) |
| **SUV** | Bentley, Rolls-Royce, Aston Martin, Ferrari, Lamborghini | (no change — locked by previous user decision) |

Brands removed are excluded for **all three uses** — volumes, accessibility (locations were already excluded for some), and share calibration. The fit becomes internally consistent: one segment, one buyer type, one set of relevant dealers.

This decision applies to the **decay fitting brief specifically**. Downstream volume forecasting (e.g. total addressable market for a future SUV launch) may want broader competitive sets — that's a separate question handled outside this brief.

### Decision D — Dealer-type weights treated as fixed prior assumptions; both non-reference weights flagged as untestable

The dealer-type acquisition weights are inputs to the fit, not outputs of it. They are applied when computing each sector's effective distance to the nearest dealer (effective distance = actual distance / weight), and their values are set by judgement, not derived from the data.

| Dealer Format | Acquisition weight | Status |
|---|---|---|
| Sales & Service | 1.0 | Reference. By definition |
| Sales Only | 0.9 | **Prior assumption.** Not testable from this dataset because almost all McLaren UK Sales Only sites are co-located with or near a Sales & Service site. For nearly every sector, S&S is the "nearest dealer" regardless of how the SO weight is set — so varying the weight produces no meaningful change in calculated distances |
| Service Only | 0.0 | **Prior assumption.** Not testable from this dataset because only 3 SO points exist across all in-scope brands. The number of sectors where SO is the nearest point is too small for the weight value to materially affect calculated accessibility |

**Reasoning for the 0.9 Sales Only value:**

There is no formal derivation. 0.9 is a calibrated judgement that says "a Sales Only point is *almost* as useful as a Sales & Service point for the act of buying a car, but not quite." A Sales Only site can do everything required to acquire a vehicle — configure, deposit, paperwork, delivery — so the weight should be close to 1.0. The discount versus 1.0 reflects that some buyers value being able to take their car back to the same site for servicing. That preference is small but non-zero in this segment, where dealer relationships matter. A value of 1.0 would say "service location is irrelevant to the buying decision"; 0.85 would say "a meaningful minority care strongly"; 0.9 sits in the middle, implying perhaps 10–15% of buyers weakly prefer S&S over SO when all else is equal.

This is the kind of input that *could* be replaced with an evidenced number if internal McLaren data on like-for-like SO vs S&S catchment performance is ever made available. Out of scope for this work, but flagged as the natural bridge from "guess" to "calibrated input."

**Reasoning for the 0.0 Service Only value:**

Service Only sites cannot transact a sale on the day. The weight reflects that they make zero direct contribution to the *acquisition* decision. This ignores secondary effects (brand presence, post-purchase relationship, psychological assurance of nearby servicing) which may genuinely contribute to share but cannot be measured from this dataset.

**§7.3 sensitivity changes:**

The brief's prescribed dealer-weight perturbation in §7.3 ("halve the Sales Only / Service Only weights to 0.5 / 0.0") is removed. Running it would produce a misleading "doesn't matter" finding for the structural reasons above — both for Sales Only (S&S typically wins the nearest-dealer calculation regardless of the SO weight) and for Service Only (too few sectors are affected by the weight at all). Reporting that finding would imply the weights have been validated when they haven't.

The remaining §7.3 sensitivity checks (COVID-year inclusion, in-segment filter test, time horizon perturbation) are unaffected and remain valuable.

**§7.5 new — observational dealer-type check:**

For the small number of sectors where a Sales Only or Service Only point is the *primary* nearest McLaren or Ferrari presence (i.e. materially closer than any S&S point), plot realised share against curve prediction. Observational only — not enough data to fit on, but visible in the validation report so the limitation isn't hidden. Likely outcomes:

- For SO sectors (very few): a visible scatter showing whether SO-served sectors over- or under-perform the curve. Even three or four data points are informative.
- For Sales Only sectors: per the user's note that almost all SO sites are co-located with S&S, the criterion may produce zero qualifying sectors. That itself is a finding worth recording — "the network geometry does not contain Sales-Only-primary sectors, so the SO weight is structurally untestable from this data."

**Implication for the Network Strategy Toolkit:**

The model **cannot evaluate Service Only network expansion scenarios**. Adding a Service Only point to the network produces no change in projected share by construction (weight 0.0 means SO points are invisible to the accessibility calculation). This must be flagged in the tool itself, not just the report — users running "add SO point in Aberdeen" scenarios will see zero change, and the tool must explain that this is a model limitation, not a finding.

By extension, the model **also cannot meaningfully evaluate Sales Only vs Sales & Service trade-offs at sites where both options are geographically realistic.** With weight 0.9, an SO point is treated as 90% as useful as an S&S point in pure accessibility terms — but the choice of 0.9 is unevidenced, and the data cannot validate it. Strategic decisions about SO vs S&S should therefore not rely solely on this model.

Both limitations sit in §10 as headline known constraints.

---

## Brands the deltas file will cover, and why

Updated to reflect Decision C — AMG, Ford, Maserati and Porsche are no longer in scope.

| Brand | In scope for deltas file? | Reason |
|---|---|---|
| **McLaren** | Yes | Required for §7.2 dealer-change validation. Source: McLaren internal records (user-supplied) |
| **Ferrari** | Yes | Major competitor across Core Supercar, Upper Supercar, Upper GT, GT, SUV. Network is small (~12 UK dealers) so changes are tractable to track |
| **Lamborghini** | Yes | Core Supercar, Upper Supercar, SUV competitor. Small UK network |
| **Aston Martin** | Yes | GT, Upper GT, SUV competitor. Moderately-sized UK network with some recent churn |
| **Bentley** | Yes | GT and SUV competitor. Larger network than the Italian brands but well-documented changes |
| **Rolls-Royce** | Yes | Upper GT and SUV competitor. Tiny UK network (~9 dealers); changes are press-released |
| Maserati | No | Removed from segment composition (Decision C). No longer in any segment |
| Mercedes-AMG | No | Removed from segment composition (Decision C) |
| Ford | No | Removed from segment composition (Decision C) |
| Porsche | No | Removed from segment composition (Decision C) |

---

## What you (the user) need to provide

### Required before deltas sourcing begins

Nothing. The competitor deltas sourcing is a parallel task I (Claude) execute via web research. No input needed from you to start it.

### Required for §7.2 historical dealer-change validation

You need to check internal McLaren records and supply, for each McLaren UK retailer change between 1 January 2022 and the current date:

- **Dealer name and location** (postcode + ideally lat/lon)
- **Type of change** — open, close, relocate, or change of operator
- **Effective date** of the change (or month/quarter if exact date unavailable)
- **Registrations data for affected sectors** for the 12 months before and 12 months after the change. Sector-level totals — same level of detail as the existing registrations file
- **Any context** that would explain anomalies — e.g. a relocation of only a few miles versus a genuine network expansion into a new catchment

If there are 2 or more clean cases with usable before/after data, §7.2 becomes a real validation step.
If there are 0 or 1 cases, or the cases don't have clean volume data, §7.2 becomes a documented gap — not a blocker.

### Required for the registrations input

Per the brief §3.1, the registrations file needs to cover the fit window. If your current `registrations_2020_2025.csv` extract already covers 2022–2025, no further extension needed (the 2020–2021 rows simply won't be used in the primary fit). If your extract starts later than 2022, you'll need to re-run it.

The file will be renamed `registrations_2022_2025.csv` going forward to avoid ambiguity. Schema unchanged.

### Required for the §7.5 observational dealer-type check

For the 2 McLaren Service Only points and the 1 Ferrari Service Only point, confirm:

- Postcode and lat/lon of each site
- The date the SO designation became effective (if not currently SO from inception)

For Sales Only sites — given the user's note that nearly all SO sites are co-located with S&S — a list of McLaren UK Sales Only points and their associated S&S nearest-neighbour distances would let the agent confirm whether any qualifying "Sales-Only-primary" sectors exist for the §7.5 check.

### Confirmation needed on segment lookup

The `McLaren_Registration_Segment.xlsx` sub-model → segment lookup needs to reflect Decision C. You'll need to either:

- Confirm the existing lookup already excludes the dropped brands (unlikely given the brief), or
- Update the lookup file before the cleaning step runs, or
- Confirm that I (Claude) should apply the exclusion in the cleaning step itself, working from the original lookup but filtering out the dropped brands

The third option is probably easiest — keeps the source-of-truth Excel file untouched, and the exclusion lives in code where it's auditable.

---

## What I (Claude) will produce

### Deltas file: `competitor_dealer_changes_2022_2025.csv`

One row per change event, covering Ferrari, Lamborghini, Aston Martin, Bentley, Rolls-Royce.

| Column | Description |
|---|---|
| `brand` | Ferrari / Lamborghini / Aston Martin / Bentley / Rolls-Royce |
| `dealer_name` | Best-known name of the site |
| `postcode` | Full postcode of the affected location |
| `latitude`, `longitude` | Geocoded coordinates |
| `change_type` | open / close / relocate / brand_swap |
| `effective_date` | Best estimate, with precision flag (exact / month / quarter) |
| `previous_location` | Where applicable (relocations and brand-swaps) |
| `source_url` | Primary source — Wayback snapshot / press release / trade press |
| `confidence` | high / medium / low — based on source quality and corroboration |
| `notes` | Free text for anything unusual |

### Sources, in priority order

1. **Wayback Machine snapshots** of each OEM's UK "find a dealer" page at roughly 6-month intervals from Jan 2022 to current
2. **OEM and dealer group press releases** — opens and brand-swaps are nearly always press-released for prestige brands
3. **Trade press** — Motor Trader, Car Dealer Magazine, AM-Online — picks up changes the OEM doesn't publicise
4. **Companies House filings** — used as a tiebreaker for effective dates where press coverage is ambiguous

### What I won't do

- Source dealer ownership / parent group history (out of scope per your decision)
- Source pre-2022 history
- Make assumptions about changes that aren't corroborated by at least one source — those will be flagged `confidence: low` with notes, for your review

---

## Brief edits required when Issue 1 is applied

These are queued and will be applied as a batch once all issues are resolved:

| Brief location | Current text / structure | Updated text / structure |
|---|---|---|
| §3.1 file path | `registrations_2020_2025.csv` | `registrations_2022_2025.csv` |
| §3.1 inputs table | (no entry) | Add `competitor_dealer_changes_2022_2025.csv` as required input |
| §4.4 time-period consistency | References 2024 vs 2025 only | Extend to 2022–2025; note 2020–2021 explicitly excluded as COVID-distorted |
| §5.4 dealer-type weights | Framed as "starting values" subject to §7.3 sensitivity | Reframe as fixed prior assumptions. Add explicit note: SO weight 0.0 and Sales Only weight 0.9 cannot be derived or validated from this dataset due to network geometry. Cross-reference Decision D in Issue 1 record |
| §6.1 segment scope | "2024–25 market units" column | Update to "2022–25 market units" with revised volume estimates (post-segment-narrowing) |
| §6.3 segment dealer sets — Core Supercar row | "McLaren, Ferrari, Porsche (911 GT-cars only), Lamborghini, Maserati" | "McLaren, Ferrari, Lamborghini" |
| §6.3 segment dealer sets — GT row | "McLaren, Porsche (911 Turbo only), Mercedes-Benz AMG, Ferrari, Bentley, Aston Martin, Maserati, Ford" | "McLaren, Ferrari, Aston Martin, Bentley" |
| §6.3 Porsche caveat paragraph | Detailed caveat about Porsche sales counted but dealers excluded | Remove entirely — Porsche is now fully out of scope |
| §6.3 SUV caveat | Unchanged | Unchanged — locked by previous decision |
| §7.2 historical dealer-change validation | "If the user can supply details..." | Reframe as scoped task with the data spec from this document |
| §7.3 sensitivity checks — 2020/2021 | "Drop 2020–2021 data (tests COVID distortion)" | Reframe as "Include 2020–2021 (tests COVID distortion vs primary fit)" since 2020–2021 is now excluded by default |
| §7.3 sensitivity checks — dealer weights | "Halve the Sales Only / Service Only weights to 0.5 / 0.0" | **Remove entirely.** Replace with an explicit note: "Dealer-type weight perturbation removed. Both non-reference weights are unverifiable from this dataset due to network geometry — running the check would produce a misleading 'robust' finding. See §7.5 for observational alternative" |
| §7.5 new section | (does not exist) | Add: "Observational dealer-type check. For sectors where a Sales Only or Service Only point is the primary nearest McLaren or Ferrari presence (materially closer than any S&S point), plot realised share vs curve prediction. Observational only — not enough data to fit on. If no qualifying sectors exist (likely for Sales Only given network co-location), record this as a structural finding" |
| §10 known limitations | (add five entries) | (a) Competitor location history pre-2022 not sourced; (b) Segment composition narrowed to direct-cross-shop brands only — volume-premium and Porsche sales no longer counted toward segment totals; (c) GT segment expected to be most data-thin after Upper Supercar following narrowing; (d) Model cannot evaluate Service Only network expansion scenarios — SO weight fixed at 0.0 by data limitation, not by evidence. Output for SO scenarios shows no change in projected share by construction; users must not interpret this as a finding; (e) Sales Only weight (0.9) is a prior assumption that cannot be validated from this dataset because nearly all McLaren UK Sales Only sites are co-located with Sales & Service sites. Strategic SO vs S&S trade-off decisions should not rely solely on this model |

---

## Open items carried forward

- **You to confirm**: McLaren UK network changes 2022–present (count and data availability) — gates §7.2
- **You to confirm**: registrations extract covers Jan 2022 onward, or needs re-running
- **You to confirm**: 2 McLaren Service Only point locations and effective dates, plus the Ferrari SO point — for §7.5 observational check
- **You to confirm**: Sales Only site list (McLaren UK) for §7.5 qualifying-sector check — likely to confirm no Sales-Only-primary sectors exist, which is itself a recordable finding
- **You to decide**: segment lookup exclusion handled in source Excel file, or in the cleaning code
- **Claude to execute** (parallel to remaining issue discussions): competitor deltas sourcing for the 5 in-scope competitor brands plus McLaren cross-check

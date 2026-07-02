# Network Strategy — Phased Action Plan

**Purpose:** What happens in what order, who does each piece, and what data each side needs to provide. Reflects confirmations gathered in the planning interview.

**Date:** 1 May 2026 (status updated 26 June 2026)
**Status:** In execution. **Registration de-distortion (the Phase 3 cleaning step, 3.1.1–3.1.4) is COMPLETE and signed off** — see `DISTORTION_REMOVAL_BRIEF.md` "IMPLEMENTED STATE" and `data/De-Distortions Registrations Task/outputs_de_distortion_FINAL/`. Remaining Phase 3 work: competitor drive-time matrix, wealth composite, cycle index, and the per-segment fit.

---

## Quick orientation

Five phases, sequenced:

1. **Data confirmations and gathering** — you check what's available; both sides confirm scope
2. **Data sourcing** — public data and competitor deltas (mostly Claude); any McLaren-internal alternatives identified by you
3. **Pipeline execution** — Claude runs the fit end-to-end agentically with sign-off Stop points
4. **Toolkit integration** — Claude produces drop-in code; your team deploys
5. **Sign-off and handover** — final report reviewed; old toolkit decommissioned

Phases 1–2 partly run in parallel. Phase 3 cannot start until Phase 1 confirmations land. Phase 4 cannot start until Phase 3 produces the curves config.

---

## Important documentation patches noted during planning

Two facts surfaced during planning that need correcting in already-produced documents. These are wording fixes, not decision changes — but they affect what §7.6 (the observational dealer-type check) is expected to produce.

### Patch 1 — Sales Only situation: more nuanced than initially stated

The Issue 1 record currently says "almost all McLaren UK Sales Only sites are co-located with Sales & Service." Two things wrong with this:

- **McLaren has zero UK Sales Only sites** (not "almost all co-located")
- **Some in-scope competitor brands do have Sales Only sites** — Ferrari most clearly (H.R. Owen's London showrooms appear sales-focused, served by a separate service centre in Acton). Lamborghini's UK network appears to be all full S&S. Other brands (Aston Martin, Bentley, Rolls-Royce) not yet verified

**The conclusion (Sales Only weight 0.9 is a fixed prior, not fitted) is unchanged.** The reasoning sharpens though: it's not "zero SO sites exist" but rather "the geometry of where SO sites sit (mostly in dense urban areas where S&S is also nearby) means the number of sectors where an SO point is materially closer than any segment-relevant S&S point is likely small even where competitor SO sites do exist."

**The §7.6 framing changes from definite-zero to empirically-determined.** Rather than "expect zero qualifying sectors," §7.6 becomes "identify all sectors where any in-scope SO point is materially closer than any S&S point of any in-scope brand; if the resulting set is non-empty, plot residuals against curve to back out an empirical SO weight signal; if empty, document as structural finding." The actual outcome is determined at execution by filtering `Competitor_Dealer_Database.xlsx` on its `Dealer Format` column.

This is potentially a *better* outcome than the brief was promising before — modest empirical signal on the SO weight rather than purely structural finding. Whether it materialises depends on competitor SO geography revealed at execution.

### Patch 2 — Cycle data resolution

Cycle data is available **monthly**, not just quarterly. The cycle index can use higher-resolution smoothing accordingly. Small upside, not a blocker.

### Patches required

| Document | What needs fixing |
|---|---|
| `ISSUE_01_FIT_WINDOW_AND_COMPETITOR_LOCATIONS.md` | Replace "almost all McLaren UK SO sites are co-located with S&S" with neutral framing about competitor SO geometry being the determining factor. Note that McLaren itself has zero SO sites |
| `DECAY_FITTING_BRIEF.md` (integrated) §5.4 reasoning, §7.6 observational check, §10 limitations | Same neutral framing. Reframe §7.6 as empirically-determined rather than near-certain-zero |
| `NETWORK_STRATEGY_METHODOLOGY.md` §12 limitations | Same neutral framing on Sales Only weight |
| `GUIDE.md` | No direct change — wording is more general |
| `ISSUE_02_WEALTH_NORMALISATION.md`, `ISSUES_03_TO_07_...md` | No change — still accurate |

### What's still genuinely outstanding for me to remember

- **Verify exact competitor Sales Only counts at execution** by filtering the JATO file's `Dealer Format` column for each in-scope brand (Ferrari, Lamborghini, Aston Martin, Bentley, Rolls-Royce). The numbers feed §7.6's qualifying-sector identification
- **Document patches above** to be applied in the next round of doc updates. Don't gate any phase
- **Cycle data being monthly** to be used as monthly-resolution input, not aggregated unnecessarily to quarterly

---

## Phase 1 — Data confirmations and gathering (you-side)

This phase gates Phase 3. The integrated brief contains placeholders for everything below; replacing those placeholders with real values is what unlocks execution.

### 1.1 Confirmed during interview — green light

| Item | Confirmed | Action |
|---|---|---|
| Registrations extract covers Jan 2022 onward | ✓ | None — proceed |
| McLaren UK-total registrations available 2014–current, monthly | ✓ | Extract when needed (Phase 2) |
| Sector-level pre/post volumes for §7.2 backtests are obtainable | ✓ | None — extract once §1.2 is complete |
| Network_Database.xlsx ready and accurate | ✓ | None |
| Competitor_Dealer_Database.xlsx ready (current snapshot) | ✓ | None |
| McLaren_Registration_Segment.xlsx ready and complete | ✓ | None |
| Existing McLaren drive-time matrix cached | ✓ | Note: will be rebuilt with population-weighted centroids in Phase 3 |
| 2 McLaren Service Only point locations and dates known | ✓ | Provide when Phase 3 reaches §7.6 |
| Ferrari Service Only point known | ✓ | Provide when Phase 3 reaches §7.6 |
| Zero McLaren UK Sales Only sites | ✓ | But some competitor brands have SO sites (Ferrari confirmed; others to verify at execution). §7.6 outcome is empirically determined — see "Patch 1" above |

### 1.2 Open — your action this phase

| Item | What's needed | Owner | Notes |
|---|---|---|---|
| **McLaren UK network changes since Jan 2022** | Identify each open / close / relocate, with date and postcode | You | Approximately 3–4 cases expected. Subject to records check |
| **Internal data check — public datasets** | Determine whether McLaren already licenses or has access to: ONSPD, ONS small-area income, Land Registry Price Paid, VOA Band H, UK HPI | You / your data team | If you have any internally, supply those to Claude in Phase 2. If not, Claude sources free public versions |

That's the entirety of Phase 1's net-new asks on you. Nothing else gates Phase 3.

### 1.3 Open — Claude's action this phase

| Item | What Claude does | Notes |
|---|---|---|
| **Patch documentation wording** | Fix the Sales Only references in Issue 1 record, integrated brief, and methodology document | Wording-only update reflecting the "zero Sales Only sites" reality |
| **Confirm execution environment** | Verify Claude has access to your data environment for Phase 3 (registrations file paths, dealer Excel files, cache directory) | Practical setup step before Phase 3 starts |

---

## Phase 2 — Data sourcing (mostly Claude-side; partly you-side)

This phase produces the data files Phase 3 will consume. Runs partly in parallel with Phase 1.

### 2.1 Claude sources

| Dataset | Used for | Notes |
|---|---|---|
| **VOA Council Tax stock by Band** (England + Wales) | Wealth composite (Band H component) | Annual release, gov.uk |
| **Scottish Council Tax stock per Local Authority** | Wealth composite (Band H component, Scotland) | Per-LA via Scottish Assessors / Scottish Government |
| **ONS MSOA net household income** | Wealth composite (income component) | ONS Open Geography Portal |
| **HMLR Price Paid full UK transactions, last 10 years** | Wealth composite (Land Registry banded score) | gov.uk Land Registry |
| **LA-level UK House Price Index (HMLR), monthly, last 10 years** | Indexation of Land Registry prices to today's value | gov.uk Land Registry / ONS |
| **ONS Postcode Directory (ONSPD), current quarterly** | Geographic lookups (LSOA → sector, MSOA → sector, ITL2 region) | ONS Open Geography Portal |
| **Competitor dealer changes since Jan 2022 (deltas file)** | Time-varying competitor accessibility | Wayback Machine snapshots, OEM press releases, trade press, Companies House. Five in-scope brands: Ferrari, Lamborghini, Aston Martin, Bentley, Rolls-Royce |

**Switch to your data if you have it:** if Phase 1's internal-data check finds that McLaren already holds any of the above (ONSPD is the most likely; income data and property data possibly), use yours instead of Claude's free version. They're lower-effort to use because they're already in a usable schema in your environment.

### 2.2 You provide (when Phase 2 needs it)

| Item | Format | Notes |
|---|---|---|
| **UK-total McLaren registrations, monthly, 2014–current** | Two-column CSV: month, registrations | **STILL NEEDED** — the cleaned registrations file only covers 2022–2025, so pre-2022 history for the cycle index isn't yet on disk. Only gates the cycle index / §7.2 backtests, not the core fit |
| ~~**McLaren UK retailer changes 2022–present**~~ | — | ✅ **ALREADY AVAILABLE** — McLaren changes are in the full competitor dealer-changes file (`Competitor_dealer_changes_2022_2026_Includes_McLaren_UPDATED...`); the de-distortion run already read 17 change pairs from it. No separate supply needed |
| ~~**Sector-level pre/post registrations for each change**~~ | — | ✅ **DERIVABLE** — slice from the cleaned registrations we already built (`registrations_cleaned_annual.csv` for year buckets; `registrations_cleaned_monthly.csv` for tight ±12-month windows around the change date). No separate file needed |

### 2.3 Output of Phase 2

By end of phase, the inputs the brief expects in §3.1 should all exist on disk:

- `mclaren_uk_total_registrations.csv` (you supply)
- `mclaren_network_changes_2022_2025.csv` (you supply)
- `mclaren_pre_post_volumes_<change_id>.csv` (you supply per change case)
- `competitor_dealer_changes_2022_2025.csv` (Claude builds)
- All wealth composite raw files: VOA, ONS income, Land Registry Price Paid, UK HPI, ONSPD (Claude sources or you supply if internal)

Plus the standing files already confirmed in §1.1.

---

## Phase 3 — Pipeline execution (Claude end-to-end, with Stop points)

Claude executes the brief agentically. The brief itself is the spec; execution follows the structure of `DECAY_FITTING_BRIEF.md` §4 through §8. Four mandatory Stop points where Claude pauses for your sign-off.

### 3.1 Execution sequence

| Step | What runs | Output |
|---|---|---|
| **3.1.1** | §4.1 — In-segment + Issue 1C filter | ✅ DONE — within the de-distortion pass (`run_de_distortion_pass.py`) |
| **3.1.2** | §4.2(a) HQ research | ✅ DONE — factory/HQ reference list built and applied (hold-to-local-average) |
| **3.1.3** | §4.2(b) statistical outliers | ✅ DONE — dealer/finance treatments + statistical finance review list; manual overrides signed off |
| **3.1.4** | §4.3–4.5 — NI/island exclusion, time consistency check | ✅ DONE — offshore islands excluded; cleaned dataset is `outputs_de_distortion_FINAL/registrations_cleaned_annual.csv` |
| **3.1.5** | §5 — Build competitor drive-time matrix (population-weighted centroids) | Cache file |
| **3.1.6** | §6.2 Step 2 — Build wealth composite | **STOP 3** — Claude presents per-sector composite distribution and component contributions; you check for anomalies before composite locks |
| **3.1.7** | §6.5 — Build cycle index | Cache file |
| **3.1.8** | §6.2 Steps 1, 3, §6.6 — Per-segment fit with block bootstrap | Fitted parameters per segment |
| **3.1.9** | §7.1–§7.6 — Validation across all checks | Validation results |
| **3.1.10** | §8.3 — Compile final report | **STOP 4** — Claude presents the full report; you accept, reject, or request re-fit |
| **3.1.11** | Once accepted | `decay_curves.yaml` written to config; `sector_wealth_composite.parquet` written to cache |

### 3.2 Your involvement during Phase 3

You're not on the keyboard but you do need to be available at the four Stop points to review and sign off. Claude pauses between Stops; expect those decision moments to take whatever time you need to review properly rather than rushing.

### 3.3 What execution produces

End of Phase 3, you have:

- `config/decay_curves.yaml` — the validated fit per segment
- `_cache/sector_wealth_composite.parquet` — per-sector wealth composite
- `_cache/mclaren_cycle_index.csv` — quarterly UK cycle index
- All other supporting cache files per brief §8.2
- `DECAY_FIT_REPORT.md` — the full analysis report with sign-off date

This is the data deliverable the toolkit will consume.

---

## Phase 4 — Toolkit integration

This phase makes the new fit usable in the live tool. Honest scoping note: Claude can write the integration code, but Claude cannot deploy into your production codebase. Realistic split:

### 4.1 Claude produces

| Item | Description |
|---|---|
| **`decay_model.py`** | New Python module loading `decay_curves.yaml` and `sector_wealth_composite.parquet`; computing `competitive_position(sector, segment)` per the methodology document; handling fragility-flag CI widening |
| **Integration patch for `network_strategy_api.py`** | Code diff replacing the existing share calculation with calls to `decay_model.py`. Includes removing the old open-point revaluation logic, band-aware shares, and cap-at-baseline rules (now redundant) |
| **Integration patch for `network_strategy_service.py`** | Updates to the heavy-compute layer to consume the new caches at startup and surface fragility flags in scenario outputs |
| **Toolkit test plan** | Specific scenarios to run before going live: known-good baseline projections, removal of an isolated dealer (should now be ≤ 0 net change without cap-at-baseline gymnastics), addition of a dealer in genuine white space, fragile-segment scenario showing wider CIs |
| **Updated `NETWORK_STRATEGY_METHODOLOGY.md` and `GUIDE.md`** | Reconciliation pass — the future-state versions already exist; small updates to reflect any deviations between aspirational design and actual implementation |

### 4.2 You / your team deploy

| Item | Owner |
|---|---|
| **Apply the integration patches** to live `network_strategy_api.py` and `network_strategy_service.py` | Whoever maintains the live toolkit |
| **Run the toolkit test plan** to confirm the new model produces sensible outputs | Same |
| **Decommission the old territory-share code paths** once the new model is live and validated | Same |
| **Action `STARTING_ACTION.md`** if and only if the rebuild is delayed and the existing toolkit is still in production — fixes the open-point cap-at-baseline issue independently | Same |

### 4.3 Stakeholder communication

Phase 4 is also when you need to brief stakeholders that the new model produces:

- Wider, honest confidence intervals (some segments newly flagged fragile)
- Smooth share projections rather than band-cliff projections
- Removal of Service Only network expansion as a model capability (must be communicated as a known limitation, not a finding)
- Wealth-based market normalisation (some sectors will look meaningfully different from before)

The "talking points" sections in the future-state `GUIDE.md` and `NETWORK_STRATEGY_METHODOLOGY.md` Appendix A give you ready-made language for this.

---

## Phase 5 — Sign-off and handover

Final phase, mostly administrative.

| Item | Owner | Notes |
|---|---|---|
| Final report sign-off | You | Already happens at Stop 4 in Phase 3 — this is the formal version that goes to whoever needs to approve |
| Toolkit deployment sign-off | You / IT | After Phase 4 testing passes |
| Documentation reconciliation | Claude → you | Future-state methodology and guide updated against actual toolkit behaviour; `_OLDOLD` versions archived |
| Decommission of legacy artefacts | You | `DECAY_FITTING_BRIEF_OLDOLD.md`, `STARTING.md`, old cache files no longer used |
| Set re-fit cadence | You | Recommend annual re-fit, or whenever the network changes meaningfully (new dealer, dealer closure). The version-string mechanism (Issue 7 Decision W) makes re-fits traceable |

---

## Critical path summary

The shortest sequence from "now" to "decay model live in toolkit":

1. You confirm McLaren network changes (Phase 1.2) and check internal data access (Phase 1.2)
2. You extract McLaren cycle data when Phase 2 needs it
3. Claude sources public data + builds competitor deltas (Phase 2)
4. Claude executes the fit end-to-end with four Stop sign-offs (Phase 3)
5. Claude produces integration code; your team deploys (Phase 4)
6. Test, sign off, decommission (Phase 5)

Phase 1 confirmations could finish quickly. Phase 2 sourcing is the chunky parallel job. Phase 3 is the analytical execution with sign-off pauses. Phase 4 is engineering. Phase 5 is administration.

Nothing in this plan is unbounded. Every step has a defined output and a defined owner.

---

## Open items consolidated for tracking

A single list of everything that's still waiting on someone, by owner:

### You — outstanding (updated 26 Jun 2026)
**Four small data items still needed (all on you). Full download links in `DATA_DOWNLOAD_TRACKER (1).md`:**
- Download **SIMD 2020 indicators** — Scotland income proxy (tracker #8)
- Download **NI Capital Value Bands by SOA** — NI Band H equivalent (tracker #10)
- Download **NI Annual House Prices by Electoral Ward** (tracker #11)
- Extract **UK-total McLaren registrations 2014–current, monthly** — internal; for the cycle index / backtests (tracker #12)

**Already done / no longer needed:**
- ~~Identify McLaren UK network changes since Jan 2022~~ ✅ already in the full competitor dealer-changes file (17 change pairs, McLaren included)
- ~~Provide network change pre/post sector volumes~~ ✅ derivable from the cleaned registrations file (annual, or monthly for tight ±12-month windows)
- ~~Check internal access to public datasets~~ ✅ E+W/UK-wide + Scotland Band H + NI income all downloaded

**Later phases:**
- Available for four Stop sign-offs during Phase 3
- Deploy integration patches and run toolkit test plan (Phase 4.2)
- Decommission legacy artefacts (Phase 5)

### Claude
- Patch wording on Sales Only references in Issue 1 record, brief, methodology — replace "almost all McLaren SO sites co-located with S&S" with neutral framing about competitor SO geometry (Phase 1.3)
- Reframe §7.6 observational check from "near-certain zero qualifying sectors" to "empirically determined at execution by filtering JATO `Dealer Format` column" (Phase 1.3)
- Verify execution environment access (Phase 1.3)
- Source public datasets where you don't have internal copies (Phase 2.1)
- Build competitor deltas file (Phase 2.1)
- At execution: filter `Competitor_Dealer_Database.xlsx` on `Dealer Format` for each in-scope brand, identify sectors where any SO point is materially closer than any in-scope S&S point. Feeds §7.6 (Phase 3)
- Execute the fit pipeline end-to-end with Stop checkpoints (Phase 3)
- Produce integration code modules and patches (Phase 4.1)
- Update future-state methodology and guide post-deployment (Phase 4.1 / Phase 5)

That's the complete plan. Once you're ready to start Phase 1 actions, the next session can begin.

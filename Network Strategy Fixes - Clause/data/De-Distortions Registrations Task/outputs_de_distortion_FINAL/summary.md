# De-Distortion Pass Summary

Output folder: `outputs_de_distortion_FINAL` (run 20260626_164911)

Matching policy: two-way postcode matching — full sectors (e.g. GU21 4) matched at sector level; the ~43% of rows that the vendor only resolved to district (e.g. CW1) matched at district level. District fallback applies to factory + dealer + finance. Dealer reductions are floored at the local area norm so genuine local demand is preserved (e.g. SW7 Lamborghini 135 -> 38, vs a local SW norm of ~4).

## Volumes (primary fit, registrations)
- Before cleaning: 15,063
- After cleaning: 13,054  (net -2,009.3)
- Factory/HQ excess removed: 1,141 (held to local avg: 41.6)
- Dealer demo removed: 868
- Finance excess identified: 123
- Finance excess redistributed UK-wide: 123
- Finance excess NOT redistributable (no recipients): 0

## Counts
- Primary-fit rows: 13,393 (excluded 5,105)
- Factory/HQ sector-years held to local avg: 36
- Dealer sector-years reduced: 315
- Finance sector-years: 34
- Statistical finance candidates (review only): 18
- Offshore island rows excluded (GY, IM, JE): 134 (155 regs)

## Review overrides applied
- LE7 added as Sytner Lamborghini/Bentley Leicester dealer (was missing from competitor file)
- BD1 treated as Bradford supercar hire/trade finance hotspot
- Channel Islands + Isle of Man excluded from the GB drive-time fit
- Aston Martin Works MK16 9 kept in fit (flagged only)

## Dealer sourcing
- Competitor pairs: 74, change pairs: 17, McLaren pairs: 8 (postcode column: Postcode)
- McLaren dealer sectors: AL10 9, B94 5, KT24 6, LS9 0, ML3 0, RG12 2, SK9 3, SO43 7

## Key outputs
- `registrations_cleaned_annual.csv/.parquet` - canonical cleaned file (sector x sub-model x year)
- `registrations_cleaned_monthly.csv/.parquet` - monthly version
- `factory_hold_audit.csv`, `dealer_reduction_audit.csv`, `finance_redistribution_audit.csv`
- `statistical_finance_candidates_REVIEW.csv`, `review_flags.csv`
- `primary_brand_unmatched_submodels_audit.csv` (coverage check of segment lookup)

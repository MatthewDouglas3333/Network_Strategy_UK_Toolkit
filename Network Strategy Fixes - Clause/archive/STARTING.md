# Starting — next session

## Outstanding decision: cap open-point revaluation at baseline?

**Context.** Removing a dealer can currently produce a small positive
Net Network Change because the open-point revaluation (applied to
sectors that drop outside every 90-min ring) has **no cap-at-baseline**.
If a dropped sector's historical McLaren share was below the UK-wide
open-point average, the revaluation lifts its projected units *above*
its baseline value. Across many low-share sectors (e.g. Scottish
Highlands when Glasgow is removed) this can net positive.

Reassignment-to-neighbour already caps at baseline (set earlier by user
request). Open-point drops do not. The two rules are inconsistent.

## Options

1. **Cap open-point revaluation at baseline** (one-line change in
   `SHARED-CODE/network_strategy_api.py`, add `cap_at_baseline=True` to
   the `_apply_share_override` call around line 1865).
   - Pro: guarantees "removal ⇒ Net Network Change ≤ 0". Consistent
     with reassignment rule.
   - Con: a genuine white-space sector with under-realised local share
     is held down to that under-realised value instead of regressing
     to the empirical open-point mean.

2. **Cap at `max(baseline, revaluation)` only when baseline > 0**
   (keep regression-to-mean for true zeros, prevent compounding lift).
   - More nuanced, more code.

3. **Do nothing, document it.** Keep current behaviour; make sure
   methodology note explains the artefact.

## Recommendation
Option 1 — matches user's existing "removal can never manufacture
volume" principle and is trivial to implement.

## Files to touch
- `SHARED-CODE/network_strategy_api.py` — line ~1865, the
  `_apply_share_override(sector_band_rows, _lookup_openpoint)` call.
- `NETWORK_STRATEGY_METHODOLOGY.md` §10.2 — update wording.
- `GUIDE.md` §5 "Open-point revaluation" — update wording.

## Already shipped this session (for reference)
- Net Network Change now uses `units_total` in both views (conservation
  holds for pure reassignment).
- "In 60-min band" informational row added in 90-min view (mirror of
  "In 90-min band" in 60-min view).

---
title: Goals and Mindset Review (2026-07-24)
category: source
summary: Read-only financial review finding every profit horizon unfavourable, attributing the loss to plain signal underperformance rather than costs
tags: [goals, governor, probe-throttle, review]
sources: 1
updated: 2026-08-01
---

# Goals and Mindset Review (2026-07-24)

**Raw source:** `raw/quant/2026-07-24_goals_mindset_review.md`

## Verdict
Every horizon UNFAVOURABLE. Weekly -17.15 vs +25 goal (0.0% attainment); monthly -16.88 vs +110
(0.0%); trailing 200 trades: win_rate 0.10, PF 0.044, expectancy -$0.1649, net -$32.99.

## Root cause
`monitor.causes` attributes **155/201 graded closes (~77%) to plain UNDERPERFORMANCE** (37
cost_overrun, 6 alpha_wrong, 2 regime_shift, 1 whipsaw). champion_brier 0.1901 is coin-flip.
"The signal mostly just didn't work." This is later re-explained by
[[sources/label-signal-quality]] and ultimately [[sources/cost-to-volatility-horizon-mismatch]].

## Account state
Equity $4,965.86; drawdown 0.69%; fees_total 34.54. Capital eras: $25k (07-10) -> $100k spike ->
$800 crash (07-12) -> reset to $5,000 (2026-07-16). **Open reconciliation item flagged, not silently
resolved**: realized_total (-19.9) vs equity-era net (-34.14) vs 200-trade net (-32.99) do not
reconcile because `scripts/reset_paper_capital.py` zeroes totals while the 200-trade window spans
the pre-reset era.

## The livelock chain
SZ-047 throttle (16 denials since restart) correctly suppresses net-negative probe flow but starves
live-label accrual; bear regime sits at 4/60 live labels so conviction's regime-known term can never
admit bear conviction, keeping the governor shadowed. See [[concepts/probe-livelock]] — decided in
[[sources/livelock-f0-decision]].

## Process finding
**Local ledger contamination**: `outputs/weekly_ledger.csv` / `monthly_ledger.csv` are polluted by
local pytest/smoke runs writing a synthetic $10k account. Authoritative source is
`control/pc_status.json`. Foreshadows [[sources/test-suite-outputs-contamination]].

## Decisions
All KEEP: weekly 25 / monthly 110 goals ("changing on a losing sample = tuning the ruler to the
miss"), `min_trigger_cost_mult` 3.0, `regime_floor_live` 60, `conviction.mode` report,
`max_probe_share` 0.35. Ranked profit levers each carry an explicit **disqualifier** (never widen G1,
never flip conviction early, never manually override the floor or kill switch).

## Mindset audit
Five principles graded against telemetry: preservation-is-root EMBODIED; evidence-buys-size PARTIAL;
context-before-conviction DESIGNED-NOT-LIVE; one-truth-ledger violated locally; corpus-is-the-asset
EMBODIED (OF-3 FAIL filed honestly rather than gate-adjusted).

## Related
[[entities/ml-governor]] · [[entities/liquiditybot]]

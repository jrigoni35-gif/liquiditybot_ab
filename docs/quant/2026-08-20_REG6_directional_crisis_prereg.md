# REG-6 (pre-registered 2026-08-20): directional crisis classification

*Operator directive: "fix the classification 'crisis' in the event of a
20% gain day." Cohort-resetting class (entry decisioning: the crisis
playbook sets allow_new=False, size 0.30, direction none). Registered
NOW, before its own evidence window resolves; adjudicated at the era-4
boundary, never mid-era. Trigger event: 2026-08-20 surge
(docs/quant/2026-08-20_event_record_surge_outlier.md).*

## The defect (agreed)

`macro == "crisis"` fires on vol_percentile >= 95 (or turbulence >= 95)
with NO direction term (regime/macro_regime.py:441-443). Semantics and
playbook were designed for crash tape; a melt-up inherits them wholesale.
The direction signal ALREADY exists in-engine (momentum read +0.33
through the event) - it is simply not consulted by the label.

## Why not even a "rename" ships mid-era

The label string is load-bearing everywhere: playbook lookup key,
regime_crisis ML one-hot (model input -> frozen), postmortem
regime_entry stratification, SZ-022 gating messages, long_book
pause_in_crisis, conviction denial taxonomy. Splitting or renaming it
changes model features and cohort strata even at identical playbook
values. Telemetry already shows direction beside the label (momentum
field); the glass is informative today even if the word is wrong.

## Proposed amendment (adjudicate ONE tier at the boundary)

Split on momentum sign at classification time:
`crisis_down` (momentum < 0) and `crisis_up` (momentum >= 0).

- **Tier 1 - semantic split only**: both new labels inherit the current
  crisis playbook unchanged (allow_new False, 0.30, none). Fixes the
  word and the strata; zero behavior change ON PURPOSE; costs the
  boundary anyway (feature/strata change) so batch it with the rest.
- **Tier 2 - crisis_up probe-only**: crisis_up additionally permits
  EXPLORATION PROBES (budgeted, tiny) but no conviction entries -
  buys labeled data inside melt-ups without real risk change.
- **Tier 3 - crisis_up trades**: allow_new True for longs at
  size_mult 0.15, leverage 1, stop_mult 1.50, limit-only. The full
  behavior change.

## Pre-registered decision criterion (evidence, not adrenaline)

By readout, gate_efficacy over candidates labeled inside crisis-stamped
windows answers the counterfactual directly: the 2026-08-20 window alone
logged 1,132 probe/candidate decisions whose labels resolve by
~2026-08-21 21:00Z. Decide by:

- crisis-window counterfactual win rate & net expectancy vs baseline
  (Wilson intervals; n_eff not row count). Below baseline -> the block
  is EARNING its keep; take Tier 1 only. Above baseline with net > 0
  after the cost stack -> Tier 2; Tier 3 only if a SECOND independent
  crisis-up window (n >= 30 candidates) reproduces it - one event never
  decides (operator's own rule).
- Mind the mean-reversion geometry: limit-only entries in vertical tape
  fill on retraces; the counterfactual labels ALREADY price that
  honestly (fills granted only when the recorded market crossed).

## Costs, named

Any tier = new execution era (boundary #6), accrual resets, and Tier 2/3
add a gate-loosening that must clear the overfit discipline (net-profit
ladder, OF-4: never tuned to this one backtest peak). Batch with the
standing docket (CRITICAL hedge-derisk fix, ALGO-5, feature-importance
verification) per the generational rule: one boundary, one docket.

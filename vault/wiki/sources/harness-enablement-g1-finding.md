---
title: Harness Enablement G1 Finding (2026-07-23)
category: source
summary: Mirroring deployed cost-floor + time-stop geometry into the quant-trials harness broke gate G1, so the enablement was reverted rather than the gate widened
tags: [quant-trials, gates, cost-floor, time-stop, deferral]
sources: 1
updated: 2026-08-01
---

# Harness Enablement G1 Finding (2026-07-23)

**Raw source:** `raw/quant/2026-07-23_harness_enablement_finding.md`

## What happened
Mirroring the deployed `profit_taking` geometry (cost floor + time stop) into the quant-trials
harness broke [[concepts/quant-trial-gates|G1]] at 200x1200. The enablement was **REVERTED** and
the cost-floor question deferred to a live paper-telemetry review armed for 2026-07-25T19:44Z.

## Key numbers
- BASELINE (commit `f6cdbe3`, neither lever) passes all five: G1 p95 4.76% vs cap 5.53%; G2 CVaR5
  -4.57% vs -6.17%; G3 median -1.37% vs floor -2.17%; G4 ruin 0.00%; G5 capture 0.55 vs 0.53.
- ENABLED (both levers) **FAILS G1**: p95 4.85% vs cap 4.66%.
- Ablation: cost-floor ONLY also fails G1 (4.71% vs 4.43%); time-stop ONLY passes (3.45% vs 3.87%)
  and is "strictly gate-positive on every metric".
- Config mirrored: `min_trigger_cost_mult: 3.0`, harness `est_cost_bps = 40.0`,
  `time_stop: {max_bars_no_progress: 36, min_mfe_frac_of_tier1: 0.5}`.

## Mechanism
1. The floor raises tier-1's effective trigger from 1.0% to 1.2% (3.0 x 40bps), delaying partial-take
   de-risking, deepening the p95 drawdown tail.
2. **Lever coupling** — `_time_stop_hit` derives its scratch threshold from the *same*
   `_tier_trigger_pct` the floor raises, so both levers together lift the scratch bar 0.5% -> 0.6%
   MFE. Combined drawdown 5.48% is worse than either alone (5.21% / 4.55%). See
   [[concepts/lever-coupling]].

## Harness-vs-live divergence
Harness synthetic cost stack is 40 bps/side so the floor (1.2%) binds ALWAYS. Live measured stack
~20.5 bps gives a 0.615% floor that binds only in low-vol regimes. **The harness overstates the
floor's bite.** See [[comparisons/harness-vs-live-cost-stack]].

## Discipline demonstrated
A G1 failure is a stop-and-report finding under [[concepts/never-widen-a-gate]]. The enablement diff
was preserved verbatim so re-running is "a paste away". The 80x1000 CI pin stayed green but its G1
margin collapsed ~10% -> ~1% — **the small-N pin is not a reliable early warning**.

## Links
- Cited by [[sources/goals-mindset-review]] (KEEP `min_trigger_cost_mult` 3.0 pending 48h verdict)
- No document in the corpus records the 2026-07-25T19:44Z verdict outcome.

## Related
[[entities/quant-trials-harness]] · [[comparisons/harness-vs-live-cost-stack]]

---
title: Geometry Alignment Adjudication (2026-07-28)
category: source
summary: Report-only closure of the geometry-alignment plan with full battery green, plus a surfaced-but-unfixed DANGEROUS cost-truth verdict
tags: [geometry, brackets, cost-truth, adjudication]
sources: 1
updated: 2026-08-01
---

# Geometry Alignment Adjudication (2026-07-28)

**Raw source:** `raw/quant/2026-07-28_geometry_alignment_adjudication.md`

## What closed
Model-lane entries now trade the same triple-barrier bet the label measures. `_bracket_for_entry`
computes each entry's bracket via the same pure `barrier_geometry()` helper the labeler uses, and
re-sizes through `PositionSizer.size(bracket=...)` so notional shrinks as `sl_pct` widens
([[concepts/risk-in-size]]). PASS-1's approved size is a **hard ceiling** on PASS-2 notional
(downscale only).

## Floored-bracket bar
`ml.label_pt_cost_mult = 4.0` floors sigma so PT >= 4x expected round-trip cost. At cost ~0.5%:
pt = 2.0%, sl = 1.5%; worst-case `b_net = (2.0-0.65)/(1.5+0.65) = 0.628`; required win rate
`1/(1+0.628) = 0.614`. Probe synthetic `p_win = 0.64` clears by 0.026; guard WARNs below 0.005.
"COMPUTED, never hardcoded."

## The cost-truth verdict — DANGEROUS
`scripts/cost_truth_report.py` at **n=16 unique closed trades**: mean `cost_overrun` **+21.17 bps**,
measured round-trip **86.17 bps** vs configured **65.00 bps**, **delta +32.6%**, past the +/-20%
tolerance. `VERDICT [XV-033]: DANGEROUS: configured UNDER measured`.

> Load-bearing caveat: `postmortem_summary.csv` contains only trades whose postmortem TRIGGERED — the
> underperforming subset by construction. Maker-leg venue fee tier is n=0 (no live credentials).
> **And the file itself is later found stale** (17 rows, ends 07-16) by
> [[sources/live-label-era-deadlock]] — so this verdict rests on a corpus frozen ~12 days earlier.

## Battery
Quant trials byte-identical to commit `7f4ffc2`; **no G-number moved**. Overfit 5 passed / 3 failed
(the standing OF-1 gap trio: logistic +0.198, gbt +0.297, mlp +0.236; pbo **0.03**). pytest 2742
passed; smoke 219; assurance 47; ruff clean; pyright 0 errors; bandit 0 issues.

## Deliberate non-action
**No config change for the cost finding** — a fee edit is the operator's conscious commit, never an
automatic script correction. Population-wide cost measurement deferred.

## The regression this shipped
The same T5 bracket work suppressed PT-060 fleet-wide — see [[sources/pt060-bracket-wedge]]. The
battery could not see it because "the trials harness runs `time_stop: {enabled: false}` and has no
bracket seam." A full-green battery and a fleet-wide protection regression shipped together.

## Related
[[entities/pretrade-gate]] · [[entities/quant-trials-harness]] · [[concepts/cost-truth]]

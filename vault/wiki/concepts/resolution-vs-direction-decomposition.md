---
title: Resolution vs Direction Decomposition
category: concept
summary: A feature scored against a triple-barrier label mixes two channels - whether the path reaches a barrier at all (RESOLUTION, which volatility loads) and which barrier it reaches (DIRECTION, the only channel that is an edge). A raw-label AUC is a blend of the two; two measured leads (T2 magnitude 2026-08-30, tape activity 2026-09-01) died to this split, so no feature counts as a signal until both numbers are reported with day-block CIs
tags: [labels, triple-barrier, instrument, overfit, the-method]
sources: 3
updated: 2026-09-02
status: SETTLED (rule); instrument SHIPPED and RUN 2026-09-02 - all 64 stored features scored, none directional
---

# Resolution vs Direction Decomposition

## The mechanism
The bot's label is triple-barrier: `label = 1` when the path touches the profit barrier
(`barrier = tb_pt`) before the stop (`tb_sl`) inside the horizon; a path that touches
neither times out (`tb_time`) and is mostly `label = 0`. So `P(label=1 | x)` factors:

    P(label=1 | x) = P(resolved | x) · P(tb_pt | resolved, x)  (+ the small tb_time→1 leak)

Any feature that moves with **volatility** raises `P(resolved | x)` — more movement, more
barrier touches — without saying anything about *which* barrier. Its raw-label AUC rises
above 0.5 while carrying zero directional information. That is not a signal; it is the
geometry of the label.

## Measured instances (the register)
| date | feature | raw AUC | RESOLUTION | DIRECTION | verdict |
|---|---|---|---|---|---|
| 2026-08-30 | T2 magnitude lead | reads as a lead | — | refuted as barrier-geometry tautology, corr 0.48 with barrier distance | dead (`2f8550de`) |
| 2026-09-01 | tape trade-count intensity `log n_60`, 7 pairs | 0.52–0.58, 4/6 CI-significant | **mean 0.616**, 6/7 significant | **mean 0.510, 0/7 significant** | dead ([[sources/session-20260901-edge-hunter-mirror]] 9b) |

Two instances of one shape make a class: [[concepts/the-method]] recurrence #10.

## The rule (binding, 2026-09-01)
No feature may be called a signal against a triple-barrier label until its skill is
reported as **three numbers on the same rows**: raw, RESOLUTION (`tb_pt|tb_sl` vs
`tb_time`), DIRECTION (`tb_pt` vs `tb_sl`, resolved rows only), each with a day-block
bootstrap CI. Only DIRECTION is an edge. A feature that is RESOLUTION-ONLY (raw CI
excludes 0.5, DIRECTION CI includes it) is a volatility proxy and goes in the null pile.

## The 64 stored features, decomposed (MEASURED 2026-09-02)
`scripts/label_decomposition_report.py` on the production corpus (12,115 rows,
`triple_barrier_h432` only, 24 day-blocks, tb_pt 4582 / tb_sl 5456 / tb_time 2077):

| channel | result |
|---|---|
| DIRECTIONAL | **5 of 64 — against 5.3 expected by chance** at the instrument's own measured null exclusion rate (8.3% per CI, not the nominal 5%). The largest deviation is the feature literally named `direction` (the trade side); its CI does not survive an independent bootstrap realization, and two of the other four point BELOW 0.5. **No stored feature is credibly directional.** |
| RESOLUTION | Loud and consistent, exactly as the mechanism predicts: `sigma_bar_pct` **0.750** [0.642, 0.881], `spread_bps` 0.662, `poc_dist` 0.613, `direction` 0.610, `th_grid` 0.604, `manip_suspect` 0.597. Volatility and spread decide whether the path reaches a barrier. |

Two instrument lessons came out of building it, both caught by an adversarial verifier
that planted its own defect rather than re-reading the author's mutation table:
a **degenerate block count manufactures flags** (one distinct day → every bootstrap
draw identical → zero-width CI → pure noise flagged DIRECTIONAL; now floored at
`MIN_CI_DAYS=5`), and the **day-block WIDTH was unpinned** (switching to hour blocks
passed all twelve original pins and the self-test). Both were missing pins, not wrong
code — which is the argument for the second lens.

## Consequences for the standing questions
- **The 64 stored features:** decomposed above. The prior "0/64 above null" was not
  hiding a RESOLUTION-ONLY feature — it was hiding that the resolution channel is
  strong and the direction channel is empty.
- **Tape features: settled 2026-09-02 on complete coverage.** Twenty tape features
  (signed imbalance, |imbalance|, log trade count, market-order share, tape return at
  60/300/900/3600 s) were scored beside the 64 stored ones — 84 features, 12,422 rows,
  25 day blocks, 98.9% join. **Not one tape feature is DIRECTIONAL**; all are NULL or
  RESOLUTION-ONLY, and the total flag count (6) is BELOW the measured chance rate (10.5).
  The resolution channel reproduces for them exactly as for stored features:
  `tape_absimb_300` RESOLUTION 0.619 [0.578, 0.667] against DIRECTION 0.509. The free
  Kraken tape, back to 2013, adds no directional information about this label.
  (`docs/quant/2026-09-02_tape_features_vs_expectancy.md`, addendum.)
- **The target-change proposal** ([[sources/session-20260901-edge-hunter-mirror]] item 3):
  a magnitude / net-expectancy target does not have this confound in the same form, but
  it has its own — volatility scales |return| too. The decomposition there is sign vs
  magnitude, and it must be pre-registered the same way.
- **Multiple comparisons — the nominal rate is the WRONG comparator (measured 2026-09-02).**
  Earlier versions of this page and of the repo handoff said "~3 of 64 CIs exclude 0.5 by
  chance at 95%". That is the nominal figure and it understates the truth by ~2.5x. The
  instrument's `--null-calibration 200` (200 pure N(0,1) features scored against the REAL
  targets, rows and day blocks) measures a realized DIRECTION exclusion rate of **12.5%**
  on this corpus — day-block bootstrap CIs at 25 blocks are anti-conservative. At 84
  features chance alone yields **10.5** directional flags. Always quote the realized rate,
  and re-measure it: it is a property of the corpus's block count, not a constant.

## Relation
[[concepts/false-strategy-theorem-and-minbtl]] (the sample cannot certify a small edge
anyway) · [[concepts/observational-equivalence]] (a volatility proxy and a directional
signal are observationally identical under a raw-label AUC) · [[concepts/partial-identification]]
(report the identified set — resolution and direction — not the blended point).

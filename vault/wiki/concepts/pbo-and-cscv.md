---
title: PBO and CSCV
category: concept
summary: Probability of Backtest Overfitting measured by combinatorially-symmetric cross-validation: the fraction of splits where the selection rule's choice underperforms out of sample
tags: [statistics, overfit, selection]
sources: 4
updated: 2026-08-01
---

# PBO and CSCV

## Definition
**PBO** is the fraction of CSCV splits in which the selection rule's chosen configuration
underperforms out of sample. Above 0.5 means the selection's **luck share dominates**. **CSCV** is the
combinatorially-symmetric cross-validation machinery that computes it by symmetric recombination of
train/test block splits.

## The load-bearing constraint
PBO is read over the rule the system **actually runs** (the [[concepts/simplicity-ladder]]), never
argmax. Argmax readings are reported only as a **stress figure**.

## Two readings distinguished
- **Widened-space PBO** — over the full measured config space including an experimental arm.
- **Pairwise PBO** — over just the base-vs-arm pairing.

A variant can look good on one and terrible on the other: in [[sources/phase3-adjudication]] the
policy-cleared prune had widened pbo 0.21 but **pairwise pbo 0.94**.

## Observed range in this corpus
0.56 (the initial breach at 3,651 rows) -> 0.23 -> **0.03** (the healthiest reading, at 4,907 rows).

## Interpretation adopted
A PBO breach is "a learning-health signal, not a trading-risk event" while the model is
governor-shadowed and probes are throttled, because champion selection then drives no live sizing.
"The system's existing defenses are exactly the mitigations this finding calls for."

## Watch condition
If PBO still straddles 0.5 once live labels resume and reach +100, **shrink the config-ladder breadth**
— 7 configs may be more selection space than the corpus affords. **Never widen the gate.**

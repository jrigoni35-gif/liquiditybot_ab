---
title: The Simplicity Ladder
category: concept
summary: The deployed selection rule: climb from simple to complex model families only where an evidence margin clears, never argmax
tags: [model-selection, governance]
sources: 5
updated: 2026-08-01
---

# The Simplicity Ladder

## Definition
The deployed selection rule orders model families simple -> complex and climbs a rung **only where the
evidence margin clears**. `logistic` is always admissible and defines the simplicity floor. **Selection
is never argmax.**

## Why it is load-bearing
Every PBO reading in the corpus is taken over this rule, because
[[concepts/gort-rule|the binding policy]] states PBO must measure **the rule the system actually runs**.
The distinction shows up concretely as **ladder winner vs mean winner**: only the ladder winner is a
valid verdict basis; the raw mean-Brier argmax is reported as a stress figure.

## Selection stays on raw Brier
Calibration is **reported per candidate and applied as the final deploy check only**. Rationale:
selecting on isotonic-calibrated Brier once let a complex model win a **pure-linear** world. **"Calibration
must not rescue complexity."** An earlier calibrated-selection experiment was also reverted for CSCV
cross-block leakage.

## Complexity is earned on ground truth
The ladder admits higher-capacity families only when the **live label count** clears a floor — "trying
every learner on a proxy-heavy corpus only manufactures an overfit winner (and inflates PBO)." See
[[concepts/evidence-floors]].

## Who runs it
[[entities/ml-governor]] owns champion/challenger; [[entities/overfit-check]] measures it.

## A citation hazard it creates
The ladder's ordering differs from the PBO instrument's own base ordering. Measuring a variant against
its *instrument* predecessor rather than its *ladder* predecessor confounds an architecture change with
a hyperparameter change — explicitly flagged in [[sources/phase3-adjudication]].

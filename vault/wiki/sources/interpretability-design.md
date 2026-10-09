---
title: Interpretability Design
category: source
summary: Report-only post-hoc interpretability using exact interventional Shapley by subset enumeration, clustered permutation importance, and an explicit refusal to explain what it cannot explain exactly
tags: [interpretability, shapley, report-only]
sources: 1
updated: 2026-08-01
---

# Interpretability Design

**Raw source:** `raw/architecture/INTERPRET.md`

## Posture
**Report-only** — "nothing here writes config, state, or the decision path." Findings feed conscious
schema revisions and the gated tuning pass, **never mid-flight feature surgery**.

## Exact Shapley, no library
The interventional (marginal) Shapley variant is the consistent one; the fast path-dependent variant
"can re-rank features between two trees computing the same function." Because the GBT grows
**depth <= 2 trees (<= 3 features per tree)**, interventional Shapley is computed **EXACTLY by subset
enumeration** against a history-spanning background stashed in the model artifact — **no `shap`
dependency, no kernel, no sampling**.

Against the Fooling-LIME/SHAP attack: "the attack surface is the *sampler*; exact enumeration has
none." Fidelity is re-proved every run via the **additivity audit** — |base + sum(phi) - margin| at
machine epsilon.

## Explain exactly or refuse
Rudin's argument is **half-adopted**: where exactness exists (logistic, gbt) we explain; where it does
not (mlp/ensemble) **we REFUSE rather than guess. "Refusal is a feature."**
See [[concepts/exact-or-refuse]].

## Permutation importance done right
Permute-and-predict forces extrapolation when features correlate; substitution effects split credit
until two informative twins both look useless; MDI/gain **cannot say "nothing matters"** because it
normalizes to 100%. Therefore permutation runs **on correlation clusters as a block**, on a
**time-ordered held-out tail**, with **Brier** as the metric — "and it can (and does) call clusters
useless."

## Two drift instruments
The **attribution fingerprint** (share of mean |phi| per feature) and **attribution drift**
(fingerprint cosine between eval halves) — "reasons can rotate before scores move," and it requires
**no labels**. Complementary to input-drift PSI. The doc does not define an action threshold for
fingerprint drift.

## Portability
The background sample **rides the artifact**, so any deployed champion is explainable without its
training corpus.

## Related
[[concepts/exact-or-refuse]] · [[entities/ml-governor]] · [[entities/lopez-de-prado]]

---
title: Exact or Refuse
category: concept
summary: Explain models where exactness is achievable and decline to explain the ones where it is not; refusal is a feature
tags: [interpretability, doctrine]
sources: 1
updated: 2026-08-01
---

# Exact or Refuse

## The rule
Where an exact attribution exists (bounded-depth trees, linear models), compute it **exactly**. Where it
does not (deep nets, ensembles), **refuse to produce an explanation at all.**

> **"Refusal is a feature."**

## Why exactness is achievable here
Because the boosted trees grow to depth <= 2 (at most 3 features per tree), interventional Shapley
values can be computed **by exhaustive subset enumeration** against a background sample — **no external
library, no kernel, no sampling.**

## The security argument for it
Against known attacks on post-hoc explainers: **"the attack surface is the *sampler*; exact enumeration
has none."** Fidelity is re-proved every run by an **additivity audit** — the reconstruction residual
checked at machine epsilon.

## The companion discipline on permutation importance
Naive permute-and-predict forces extrapolation when features correlate, and substitution effects split
credit until two informative twins both look useless. Gain-based importance **cannot say "nothing
matters"** because it normalizes to 100%. So permutation runs on **correlation clusters as a block**,
on a **time-ordered held-out tail**, scored by Brier — "and it can (and does) call clusters useless."

## The posture
**Report-only.** "Nothing here writes config, state, or the decision path." Findings feed conscious
schema revisions, **never mid-flight feature surgery**.

## Source
[[sources/interpretability-design]]

## A drift instrument worth stealing
The **attribution fingerprint** (share of mean absolute attribution per feature) and its cosine drift
between evaluation halves: **"reasons can rotate before scores move," and it requires no labels.**

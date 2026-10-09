---
title: Average Uniqueness and Effective Sample Size
category: concept
summary: Overlapping label windows make rows non-IID; concurrency-based weighting and the Kish effective sample size reveal how much less the corpus knows than its row count claims
tags: [labeling, statistics, weighting, afml]
sources: 4
updated: 2026-08-02
---

# Average Uniqueness and Effective Sample Size

## The problem
Labels with overlapping outcome windows are not IID. Quoted verbatim from the canonical source:
*"the series of labels {y_i} are not IID whenever there is an overlap between any two consecutive
outcomes."*

## The correction
Per-(asset, 5-minute-bar) concurrency `c_t`; each row's weight scales by **mean(1/c_t)** over its
`[signal_ts, ts]` lifespan. The correction is **mass-preserving** — it redistributes loss weight rather
than removing it, so the total regularization balance is unchanged and ratios and ESS carry the fix.

## The measurement that made it real
On a 1,741-row corpus: mean average-uniqueness **0.0655** — the average row shares its return window
with ~15 others on the same asset. **Kish effective sample size 1,624 -> 239.**

> "The corpus knew ~7x less than its row count claimed."

Worked example from an actual quiet weekend: ~13 concurrent candidates, each weighted ~0.077, so a
~200-row batch counts as **about one fact**.

## Later readings
Mean uniqueness settles around **0.158-0.159** at ~6,462 rows — genuine window overlap (median label
lifespan ~38 bars with per-cycle registration gives ~6 concurrent labels per asset-bar), not duplicate
flooding: exact feature-row duplicates are only **1.1%**.

## A carried defect
`last_load_stats` computes `ess_kish` and `mean_uniqueness` **PRE**-exclusion while `rows` and
`live_clean` are **POST**-exclusion, so the two views report the same ESS while describing different
populations.

## A second carried defect, fixed (2026-08-02)
`label_transfer_filter` had applied the **Kish formula to uniform weights** — with uniform
weights Kish ESS degenerates to the raw count, so the check measured nothing. Fixed to use the
**weight sum**; with the fix the filter **refuses transfer** (closest old-era/new-era analogue
pair 4.5x off the 18x concurrency target — verdict NO ANALOGUE, [[concepts/era-exclusion]]
stands). ([[sources/session-20260802-digest]] second addendum)

## Where it lives
[[entities/historystore]] applies the correction at load time.

## Deliberately not done
Sequential bootstrap is skipped until a bagged family wins selection on merit — it is second-order at
this scale and only touches bagged families.

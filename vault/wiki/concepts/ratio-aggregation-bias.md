---
title: Ratio-Aggregation Bias
category: concept
summary: Averaging per-unit ratios unweighted when the correct estimator is size-weighted, letting tiny observations outvote large ones
tags: [statistics, estimators, telemetry]
sources: 1
updated: 2026-08-01
---

# Ratio-Aggregation Bias

## Definition
Reporting the unweighted mean of per-observation ratios when the estimand is a **population ratio**.
The correct instrument is a size-weighted (Cochran ratio) estimator.

## The instance
Slippage was reported as a **per-fill unweighted mean**, so **$10 exploratory fills outvoted fills at
4x the notional**, making the number **~0.3-0.5 bps rosier** than reality. Fixed by storing
`(slip, notional)` pairs and publishing a notional-weighted key **beside** the legacy one (additive,
non-breaking).

## The two-stage failure that followed
The corrected metric **never reached the dashboard** — it was missing from an export whitelist, so the
right estimator was invisible while the wrong one kept the panel. Caught only by
[[concepts/adversarial-verification]]. **The estimator fix and the plumbing fix are separate work.**

## Where the same shape was deliberately *not* fixed
A markout metric has the identical defect, but its observation deque is snapshot-persisted, so fixing it
requires a versioned persistence migration — consciously deferred as a standalone task rather than
bundled.

## Where it was ruled a known deviation instead
A per-trade cost mean was left alone because the **estimand really is per-trade** and the population is
documented. Same arithmetic shape, different estimand, different verdict — which is the point: the bias
only exists relative to a stated estimand.

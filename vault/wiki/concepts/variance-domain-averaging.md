---
title: Variance-Domain Averaging
category: concept
summary: Averaging volatilities instead of variances biases the estimator down by a computable factor
tags: [statistics, estimators, defect-class]
sources: 1
updated: 2026-08-01
---

# Variance-Domain Averaging

## The defect
Taking the mean of a volatility series in the **volatility domain** rather than the **variance domain**
introduces a Jensen bias. For the range-based estimator involved, the bias is **exactly -4.2%**
(`E[|hl|]/sqrt(4 ln 2) = 1.5958/1.6651`).

## The fix
Take the **root mean square** — average in the variance domain, then take the square root. Verified on
planted synthetic data: the estimator recovered from **0.919 to 0.963** of the true value, with the
residual attributable to a separately-disclosed discrete-monitoring bias.

## The sibling defects in the same family
- **Sampling-frequency noise amplification** — computing volatility from 5-second mids and rescaling to
  bar sigma amplifies microstructure noise variance by a factor of ~60. Fixed with a sparse 60-second
  subsample-and-average.
- **Population vs sample moments** — using `ddof=0` on a hard gate inflated a Sharpe estimate by ~1.7%
  at n=30, **anti-conservative on a gate**. Fixed to `ddof=1`.
- **Asymptotic vs exact quantiles** — a `sqrt(2 ln N)` expected-maximum approximation overstates the
  null Sharpe by **12-17% at N=10-100 and 67% at N=2**. Fixed with exact inverse-normal quantiles.
- **[[concepts/ratio-aggregation-bias|Ratio aggregation]]** — an unweighted mean of per-unit ratios
  where the correct estimator is notional-weighted.

## The unifying lesson
Every one of these is a **unit or domain error in an estimator that runs correctly and returns a
plausible number**. None would fail a test. They are found only by re-deriving each formula against its
canonical treatment **at the system's actual operating point** — see
[[concepts/defect-category-audit]] and [[sources/defect-categories-audit]].

Note the direction discipline: each residual bias is classified as **protective** or
**anti-conservative**, and only the anti-conservative ones are treated as urgent.

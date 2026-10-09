---
title: Correction Verification (2026-07-29)
category: source
summary: Three fresh-eyed verifiers instructed to refute adversarially re-checked five correction waves; 18 of 20 confirmed, 2 suspect items fixed same day
tags: [verification, adversarial, ml-083, grafana]
sources: 1
updated: 2026-08-01
---

# Correction Verification (2026-07-29)

**Raw source:** `raw/quant/2026-07-29_correction_verification.md`

## Method
Three independent verifiers, each **instructed to REFUTE** rather than confirm, re-checked the five
2026-07-29 correction waves. See [[concepts/adversarial-verification]]. Result: 18 of 20 items
CONFIRMED-GOOD, 2 SUSPECT items produced same-day fixes.

## Independent re-derivations
- Payoff math to **1e-12** (`b_net 0.44877`, breakeven **0.69024**).
- CVaR anchor-return exactness under a 47s poll stall.
- Parkinson Jensen removal on planted GBM: **0.919 -> 0.963** (residual = disclosed discrete-monitoring bias).
- `_norm_ppf` accurate to **<=5e-7** vs known quantiles.
- Probe floor-withhold dies as an explicit SZ-042 veto with OM-013 backstop.

## The two SUSPECT findings
1. **ML-083 was fail-closed but likely INEFFECTIVE.** `should_deploy`'s no-champion disjunct frees
   the bar only when the badge is >= 0.25, but the live era-orphaned badge is **0.1237** (measured on
   the dead 0.169-base population), so challengers on the new 0.30-base corpus still lost to a ghost.
   Fixed by calling `should_deploy(..., ignore_champion=True)` under the **ML-076 ghost-badge
   doctrine** — "a cross-base-rate Brier is exactly what a like-for-like gate refuses to compare."
   See [[concepts/ghost-badge]].
2. **`slip_bps_notional_weighted` never reached Grafana** — missing from `gc_pusher`'s whitelist, so
   the correct Cochran ratio estimator was invisible while the dust-skewed simple mean kept the panel.
   A two-stage defect arc: estimator fixed, then plumbing fixed.

Also found: `cvar.bar_sec` had **zero config_guard coverage** — now FATAL outside [60, 1800]s.

## Grafana free-tier audit
100% core panel types + 6 free signed Business Text panels; Prometheus-only; active series ~600-800
= under 10% of the 10k allowance. `GC_PERIOD_SEC` default 30s -> 60s because 2 datapoints/minute
doubled the free tier's 1-DPM metering for zero benefit.

## Conscious deferrals
CVaR post-restart warmup ~10h (the bar-return window is not persisted; shortening it needs a snapshot
schema migration); the <=25s give-back mask during resting-maker PT-060 deferral.

---
title: Fill Hazard L1 Report (2026-07-31)
category: source
summary: Attempted empirical adjudication of maker-fill hazard time-consistency; returns INSUFFICIENT_EVIDENCE because all 366 tapes are burst re-reads rather than engine polls
tags: [fill-model, measurement, insufficient-evidence]
sources: 1
updated: 2026-08-01
---

# Fill Hazard L1 Report (2026-07-31)

**Raw source:** `raw/quant/2026-07-31_fill_hazard_l1.md`

## Verdict
**INSUFFICIENT_EVIDENCE (`XV-052`)**. No verdict, no change.

## What was attempted
Whether the maker-fill sim's constant-per-poll hazard is time-consistent. Mode is **book-frame
synthesis** — recordings contain order-book snapshots only, so resting-maker episodes are synthesized
by replaying frames against a hypothetical resting level.

## Why it failed
Recordings: 61 sessions, **366 symbol-tapes**, 732 book frames, ~110.8h wall clock. Per-tape median
intra-frame gap is **0.011-0.018s** against `polling_interval_sec = 5s`. **All 366 tapes deviate by
more than 3x** and were excluded by the frame-gap guard -> **0 tapes fitted**. There are only ~2.0
book polls per tape and the longest observed episode is **0 polls vs horizon T=5** — poll ages beyond
that are structurally unobservable in these recordings **regardless of session count**.

These are **burst re-read tapes**: they measure intra-second book flicker, not the per-poll hazard.

## Standards stated
Verdict rule: YES iff relative misstatement of F(T) > 10% AND LR p < 0.05, against the best-fit
constant hazard — a **shape** test only; the LEVEL belongs to `calibrate_fills.py`. Resolution needs
>= 2 resolved bins, 80 episodes and 10 hits per bucket.

## Caveats that would qualify any future YES
With `queue_aware` on, the sim's effective hazard is **0 until the modeled queue clears, then
constant** — the assumption under test is the post-queue-clear phase. Residual heterogeneity biases a
pooled hazard **toward apparent decrease (frailty artifact)**.

## Remediation prescribed
Accrue recordings via `system.record_feeds` **polled at the engine cadence** with enough polls per
session to cover the order-timeout horizon, then re-run.

## Standing
The ~3.5x sim optimism flagged in [[sources/literature-estimator-audit]] remains **unmeasured**. Net
movement across two documents: zero — but the instrument now exists and the data requirement is
specified. A model instance of [[concepts/honest-null-result]].

---
title: quant_trials (the Monte-Carlo harness)
category: entity
summary: The 200x1200 Monte-Carlo path simulator enforcing the five risk gates, and a documented example of a harness diverging from live
tags: [script, measurement, risk]
sources: 4
updated: 2026-08-01
---

# quant_trials (the Monte-Carlo harness)

The Monte-Carlo harness enforcing [[concepts/quant-trial-gates|G1-G5]] over 200 paths x 1200 bars at a
fixed seed, deterministic across runs. Runtime ~4 seconds.

## Two arms
A **baseline** arm and a **protocol** arm; several gates are comparative (does the protocol stack
preserve upside and improve the tail?).

## Its two documented blind spots
1. **A synthetic cost stack that diverges from live.** Its 40 bps/side assumption makes a cost floor
   bind *always*, where the live ~20.5 bps stack makes the same floor bind only in low-volatility
   regimes. **The harness overstates the effect.** See [[comparisons/harness-vs-live-cost-stack]].
2. **No bracket seam, and the time stop disabled.** It reported "ALL GATES PASS, no G-number moved" for
   the same change that shipped a fleet-wide protection regression — the harness structurally could not
   see it.

## The small-N pin caveat
A cheaper CI replica exists but is **explicitly not a substitute**: under a change that broke G1 at full
scale, the pin stayed green while its margin collapsed from ~10% to ~1%. **Re-baseline only at full
scale.**

## Governing rule
A gate failure is a stop-and-report finding. If live data confirms a harness direction at material size,
re-derive the mechanism and re-baseline all five gates — [[concepts/never-widen-a-gate]].

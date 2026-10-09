---
title: Lever Coupling
category: concept
summary: Two controls sharing a common computed quantity, so enabling both produces an effect worse than either alone
tags: [risk, configuration, non-additivity]
sources: 2
updated: 2026-08-01
---

# Lever Coupling

## Definition
Two independently-configured levers that both derive from the **same underlying computed quantity**.
Enabling both does not compose additively — it compounds, because each change to the shared quantity
moves both levers at once.

## The instance
A cost floor raises tier-1's effective trigger. The time-stop's scratch threshold is derived from
**that same trigger function**, so raising the floor also raises the scratch bar (0.5% -> 0.6% MFE),
scratching a wider band of trades. Measured drawdowns: **5.21% floor-only, 4.55% time-stop-only, 5.48%
both** — the combination is worse than either.

Individually, one lever is "strictly gate-positive on every metric" and the other fails G1. Together
they fail worse than the failing one alone.

## Operational consequence
> "Changing one re-runs untested coupling."

This is why both levers were held at their current values pending a single verdict rather than tuned
separately — a coupled pair must be adjudicated as a pair.

## Detection
Coupling of this kind is invisible in single-lever ablation *summaries* and only appears when the
ablation grid includes the both-on cell **and** someone reads the shared call site. It was found by
tracing `_time_stop_hit` back to the same trigger helper the floor modifies.

## Related
[[sources/harness-enablement-g1-finding]] · [[comparisons/harness-vs-live-cost-stack]] ·
[[concepts/quant-trial-gates]]

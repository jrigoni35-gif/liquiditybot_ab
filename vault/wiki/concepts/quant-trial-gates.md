---
title: Quant Trial Gates (G1-G5)
category: concept
summary: Five Monte-Carlo acceptance gates on the trials harness measuring tail drawdown, tail outcome, upside, ruin, and capture
tags: [gates, monte-carlo, risk]
sources: 3
updated: 2026-08-01
---

# Quant Trial Gates (G1-G5)

## The five gates
- **G1** — tail drawdown: MaxDD p95 vs cap
- **G2** — tail outcome: CVaR5 vs floor
- **G3** — upside intact: median terminal vs floor
- **G4** — ruin rate
- **G5** — gain capture (protocol arm vs baseline arm)

Run at **200 paths x 1200 bars, seed 7**, deterministic. A small-N pin (80x1000) exists in CI.

## A representative green reading
G1 4.76% vs cap 5.53% | G2 -4.57% vs -6.17% | G3 -1.37% vs floor -2.17% | G4 0.00% | G5 0.55 vs 0.53.

## Two hard lessons
1. **The small-N CI pin is not a reliable early warning.** Under an enablement that broke G1 at full
   scale, the 80x1000 pin stayed green while its G1 margin collapsed from ~10% to ~1%.
   **Re-baseline only at 200x1200.**
2. **The harness cannot see what it does not model.** It runs with the time stop disabled and has no
   bracket seam, so it reported "ALL GATES PASS, no G-number moved" for the same task that shipped a
   fleet-wide protection regression ([[sources/pt060-bracket-wedge]]).

## The harness
[[entities/quant-trials-harness]]

## Discipline
A G1 failure is a **stop-and-report finding** under [[concepts/never-widen-a-gate]]. If live data
confirms a harness direction at material size, the fix is a conscious re-derivation of the mechanism,
"never a gate widen" — then re-run and re-baseline all five.

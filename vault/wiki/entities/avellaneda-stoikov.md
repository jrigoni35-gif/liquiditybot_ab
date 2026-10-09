---
title: Avellaneda-Stoikov (and the GLFT extension)
category: entity
summary: The market-making model behind inventory-skewed quoting, adopted in its stationary perpetual-quoting form
tags: [model, external, execution]
sources: 3
updated: 2026-08-01
---

# Avellaneda-Stoikov (and the GLFT extension)

The quoting model: a reservation price that leans against inventory, with spread width determined
separately from spread center.

## What was adopted
`r = s - q*gamma*sigma^2*(T-t)`; an inventory-skewed quote; and a **hard bound that stops
inventory-increasing quotes while exits stay allowed** — noted as **"exactly our invariant-5 philosophy,
independently derived."**

Quantified tradeoff from the source: inventory skew costs **~6% expected profit for >2x lower P&L
variance.**

## The documented deviation
The implementation uses **linear-sigma** half-spread, which is the **stationary (GLFT) normalization** —
correct for perpetual quoting, because the raw finite-horizon form collapses as time-to-terminal goes to
zero. The intensity parameterization is a re-parameterization of the original, and this is now stated in
the docstring rather than left implicit. Above a volatility threshold the max-half-spread clamp binds
anyway.

## The governance rule attached
**Gamma stays a config knob under the gated tuning pass, never learned live** — reinforcement-tuned
variants showed extreme-drawdown tails.

## Its architectural consequence
"Inventory mean-reverts by construction" — the skew leans against inventory, soft caps stop same-side
adds, hard caps force reduction. This is a *structural* property rather than a policy, which is why it
survives every other layer being disabled.

## Related
[[sources/research-20260718-sweep]] · [[sources/architecture-v2]] ·
[[sources/literature-estimator-audit]]

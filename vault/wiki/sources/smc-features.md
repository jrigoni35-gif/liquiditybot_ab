---
title: SMC Feature Module
category: source
summary: Smart Money Concepts as a pure feature-computation module adding seven structural context columns; it never gates, sizes, or times an order
tags: [features, smc, ml, structure]
sources: 1
updated: 2026-08-01
---

# SMC Feature Module

**Raw source:** `raw/architecture/SMC.md`

## What it is
ICT/Smart-Money-Concepts structural context, recomputed fresh from candle history every cycle and
handed to the meta-model as **seven extra feature columns**. Its role is identical to the other state
features: **it never touches `direction` or `all_confirmed`.** The signal engine still decides whether
a trade fires; **SMC only shades what the meta-model believes `p(win)` is once one does.**

## Stateless by design
Every feature is recomputed from the view's candles — no per-asset accumulator to keep in sync,
**no train/serve skew**; short or garbage history degrades to a neutral value rather than raising,
"the same fail-safe contract as THALES."

## The seven columns
- **`mtf_align` [-1,1]** — EMA fast/slow cross computed independently on LTF view candles **and on
  genuine HTF daily candles, not a resample** of the same short window. Each timeframe with a defined
  trend casts one vote; **a timeframe with insufficient history drops its vote rather than forcing a
  tie**.
- **`pd_zone` [0,1]** — price position inside the swing range (0 = discount, 1 = premium). **The model
  learns the bias itself** via interaction with `direction`; the module does not hardcode it.
- **`liq_pocket_pull` [0,1]** — magnetism toward the resting stop cluster beyond the swing extreme in
  the trade's own direction.
- **`fvg_pull` [0,1]** — proximity to the nearest unfilled 3-candle fair value gap.
- **`fvg_liq_confluence` [0,1]** — how closely the nearest unfilled gap overlaps the liquidity target.
  "High confluence marks a higher-probability zone precisely because two independent SMC readings
  agree on it."
- **`poc_dist` [-1,1]** and **`va_pos` [-1,1]** — signed distance to the volume-profile point of
  control and position relative to the Value Area.

## The shared primitive
`swing_high_low` is shared with THALES TH-013 — "rather than maintaining two drifting definitions of
'swing'." **THALES uses it defensively** (shade down when OUR order would rest in the herd's cluster);
**SMC uses it as a target** (shade the model's belief when price is drawn toward one). Same primitive,
opposite polarity.

## Gaps
No evidence yet that the seven columns improve OOS Brier — SMC ships as features and lets the
meta-model decide. Unlike THALES it has **no shadow/advise activation ladder**; the only kill switch
is the enable flag.

## Related
[[comparisons/smc-vs-thales-swing-usage]] · [[entities/thales-engine]]

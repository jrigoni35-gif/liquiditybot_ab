---
title: MDPI Label-Driven Optimization (2025) — the Monotone-Horizon Signal
category: source
summary: Peer-reviewed paper arguing the optimal label look-ahead window is asset-specific and should be tuned per instrument; adjudicated against this project's per-asset ladder — the claim has something to grab only in the two BTC cells (h=48/96) that sit above the first-touch null
tags: [research, labeling, horizon, per-asset, external]
sources: 1
updated: 2026-08-02
source_path: raw/research/2026-08-02_mdpi_label_driven_optimization.md
source_date: 2025-12
authors: [not captured in snapshot — MDPI Mathematics 13(23):3889]
ingested: 2026-08-02
---

# MDPI Label-Driven Optimization (2025)

*"Label-Driven Optimization of Trading Models Across Indices and Stocks: Maximizing Percentage
Profitability"*, MDPI **Mathematics 13(23):3889**, published 2025-12-04. Ingested 2026-08-02
([[sources/session-20260802-digest]] second addendum).

## What the paper does
A labeling-aware ML pipeline that **jointly tunes model, feature subset, and label look-ahead
window per asset**, using a deterministic **Monotone-Horizon Signal (MHS)** label built on the
price path's monotonic behavior (no arbitrary thresholds). Universe: daily OHLCV 2005–2024,
4 indices (SPX, NASDAQ-100, DJI, TASI) + 12 constituents; train 2005–2021, test 2022–2024;
85 engineered technical features; grid of 16 instruments × 6 model types × 8 look-ahead horizons
× 4 feature-subset sizes (**3000+ configurations**).

## Its four claims
1. **Stock-specific label tuning** — the optimal look-ahead window varies per asset: liquid U.S.
   stocks favor short windows (~3 days), less-liquid TASI names longer (6–10 days).
2. **Compact feature discovery** — permutation-importance ranking down to the most informative
   features.
3. **Model–label–feature joint optimization** — the best combination is per-asset.
4. **Transferable configurations** — index-level winners often transfer to constituents.

## Adjudication against this project (2026-08-02)
The one claim that touches this system is #1, per-asset horizon tuning. Measured against the
per-asset ladder ([[sources/session-20260802-digest]] second addendum): only
**BTC h=48 (0.482 [0.448, 0.517])** and **BTC h=96 (0.479 [0.448, 0.510])** sit above the
first-touch null of 0.429 — with a multiple-testing caveat — while **LTC h=48/96 ≈ 0.10** and
**FLOW ≈ 0.33** sit *below* null. **Per-asset tuning has something to grab only in the BTC
cells.** Elsewhere there is nothing to tune toward.

## Caveats that bound any adoption
- **Daily equity bars, not 5-minute crypto** — a different microstructure and cost regime.
- A **3000+-configuration grid search selecting on profitability** is exactly the
  selection-under-multiplicity that [[concepts/pbo-and-cscv]] and [[concepts/gort-rule|the Gort
  Rule]] exist to punish; nothing from this paper is champion-eligible without CSCV measurement.
- Any horizon change is frozen anyway until the 432-bar cohort fills
  ([[comparisons/horizon-96-vs-24-bars]]).

**Status: no adoption.** The paper functions as a hypothesis pointer at the BTC cells, nothing
more.

## Related
[[concepts/triple-barrier-labeling]] · [[concepts/cost-to-volatility-ratio]] ·
[[synthesis/the-money-path-thesis]]

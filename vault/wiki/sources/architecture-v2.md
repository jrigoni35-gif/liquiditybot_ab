---
title: Architecture V2
category: source
summary: The three-cadence system map layering a macro regime brain, execution stack, ML sizing layer, and narrative-resistance filter over the signal engine and profit tiers
tags: [architecture, pipeline, regimes, base-map]
sources: 1
updated: 2026-08-01
---

# Architecture V2

**Raw source:** `raw/architecture/ARCHITECTURE_V2.md`

The **base map**. Every other architecture doc hardens, audits, extends, or supersedes part of it.

## Three cadences
- **Hourly** — daily candles -> `MacroRegimeEngine` (HMM + TSMOM + drawdown/vol) ->
  `CorrelationEngine.turbulence` (Kritzman-Li) -> a per-regime playbook setting bias, size, leverage,
  tiers, stops.
- **Slow (30s)** — books+candles -> `FairValueEngine` (depth-weighted microprice) -> `VolRegimeEngine`
  (Parkinson blend) -> `LiquidityRegimeEngine` (spread/depth/spoof) -> `CorrelationEngine`; in
  parallel news/RSS/Reddit -> `SentimentScanner` and CoinGecko + Fear&Greed -> `WebDataFeed` ->
  `NarrativeFilter`.
- **Fast (5s)** — Kraken marks/books -> `OrderManager.poll` -> fills -> positions -> hard stops ->
  tier exits -> `InventoryManager.derisk` -> `HedgeEngine`.

## Decision chain
5-gate signal -> features -> `MetaModel P(win)` -> Kelly sizer x (regime, vol, liq, sentiment) ->
Avellaneda-Stoikov inventory-skewed quote -> `PreTradeGate` (edge >= 1.3x fees + spread + book-walk +
sqrt-impact) -> `OrderManager.submit` (post-only limit).

## The seven key design rules
1. **Fair value first** — nothing prices off last trade.
2. **Vetoes compose** — regime playbook -> inventory caps -> leverage governor -> Kelly sizer ->
   pre-trade gate; **any zero kills the trade**. Exits are exempt from the edge gate.
3. **Inventory mean-reverts by construction** — AS skew leans against inventory; soft caps stop
   same-side adds; hard caps force reduction.
4. **Spoof detection is defensive only** — "the bot never paints liquidity itself."
5. **Sentiment is a filter, never a trigger** — enforced structurally by limiting the scanner's
   consumers to the NarrativeFilter plus two feature columns.
6. **Leverage is earned, never default** — `use_margin=false` ships default; config is a ceiling, not
   an entitlement.
7. **ML is honest or absent** — cold-start prior only when all gates confirm; a challenger must beat
   the baseline OOS in purged walk-forward to deploy; probabilities shrunk toward 0.5. **The monitor
   can only make the bot more conservative than config, never less.**

## Venue split
**Kraken is the sole execution venue and holds the only credentials.** OKX and Binance.US are public,
read-only, keyless data. Binance.US is spot-only, so the funding gate rides the OKX perp alone.

## Model pedigree
Every component traced to a named published model: Hamilton 1989, Moskowitz-Ooi-Pedersen 2012,
Moreira-Muir 2017, Kritzman-Li 2010, RiskMetrics EWMA, Avellaneda-Stoikov 2008, Almgren-Chriss
sqrt-impact, Lopez de Prado, fractional Kelly.

## Stale claims
Several parts are superseded — the active engine (see [[sources/assurance-rev3]]), the two-model
"MLP vs logistic" framing (the zoo now has gbt/blend/mlp/adaptive_gbt), and calibration's role
(selection stays on **raw** Brier per [[sources/thales-doctrine]]). See
[[synthesis/documentation-drift-register]].

## Related
[[entities/liquiditybot]] · [[entities/kraken]] · [[entities/read-only-venues]] ·
[[entities/ml-governor]] · [[entities/pretrade-gate]]

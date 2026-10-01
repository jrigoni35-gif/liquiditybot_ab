# 2026-10-01 — Per-asset venue leverage caps for the operator's location (COHORT FORK, STAGED for the 10-12 review)

Operator, verbatim (2026-10-01): "1. Alabama" / "2. Yes correlate all assets
with the leverage options appropriate for my location." Question 2 was asked
as "Should the PAXG leverage limit drop to 5x ... at the 10-12 review?", so
this ships AT the review, on branch `claude/per-asset-leverage`, not before -
deploying now would reset the cohort the operator is waiting on.

**Fork:** config (`leverage.asset_max_leverage`, `unlisted_asset_max_leverage`)
plus `risk/leverage.py` and one `main.py` call. Running `6709bbc2778d` ->
staged `5e79a7822082`. Hard invariants untouched: nothing here weakens a
safety property; it narrows leverage, never widens it.

## Evidence

- **Location:** Kraken's geographic-restrictions page (read 2026-10-01): no
  service to residents of Maine and New York only; margin "available to
  eligible US retail clients", no US state excluded. Alabama: served.
- **Venue caps:** Kraken "Getting started with US margin" (read 2026-10-01),
  provider NinjaTrader Clearing, LLC d/b/a Kraken Derivatives US (CFTC FCM,
  NFA 0309379): 20x BTC; 10x ADA AVAX DOGE ETH LINK LTC SOL SUI USDC XRP; 5x
  AAVE BCH CRV DOT HBAR HYPE PEPE PAXG SHIB TRX UNI ZEC; 3x PENGU NEAR RENDER;
  2x ALGO XLM. Of the 15 assets the bot has traded, **ARB, MINA, FLOW are not
  marginable for US clients**.
- **Gap:** `region_max_leverage: 10` was a flat scalar; PAXG's venue cap is 5x.

## Change

| asset(s) | cap | note |
|---|---|---|
| BTC | 20 (venue) | region ceiling 10 still binds -> **10x** effective |
| ETH LINK ADA SOL XRP DOGE SUI AVAX LTC | 10 | |
| PAXG DOT | 5 | binds even today: the shipped 35% vol target tops out at 7x (vol floor 5%) |
| ARB MINA FLOW + any unlisted | 1.0 (spot only) | fail closed - never levered by omission |

- `LeverageGovernor.decide(..., asset=None)`: extended with a default; no
  asset or no table = legacy behaviour exactly. The asset cap bounds the
  BOOK's allowed leverage for an entry in that asset (conservative).
- `config_guard._validate_asset_leverage`: malformed cap FATAL; unlisted cap
  above region FATAL; **a LIVE margin config without the table FATAL**; a cap
  above region WARNs (region still binds).

**Expected effect:** realized leverage has been 0.004-0.12x per position and
0.344x aggregate (`2026-09-02_leverage_liquidation_distance.md`); no cap has
ever bound, so entries should not change in practice. The protection matters
the moment leverage is actually used, and above all before ARM LIVE.

**Not decided here (operator):** raising `region_max_leverage` to let BTC use
its 20x venue cap. Not recommended - no edge is established and leverage
without edge is pure variance drag (`docs/research/regulation/02_literature_2025_2026.md`).

Pins: `tests/test_asset_leverage.py` (24, mutation 7/7 vs green control),
including the shipped table equal to the venue table for every traded asset.

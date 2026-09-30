# 2026-09-30 — TE-1: every closed trip explains its own PnL (SAFE)

Operator, verbatim: "Whether the position ends in a negative PnL or a positive
PnL, all features should coupling in ways where said PnL and evidence of why
it resulted in that PnL should be apparent. It shouldn't just end in 'more
data will show' because so far it has not." / "react with a better sample
format that the bot can read in outputs".

**Class: SAFE** (measurement + telemetry export). `scripts/trip_explain.py`
writes `outputs/trip_explanations.jsonl` (schema TE-1, one JSON record per
closed trip, regenerated whole, atomic replace). Nothing in the decision path
reads it (pinned). Wiring it INTO a decision would fork the cohort.

## The record (TE-1)

Exact identity, checked per trip (`identity_residual_usd`, max 0.000000 over
445 trips on the first run):

    net = market + asset_specific + timing + slippage + fees
          (or price_unattributed + slippage + fees when the tape is missing)

- `market` = side x beta x basket return (BTC/ETH/LINK excluding the asset),
  beta by OLS on 5m returns from up to 7 days BEFORE entry.
- `asset_specific` = what the asset did beyond beta x basket.
- `timing` = the fills vs the 5m anchors; `timing_split_usd` separates entry
  from exit. **Read exit timing by exit reason**: a stop fires exactly when
  price moves against the trade inside a bar the anchor has not closed, so it
  is negative by construction (tb_sl median -32.7 bps, tb_pt +27.8) -
  anchor-lag selection, not a cost. The execution cost is `slippage`.
- `evidence`: every side-relative `*_dir` feature at entry, counted with /
  against, top 3 each, the `lane` (probe / conviction), and whether the
  evidence majority matched where the price went. A probe's `p_win` is the
  exploration constant, never a model estimate.
- `verdict` (deterministic): `WIN_<driver>`, `COST_EATEN`, `LOSS_<driver>`,
  drivers MARKET / ASSET / TIMING / PRICE; losses tagged
  `AHEAD_THEN_REVERSED` (best excursion beat the trip's own cost) or
  `NEVER_AHEAD`.
- `why`: one sentence composed from the numbers above.

CS-1: unit = position. First run `n=610 = explained=445 + hedge_book=159 +
open=6 [OK]`. Cohort = the entry leg's `decision_fp` via `core.cohort`.

## What it said on first run (2026-09-30; re-derive, never copy forward)

Era-9 (entries since 2026-09-08T23:47:45Z): 93 trips, net -37.91 USD =
fees -23.77 + price_unattributed -10.50 + asset_specific -3.07 + timing -1.80
+ market -0.36 + slippage +1.58.

- **Lane**: probe 81 trips net -37.76 (fees -21.81, 37 wins); conviction 10
  trips net +0.25 (4 wins). The era-9 loss is the probe lane - the settled
  "keep exploring" decision (HANDOFF), now priced per trip.
- **Fees are the largest single cause** (63% of the era-9 loss).
- **Entry evidence did not predict the move**: evidence majority WITH the
  trade in 69 trips, price then moved with it in 34 (49%).
- **Entry timing median 0.0 bps**: the bot does not chase its entries.

## The tape gap this exposed (and what was done)

The 5m candle store's intraday lanes ended 2026-09-01..09-07: the primary
collector (`scripts/candle_collect.py`, zero API cost, reads the bot's ring)
was never scheduled - the daily task backfills `--interval 86400` only. Its
own docstring: every day it does not run is 5m path lost from the world.
Recovered 2026-09-30T12:00Z with one `--once` run: 32,400 bars (2,160 x 15
assets), 0 conflicts; BTC/ETH/LINK/PAXG now covered 2026-09-23T00:35Z..now.
Still open: 2026-09-07..09-23 (71 of 93 era-9 trips report
`price_unattributed`); Kraken OHLC reaches ~2.5 days, so it needs the trades
backfill. Scheduling the collector is a persistent configuration change -
OPERATOR DECISION.

## Companion: why the Markov report printed insignificant numbers

`scripts/markov_edge_power.py` planted edges into the real corpus structure:
the calibration-gain metric detected 0/40 even at delta 2.0 under the real
day-level drift (sd 3.49 barrier-widths) - blind; the within-day AUC detected
delta 0.6 in 38/40 and 1.2 in 40/40. The p floor at 200 null reps (0.004975)
sat above the 12-test Bonferroni bar (0.004167). Real basis AUC 0.543 maps to
delta ~0.5, ~40% of break-even. The report now prints both facts every run.

---
title: "Session 2026-09-30 — TE-1: every closed trip explains its own PnL; the candle collector was never scheduled; the Markov report's gain metric was blind"
category: source
status: SETTLED-AS-OF-RUN
summary: "Operator: PnL and its why must be apparent per trip, in a bot-readable format. scripts/trip_explain.py writes outputs/trip_explanations.jsonl (TE-1): exact identity net = market + asset_specific + timing + slippage + fees (max residual 0 over 445 trips), entry evidence, lane, verdict, why. Era-9: -37.91 USD, probe lane -37.76, fees -23.77 largest cause, entry evidence majority matched the move 49%. Exit timing is anchor-lag selection (tb_sl -32.7 bps by construction), not a cost. The 5m collector was never scheduled; 32,400 bars recovered. Power run: the Markov report's gain metric detected 0/40 even at delta 2.0; within-day AUC has power; basis ~ delta 0.5."
tags: [trip-explanation, te-1, pnl-attribution, beta, probe-lane, fees, candle-store, candle-collect, tape-gap, power-analysis, markov-edge, anchor-lag, era-9]
sources: 1
updated: 2026-09-30
---

# Session 2026-09-30 — TE-1 trip explanations

Repo record: `docs/quant/2026-09-30_trip_explanations_te1.md`. Code: `scripts/trip_explain.py`
(19 tests, mutation 11/11 vs green control), `scripts/markov_edge_power.py`.
Follows [[sources/session-20260929-markov-brownian-edge|the Markov-Brownian walk-forward]] and
[[synthesis/the-money-path-thesis|the money-path thesis]] (fees as the binding term, now per trip).

> [!info] UPDATED 2026-09-30T16:15Z — the tape hole is closed
> Trade-tape backfill (BTC 2.59M / ETH 1.27M / LINK 289k / PAXG 89k trades, end_of_tape, IDs double-derived) -> tape_to_candles 5m:
> ~6,580 new bars per major (22.86 d x 288), 0 conflicts. The candle collector now runs from pc_supervisor every 6 h.
> Re-run: ALL 97 era-9 trips split (was 22 of 93). Era-9 net -37.13 = fees -24.76 + timing -12.19 (stop anchor-lag, mechanical)
> + asset -6.77 + market +5.02 + slippage +1.56. Probe (85): market -1.58, fees -22.80. Conviction (10): market +6.38, fees -1.47.
> Finding 2's 'price_unattributed -10.50 (tape hole)' is SUPERSEDED by this split.

## Findings (first run 2026-09-30; re-derive)

1. Identity closes exactly per trip; CS-1 `n=610 = explained 445 + hedge_book 159 + open 6`.
2. Era-9 (93 trips) -37.91 USD: fees -23.77, price_unattributed -10.50 (tape hole), asset -3.07,
   timing -1.80, market -0.36, slippage +1.58. Probe lane -37.76 (81 trips); conviction +0.25 (10).
3. Entry evidence majority WITH the trade in 69 era-9 trips; price moved with it in 34 (49%).
4. Entry timing median 0.0 bps (no chasing). Exit timing by reason: tb_sl -32.7 (n=47), tb_pt +27.8
   (n=9): a lagged anchor conditioned on the trigger — mechanical, NOT a cost. I first read it as a
   cost channel and corrected it the same session.
5. The 5m candle collector (`candle_collect.py`) was never scheduled; the daily task fetches 1d only.
   Intraday lanes ended 09-01..09-07. Recovered 09-23..now (32,400 bars, 0 conflicts).
   OPEN (operator): schedule the collector; trades-backfill 09-07..09-23.
6. Power: Markov report calibration gain 0/40 at planted delta 2.0 under the real day level (sd 3.49);
   within-day AUC 38/40 at 0.6, 40/40 at 1.2. p floor 1/201 above Bonferroni 0.05/12. Basis ~ delta 0.5.

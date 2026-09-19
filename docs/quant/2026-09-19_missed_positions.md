# Missed positions — what era-9 did NOT enter, and why (2026-09-19, SAFE-class)

Measurement only. Sources: `outputs/audit.jsonl` (4,446 era records since
2026-09-08Z), `outputs/fills.csv` (era stamp 12-10d4d0c2), and the new
research corpus (`research/corpus/binance_vision/`, Binance 5m bars; ~7-9 bps
USD/USDT basis vs Kraken — shape analysis, not venue-exact levels).
Chart: `outputs/reports/missed_positions_2026-09-19.png`.

## The funnel (era-9, 09-08 → 09-19T21:50Z)

| Stage | Count | Note |
|---|---|---|
| Entry-sweep arrivals (EN-000, cumulative) | 8,040 | |
| — skipped, signal unconfirmed (EN-030) | 6,643 | **82.6% die here** |
| Deeper funnel | 1,397 | |
| Conviction-stack evaluations | 455 | CV-000 75 admitted / CV-010 208 agreement-low / CV-030 172 regime-unknown — **all `mode:"report"`: the conviction lane judges but does not gate** |
| Probe-lane throttles | SZ-049 ×193 (budget exhausted), SZ-053 ×24 (tuition governor, e.g. trailing-24h tuition $1.03 vs cap $0.79 → refill 0.76) | self-limiting after losses |
| Entry orders reaching terminal state | 476 | |
| — expired unfilled (OM-040, fill_ratio 0.00, sim timeout) | 374 | **79% of placed entry orders never fill** (ETH 255, LINK 49, PAXG 48, BTC 22) |
| Entry fills (fills.csv, era-9, all books) | 58 | ≈ 4.9/day |
| Closed trips (SELECTED 5m-book row, era readout) | 40 + 4 open | net −$0.43/trip, CI [−0.71, −0.17] |

## What the tape offered at the bot's own label geometry

Label geometry: +1.80% / −1.35%, vertical 432 × 5m bars = **36h** (config
`_max_bars_migration_doc`). Every 5m bar in 09-08→09-19 treated as a
hypothetical entry (full-forward only; 432 trailing bars censored):

| Symbol | PT-first | stop-first | vertical (36h unresolved) |
|---|---|---|---|
| BTC | 34.4% | 37.6% | 28.0% |
| ETH | 37.4% | 62.3% | 0.3% |
| LINK | 24.2% | **75.4%** | 0.3% |
| PAXG | 15.0% | 42.3% | **42.6%** |

**The unconditional tape is hostile at this geometry** — stop-first
majorities everywhere (LINK 3.1:1 against). Expected in theory (the stop is
1.33× closer than the target); now measured. There is no large pool of
"obvious" winners the bot is ignoring.

## How the bot's actual entries grade against that tape

58 era-9 entry fills, 36h forward from fill price (11 censored by corpus
end; 47 evaluable):

| Symbol | PT-first | stop-first | vertical | vs base rate |
|---|---|---|---|---|
| BTC | 6 | 6 | 2 | better (43% vs 34%) |
| ETH | 8 | 5 | 0 | much better (62% vs 37%) |
| LINK | 7 | 2 | 0 | much better (78% vs 24%) |
| PAXG | 1 | 6 | 4 | **worse than its own bad base rate (9% vs 15%)** |

## Why the "expected" positions aren't being placed — structural causes

1. **The conviction lane is report-only.** It evaluated 455 candidates and
   would have admitted 75 — but `mode:"report"` means nothing it says opens
   a position. The live lane is the model-free exploration probe lane
   (p_win substituted at 0.85, both profit gates bypassed — 09-16 firing
   audit).
2. **Even the conviction lane's own numbers don't clear the cost bar.**
   Sampled CV-010 readings: est_edge 68–107 bps vs est_cost ~63 bps with
   `ev_cost_mult` 2.0 → required edge ≳126 bps; agreement 0.0 vs floor
   0.75; regime unknown. At the booked 30 bps taker + spread, the EV gate's
   arithmetic refuses almost everything this tape offers.
3. **The probe lane self-throttles after losses.** 193 budget-exhausted
   denials + 24 tuition-governor engagements — the era's −0.43 $/trip feeds
   back as fewer entries, by design.
4. **79% of entry orders expire unfilled.** Post-only limit placement
   rarely gets hit (OM-040 ×374 vs 102 clean-terminal). The positions the
   bot "doesn't put on" include most of the ones it *tried* to put on.
5. **PAXG is geometrically mis-framed.** 42.6% of its 36h windows resolve
   NEITHER barrier — gold's sigma is too small for a 1.8%/1.35% bracket —
   and the bot's PAXG entries graded *below* the already-bad base rate.
   Every PAXG entry is a bet the label geometry cannot cash (compounds the
   09-16 audit's trail/bracket arithmetic finding).
6. **Long book: 533 add denials (LB-010)** — heat cap binding at
   0.3766 vs 0.35 cap; plus 282 cadence pauses and 188 context blocks. Its
   "expected" adds are heat-starved, not signal-starved.

## Reading for the 09-22 boundary

The bot is not overlooking a visible pile of winning positions: at the
shipped geometry the raw tape is stop-first majoritarian, the lane that
could select is report-only, the lane that trades is tuition-throttled, and
four of five orders never fill. The measured entry selection *does* beat
the unconditional tape on ETH/LINK/BTC — the deficit vs profitability is
the cost bar (≈126 bps required edge vs 68–107 estimated) and PAXG's
geometry, i.e. the same fee-stack problem the scaling-governor design
(`2026-09-19_scaling_system_design.md`) is pre-registered against. Any
change to lane modes, EV multiple, or bracket geometry is cohort-resetting —
docket material, not this document.

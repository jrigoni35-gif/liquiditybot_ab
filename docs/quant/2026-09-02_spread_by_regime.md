# Spread by regime, bull vs bear, as a cost the bot actually pays (2026-09-02)

**Class: SAFE, measurement only. No code changed. No writes under `outputs/`.**
Scratch instrument: `scratchpad/s1_spread_by_regime.py` (seed 7, B=400 day-block bootstrap,
`MIN_DAYS=5` refusal floor). Standard applied: `docs/INSTRUMENT_VERIFICATION_STANDARD.md`.

## Hypothesis under test
Spread behaviour differs materially between bullish and bearish environments and is a
material, regime-dependent drag on this bot.

**Verdict: REFUTED on materiality AND, after repair, on existence at the pooled level: the
pooled bull_quiet−bear gap is asset-mix composition, not a regime effect; the within-asset
gap is ≤0.15 bps at the median (FLOW alone carries a real +3.2 bps).** Details and the triad
split in the verdict paragraph at the end.

> **REPAIR 2026-09-02 (verification finding, WARNING, applied 23:24Z).** BEFORE: "Bull_quiet −
> bear difference of medians −1.0 bps, CI [−1.50, −0.35], statistically real." AFTER: that
> gap is fully reproduced by a placebo carrying NO regime information — a within-asset
> circular time-shift of the regime label (`np.roll` per asset on rows sorted
> `asset,signal_ts`; scratch `s6r_s1shift.py`, `signal_history.csv` re-read
> **2026-09-02T23:24:01Z**, 23,036 rows, ts 1783946147..1788380400): bq−bear at k = 50 / 100 /
> 200 / 400 / 800 / 1600 / 3000 rows = **−1.05 / −1.16 / −1.05 / −1.07 / −0.99 / −1.00 / −1.18
> bps** vs real −1.00. Cause: regime mix per asset differs (bear share FLOW 0.343, ETH 0.073,
> BTC 0.130; bull_quiet 0.175 / 0.182 / 0.099) and FLOW's 34–38 bps spread dominates the bear
> cell. The row-shuffle placebo below destroys asset structure and so could not see this; it
> is retained as a record, NOT as the null. Within-asset bear−bq gaps (bps, n≥20 both cells,
> `s1v_verify_spread.py` 23:20:04Z): FLOW **+3.22**, ARB +1.19, SOL +0.39, LTC +0.27, PAXG
> +0.15, ETH +0.001, BTC +0.003, LINK −0.08, MINA −1.38; median across the 9 assets **0.147
> bps**. Asset-normalized bear−bq 0.041 vs time-shift null 0.033 / 0.023 / 0.002 / −0.013 /
> −0.018 / 0.0006 / −0.013 (same k grid) — marginal, inside the null's range. The "7.7 %
> relative gap" claim below is likewise composition-inflated and is struck. Verdict direction
> unchanged (strengthened): the operator's hypothesis is refuted on existence pooled, and on
> materiality everywhere except FLOW, which never fills.

## Method and as-of stamps
- `outputs/signal_history.csv` read **2026-09-02T23:09:10Z**, 23,029 rows, `signal_ts`
  1783946147..1788380400 inclusive (2026-07-13 12:35:47 .. 2026-09-02 20:20:00 UTC). Row
  filter for (a): ALL rows (every row is one-hot on the five `regime_*` flags; asserted).
  Regime = the flag that is 1. Day block = `signal_ts // 86400` (UTC day).
- `outputs/fills.csv` read **2026-09-02T23:09:10Z**, 1,216 rows; `purpose=='entry'` 543 rows
  = 331 positions (partials collapsed, notional-weighted); `purpose=='exit'` 485 positions.
- **Decode (instrument check first):** `spread_bps` in signal_history is STORED as
  `clip(raw,0,60)/10` (`ml/features.py:378`, `ml/history.py:357`). All numbers below are
  `stored*10` = bps. 151 rows censored at 60 bps (FLOW 119, MINA 32) — FLOW p90 is a censoring
  artefact, not a measurement. Cross-implementation (standard check 1): live
  `status.json:/regimes/<asset>/spread_bps` read 23:10:12Z vs last-24h signal_history median
  — FLOW 37.2 vs 38.1, MINA 19.7 vs 16.6, ARB 8.0 vs 8.9, DOT 3.5 vs 3.44 (ratios 0.84–1.11
  PASS). Planted defect (check 2): decode ×1 instead of ×10 → ratios 0.08–0.11 FAIL. The
  check discriminates.
- Fill-side: `slip_bps` sign = `sgn*(fill-ref)/ref` (`execution/order_manager.py:738`),
  positive = adverse. Fee bps = `fees_delta_usd / (fill_size*fill_price) * 1e4`. Round trip
  RT = spread@signal + slip_in + slip_out + fee_in + fee_out; missing exit leg imputed from
  entry leg (1 of 324 positions). `exec_era` NaN = **untagged** (pre-cut-7); reported as its
  own bucket, never pooled.
- Entered subset = `disp=='entered'` (383 rows) rather than `source=='live'` (397): `disp` is
  the sizer's own disposition; 324 rows are both; the 73 live-not-entered rows are relabel
  copies, not decisions.

## (a) Spread at signal time, regime × side — ALL candidates (bps; med [day-block 95% CI]; d = day blocks)

| regime | side | POOLED (all 15 assets) | FLOW | ETH | BTC |
|---|---|---|---|---|---|
| bull_quiet | long | n=1425 d=26 **1.42** [0.89,2.76] p90 22.3 | n=87 d=13 **33.96** [33.50,34.31] | n=396 d=20 **0.05** [0.04,0.05] | n=124 d=12 **0.01** [0.01,0.01] |
| bull_quiet | short | n=993 d=25 0.84 [0.53,1.03] p90 30.6 | n=100 d=12 34.01 [33.50,34.42] | n=319 d=18 0.05 [0.04,0.20] | n=104 d=11 0.01 [0.01,0.01] |
| bull_vol | long | n=836 d=14 9.38 [1.07,15.62] p90 23.5 | n=1 d=1 REFUSED | n=99 d=3 REFUSED | n=68 d=4 REFUSED |
| bull_vol | short | n=647 d=16 2.49 [1.12,11.96] p90 19.0 | n=10 d=3 REFUSED | n=66 d=3 REFUSED | n=24 d=3 REFUSED |
| range | long | n=5899 d=49 0.67 [0.05,1.20] p90 11.8 | n=206 d=33 35.65 [34.19,37.26] | n=1630 d=38 0.05 [0.05,0.05] | n=1018 d=37 0.02 [0.02,0.02] |
| range | short | n=3817 d=49 0.91 [0.21,1.29] p90 11.6 | n=177 d=24 37.24 [36.04,39.14] | n=776 d=36 0.05 [0.05,0.05] | n=500 d=34 0.02 [0.02,0.02] |
| bear | long | n=3858 d=43 **2.50** [1.83,2.74] p90 19.3 | n=215 d=26 **37.66** [35.27,38.83] | n=174 d=16 **0.05** [0.05,0.05] | n=177 d=16 **0.02** [0.02,0.02] |
| bear | short | n=2682 d=43 1.54 [1.46,1.95] p90 14.7 | n=151 d=26 36.70 [36.03,39.29] | n=114 d=11 0.05 [0.05,0.05] | n=123 d=16 0.02 [0.02,0.02] |
| crisis | long | n=1937 d=8 2.59 [2.41,3.00] p90 22.2 | n=65 d=5 34.31 [31.95,37.38] | n=227 d=6 0.04 [0.04,0.25] | n=114 d=5 0.01 [0.01,0.01] |
| crisis | short | n=935 d=8 2.22 [1.22,3.50] p90 20.2 | n=55 d=4 REFUSED | n=118 d=5 0.04 [0.04,0.33] | n=47 d=4 REFUSED |

Pooled all-side medians: bull_quiet 1.06, bull_vol 5.06, range 0.78, bear 2.06, crisis 2.45.
Bull_quiet − bear difference of medians, day-block CI **[−1.50, −0.35] bps** (bear wider).

**Confounder, second route.** The pooled gap is mostly asset mix: FLOW is 34% bear rows,
ETH 7%, BTC 13%. Asset-normalized (spread ÷ asset median), per-regime median: bear 1.015,
range 1.001, bull_quiet 0.974, crisis 0.962, bull_vol 0.938 — a **7.7% relative gap**,
i.e. for ETH 0.004 bps, for FLOW ~2.8 bps. ETH and BTC medians sit on one tick
(0.01/1900, 0.1/65000) in EVERY regime, long and short. FLOW long vs short: 36.04 vs 36.17.

**Placebo — SUPERSEDED by the within-asset time-shift in the REPAIR block (this row-shuffle
is anti-conservative on TWO counts: it ignores day clustering AND it breaks asset×regime
mix, so it cannot detect composition).** Original text: (300 row-shuffles of the regime
label, marginals kept) null band of the
pooled per-regime median [1.31, 1.41] in all five cells; real medians all sit outside it; real
max−min gap 4.28 bps vs null 97.5th pct 0.105; asset-normalized gap 0.077 vs null 0.005. The
row-shuffle null ignores day clustering and is therefore anti-conservative — the day-block CIs
above are the standard; both agree the gap is non-zero, neither makes it large.

**Power (null-base: one regime's DAYS split at random into halves, factor k planted on one
half, 12 trials, detect = block-CI excludes 0):** pooled bear (44 d): k=1.3 → 50%, k=2.0 →
92% ⇒ **MDE ≈ 2× on the pooled median**; pooled range (49 d): k=2.0 → 25% (pooled median is
composition-driven, blocks re-mix assets). FLOW bear (27 d): k=1.2 → 100% ⇒ MDE ≈ 1.1–1.2×
(~4–7 bps). ETH/BTC: k=1.05 → 100% but DEGENERATE — the median is tick-pinned with ~zero
bootstrap variance, so "detection" of a 5% shift of 0.05 bps is a property of the
instrument, not evidence of a meaningful sensitivity. Any real regime effect on ETH/BTC
spread is below one tick and unmeasurable from this column.

## Gate pass-through: entered vs all candidates (bps)

| regime | all (med, p90) | entered (med [CI], p90) | share ≥10 bps all → entered | ETH ent | BTC ent | FLOW ent |
|---|---|---|---|---|---|---|
| bull_quiet | 1.06, 22.4 | n=16 d=12 0.21 [0.04,0.94], 2.3 | 0.283 → 0.000 | n=8 0.05 | n=1 REFUSED | **n=0** |
| bull_vol | 5.06, 21.9 | n=12 d=6 1.72 [0.41,10.69], 10.6 | 0.454 → 0.250 | n=4 REFUSED | n=1 REFUSED | n=0 |
| range | 0.78, 11.7 | n=289 d=36 1.10 [0.05,1.29], 3.6 | 0.119 → 0.052 | n=61 0.05 | n=29 0.02 | n=0 |
| bear | 2.06, 17.1 | n=66 d=24 1.33 [1.17,1.47], 4.2 | 0.227 → 0.015 | n=4 REFUSED | n=8 0.02 | n=0 |
| crisis | 2.45, 21.8 | n=0 (SZ-021 blocks) | 0.289 → — | — | — | — |

The gate does NOT let wide-spread signals through: entered p90 is 2.3–4.2 bps vs 12–22 bps
for candidates; the ≥10 bps share falls 5–19× on entry. **FLOW: zero entries ever** (1,067
candidates; disp: SZ-045 472, capped 270, SZ-023 177, SZ-022 80, SZ-021 36, SZ-030 21) — FLOW
cannot be measured on realized trades and is a candidate-only column throughout.

## (b) Realized entry cost by regime, per exec_era (medians, bps)
Join entry positions → signal_history by `position_id`: **324 of 331** (era 7: 59/60, era 8:
6/6, era 9: 15/18, untagged: 244/247); exit leg found for 323/324.

| era | regime | n / d | spread@sig | slip RT | maker share | fee RT | **RT total** | spread share of RT |
|---|---|---|---|---|---|---|---|---|
| untagged | bear | 42 / 14 | 1.3 | −0.1 | 0.83 | 65.0 | **65.9** | 0.019 |
| untagged | range | 200 / 19 | 0.7 | 0.0 | 0.83 | 65.0 | **66.3** | 0.011 |
| untagged | bull_quiet | 2 / 1 | 2.2 | 6.7 | 0.50 | 72.5 | 81.4 | REFUSED |
| 7-e7d5ca1a | bear | 15 / 10 | 1.5 | −0.6 | 0.73 | 65.0 | **66.3** | 0.028 |
| 7-e7d5ca1a | bull_quiet | 8 / 7 | 0.1 | −1.2 | 0.88 | 65.0 | 66.1 | 0.002 |
| 7-e7d5ca1a | bull_vol | 10 / 5 | 1.7 | 0.3 | 0.70 | 65.0 | 69.5 | 0.027 |
| 7-e7d5ca1a | range | 26 / 13 | 1.3 | 1.1 | 0.85 | 65.0 | **67.4** | 0.019 |
| 8-ca55e2ba | all | 6 / 3 | 0–2.0 | −2.8..5.8 | 0.67 | 78–160 | 88–160 | REFUSED (40/80 era) |
| 9-16ec821e | bull_quiet | 3 / 3 | 0.9 | −10.7 | 1.00 | 60.0 | 50.0 | REFUSED |
| 9-16ec821e | range | 12 / 3 | 1.6 | −6.0 | 0.75 | 60.0 | **59.6** | REFUSED (3 d) |

Triad, realized (era untagged / era 7): ETH n=46 RT 65.0 (spread 0.1) / n=10 RT 62.9;
BTC n=33 RT 65.0 (spread 0.0) / n=4 RT 67.7; FLOW n=0 in every era. Era-9 ETH n=2 RT 55.0,
BTC n=0. Fee per leg medians: untagged 25.0, era 7 25.0, era 8 40.0, era 9 22.0 bps — the
booked schedule, not the venue, moves the RT; fee RT of 65 = 0.8 maker × 25 + 0.2 taker × 40
per leg × 2. **In no era, no regime, no position does spread@signal exceed the fee round
trip (share 0.000 in all four eras).**

## (c) Spread share of the cost stack at the 22/38 tier
Denominator = maker-both-legs fee RT 44 bps + spread@signal (candidate rows, all 15 assets):
pooled median share bear 0.045, bull_quiet 0.023, bull_vol 0.103, crisis 0.053, range 0.017;
share of candidates with spread > 44 bps: 0.5–1.3%. **FLOW: 0.43–0.46 in every regime**
(spread ≈ fee; 3–17% of FLOW rows exceed 44 bps). **ETH ≤0.005, BTC 0.000 in every regime.**
On realized positions (denominator = full RT incl. slip) the spread share is 0.002–0.028.

## (d) Realized stack vs the label's cost floor
Label cost = 0.6% + min(spread, 60 bps)/100 (`ml/history.py:_cost_pct`, keys
`label_round_trip_cost_pct=0.6`, `label_include_spread=true`, `label_spread_cap_bps=60`, read
2026-09-02). Realized RT − label cost, median / share > 0: era 9 range **−0.9 / 0.33**
(n=12, 3 d), bull_quiet −10.7 / 0.00 (n=3); era 7: +5.9..+6.8 / 0.65–0.88 in all four
regimes; untagged: +5.1 / 0.74–0.83. Share of realized RT > flat 60 bps: era 9 0.33, era 7
0.76, untagged 0.86, era 8 1.00. **Reading:** the era-7/untagged excess is the OLD booked
fee (25/40) against the NEW 0.6% floor — anachronistic by construction, cited only as the
bound. In the only era priced at 22/38 (era 9, n=15, 3 day-blocks, CI refused) the floor
matches realized cost within ~1 bps and spread contributes 0.9–1.6 bps of it. Nowhere does
the spread+fee stack exceed 0.6% because of spread; where it exceeded, the fee did it.

## Verdict
The hypothesis is **refuted as a material, regime-dependent drag**. [REPAIRED] The pooled
bear-vs-bull_quiet gap (−1.0 bps) is asset-mix composition — a regime-blind time-shift
placebo reproduces it at −0.99..−1.18 bps — so at the pooled level there is NO regime effect
to price; within assets the median gap is 0.15 bps, and only FLOW shows a real bear widening
(+3.2 bps, day-block CIs disjoint). Even taken at face value the gap is ~1 bps against a
44–76 bps fee round trip, i.e. spread is 1–5% of the cost stack pooled and ≤0.5% on ETH/BTC.
The gate already strips wide-spread candidates (entered p90 2–4 bps), so what the bot PAYS
is fee-shaped in every era and every regime; long/short differ by <1 bps within any asset.
**Triad:** FLOW spread (34–38 bps, censored at 60) is a first-order cost, ~equal to the fee
in every regime and 66× ETH's per the tape ratio — but FLOW has never filled, so its cost is
a candidate-side fact the gate makes moot. ETH (0.05 bps) and BTC (0.02 bps) sit on one tick
in every regime and side; on "lowest spread cost" BTC earns "reliable" trivially and ETH
ties it — the distinction is unmeasurable below the tick. What would change the verdict: a
regime × asset cell where spread@signal clears ~10 bps on an asset the gate actually enters
(none exists: entered p90 ≤ 4.2 bps), or a fee tier drop that makes 1–2 bps material.

## What this could not see
Spread is the SIGNAL-time top-of-book (`regime/liquidity_regime.py`), not the spread at
fill; no book snapshot at fill time exists in the ledgers, so fill-time widening is captured
only through `slip_bps`. bull_vol and crisis have 8–17 day blocks pooled and <5 per triad
asset (refused). Era 9 has 3 day blocks — every era-9 number is a point, not an interval.
The ETH/BTC "power" is degenerate (tick-pinned median). Not run: candle/tick markout
(`scripts/markout_report.py`), which is the right instrument for fill-time cost and is a
separate item. Realized RT uses booked `fees_delta_usd` (era-dependent schedule), not
Kraken-reconciled fees.

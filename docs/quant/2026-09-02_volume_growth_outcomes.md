# Does rising volume make outcomes worse, or just more resolved? (item 3, 2026-09-02)

**Class: SAFE, measurement-only. No code, config, or `outputs/` write.** Scratch instruments
(`s3_build.py`, `s3_power.py`, extra CSV) live in the session scratch dir and are NOT committed;
per `docs/INSTRUMENT_VERIFICATION_STANDARD.md` check 7 every number here is a one-run
number until the instrument is committed and re-executed. Verdict first, tables after.

> **REPAIR 2026-09-02 (two verification findings, WARNING, applied 23:24Z; scratch
> `s6r_s3comp.py` on `s3_rows.parquet`, 12,659 rows / 12,332 with `g_n3600@0`).**
> **(1) Pooled quintile edges are an ASSET SELECTOR.** Row share by asset per pooled `g_n3600`
> quintile (Q1→Q5): FLOW .075 / .032 / .023 / .042 / .070; ETH .055 / .165 / .163 / .125 / .079;
> BTC .012 / .072 / .091 / .069 / .027. Q5's top three are ARB .167, PAXG .153, MINA .150 —
> and so are Q1's (ARB .179, PAXG .176, MINA .164): the log-ratio on thin tapes is coarse, so
> thin listings populate BOTH extremes while ETH/BTC sit in Q2–Q4. Asset baseline returns
> differ (mean `label_ret_pct` FLOW −1.65, ETH −1.08, BTC −0.82 on the 5,721 ret rows with the
> feature), so the pooled Q5−Q1 (+0.19 pct) is a composite of asset mix and growth, NOT a pure
> growth sort. The within-asset rank (`n3600_apct`) was the clean design; the pooled `g_*` rows
> in Table A must be read as mix-confounded. The verdict survives because the FLOW / ETH / BTC
> columns are independently null (each asset compared with itself), and the shipped
> decomposition instrument (AUC, rank-based per feature) is also null.
> **(2) Table C triad completed.** Per-asset placebo cells (from `s3_q5_minus_q1.csv`, same
> run) are now in Table C-triad below; FLOW's return placebo cells are CI-REFUSED (2–3 blocks)
> — a refusal the memo previously did not surface.

## Verdict (two parts, as asked)

**(1) Does rising volume predict a WORSE realized return?  NO — null, with power.**
Pooled top-minus-bottom quintile of 1h trade-count growth (`g_n3600`): mean `label_ret_pct`
**+0.19 pct [−0.05, +0.36]** (9 day-blocks), cost-clearance P(ret>0.6) **+0.033 [−0.010, +0.064]**.
Sign is the *opposite* of the hypothesis and the CI includes zero. Power on the same rows
(random-feature plant, 12 seeds): a 0.32 pct Q5−Q1 gap is detected 10/12, 0.48 pct 12/12 —
**MDE ≈ 0.4 pct** on the pooled return. 15-min growth, notional growth, and the stored
`volume_z` are all null too (table A). The shipped decomposition instrument scores every
volume feature **NULL** (RAW/RES/DIR AUCs all within 0.49–0.52) and its own MDE is 0.05 SD.
The time-shift placebos (feature read 24 h before/after the signal) produce *larger* Q5−Q1
returns than the real feature (−0.38 and +0.23 pct, both nominally "significant"), which
sets the noise floor: a real effect must exceed ~0.4 pct to be distinguished from day-level
drift in this 10-block return corpus, and none does.

**(2) Does rising volume predict a stop hit beyond its resolution effect?  NO — null.**
Pooled `g_n3600` Q5−Q1: RESOLUTION **+0.019 [−0.014, +0.056]**, DIRECTION P(pt|resolved)
**+0.027 [−0.017, +0.065]**, STOP tb_sl/(pt+sl) **−0.027 [−0.065, +0.017]** (23 blocks).
Stop-rate MDE (planted flips, random feature): 0.05 absolute detected 12/12, 0.03 8/12.
So rising volume does not raise the stop rate by ≥5 points. The resolution channel is
where volume *would* load (sigma_bar_pct RES AUC 0.752, spread_bps 0.662 in the shipped
run), yet even resolution is null for the growth features; only the within-asset activity
*level* (`n3600_apct`) loads resolution (RES 0.575 [0.502, 0.660], DIR 0.510 [0.461, 0.558],
flag RESOLUTION-ONLY, half-split unstable `*`). Rank-corr(g_n3600, sigma_bar_pct) = −0.03:
volume growth is not a volatility proxy here, which is why it inherits neither channel.

**Premise verdict: REFUTED at the stated power floors** (pooled ret MDE ~0.4 pct; stop MDE
0.05). Not "safe" either — every quintile of every volume measure has a negative mean net
return (−0.58 to −0.87 pct pooled); volume just does not sort it.

**Triad.** FLOW (620 rows / 348 with ret; ZERO fills ever, so this is candidate-only by
construction): Q5−Q1 ret +0.27 [−0.50, +1.19], STOP −0.046 [−0.146, +0.046]; its MDE is
~1.3 pct (8/12) and 0.2 on stop — FLOW cannot resolve anything under ~1 pct. Its 900 s
window holds 0/1/2/5 trades at the 20/40/60/80 pct-iles, so the "growth" ratio is
quantized (118 distinct values). ETH (1,464 / 602): Q5−Q1 ret **+0.99 [+0.09, +1.98]**
(7 blocks) — rising volume associated with *better* return, but both ETH placebos sit at
+0.55 / +0.38 with overlapping CIs, so it is not separable from day drift; STOP +0.049
[−0.174, +0.162]. BTC (670 / 290): g_n3600 Q1 holds only 9 ret rows over 4 days → **CI
refused**; STOP +0.066 [−0.264, +0.321]. "BTC is reliable", operationalized as lowest
stop rate: BTC 0.508 [0.404, 0.621] vs ETH 0.577 [0.482, 0.677] vs FLOW 0.602 [0.505,
0.688] — ordered as the operator expects but all three CIs overlap; BTC does NOT earn it at
this n. BTC also has the *lowest* cost-clearance (0.269 [0.158, 0.379] vs FLOW 0.305, ETH
0.336) — fewer stops, fewer wins: it resolves less (RES 0.737 vs 0.85–0.87).

## Method

- Corpus: `outputs/signal_history.csv` read **2026-09-02T23:12:13Z** (live file; 23,035 rows
  at read, 23,029 at the 23:06Z first read — the runner appended 6 rows during the run).
  Filter: `label_era == "triple_barrier_h432"` AND `barrier in {tb_pt, tb_sl, tb_time}` →
  **12,702** rows (double-derive: `grep -c triple_barrier_h432` = 12,696 at 23:06Z; the two
  counts differ by the 6 appended rows — same snapshot-drift, not a filter disagreement).
  Minus 43 `source == live` (cost basis differs: live is net of booked fees, candidate net of
  `label_round_trip_cost_pct` + capped spread, `ml/history.py:312-322, 377-380`) → **12,659**
  candidate rows, signal_ts 1786237200 – 1788380400 inclusive (2026-08-09T01:00Z –
  2026-09-02T20:20Z), 25 distinct UTC days. `label_ret_pct` non-null on **6,048** of them
  (2026-08-24T09:05Z onward, column added schema 94), 10 distinct days. No other label era
  or exec era is pooled.
- `label_ret_pct` is already NET of the 0.6 % label cost (config `ml.label_round_trip_cost_pct`
  = 0.6, re-read). Hence "P(ret > 0.6)" is *cost-clearance plus a second 0.6 % margin*; P(ret>0)
  is reported beside it in the scratch CSV and behaves identically.
- Tape features via `scripts.kraken_trades_backfill.TickStore().load(kraken_pair(asset))`,
  sorted by `time_s`, cumsum + `searchsorted` (no per-row loop). Window [T−w, T) vs
  [T−2w, T−w), w ∈ {900, 3600} s; count `n_w` and notional Σ price·volume `v_w`; growth
  `g = ln((cur+1)/(prev+1))`. Rows with T−7200 < tape t_min or T > tape t_max → NaN
  (**327 dropped**, all at the tape's tail). Level measure: within-asset percentile of
  `n3600` (`n3600_apct`). Coverage (`--coverage`, all 15 pairs, 2026-07-13 → 2026-09-01T23:18Z
  … 2026-09-02T01:59Z; BTC 2,930,099 / ETH 1,207,483 / FLOW 18,372 trades).
- Route 2 on the window arithmetic: brute-force boolean mask on 291 random rows —
  **0 mismatches**; a planted look-ahead window ([T, T+3600)) mismatches **285/291**, so the
  check discriminates (standard check 2).
- Quintiles: pooled rank bins (ties by row order), so FLOW/ETH/BTC columns use the SAME edges;
  `n3600_apct` is within-asset by construction. [REPAIRED] Pooled edges sort by asset as well
  as by growth (see REPAIR block): the pooled `g_*` Q5−Q1 rows compare different asset baskets. Outcomes per bin: mean ret, P(ret>0.6),
  RESOLUTION = P(tb_pt|tb_sl), DIRECTION = P(tb_pt | resolved), STOP = P(tb_sl | resolved).
- CI: day-block bootstrap (UTC day, 400 reps, seed 7, percentile 95 %), block count = distinct
  days in the bin; **CI refused under 5 blocks** (`[refused]`). Blocks are stated per cell.
- Placebo: tape features re-read at signal_ts ∓ 86,400 s; stored `volume_z`/`vol_percentile`
  shifted by nearest same-asset row within ±1,800 s of signal_ts ∓ 86,400 (route-2 check: 47/49
  sampled rows agree, 2 differ on equidistant duplicate-key ties).
- Power: plant on a RANDOM feature's rank (feature-side, as the shipped `--power-calibration`
  does): ret + δ·2·(rank−½); stop flips tb_pt→tb_sl in the random Q5. 12 seeds × 200 reps.

## Table A — Q5 − Q1, real-time features (ret pct; others absolute rates)

| feature | sub | ret [CI] blk | P>0.6 [CI] | RES [CI] blk | DIR pt\|res [CI] | STOP [CI] |
|---|---|---|---|---|---|---|
| g_n3600 | ALL | +0.19 [−0.05,+0.36] 9 | +0.033 [−0.010,+0.064] | +0.019 [−0.014,+0.056] 23 | +0.027 [−0.017,+0.065] | −0.027 [−0.065,+0.017] |
| | FLOW | +0.27 [−0.50,+1.19] 9 | +0.030 [−0.091,+0.169] | +0.030 [−0.044,+0.117] 20 | +0.046 [−0.046,+0.146] | −0.046 [−0.146,+0.046] |
| | ETH | +0.99 [+0.09,+1.98] 7 | +0.167 [−0.000,+0.389] | +0.014 [−0.050,+0.106] 18 | −0.049 [−0.162,+0.174] | +0.049 [−0.174,+0.162] |
| | BTC | +0.54 refused 4 | +0.162 refused | +0.055 [−0.110,+0.266] 12 | −0.066 [−0.321,+0.264] | +0.066 [−0.264,+0.321] |
| g_n900 | ALL | −0.08 [−0.26,+0.17] 10 | −0.017 [−0.062,+0.047] | +0.002 [−0.018,+0.020] 25 | −0.012 [−0.045,+0.022] | +0.012 [−0.022,+0.045] |
| | FLOW | −0.17 [−0.63,+0.31] 10 | −0.060 [−0.120,+0.006] | −0.051 [−0.147,+0.036] 21 | −0.024 [−0.094,+0.051] | +0.024 [−0.051,+0.094] |
| | ETH | −0.26 [−0.80,+0.25] 8 | −0.062 [−0.192,+0.067] | +0.014 [−0.072,+0.109] 19 | −0.015 [−0.094,+0.089] | +0.015 [−0.089,+0.094] |
| | BTC | −0.14 [−1.10,+0.52] 5 | −0.086 [−0.375,+0.142] | +0.070 [−0.141,+0.292] 15 | +0.075 [−0.180,+0.309] | −0.075 [−0.309,+0.180] |
| g_v3600 | ALL | +0.02 [−0.31,+0.27] 10 | −0.007 [−0.085,+0.060] | +0.020 [−0.010,+0.055] 24 | +0.006 [−0.049,+0.059] | −0.006 [−0.059,+0.049] |
| g_v900 | ALL | −0.08 [−0.22,+0.08] 10 | −0.009 [−0.037,+0.029] | +0.003 [−0.014,+0.020] 25 | −0.007 [−0.033,+0.015] | +0.007 [−0.015,+0.033] |
| volume_z | ALL | −0.01 [−0.26,+0.25] 10 | +0.006 [−0.049,+0.065] | +0.033 [−0.002,+0.072] 25 | −0.004 [−0.051,+0.044] | +0.004 [−0.044,+0.051] |
| | FLOW | +0.59 refused 4 | +0.063 refused | −0.122 [−0.217,−0.048] 8 | +0.107 [−0.362,+0.316] | −0.107 [−0.316,+0.362] |
| | ETH | −0.18 [−0.48,+0.03] 9 | −0.082 [−0.142,−0.022] | +0.090 [+0.025,+0.188] 21 | −0.051 [−0.142,+0.045] | +0.051 [−0.045,+0.142] |
| | BTC | +0.05 [−0.44,+0.41] 8 | +0.058 [−0.125,+0.230] | +0.066 [+0.009,+0.149] 21 | +0.139 [+0.027,+0.270] | −0.139 [−0.270,−0.027] |
| n3600_apct | ALL | −0.06 [−0.72,+0.74] 10 | +0.037 [−0.107,+0.184] | +0.099 [−0.023,+0.219] 24 | +0.013 [−0.093,+0.121] | −0.013 [−0.121,+0.093] |
| vol_percentile | ALL | +0.44 [−0.42,+1.91] 8 | +0.164 [+0.010,+0.347] | +0.104 [−0.063,+0.261] 18 | +0.055 [−0.056,+0.192] | −0.055 [−0.192,+0.056] |

Cells that nominally exclude zero: ETH volume_z P>0.6 and RES; BTC volume_z DIR/STOP
(fewer stops at high volume — the *opposite* of the hypothesis); FLOW volume_z RES (8 blocks).
Read them against Table C: the BTC volume_z@−1d placebo gives STOP −0.212 [−0.313, −0.040],
same sign and larger; the ETH volume_z@+1d placebo gives P>0.6 −0.129 [−0.235, +0.059], same
magnitude. Neither survives its placebo. `vol_percentile` quintiles select *days* (Q5 spans 8
of 25), and its +1d placebo returns RES +0.338 [+0.073, +0.493], DIR +0.218 [+0.045, +0.372]
— the feature is uninterpretable at this block count.

## Table B — quintile decomposition, `g_n3600` (pooled edges), n = resolved-rows/ret-rows

| sub | Q | med g | n | blk | ret [CI] | P>0.6 [CI] | RES [CI] | DIR [CI] | STOP [CI] |
|---|---|---|---|---|---|---|---|---|---|
| ALL | 1 | −0.81 | 2466/1124 | 23/10 | −0.87 [−1.35,−0.44] | .375 [.283,.459] | .823 [.730,.895] | .443 [.372,.505] | .557 [.495,.628] |
| ALL | 2 | −0.27 | 2466/1128 | 25/10 | −0.58 [−0.89,−0.26] | .415 [.343,.486] | .825 [.729,.902] | .484 [.430,.541] | .516 [.459,.570] |
| ALL | 3 | +0.01 | 2467/1236 | 25/10 | −0.80 [−1.15,−0.45] | .369 [.289,.441] | .831 [.737,.906] | .446 [.393,.499] | .554 [.501,.607] |
| ALL | 4 | +0.31 | 2466/1165 | 25/10 | −0.76 [−1.04,−0.44] | .380 [.291,.453] | .835 [.754,.902] | .451 [.395,.509] | .549 [.491,.605] |
| ALL | 5 | +0.91 | 2467/1068 | 24/9 | −0.67 [−1.08,−0.27] | .407 [.338,.471] | .842 [.772,.896] | .470 [.394,.550] | .530 [.450,.606] |
| FLOW | 1 | −0.94 | 185/100 | 20/10 | −1.63 [−2.32,−1.06] | .300 [.211,.378] | .843 [.712,.954] | .378 [.279,.495] | .622 [.505,.721] |
| FLOW | 5 | +0.96 | 173/94 | 20/9 | −1.36 [−2.40,−0.37] | .330 [.175,.475] | .873 [.785,.940] | .424 [.316,.535] | .576 [.465,.684] |
| ETH | 1 | −0.66 | 136/41 | 18/7 | −1.20 [−2.19,−0.35] | .341 [.156,.465] | .919 [.793,.977] | .544 [.286,.742] | .456 [.258,.714] |
| ETH | 5 | +0.77 | 195/61 | 18/8 | −0.21 [−0.71,+0.32] | .508 [.389,.611] | .933 [.820,.986] | .495 [.364,.605] | .505 [.395,.636] |
| BTC | 1 | −0.61 | 30/9 | 12/4 | −1.05 refused | .222 refused | .733 [.421,.951] | .682 [.307,.885] | .318 [.115,.693] |
| BTC | 5 | +0.71 | 66/26 | 14/6 | −0.51 [−0.99,−0.21] | .385 [.125,.583] | .788 [.539,.941] | .615 [.452,.816] | .385 [.184,.548] |

Full 5×4×13 grid: scratch `s3_quintiles.csv`. Monotone trend absent in every column; the
pooled stop rate sits at 0.52–0.56 in all five bins. Asset baselines (all rows): ret ALL
−0.708 [−1.010,−0.379], FLOW −1.525 [−2.104,−0.994], ETH −1.103 [−1.515,−0.723], BTC −0.822
[−1.046,−0.563]; RES ALL .836, FLOW .847, ETH .868, BTC .737 [.586,.875].

## Table C — placebos (feature read 24 h away from the signal), Q5 − Q1 pooled

| feature | ret [CI] blk | P>0 [CI] | RES [CI] | DIR [CI] | STOP [CI] |
|---|---|---|---|---|---|
| g_n3600 @ −1d | +0.23 [+0.00,+0.41] 10 | +0.049 [+0.004,+0.078] | −0.011 [−0.033,+0.016] | +0.039 [+0.008,+0.069] | −0.039 [−0.069,−0.008] |
| g_n3600 @ +1d | −0.38 [−0.62,−0.15] 9 | −0.076 [−0.115,−0.047] | +0.008 [−0.024,+0.044] | −0.049 [−0.092,−0.010] | +0.049 [+0.010,+0.092] |
| g_n900 @ −1d | +0.07 [−0.17,+0.26] 10 | +0.002 [−0.051,+0.054] | +0.003 [−0.009,+0.016] | +0.011 [−0.016,+0.035] | −0.011 [−0.035,+0.016] |
| g_n900 @ +1d | +0.00 [−0.13,+0.19] 9 | +0.006 [−0.016,+0.038] | −0.002 [−0.020,+0.014] | +0.007 [−0.019,+0.036] | −0.007 [−0.036,+0.019] |
| g_v3600 @ −1d | +0.16 [−0.07,+0.34] 10 | +0.041 [+0.002,+0.071] | −0.005 [−0.028,+0.017] | +0.036 [+0.006,+0.063] | −0.036 [−0.063,−0.006] |
| g_v3600 @ +1d | −0.38 [−0.71,−0.17] 9 | −0.078 [−0.155,−0.011] | +0.043 [+0.005,+0.079] | −0.031 [−0.088,+0.025] | +0.031 [−0.025,+0.088] |
| volume_z @ −1d | −0.12 [−0.36,+0.13] 10 | −0.005 [−0.060,+0.045] | −0.009 [−0.051,+0.023] | −0.006 [−0.031,+0.016] | +0.006 [−0.016,+0.031] |
| volume_z @ +1d | −0.26 [−0.57,+0.06] 9 | −0.056 [−0.114,+0.012] | +0.001 [−0.029,+0.036] | −0.021 [−0.068,+0.019] | +0.021 [−0.019,+0.068] |

**Table C-triad — placebos per asset, Q5 − Q1 (ret pct; STOP absolute); REF = CI refused (<5 blocks)**

| feature | sub | ret [CI] blk | P>0.6 [CI] | STOP [CI] blk |
|---|---|---|---|---|
| g_n3600 @ −1d | FLOW | −0.18 [−1.12,+0.74] 10 | −0.030 [−0.178,+0.115] | +0.018 [−0.122,+0.144] 19 |
| | ETH | +0.55 [−0.39,+1.91] 7 | +0.133 [−0.012,+0.333] | +0.091 [−0.114,+0.250] 17 |
| | BTC | +0.32 REF 4 | +0.097 REF | −0.155 [−0.393,+0.169] 11 |
| g_n3600 @ +1d | FLOW | −0.52 [−2.13,+1.03] 8 | −0.055 [−0.306,+0.190] | +0.042 [−0.133,+0.230] 18 |
| | ETH | +0.38 [−0.57,+1.28] 6 | +0.060 [−0.239,+0.323] | +0.105 [−0.071,+0.261] 13 |
| | BTC | +0.08 REF 4 | +0.360 REF | +0.033 [−0.267,+0.272] 9 |
| volume_z @ −1d | FLOW | +0.21 REF 3 | +0.061 REF | +0.165 [−0.254,+0.633] 6 |
| | ETH | +0.40 [−0.29,+1.04] 9 | +0.104 [−0.051,+0.233] | +0.043 [−0.066,+0.118] 15 |
| | BTC | −0.59 [−1.67,+0.45] 8 | −0.062 [−0.415,+0.242] | **−0.212 [−0.313,−0.040]** 15 |
| volume_z @ +1d | FLOW | +0.69 REF 2 | +0.169 REF | +0.050 REF 3 |
| | ETH | −0.33 [−0.76,+0.33] 8 | **−0.129 [−0.235,+0.059]** | +0.011 [−0.145,+0.173] 15 |
| | BTC | +0.53 [−0.31,+1.14] 7 | +0.233 [+0.056,+0.348] | −0.141 [−0.284,+0.029] 14 |

Every real-time triad cell in Table A has a same-asset placebo of equal or larger magnitude
(ETH g_n3600 +0.99 vs placebos +0.55 / +0.38; BTC volume_z STOP −0.139 vs −1d placebo −0.212);
BTC's +1d volume_z P>0.6 +0.233 [+0.056, +0.348] is a placebo that nominally excludes zero
on 7 blocks — the false-exclusion rate at work, not a finding. FLOW's return placebos cannot
be evaluated (2–3 blocks) so FLOW's Table-A return cells have NO placebo control.

Four of eight pooled placebo rows exclude zero on at least one outcome at nominal 95 %. That is the
realized false-exclusion rate of a 9–10-block bootstrap, not a finding — and it is the bar
the real-time rows in Table A fail to clear. (The +1d shift also drops the corpus's last day,
whose window lies past the tape.)

## Shipped instrument, verbatim (`scripts/label_decomposition_report.py --extra-csv
s3_extra.csv --key-cols asset,signal_ts --reps 400 --power-calibration 12 --null-calibration 120`)

```
== LABEL DECOMPOSITION (read 2026-09-02T23:10:47Z) ==
  rows loaded 12650  barriers {tb_pt: 4846, tb_sl: 5716, tb_time: 2088}
  tb rows 12650 (0 non-tb dropped)  2026-08-09T01:00:00Z -> 2026-09-02T20:20:00Z  distinct days 25
  day-block bootstrap percentile 95%, 400 reps, seed 20260901; features scanned 71 -> NOMINAL ~3.6 CIs exclude 0.5 per channel by chance.
  POWER on THIS corpus (12 planted-direction features per grid point, 10562 resolved rows): 0.02sd:33%  0.05sd:100%  0.1sd:100%  0.2sd:100%  0.4sd:100%
  -> minimum detectable effect 0.05 SD at 80%. A null means 'no effect above 0.05 SD', never 'no effect'.
  null calibration on THIS corpus (120 N(0,1) features ...): realized exclusion rate {'raw': 0.0583, 'resolution': 0.075, 'direction': 0.1} -> at 71 features expect 7.1 DIRECTION exclusions by chance; null-run flags {'DIRECTIONAL': 12, 'RESOLUTION-ONLY': 8, 'NULL': 100, 'UNDEFINED': 0}
  extra: {'csv_rows': 12653, 'csv_duplicate_keys': 155, 'corpus_rows_matched': 12601, 'corpus_rows_unmatched': 49, 'corpus_duplicate_keys': 154, 'corpus_join_rate': 0.9961, 'extra_features': ['g_n3600', 'g_n3600_shm1d', 'g_n3600_shp1d', 'g_n900', 'g_v3600', 'g_v900', 'n3600_apct']}
  flags: {'DIRECTIONAL': 7, 'RESOLUTION-ONLY': 24, 'NULL': 40, 'UNDEFINED': 0}  * = flag not reproduced by both bootstrap halves
  feature                     n  n_res days  RAW                    RESOLUTION             DIRECTION              flag
  sigma_bar_pct           12650  10562   25  0.526 [0.479,0.577]  0.752 [0.644,0.879]  0.526 [0.480,0.573]  RESOLUTION-ONLY
  vol_percentile          12650  10562   25  0.528 [0.480,0.580]  0.567 [0.482,0.669]  0.526 [0.482,0.572]  NULL
  g_n3600_shp1d           11599   9526   24  0.486 [0.476,0.501]  0.504 [0.479,0.525]  0.483 [0.466,0.501]  NULL*
  g_n3600_shm1d           12601  10524   25  0.520 [0.509,0.532]  0.496 [0.473,0.512]  0.515 [0.503,0.527]  DIRECTIONAL
  n3600_apct              12284  10207   25  0.523 [0.475,0.574]  0.575 [0.502,0.660]  0.510 [0.461,0.558]  RESOLUTION-ONLY*
  spread_bps              12650  10562   25  0.511 [0.482,0.545]  0.662 [0.629,0.700]  0.509 [0.479,0.543]  RESOLUTION-ONLY
  g_n900                  12284  10207   25  0.496 [0.486,0.507]  0.504 [0.493,0.515]  0.494 [0.483,0.506]  NULL
  g_n3600                 12284  10207   25  0.511 [0.495,0.529]  0.512 [0.484,0.535]  0.504 [0.487,0.522]  NULL
  g_v900                  12284  10207   25  0.497 [0.488,0.506]  0.503 [0.491,0.517]  0.497 [0.486,0.508]  NULL
  g_v3600                 12284  10207   25  0.508 [0.494,0.524]  0.514 [0.491,0.534]  0.500 [0.485,0.517]  NULL
  volume_z                12650  10562   25  0.501 [0.484,0.519]  0.524 [0.500,0.544]  0.500 [0.482,0.520]  NULL*
```
(Rows for the other 60 stored features omitted; full text in scratch `s3_shipped.txt`.)
Join rate **99.61 %** (12,601 / 12,650; the 49 unmatched are the 6 rows appended between the
two reads plus tape-tail NaN keys; the 154/155 duplicate keys are same-asset-same-ts both-side
rows, documented in `join_extra_csv`). Note the **−1d placebo `g_n3600_shm1d` is flagged
DIRECTIONAL at 0.515 [0.503, 0.527]** while the real-time `g_n3600` is NULL at 0.504: with a
10 % realized DIRECTION false-exclusion rate and 71 features, ~7 such flags are expected by
chance, and the placebo drew one. The real feature did not even reach the chance flag.

## Power (scratch plant, random-feature rank, 12 seeds × 200 reps; detect = CI excludes 0)

| sub | ret rows | Q5−Q1 gap pct → detect | res rows | stop gap → detect |
|---|---|---|---|---|
| ALL | 6,048 | 0.08→2/12 · 0.16→3/12 · **0.32→10/12** · 0.48→12/12 | 10,579 | 0.03→8/12 · **0.05→12/12** |
| FLOW | 348 | 0.32→2/12 · 0.80→6/12 · **1.28→8/12** | 525 | 0.12→3/12 · **0.20→10/12** |
| ETH | 602 | 0.48→4/12 · **0.80→10/12** · 1.28→12/12 | 1,271 | 0.08→6/12 · **0.12→11/12** |
| BTC | 290 | 0.48→6/12 · **0.80→10/12** · 1.28→12/12 | 494 | 0.12→6/12 · **0.20→10/12** |

The 2–3/12 "detections" at 0.08 pct are the realized false-positive rate (≈ the shipped
instrument's 6–10 %). Per-asset MDEs are 2–4× the pooled one: the triad columns can only
refute large effects.

## What this could not see

- 10 return-blocks / 25 barrier-blocks. A day-block bootstrap this short is anti-conservative
  (measured: placebos fire at ~2× nominal). Effects inside ±0.4 pct / ±0.05 stop are invisible.
- Candidate rows only; FLOW has never filled, BTC/ETH fills were not scored here (fills.csv
  rows carry no barrier label). "Liquidated" was measured as tb_sl, not as a margin call —
  the leverage-distance question is item 2's.
- One label era (h432), one fee/label cost (0.6 %); nothing pooled across eras, nothing
  re-priced.
- Tape features end at each pair's `t_max` (327 signal rows dropped at the tail);
  `volume_z`/`vol_percentile` are the stored, feature-contract values whose own window
  definitions were not re-derived here.
- Two snapshots of a live file (23:10:47Z for the shipped run, 23:12:13Z for the scratch
  tables; 12,650 vs 12,659 rows). All counts are as-of.
- Scratch code is uncommitted: standard check 7 says these are not yet reproduced numbers.

Re-derive: rerun `s3_build.py` + `s3_power.py` from the scratch dir against a fresh
`signal_history.csv`; the shipped command line above is the committed half.

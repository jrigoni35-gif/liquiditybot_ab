# Stop-hunt / fakeout signature at 5-minute resolution — measurement memo (2026-09-02)

**Class: SAFE (measurement only; no code, config or `outputs/` touched).** Instrument: scratch
`sh5_main.py` (+ `sh5_results.json`, `sh5_events.parquet`), NOT committed — per
`docs/INSTRUMENT_VERIFICATION_STANDARD.md` §7 nothing here is reproduced until it is. All values
as-of **read 2026-09-02T23:38:10Z** (runner writing). Second pass on the 1 h memo
`docs/quant/2026-09-02_stop_hunt_fakeout_signature.md`: same population needle, same placebo A/B
design, same day-block CI; only the price-path resolution changed.

## Verdict (plain)

**FALSE at the floor. The bot's stops are not swept by transient moves that reverse, and rising
volume raises neither the reversal rate nor the stop rate.** On the exact tape, strictly after the
stop print, the reversal-through-entry rate R(k) equals the rate after a RANDOM entry with the same
pt/sl geometry (placebo B) at every k from 15 min to 24 h, pooled and per triad asset. Power floor
(80 %, cluster-preserving plant): **pooled +5 pp at 30 min / +15 pp at 2 h; FLOW +8/+20, ETH
+15/+30, BTC +8/+20.** The one thing this resolution could newly see — the sweep's depth and
duration — is also placebo: median excursion beyond the stop 48 bps in 30 min (placebo 50), 83 bps
in 2 h (92); median time below the stop 0.6 min (0.7); the hunt-signature share (shallow ≤ 1σ,
back through the stop ≤ 30 min, back through entry ≤ 2 h) is **5.5 % [3.3, 8.1] vs 4.7 % [3.2,
6.2], diff +0.8 pp [−1.9, +4.0], MDE 5 pp.** Rising volume INTO the resolution lowers the stop
share (Q1 .600 → Q4 .493), it does not raise it. BTC does not earn "reliable" (see Triad).

## Method (what resolution changed)

- **Corpus** `outputs/signal_history.csv` 23,046 rows, `fills.csv` 1,216. Needle unchanged:
  `source=='candidate' & label_era∈{triple_barrier_h432,triple_barrier} & barrier=='tb_sl' &
  entry_price>0 & sl_frac>0` → 7,028 tb_sl, **6,075 usable (pandas 6,075 / csv.DictReader 6,075)**;
  h432 5,725, legacy 350. Eras never pooled.
- **Lane** = production `outputs/candles/parquet/<SYM>_300.parquet` (all 15 assets, source=kraken,
  quote=USD, 190,712 bars, strings cast, 0 duplicate t_open, OHLC self-consistent). Missing bar =
  quiet window: FLOW 5,218 bars / 14,707 windows (9,489 empty), ETH 3 empty, BTC 3 empty; lane ends
  2026-09-02T01:35–01:50Z. **Tape** = `TickStore` (FLOW 18,372 / ETH 1,207,483 / BTC 2,930,099
  trades), stable time-sort.
- **Stop time**: first lane bar with t_open in (signal bar, +hz·300], hz = 432 (+48 grace) / 96
  (+48) legacy, low ≤ S (long) / high ≥ S (short), S = E·(1∓sl_frac); then the first tape print
  at/beyond S inside that bar. **Located 5,660** (h432 5,457 / legacy 203); **not located 415**:
  177 signal outside tape coverage, 147 no bar crossed (`no_cross`), 89 window ran past lane end
  with no cross (right-censored), **2 windows with NO bar at all** (both FLOW-class quiet; dropped
  and counted, not imputed). Triad: FLOW 314 located / 11 censored / 8 outside / 3 no_cross / 1
  no_bars; ETH 708 / 16 / 14 / 30; BTC 250 / 1 / 1 / 8. Every located stop had a tape print inside
  its lane bar (0 `lane_bar_no_tape_cross`); an independent full-tape search over the same window
  returned the identical print for **100 %**; the 1 h pass's scratch bars agree on the 5-min bin
  for 99.7 % of 5,678 key matches (p90 |Δ| 4.4 min). Tape refinement moves the stop **median 147 s
  into its bar (p10 29 s, p90 264 s)** — the resolution the 1 h pass lacked. Empty windows inside
  the search: FLOW 98.7 % of stops had ≥ 1 (median 81 empty bars), ETH 0.8 %, BTC 2.4 %.
  Recorded resolution `ts` − tape stop: median +4.1 min (p10 1.8, p90 6.6), 94.4 % in [−5, +60].
  Lane barrier vs the row's recorded barrier over all 10,015 located sl+pt rows: **5,457 tb_sl→sl,
  4,558 tb_pt→pt, 0 off-diagonal** (the labeler is reproduced exactly wherever it is reproduced at
  all; the 4 % unlocated remains unexplained, the 1 h memo's "different venue feed" gloss is not
  established by this).
- **R(k)** = any tape print strictly after the stop print, time in (t_s, t_s + k·300], at/beyond
  ENTRY; k ∈ {3, 6, 12, 24, 48, 96, 288}; NaN if the window runs past tape end. Lane route
  (bars strictly after the stop bar) is the cross-implementation.
- **Placebo A** random timestamp, level one sl-distance away, same side, 5×. **Placebo B** (load-
  bearing) random ENTRY time day-block resampled per asset over the era span, same asset/side/
  pt/sl, lane labeler semantics (SL first), keep SL-resolved, then the SAME tape refinement and
  excursion as real; 5× → 12,398 rows / 23 blocks (h432).
- **CI** day-block bootstrap on UTC day of the stop print, 1,000 draws, refused < 5 blocks. Real
  h432 = 5,457 rows = **1,739 (asset, stop-5m-bin) clusters / 22 blocks.** **MDE** = one flag per
  cluster at (placebo-B per-day rate + δ), 30 trials, 300-draw diff CI, 80 % detection; grid
  2–30 pp. Excursion: max adverse print beyond S in bps within 30 min / 2 h / 24 h; duration =
  minutes until the first print back at/through S (censored 1,440); tape σ = std of log
  close-to-close over the 12 lane bars before the signal.
- **Injection (§2)**: 400-row sample, k = 6: baseline .015 → entry := S **.815** (= the 86 %
  back-through-S-in-30-min rate, as it should) → side flipped **.998** → stop shifted −1 h
  **.288**. Synthetic tape with planted 37.4 bps / 17 min / reversal at 39 min: instrument returned
  37.37 / 17.0 / 39.0, R12 True, R6 False; the tape-end censor guard fired (NaN) when the window
  was set past the synthetic tape's end.

## R(k) real vs placebo — h432, tape route, strictly post-stop

Real n / blocks / clusters: pooled 5,457 / 22 / 1,739 · FLOW 296 / 19 / 94 · ETH 704 / 17 / 131 ·
BTC 249 / 17 / 92. Placebo B: 12,398 / 775 / 1,395 / 499. Lane route agrees with tape to ≤ 0.3 pp
at every pooled k (k6 .014 vs .013, k24 .126 vs .125).

| k | pooled real | plB | diff [CI] | MDE | FLOW real / plB | diff | ETH real / plB | diff | BTC real / plB | diff |
|---|---|---|---|---|---|---|---|---|---|---|
| 3 (15m) | .003 [.001,.007] | .007 [.004,.011] | −.004 [−.008,+.001] | — | .000 / .003 | −.003 [−.009,0] | .000 / .005 | −.005 [−.010,−.001] | .008 [0,.025] / .000 | +.008 [0,+.025] |
| 6 (30m) | .013 [.006,.021] | .025 [.011,.043] | −.012 [−.031,+.006] | .05 | .007 [0,.023] / .007 | .000 [−.015,+.018] (MDE .08) | .000 [0,0] / .025 [.004,.056] | −.025 [−.056,−.004] (MDE .15) | .012 [0,.031] / .002 | +.010 [−.003,+.029] (MDE .08) |
| 12 (1h) | .050 [.027,.079] | .059 [.031,.094] | −.009 [−.052,+.034] | — | .010 / .010 | .000 [−.020,+.030] | .007 / .034 | −.027 [−.060,0] | .028 / .030 | −.002 [−.051,+.041] |
| 24 (2h) | .125 [.079,.175] | .124 [.075,.175] | +.001 [−.068,+.072] | .15 | .044 [.012,.092] / .057 | −.013 [−.082,+.050] (MDE .20) | .077 [.014,.153] / .115 | −.038 [−.154,+.074] (MDE .30) | .044 [.009,.085] / .036 | +.008 [−.056,+.065] (MDE .20) |
| 48 (4h) | .232 [.155,.317] | .209 [.144,.282] | +.023 [−.085,+.128] | — | .105 / .086 | +.019 [−.087,+.131] | .162 / .176 | −.015 [−.220,+.207] | .072 / .062 | +.010 [−.079,+.104] |
| 96 (8h) | .397 [.302,.491] | .354 [.266,.433] | +.043 [−.084,+.171] | — | .194 / .166 | +.028 [−.102,+.164] | .384 / .353 | +.031 [−.278,+.315] | .268 / .263 | +.004 [−.193,+.217] |
| 288 (24h) | .574 [.434,.680] | .512 [.398,.619] | +.063 [−.113,+.227] | — | .365 / .294 | +.071 [−.156,+.307] | .509 / .491 | +.019 [−.326,+.320] | .427 / .377 | +.050 [−.242,+.329] |

Placebo A pooled: k6 .017, k24 .088, k96 .259, k288 .434; real − A = +0.7 / +3.7 / **+13.8 pp
[+2.1, +24.9]** / +14.0 [−1.5, +27.1] — the 8 h excess over a no-prior-move null is the mean
reversion that follows ANY one-stop-distance move and is fully reproduced by placebo B (+4.3 pp
[−8.4, +17.1]). ETH reverts LESS than placebo at 15–60 min (−2.5 pp [−5.6, −0.4] at 30 min, 0 of
704) — same sign and size as the 1 h pass; not separated from an entry-stamp artefact (see Concerns).

Resolution shares, denominator = all labeled tb rows in era (n 12,670): real sl .452 / pt .384 /
time .164; placebo B (n 27,280) .454 / .322 / .224. The bot's stop rate equals a random entry's.

**Legacy era** (203 rows / 10 blocks / 121 clusters; plB 544 / 11): R6 .000 vs .004 (MDE .05), R24
.020 [0,.056] vs .048 [.019,.077], diff −2.8 pp [−6.6, +1.6] (MDE .15), R288 .404 vs .441. FLOW 18 /
7 blocks: R24 .222 vs .244 (MDE > .30); ETH 4 / 1 block, BTC 1 / 1 → refused. Null.

## The new measurement: sweep depth and duration (h432, tape, bps beyond the stop)

| | pooled real | plB | FLOW real / plB | ETH real / plB | BTC real / plB |
|---|---|---|---|---|---|
| depth 30 min, median [CI] | 48.1 [39.8,58.0] | 50.2 [40.8,60.0] | 85.9 [56,126] / 73.1 [49,116] | 54.7 [36,81] / 40.6 [26,61] | 29.7 [23.5,36.8] / 31.4 [24.8,40.5] |
| depth 2 h, median | 82.6 [64.5,105] | 91.9 [72.8,115.5] | 126 [86,190] / 109 [78,183] | 87.0 [63,120] / 75.5 [43,106] | 60.5 [33,145] / 62.5 [42,107] |
| depth 24 h, median | 221 [156,326] | 256 [190,366] | 326 / 265 | 177 / 196 | 109 / 148 |
| depth 2 h in tape-σ (p10/p50/p90) | .56 / 3.98 / 19.0 | .66 / 4.64 / 23.4 | .49 / 2.34 / 9.6 · .36 / 2.50 / 12.8 | .97 / 6.07 / 33.1 · .78 / 5.93 / 34.0 | .57 / 5.33 / 114 · .85 / 7.00 / 81.5 |
| depth 2 h in row σ_bar_pct (real) | .67 / 4.74 / 23.2 | — | 1.68 / 7.14 / 30.5 | .87 / 5.81 / 28.6 | .63 / 5.43 / 150 |
| minutes below stop, median (p75, p90) | 0.6 [0.5,0.9] (6.1, 70.5) | 0.7 [0.5,0.9] (7.4, 83.8) | 11.4 [4.7,22.9] (62, 412) / 10.7 (48, 578) | 0.0 (0.3, 3.6) / 0.0 (0.3, 2.7) | 0.0 (0.5, 2.2) / 0.0 (0.6, 4.8) |
| depth before reversal, reverted-in-24h subset | 82.0 (n 2,938) | 82.3 (n 6,157) | 88.8 / 87.1 | 119.7 / 99.0 | 32.8 / 36.7 |
| depth 24 h, NOT reverted | 365 (n 2,519) | 382 (n 6,241) | 423 / 328 | 273 / 245 | 200 / 223 |
| back through S ≤ 30 min | .861 [.823,.895] | .853 [.814,.886] | .644 / .658 | .929 / .940 | .968 / .950 (+.018 [−.034,+.081]) |
| deep ≥ 2σ within 2 h | .692 [.623,.750] | .726 [.678,.770] | .535 / .584 | .821 / .791 | .707 / .786 (−.079 [−.230,+.071]) |
| **hunt signature** (≤ 1σ & back ≤ 30 min & R24) | **.055 [.033,.081]** | **.047 [.032,.062]** diff +.008 [−.019,+.040] MDE .05 | .044 / .043 (+.001 [−.062,+.070], MDE .20) | .020 / .030 (−.010 [−.032,+.012], MDE .10) | .024 / .012 (+.012 [−.017,+.041], MDE .10) |

Reverting and non-reverting paths separate by DEPTH exactly as a random walk does (82 vs 365 bps
real; 82 vs 382 placebo): a stop that comes back was a shallow break, not a hunt — the placebo has
the identical bimodality. Legacy era pooled: depth 30 min 22.2 [19.0,28.9] vs 27.5; 2 h 36.5 vs
52.0; hunt signature .011 vs .015 (diff −.004 [−.026,+.027], MDE .08).

## Volume conditioning (h432; R6 / R24 with CI; tb shares from ALL tb rows in era per quintile)

**volume_z at signal** (edges −0.44 / −0.31 / −0.16 / +0.47; ~1,091 rows, 21–22 blocks each):
R6 .007 / .012 / .009 / .015 / .023; R24 .147 [.085,.210] / .113 / .105 / .119 / .139 [.091,.193]
— flat, every CI overlaps. Shares (n 2,594 / 2,618 / 2,472 / 2,551 / 2,435): tb_sl .451 / .432 /
.455 / .450 / .473, tb_pt .394 / .371 / .360 / .391 / .404. Triad R24 Q1→Q5: FLOW .067 (3 blocks) /
.075 / .028 / .025 / .047; ETH .081 / .108 / .044 / .067 / .095; BTC .000 / .050 / .000 / .086 / .072.

**vol_percentile at signal** (edges .14 / .40 / .60 / .76): R24 .030 [0,.092] / .045 / .166 / .211
[.156,.269] / .172 — rises with volatility, but tb_pt rises the same way (.330 / .342 / .434 / .383
/ .422) while tb_sl is flat (.442 / .482 / .422 / .461 / .457): RESOLUTION loads on σ, not
direction. Tape-σ quintiles, real vs placebo B on the same edges: R24 .036 vs .036, .083 vs .102,
.145 vs .139, .192 vs .168, .196 vs .239 (Q5 diff −4.3 pp [−11.1, +1.9]). Real never beats placebo.

**Rising volume INTO the stop** (tape trades in the 3,600 s before the stop print ÷ before the
signal; edges 0.73 / 1.15 / 1.71 / 2.99):

| vgrow Q | pooled R6 real / plB | pooled R24 real / plB | diff R24 [CI] | MDE | FLOW R24 real / plB | ETH R24 | BTC R24 |
|---|---|---|---|---|---|---|---|
| Q1 (< 0.73) | .008 / .012 | .126 [.090,.166] / .127 [.083,.176] | −.001 [−.060,+.062] | .15 | .047 / .046 | .028 / .045 | .097 / .024 |
| Q2 | .008 / .034 | .163 / .173 | −.010 [−.093,+.075] | .20 | .081 / .104 | .090 / .093 | .044 / .036 |
| Q3 | .019 / .022 | .129 / .141 | −.012 [−.095,+.060] | .15 | .138 / .119 | .102 / .115 | .087 / .055 |
| Q4 | .013 / .027 | .092 [.044,.174] / .111 | −.019 [−.089,+.069] | .15 | .050 / .061 | .083 / .130 | .000 / .034 |
| Q5 (> 2.99) | .017 / .030 | .116 [.044,.194] / .082 [.030,.155] | +.033 [−.073,+.133] | .15 | .000 / .034 | .014 / .161 | .000 / .014 |

**Resolution vs direction, answered separately.** Trade-count growth into the RESOLUTION print
for every located sl + pt row (n 10,002; tb_time rows have no resolution print and are excluded;
denominator = located sl + pt rows in the bucket), same edges: **tb_sl share Q1 .600 [.500,.707] ·
Q2 .584 [.509,.660] · Q3 .536 [.478,.594] · Q4 .493 [.393,.578] · Q5 .524 [.430,.637]**, tb_pt =
1 − that. Triad sl share Q1→Q5: FLOW .683 / .638 / .558 / .541 / .584; ETH .567 / .704 / .560 /
.544 / .461; BTC .554 / .549 / .543 / .466 / .443. Rising volume does not raise the stop rate (the
point estimate falls, edge CIs overlap) and does not raise the reversal rate (table above).

## Cut #7 (Osler widen-beyond, 2026-08-11T00:00Z = 1786406400), never pooled

- h432: **before n = 0** (era's first stamped stop signal_ts 1786439400 = 2026-08-11T09:10Z);
  after 5,457 / 22 blocks, R6 .013, R24 .125, MDE vs placebo .05 / .15. Nothing to compare.
- legacy: before 163 / 9 blocks R6 .000 [0,0], R24 .012 [0,.045]; after 40 / **2 blocks → CI and
  MDE refused** (floor 5). Cross-era comparison would pool label eras: not reported.
- Structural, unchanged: `_nudge_stop` (`main.py`) touches LIVE stop prices only; candidate
  `sl_frac` is `barrier_geometry()`, never nudged — candidate rows cannot see cut #7 at any n.

## Live population (fills.csv; descriptive, kept separate)

33 stop exits (`purpose=='exit' & reason =~ ^tb_sl$|^stop .* hit$`), 30 inside tape; exec eras
7 / 8 / 9 / unstamped = 14 / 2 / 6 / 8. Pooled ACROSS exec eras, descriptive only (16 blocks): R3
.000, R6 **0/30**, R12 .067, R24 .067 [0,.200], R48 .167, R96 .310 [.130,.480], R288 .552
[.357,.731]. Excursion beyond the fill: median 29.6 bps at 30 min, 65.9 at 2 h; minutes below
the fill median 0.13 (p90 2.4) — the fill IS the stop print, so duration is ~0 by construction.
Era 7 alone 14 / 7 blocks: R6 .000, R24 .071 [0,.30]; eras 8, 9, unstamped below the floor.

## Triad — does BTC earn "reliable"?

Definition for this item: lowest reversal-above-placebo rate at 30 min and 2 h. **BTC has the
HIGHEST point estimate of the three** (+1.0 pp [−0.3, +2.9] at 30 min, +0.8 pp [−5.6, +6.5] at 2 h)
vs ETH −2.5 pp [−5.6, −0.4] / −3.8 pp and FLOW 0.0 pp / −1.3 pp; all inside their floors (30 min:
BTC .08, ETH .15, FLOW .08). BTC's excursions are the shallowest in bps (29.7 bps at 30 min) but
equal to its own placebo (31.4) — that is BTC's volatility, not a property of its stops. **BTC does
not earn "reliable" on this axis; if anything ETH has the lowest reversal rate, and it is below
placebo.** FLOW (98.7 % of stops searched through empty windows, zero fills ever) is measurable
only on candidates and matches its placebo at every k and in every excursion statistic.

## vs the 1 h pass (number by number)

1. **Stop time.** Same 5-min bin as the 1 h pass's scratch bars for 99.7 % of 5,678 matches, and
   identical to an independent full-tape search for 100 %. New: the print sits median 147 s into
   its bar; the 1 h pass's "[j, j+k]" leak (REPAIR finding 1) cannot occur on a print-anchored window.
2. **R(k) pooled.** 30 min: 1 h tick-repair .015 vs plB .028 (−1.3 pp [−3.4, +0.6]) → now .013 vs
   .025 (**−1.2 pp [−3.1, +0.6]**). 2 h: +0.2 pp [−6.6, +7.5] → **+0.1 pp [−6.8, +7.2]**. 24 h:
   +6.8 pp [−12.5, +23.9] → +6.3 pp [−11.3, +22.7]. Verdict did not move.
3. **Triad at 30 min.** BTC −0.8 pp [−5.4, +2.4] → **+1.0 pp [−0.3, +2.9]** (the 1 h pass's placebo
   B at 30 min was .020; on the exact window it is .002 — BTC placebo reversals inside 30 min
   were mostly the pre-stop prints of the stop bar); ETH −2.6 pp [−6.0, 0] → **−2.5 pp [−5.6,
   −0.4]** (now excludes 0, below placebo); FLOW −0.3 pp → 0.0 pp [−1.5, +1.8].
4. **Power floors.** 1 h corrected pooled .04 / .10, BTC .10 / .15, ETH .08 / .20, FLOW .05 / .10
   → now **pooled .05 / .15, BTC .08 / .20, ETH .15 / .30, FLOW .08 / .20** (30 min / 2 h).
   ETH/FLOW moved UP: method, not data — the plant here is one flag per cluster (the 1 h REPAIR
   planted per row at cluster-level rates) and the placebo per-day rates on the exact window are
   more dispersed. The nulls above are only as small as these floors.
5. **New — excursion.** Depth and duration of the sweep, real vs placebo, indistinguishable
   (table above); hunt-signature share +0.8 pp [−1.9, +4.0], MDE 5 pp. The 1 h pass could not
   measure this.
6. **New — resolution vs direction on growth into the RESOLUTION** (not only into the stop): stop
   share .600 → .493 / .524 from Q1 to Q4 / Q5. The 1 h pass answered "stop rate" only via
   volume_z shares.
7. **Placebo A at 8 h** now significant (+13.8 pp [+2.1, +24.9]) where the 1 h pass had no 8 h row;
   reproduced by placebo B (+4.3 pp [−8.4, +17.1]) → prior-move mean reversion, not a hunt.
8. **k = 3 (15 min)** added: pooled .003 vs .007.

## What this check could not see / concerns

- 415 of 6,075 usable stops not measured (177 outside tape, 147 never crossed on Kraken, 89
  right-censored at lane end, 2 no bar); the 89 censored are late-window stops — survivorship
  toward early stops, direction of bias on R(k) unknown.
- ETH real R6 = 0/704 vs placebo .025 (below placebo, CI excludes 0) is not separated from an
  entry_price-stamp artefact (entry stamped at a different price than the tape's print at
  signal_ts); the 1 h pass showed the same sign. Instrument suspect first; not resolved here.
- 100 % barrier agreement on located rows vs 4 % unlocated: the unlocated cause is unexplained.
- Placebo rows are seeded but rng-order dependent: adding the hunt-signature MDE changed the
  legacy placebo-B n 576 → 544 between runs (h432 numbers unchanged). Reproduction = commit
  `sh5_main.py` (standard §7); until then every figure is as-of 23:38:10Z.
- MDE grid is coarse (2/3/4/5/6/8/10/15/20/30 pp), 30 trials, 300-draw CI inside the plant.
- Live placebo B, live per-exec-era CIs, cut-#7 MDE: below the block floor, not run. Tape/lane
  end 2026-09-02T01:35–01:50Z: the last ~22 h of the corpus is outside coverage.
- Reversal is to the ENTRY only; "did the herd's stops fire first" (round-level Osler test) still
  needs the live stop level vs the round level, absent from both CSVs.
- **BOUNDARY (described, not done):** none of this licenses a geometry change; the ALGO-5 stop-width
  amendment may NOT cite "hunts" as motivation — the hunt is not there at the floor. SAFE follow-up:
  commit the instrument as `scripts/stop_hunt_report.py` with the injection table as its test.

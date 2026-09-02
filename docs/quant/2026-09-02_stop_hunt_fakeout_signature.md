# Stop-hunt / fakeout signature — measurement memo (2026-09-02)

**Class: SAFE (measurement only; no code, config or outputs/ touched).** Scratch instruments:
`s2_bars.py`, `s2_stophunt.py`, `s2_long.py` (scratch dir, not committed — per
`docs/INSTRUMENT_VERIFICATION_STANDARD.md` §7 these numbers are NOT reproduced until the
scripts are committed; treat every figure below as as-of its read time).

**Hypothesis under test (operator):** the bot's stop-outs are frequently followed by price
reverting back through the entry (stop swept by a transient "hunt"/fakeout), and more so
when volume is rising.

> **REPAIR 2026-09-02 (three verification findings, all WARNING, applied 23:24Z; scratch
> `s2v_tick.py` re-run, output `s6r_s2v_rerun.txt`, tape/corpus read 2026-09-02T23:24:22Z).**
> **(1) Window artefact.** `s2_stophunt.py:reverted()` scans `[j, j+k]` — it INCLUDES the
> stop bar j, i.e. prints that occurred BEFORE the stop inside that 5-min bar. R0 (k=0) is
> therefore not a post-stop statistic, and it leaks into every R(k). BEFORE (verdict triad):
> "BTC +3.0 pp [−0.3, +7.5] at 30 min, the least-null of the three." AFTER, on the strict
> post-stop TICK route (window (t_stop, t_stop+W], tick-level stop time, same placebo B,
> day-block CI): BTC R(30 min) real **.012** [0, .030] vs plB .020 [0, .066], diff **−0.8 pp
> [−5.4, +2.4]** (n 249 / 17 blocks / 92 clusters); ETH real .000 vs plB .026, diff −2.6 pp
> [−6.0, 0]; FLOW −0.3 pp [−2.9, +2.2]; pooled real .015 vs plB .028, diff −1.3 pp [−3.4,
> +0.6] (5,457 rows / 22 blocks / 1,735 clusters). At 2 h: BTC −0.3 pp [−7.4, +5.8], ETH −4.2
> pp [−14.9, +6.6], FLOW −1.8 pp [−8.2, +4.9], pooled +0.2 pp [−6.6, +7.5]. BTC's 2.4 of the
> 3.0 pp was the stop bar itself (table row k=0: BTC .024 vs plB .000); post-stop, BTC sits
> BELOW placebo like ETH and FLOW. The k=0 row and every "[j, j+k]" number in the tables
> below stand as recorded but are bar-inclusive; the tick route is the corrected statistic.
> **(2) Power floor understated for the triad.** BEFORE: MDE at 30 min BTC .04, ETH .06,
> FLOW .06. Cause: `mde()` redraws flags i.i.d. per ROW inside a day (`rng.random((days ==
> d).sum())`), discarding the 249-rows-in-92-clusters structure. AFTER (planted +δ on real
> rows at placebo per-day rates, 30 trials, 80 % detection, tick route): **BTC .10 / .15
> (30 min / 2 h), ETH .08 / .20, FLOW .05 / .10, pooled .04 / .10** (pooled agrees with the
> table). The memo's own BTC CI half-width (3.9 pp) already implied ≥ ~5.6 pp. The per-asset
> nulls therefore read "no excess above 10 pp (BTC), 8 pp (ETH), 5 pp (FLOW) at 30 min".
> **(3) Overclaim struck.** "the highest-growth buckets revert LESS … volume-driven stops look
> like genuine breaks, not fakeouts" — Q4 real .085 [.040, .161] vs plB .108 [.062, .168] vs
> Q1 .139 [.103, .176]: every CI overlaps and no per-quintile MDE was run. Supported statement:
> rising volume into the stop does not raise reversal above placebo. "Marks the break as real"
> was an explanation chosen on plausibility and is withdrawn (edited in place below).

## Verdict (plain)

**NO. The bot's stops are NOT being hunted at a rate above the volatility base rate, at a
power floor of +4 pp (30 min), +10–15 pp (2 h) pooled; per asset BTC +10 pp / ETH +8 pp /
FLOW +5 pp at 30 min (repaired, see REPAIR block).** The
reversal-through-entry rate after a stop, R(k), is statistically indistinguishable from the
rate after a RANDOM entry with the identical pt/sl geometry (placebo B) at every horizon
from 5 min to 24 h, pooled and for each of FLOW / ETH / BTC. Rising volume into the stop
does not raise the reversal rate above placebo in any growth quintile (Q4: 8.5 % [4.0, 16.1]
vs placebo 10.8 % [6.2, 16.8] — overlapping, no per-quintile MDE run; the earlier "genuine
breaks, not fakeouts" reading is withdrawn as an unevidenced gloss). The one
excess that does exist is over placebo A (random level at a random time, no prior move) and
it is the mean reversion that follows ANY move of one stop-distance, not a bot-specific
signature. The cut-#7 before/after comparison is UNDETERMINED (after-side 2 day-blocks,
below the 5-block floor) AND vacuous by construction on candidate rows (the Osler nudge lives
in `main.py:_nudge_stop`, live positions only; candidate `sl_frac` = `barrier_geometry()`,
never nudged). The live population (33 stop exit fills, 30 measurable) shows R(30 min) =
0/30 and cannot be split by exec era at the block floor.

Triad: **FLOW** (thin, 15 trades/h, 9,489 of 14,708 5-min bars empty) has the widest CIs and
zero fills — measured on candidates only; its R(k) equals its own placebo at every k.
**ETH** (liquid) reverts LESS than placebo at 30 min–2 h (bar route −2.0 / −3.2 pp; strict
post-stop tick route −2.6 pp [−6.0, 0] / −4.2 pp [−14.9, +6.6], not significant). **BTC**
[REPAIRED]: the bar-route "+3.0 pp above placebo at 30 min" was the stop-bar-inclusive
artefact (2.4 of the 3.0 pp came from prints BEFORE the stop inside bar j); on the strict
post-stop tick route BTC is **−0.8 pp [−5.4, +2.4]** at 30 min and −0.3 pp [−7.4, +5.8] at
2 h, below placebo like ETH and FLOW. "Reliable" defined as lowest stop-reversal rate above
placebo: all three are null at their floors (BTC 10 pp, ETH 8 pp, FLOW 5 pp at 30 min), so
BTC neither earns nor forfeits it — the triad is indistinguishable on this axis at this n
(249 rows / 92 clusters for BTC).

## Method

- **Corpus** (read 2026-09-02T23:13:12Z; runner writing): `outputs/signal_history.csv`
  23,035 rows; `outputs/fills.csv` 1,216 rows. Needle, candidate population:
  `source=='candidate' & label_era in {triple_barrier_h432, triple_barrier} & barrier=='tb_sl'
  & entry_price>0 & sl_frac>0` → 7,023 tb_sl rows, 6,070 usable (the 4,375 legacy
  `triple_barrier` rows with `entry_price==0` predate the 2026-08-03T01:00Z onset of
  entry_price stamping — full-range scan). Eras never pooled: h432 = 5,720, legacy = 350.
- **Live population** needle: `fills.csv purpose=='exit' & reason =~ ^tb_sl$|^stop .* hit$`
  → 33 fills (28 `tb_sl`, 5 `stop <px> hit`); joined to entry fill via `position_id`, 30
  inside tape coverage. Exec eras 7/8/9 = 14/2/6 (+8 dropped/unmatched). **exit_sim `sl`
  rows (1,935) carry `entry_price==0` and `sl_frac==0` on all 1,935 → UNMEASURABLE**
  (finding: the exit_sim era never stamped geometry).
- **Price path.** `outputs/candles/parquet/` holds ONLY 3600 / 14400 / 86400 s (15 assets,
  multi-source okx/binanceus/kraken, ends 2026-08-29T16:00Z — before ~3 days of the
  corpus). Finest interval = 3600 s. Therefore the primary path is **5-minute bars built
  from the local Kraken tape** (`TickStore`, all 15 assets 2026-07-13 → 2026-09-02T01:59Z;
  read 23:09:24Z), matching the labeler's 5m book; timing resolution 5 min (FLOW: a bar
  crosses only when a trade prints — 64 % of its 5-min bars are empty, so FLOW's stop
  time is bounded by its next print, median trade gap ~4 min). Kraken 3600 s parquet is the
  cross-implementation route.
- **Stop time** = first 5m bar after the signal bar whose low ≤ S (long) / high ≥ S (short),
  S = E·(1∓sl_frac), horizon 432 (+48 grace). Re-derived on tape for 5,660 of 5,898
  in-coverage rows (238 = 4.0 % unreproduced: tape never crossed within horizon — the
  labeler's bars come from a different venue feed; excluded). Cross-check vs the row's
  recorded resolution `ts`: median +6.5 min (p10 5.3, p90 7.5), 94.3 % within [−5, +60] min.
- **R(k)** = price back through the ENTRY on any bar in [stop bar, stop bar + k], k ∈
  {0, 6, 12, 24, 48} 5m bars (= same bar, 30 min, 1 h, 2 h, 4 h) plus {72, 144, 288}
  (6/12/24 h).
- **Placebo A**: random timestamp (day-block resampled per asset over the era span), level at
  the same sl distance, same side; 5× real n. **Placebo B** (the load-bearing null): random
  ENTRY time, same asset/side/pt_frac/sl_frac, labeler semantics (SL checked first), keep
  only SL-resolved paths; 5× real n. Both get the same day-block CI.
- **CI**: day-block bootstrap (UTC day of stop), 1,000 draws, refused below 5 blocks.
  Effective n ≠ row n: 5,457 h432 rows = 1,739 distinct (asset, stop-bar) clusters, 22 days.
- **Power**: null-matched planted effect — real rows redrawn at placebo-B per-day rates,
  +δ planted, detection = 95 % diff CI excludes 0 in ≥ 80 % of 40 trials; smallest δ on
  {2,4,6,8,10,15,20,30} pp.
- **Instrument checks** (standard §1, §2, §4): cross-implementation on kraken 3600 s
  candles, stop hour agrees 99.0 % (n = 3,704); R at 6 h route A 0.357 vs route B 0.356, at
  24 h 0.586 vs 0.582 (same 3,704-row subset). Mutation/injection on a 400-row sample, k=6:
  baseline 0.035 → entry := stop level (planted hunt) 0.940 → side flipped 1.000 → stop bar
  shifted −12 bars 0.315. The detector fires on the planted defect.

## R(k) real vs placebo — candidate rows, era `triple_barrier_h432` (5m bars)

Real n / blocks / clusters: pooled 5,457 / 22 / 1,739 · FLOW 296 / 19 / 94 · ETH 704 / 17 /
131 · BTC 249 / 17 / 92. Placebo B n: 12,398 / 775 / 1,395 / 499.

| k | pooled real | plB | diff [CI] | MDE | FLOW real | plB | ETH real | plB | BTC real | plB | diff(BTC) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 (bar) | .017 [.005,.033] | .011 | +.005 [−.007,+.022] | — | .027 [0,.085] | .014 | .011 [0,.037] | .009 | .024 [0,.068] | .000 | +.024 [0,+.068] |
| 6 (30m) | .027 [.012,.045] | .035 [.019,.057] | −.008 [−.034,+.017] | .04 | .034 [0,.101] | .018 | .011 [0,.034] | .032 | .032 [0,.078] | .002 | +.030 [−.003,+.075] |
| 12 (1h) | .062 [.036,.097] | .069 [.036,.111] | −.007 [−.052,+.039] | — | .051 [.010,.125] | .026 | .020 [.003,.048] | .044 | .048 [.008,.091] | .030 | +.018 [−.044,+.076] |
| 24 (2h) | .135 [.082,.190] | .131 [.079,.182] | +.004 [−.068,+.082] | .15 | .071 [.021,.154] | .068 | .088 [.024,.171] | .120 | .060 [.011,.122] | .036 | +.024 [−.046,+.100] |
| 48 (4h) | .240 [.162,.322] | .215 [.144,.290] | +.025 [−.081,+.131] | — | .132 [.060,.248] | .097 | .175 [.035,.364] | .182 | .088 [.009,.199] | .062 | +.026 [−.079,+.154] |
| 72 (6h) | .325 [.242,.417] | .283 [.205,.358] | +.042 [−.068,+.163] | — | .173 [.094,.303] | .138 | .237 [.080,.450] | .241 | .133 [.036,.240] | .097 | +.036 [−.086,+.167] |
| 144 (12h) | .490 [.364,.585] | .426 [.330,.523] | +.064 [−.093,+.212] | — | .354 [.208,.555] | .279 | .474 [.193,.704] | .428 | .378 [.202,.573] | .300 | +.078 [−.164,+.319] |
| 288 (24h) | .581 [.428,.687] | .513 [.391,.624] | +.068 [−.125,+.239] | — | .394 [.231,.598] | .326 | .519 [.226,.742] | .501 | .445 [.235,.679] | .370 | +.074 [−.226,+.373] |

MDE (null-matched, 80 % power) per asset — SUPERSEDED (per-row redraw, optimistic): FLOW R6
.06 / R24 .15 · ETH .06 / .20 · BTC .04 / .10. **Corrected (cluster-preserving plant on real
rows, tick route, 30 trials): FLOW .05 / .10 · ETH .08 / .20 · BTC .10 / .15 · pooled .04 / .10.**
Placebo A (random level, no prior move), pooled: R6 .018 [.011,.027], R24 .089 [.059,.120],
R48 .165 [.113,.219] — real exceeds A by +0.9 / +4.5 / +7.5 pp (all CIs include 0 except
k=0: +1.6 pp [+0.4,+3.1]). That excess is fully reproduced by placebo B.

Legacy `triple_barrier` era (203 rows / 10 blocks / 121 clusters; FLOW 18 / 7; ETH 4 / 1 and
BTC 1 / 1 → refused): pooled R6 .030 [0,.071] vs plB .023 [.004,.049] (MDE .06); R24 .044
[0,.090] vs plB .061 [.029,.100] (MDE .10); R48 .099 [.043,.177] vs plB .140 [.089,.203].
FLOW R24 .278 [0,.600] vs plB .260 (MDE > .30, uninformative). Null, both eras.

## Barrier-geometry discipline — resolution shares (denominator = all labeled tb rows in era)

h432 real: pooled sl .452 / pt .384 / time .164 (n = 12,659); FLOW .510/.337/.153; ETH
.501/.367/.132; BTC .375/.363/.263. Placebo-B random entries, same geometry: pooled sl .454 /
pt .322 / time .224; FLOW .524/.324/.152; ETH .396/.306/.298; BTC .401/.277/.322. **The
bot's stop rate equals a random entry's stop rate** (45.2 % vs 45.4 % pooled); its pt rate
is 6 pp higher. No adverse-selection signature on RESOLUTION either.

## Volume conditioning (h432, R6 / R24, quintiles within era)

**volume_z at signal** (Q1 −1.30..−0.44 → Q5 0.47..5.00, ~1,091 rows / 21–22 blocks each):
pooled R6 .022 / .018 / .028 / .026 / .040; R24 .156 / .118 / .121 / .126 / .152 — flat,
every CI overlaps every other. Resolution shares by quintile (all tb rows, n≈2,400–2,600
each): sl .45/.43/.46/.45/.47, pt .39/.37/.36/.39/.40 — **volume_z raises neither the stop
rate nor the reversal rate.** Triad R24: FLOW .067(Q1,3 blocks)/.090/.064/.049/.078; ETH
.096/.126/.058/.067/.111; BTC .016/.050/.000/.103/.101 (BTC Q4–Q5 vs Q1–Q3: CIs overlap,
n = 58–69 / 15 blocks).

**vol_percentile at signal** (Q1 0–.14 → Q5 .76–1.0): pooled R24 .035 [.004,.096] / .049 /
.167 / .230 [.152,.298] / .192 — rises with volatility, BUT the tb_pt share rises the same
way (.33/.34/.43/.38/.42) while tb_sl is flat (.44/.48/.42/.46/.46): **RESOLUTION loads on
volatility, not DIRECTION** — a fixed-percent cost-floored sl (median 1.80 %) is fewer sigmas
away when sigma is high, so both barriers and the walk back to entry all speed up. Confirmed
on the tape-side sigma (12 prior 5m bars, real and placebo B on the same edges): Q1 (< 9.9 bp)
real R24 .038 vs plB .039; Q3 .150 vs .131; Q5 (> 34.5 bp) .211 [.156,.262] vs plB .255
[.189,.308]. Real never exceeds placebo in any sigma bucket.

**Rising volume INTO the stop** (tape trade count in the 3,600 s before the stop ÷ the 3,600 s
before the signal; quintile edges 0.66 / 1.03 / 1.54 / 2.67; Q5 up to 229×):

| vgrow Q | pooled R6 | plB R6 | pooled R24 | plB R24 | FLOW R24 | ETH R24 | BTC R24 |
|---|---|---|---|---|---|---|---|
| Q1 (<0.66) | .015 [.005,.027] | .023 [.014,.032] | .139 [.103,.176] | .139 [.087,.191] | .065 (77) | .110 (100) | .121 (33) |
| Q2 | .021 | .037 | .163 [.106,.214] | .165 | .109 (46) | .084 (167) | .086 (35) |
| Q3 | .045 | .048 | .162 [.091,.231] | .165 | .074 (27) | .155 (174) | .113 (71) |
| Q4 | .023 | .034 | .085 [.040,.161] | .108 [.062,.168] | .023 (44) | .048 (188) | .000 (68) |
| Q5 (>2.67) | .031 | .035 | .126 [.062,.212] | .091 [.039,.167] | .084 (95) | .013 (75) | .000 (42) |

Real tracks placebo B in every bucket (all CIs overlap; per-quintile MDE not run, so
bucket-to-bucket differences of ~2–5 pp are not resolvable here). **Rising volume into the
stop does not raise the reversal rate above placebo.** [REPAIRED: "if anything it marks the
break as real" struck — Q4/Q5 vs Q1 differences are inside overlapping CIs.]
(vgrow is only defined on stopped rows, so "does rising volume raise the stop rate" is
answered by the volume_z resolution shares above: no.)

## Cut #7 (Osler widen-beyond, 2026-08-11T00:00Z = 1786406400)

- h432 era: before n = 0 usable stop rows (era's first stamped rows begin 2026-08-09; 17 rows
  before the cut, none tb_sl with geometry) → nothing to compare.
- legacy era: before n = 163 / 9 blocks, R6 .000 [0,0], R24 .012 [0,.043]; after n = 40 /
  **2 blocks** → CI REFUSED (floor 5). Cross-era comparison would pool label eras: not
  reported. MDE at these block counts: not computable (after-side below floor).
- Structural point: `_nudge_stop` (`main.py:1630`) is applied to LIVE stop prices only; the
  candidate labeler's `sl_frac` comes from `barrier_geometry()` and is never nudged. A
  candidate-row before/after test cannot see cut #7 even with infinite data. Live rows:
  1 stop before the cut, 27 after — untestable.

## Live population (fills.csv, 30 measurable of 33)

| k | live real (n=30, 16 blocks, pooled across exec eras 7/8/9 — DESCRIPTIVE ONLY) | placebo A |
|---|---|---|
| 6 (30m) | .000 [0,0] | .012 [.002,.026] |
| 12 (1h) | .067 [0,.182] | .035 |
| 24 (2h) | .067 [0,.182] | .062 [.037,.092] |
| 48 (4h) | .167 [.032,.323] | .137 |
| 144 (12h) | .448 [.238,.640] | .231 [.169,.306] |
| 288 (24h) | .552 [.350,.731] | .321 [.250,.402] |

Era 7 alone (14 rows / 7 blocks): R6 .000, R24 .071 [0,.30], R48 .286 [.071,.616]; eras 8
(2 rows) and 9 (6 rows / 3 blocks) below the block floor. Triad: FLOW 0 fills ever (SZ-045
refuses it; measured on candidates above), ETH 1, BTC 1 — no live triad statement possible.
The 12–24 h live excess over placebo A is the same prior-move mean reversion seen on
candidates; the placebo-B arm was NOT run on live (n too small to matter) — do not read it
as a hunt.

## What this check could not see / did not run

- exit_sim `sl` rows: geometry never stamped → not measured (finding above).
- 238 candidate stops (4 %) whose stop the Kraken tape never crossed: excluded; the labeler
  feed is a different venue's bars. 172 rows outside tape coverage (signal after tape end).
- Reversal is measured to the ENTRY only; partial retracements and "did the herd's stops fire
  first" (the Osler mechanism) were not measured — that needs the live stop level vs the
  round level, not present in either CSV.
- Live placebo B, cut-#7 MDE, and per-exec-era live CIs: below the block floor, not run.
- Concurrency: 5,457 rows are 1,739 clusters; day-block CIs absorb this but the bar-route
  planted-MDE redraws per row inside a day — measured to understate the triad floors by
  1.5–2.5× (BTC .04 → .10, ETH .06 → .08); the corrected floors are in the REPAIR block.
- The bar-route R(k) tables are stop-bar-INCLUSIVE ([j, j+k]); a strict post-stop statistic
  is the tick route in the REPAIR block. The two agree everywhere except where R0 is a
  material share of R6 (BTC).
- Scripts are scratch, uncommitted: reproduction requires committing them (standard §7).

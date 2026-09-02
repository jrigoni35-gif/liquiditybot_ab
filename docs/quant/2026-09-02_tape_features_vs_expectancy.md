# Tape features against a continuous target (T3) — nothing survives

**Class: SAFE / measurement-plane.** Read-only. No repo code changed; scripts
lived in the session scratchpad. No order, gate, config, or model touched.

**REVISION 2 (2026-09-02T02:40Z).** Every number below was RE-DERIVED after
review found four defects in revision 1 — a measured bootstrap-coverage
result that the memo published as "not measured", a two-column join key that
mis-signed 1.4% of rows, a catastrophically unstable variance, and placebos
scored on different rows than the real run. §0 states each correction and
what it moved. The verdict is unchanged; two of the seven revision-1 flags
were artifacts and are gone, and the chance baseline the verdict is read
against is now measured rather than assumed.

**Question.** The 1-bit label showed tape trade-count intensity loads
RESOLUTION (0.616) not DIRECTION (0.510). Does a tape feature carry
information about the *continuous* outcome — magnitude / net expectancy —
that the 1-bit label cannot score?

**Answer: no.** 12 of 72 cells' 95% CIs exclude the null. The MEASURED chance
expectation on this corpus is **9.2** (not the nominal 3.6 — §1 "null
calibration"). The −24h placebo produced **12** and the +24h placebo **9**, on
the SAME 5,003 rows and the same 9 day blocks. The real run does not beat its
own placebos. One cell (`absimb_60`) is not reproduced by either placebo, and
it is an **unsigned** feature that cannot direct a trade.

---

## 0. Corrections to revision 1 (all four confirmed, all four repaired)

| # | Defect in revision 1 | Repair | What it moved |
|---|---|---|---|
| 1 | The memo said "bootstrap coverage at 9 blocks is assumed, not measured" — but a calibration had ALREADY been run (`t3_nullrate.log`, day-block exclusion 13/100) and was never carried in. The chance baseline quoted (3.6 = 0.05 × 72) was the NOMINAL one. | Re-measured on the exact scored rows at the exact reps, per statistic (`t3_nullrate.py`, rewritten). | Chance baseline **3.6 → 9.2**. The verdict survives (and the "real ≈ placebo" reading is what carries it), but the headline arithmetic was wrong by ~2.6×. |
| 2 | The join key was `(asset, signal_ts)`, which is NOT unique — long and short rows share a timestamp — and `drop_duplicates(keep="first")` then gave 69 of 5,054 rows (1.37%) the OPPOSITE side's sign on all 8 side-signed features. The cross-route instrument reported `csv_duplicate_keys: 69` in its own JSON and the memo never mentioned it. | Key is now `(asset, signal_ts, side)` in the feature CSV, the scorer, the tables and the positive control. Duplicate keys are counted and printed: **0** at the three-column key. | 3rd–4th decimal on `imb_signed_*` / `tapret_*`; no flag changed on this account alone. |
| 3 | `rv_W` used `E[x²] − E[x]²` on LOG PRICES (x² ≈ 21 against a target variance ≈ 1e-8; ~9 digits of cancellation, then clamped at 0). Two identical-in-exact-arithmetic summation orders agreed on `rv_60`'s rank ordering only to 0.973, and `rv_60` was a published flag. | `rv_W` is now a REALIZED volatility: the square root of the sum of squared CONSECUTIVE log returns inside the window. Every term is non-negative, so the window sum is a difference of increasing prefix sums and carries no cancellation. | **`rv_60`'s Spearman flag disappeared** (−0.0353 [−0.0624, −0.0139] → +0.0117 [−0.0523, +0.0590]). It was a numerical artifact. |
| 4 | The coverage mask was applied to the SHIFTED timestamp, so "same rows" (the memo's own §3 header) was false: real 5,054 rows / 9 days, −24h 5,100 / 10, +24h 4,514 / 8, with 533 real keys absent from +24h. | The mask is the INTERSECTION over all three shifts. | All three runs are now **5,003 rows / 9 days / identical keys**. |
| 5 | FLOW's signal-row count was given as "~481" — the only estimate in a table of exact counts, and wrong; the table's own column summed to 5,722 against a stated 5,541. | Re-derived exactly: FLOW = **300**. Column sums to the stated total. | Nothing else; the row was already excluded for having no tape. |

Two further facts changed under the repair for reasons that are NOT defects:
the corpus grew (the runner is live: 5,541 → **5,590** rows pass the filter),
and **FLOW and the rest of BTC now have tape** — the FLOW backfill landed at
02:32Z with 18,372 rows and BTC reached `t_max` 2026-09-02T01:59:31Z, so
FLOW (283 rows) and 269 BTC rows are scored here and were not in revision 1.

---

## 1. Method — exact filters, exact bounds

**Row universe.** `outputs/signal_history.csv`, read **2026-09-02T02:32:01Z**
by the feature builder (the runner is live and appending — every count is
as-of). Filter, verbatim:
`label_ret_pct.notna() AND label_era == "triple_barrier_h432"` → **5,590
rows**. The `exit_sim` era (n=13 at revision 1) is still excluded: single
barrier `realized`, cannot support a day-block CI.

`label_ret_pct` is in the **trade frame** (already side-signed).

**Tape.** `outputs/ticks/kraken/<PAIR>/<YYYY-MM>.parquet` via
`scripts.kraken_trades_backfill.TickStore(outputs/ticks).load(pair)`.
Coverage from `python scripts/kraken_trades_backfill.py --coverage --pairs …`
read **2026-09-02T02:32:09Z**, cross-checked against the loader's own read at
02:32:01Z:

| asset | pair | tape rows | t_max (UTC) | signal rows | kept (all 3 shifts) |
|---|---|---|---|---|---|
| ADA | ADAUSD | 556,533 | 2026-09-01T23:18:21Z | 73 | 73 |
| ARB | ARBUSD | 48,100 | 2026-09-02T00:12:47Z | 766 | 662 |
| BTC | XBTUSD | 2,930,099 | 2026-09-02T01:59:31Z | 286 | 269 |
| DOGE | XDGUSD | 290,840 | 2026-09-01T23:52:33Z | 522 | 487 |
| DOT | DOTUSD | 169,080 | 2026-09-02T00:12:47Z | 313 | 264 |
| ETH | ETHUSD | 1,207,483 | 2026-09-02T01:10:32Z | 561 | 508 |
| FLOW | FLOWUSD | **18,372 (new)** | 2026-09-02T01:44:39Z | **300** | 283 |
| LINK | LINKUSD | 278,754 | 2026-09-01T23:47:51Z | 304 | 257 |
| LTC | LTCUSD | 342,193 | 2026-09-02T00:19:07Z | 28 | 28 |
| MINA | MINAUSD | 34,166 | 2026-09-02T00:21:05Z | 650 | 579 |
| PAXG | PAXGUSD | 114,684 | 2026-09-02T00:20:19Z | 884 | 810 |
| SOL | SOLUSD | 1,023,613 | 2026-09-02T00:10:00Z | 196 | 175 |
| SUI | SUIUSD | 342,902 | 2026-09-01T23:24:03Z | 317 | 274 |
| XRP | XRPUSD | 1,158,461 | 2026-09-01T23:43:21Z | 390 | 334 |
| **total** | | | | **5,590** | **5,003** |

**Inclusion rule** (per row, applied ONCE and shared by every shift):
`signal_ts + s − 3600 ≥ t_min AND signal_ts + s + 3600 ≤ t_max` for that pair,
for **all** s ∈ {0, −86,400, +86,400}. Kept **5,003 / 5,590 = 89.5%**;
identical rows and identical 9 day blocks in all three runs. (At shift 0
alone 5,583 rows would qualify; the intersection is the price of a placebo
that is actually a control.) All 587 dropped rows are BTC/ARB/DOT/LINK/etc.
rows whose ±24h window runs past their pair's `t_max`.

**Features** (6 × 4 windows W ∈ {60, 300, 900, 3600} s, cumulative sums +
`searchsorted` on the time-sorted tape; window is `(signal_ts − W,
signal_ts]`): `imb_signed_W = log((buy_vol+1)/(sell_vol+1)) × side_sign` ·
`logn_W = log1p(trade count)` · `mktshare_W = market-order count / count` ·
`absimb_W = |buy_vol − sell_vol| / (buy_vol + sell_vol)` (**unsigned**) ·
**`rv_W` = √Σ (Δ log price)² over consecutive trades in the window (realized
vol — see correction 3; revision 1's `E[x²]−E[x]²` form was not
reproducible)** · `tapret_W = (log p_last − log p_first) × side_sign`.

**Targets.** (T-a) Spearman(feature, `label_ret_pct`), pandas `rank().corr()`,
no scipy. (T-b) among **resolved** rows (`barrier ∈ {tb_pt, tb_sl}`, n=3,632)
rank-AUC of the feature against `sign(label_ret_pct) > 0`. (T-c) cost
clearance `P(label_ret_pct > 0.6)` in the top vs bottom quintile.
**0.6 is `config.json` `ml.label_round_trip_cost_pct`** [K] — the cut-#9 label
round-trip cost. Pooled base rates on the joined rows:
`P(ret > 0.6) = 0.3826`, `P(ret > 0) = 0.4225`.

**CIs.** Day-block bootstrap, 400 reps, seed 20260902: calendar UTC days
resampled with replacement, statistic recomputed inside each resample.
**The corpus spans 9 distinct UTC days** — that is the effective sample size
for every CI here, not 5,003.

**NULL CALIBRATION (measured, not assumed — correction 1).** A random N(0,1)
feature scored against the REAL target on the REAL day blocks of these exact
5,003 rows, 100 draws × 400 reps, seed 99, read 2026-09-02T02:36:42Z and
02:38:15Z:

| statistic | realized 95%-CI exclusion rate | nominal | expected flags |
|---|---|---|---|
| Spearman, day blocks | **9/100 = 0.090** | 0.05 | 2.2 of 24 |
| direction AUC, day blocks (resolved rows) | **14/100 = 0.140** | 0.05 | 3.4 of 24 |
| quintile ΔP, day blocks | **15/100 = 0.150** | 0.05 | 3.6 of 24 |
| Spearman, HOUR blocks (comparison) | 7/100 = 0.070 | 0.05 | — |
| **all three targets** | | | **9.2 of 72** |

A 9-block percentile bootstrap is anti-conservative by 1.8–3.0× depending on
the statistic; the quintile difference is the worst. At K=100 draws each rate
carries a binomial SE of ~0.03, so "9.2" is ±~2 flags. An earlier calibration
on a slightly different row set (source=='candidate', BTC/FLOW dropped,
n=4,924, B=1,000, read 2026-09-02T01:33Z) gave 13/100 for Spearman — same
conclusion, both far above nominal.

**Effective n.** Hour-clustered Kish on the joined rows: k=184 hour clusters,
mean 27.19 rows per cluster, one-way ICC ρ=0.1059, **deff = 3.774, n_eff ≈
1,326** against a nominal n of 5,003. The block bootstrap already carries
this; a naïve nominal-n SE would be optimistic by √3.774 ≈ 1.94×.

---

## 2. Full table (real, shift 0) — 5,003 rows, 9 day blocks

`n` = finite feature rows; `n_res` = resolved subset (3,632 max). Bold = CI
excludes the null.

| feature | n | Spearman [95% day-block] | dir AUC [95%] | ΔP(ret>0.6) Q5−Q1 [95%] |
|---|---|---|---|---|
| imb_signed_60 | 3097 | −0.0243 [−0.0857, +0.0195] | 0.4909 [0.4614, 0.5155] | −0.0048 [−0.1152, +0.0139] |
| logn_60 | 3097 | −0.0649 [−0.1457, +0.0104] | 0.4441 [0.3886, 0.5003] | −0.0946 [−0.2212, +0.0227] |
| mktshare_60 | 3097 | +0.0177 [−0.0517, +0.0945] | 0.5115 [0.4587, 0.5669] | +0.0510 [−0.0474, +0.1724] |
| **absimb_60** | 3097 | **+0.0398 [+0.0079, +0.0630]** | **0.5305 [0.5114, 0.5468]** | +0.0205 [−0.0440, +0.0690] |
| **rv_60** | 2477 | +0.0117 [−0.0523, +0.0590] | 0.5283 [0.4970, 0.5634] | **+0.1331 [+0.0241, +0.2341]** |
| tapret_60 | 3097 | +0.0161 [−0.0098, +0.0418] | 0.5036 [0.4763, 0.5369] | +0.0065 [−0.0643, +0.0614] |
| **imb_signed_300** | 4294 | −0.0139 [−0.0699, +0.0240] | 0.4887 [0.4667, 0.5083] | **−0.0373 [−0.0742, −0.0043]** |
| logn_300 | 4294 | −0.0305 [−0.1244, +0.0661] | 0.4542 [0.4033, 0.5234] | −0.0595 [−0.1904, +0.0843] |
| mktshare_300 | 4294 | +0.0335 [−0.0130, +0.0658] | 0.5134 [0.4773, 0.5457] | +0.0601 [−0.0008, +0.1332] |
| absimb_300 | 4294 | −0.0086 [−0.0423, +0.0362] | 0.5023 [0.4908, 0.5148] | +0.0228 [−0.0282, +0.0798] |
| **rv_300** | 3909 | +0.0207 [−0.0531, +0.0831] | 0.5372 [0.4997, 0.5821] | **+0.1573 [+0.0314, +0.2654]** |
| tapret_300 | 4294 | −0.0133 [−0.0437, +0.0207] | 0.4853 [0.4679, 0.5095] | −0.0326 [−0.0681, +0.0129] |
| imb_signed_900 | 4813 | −0.0190 [−0.0634, +0.0195] | 0.4902 [0.4727, 0.5084] | −0.0291 [−0.0594, +0.0065] |
| logn_900 | 4813 | +0.0171 [−0.0716, +0.1188] | 0.4724 [0.4165, 0.5292] | −0.0355 [−0.1592, +0.0889] |
| **mktshare_900** | 4813 | **+0.0703 [+0.0229, +0.1104]** | 0.5283 [0.4978, 0.5536] | **+0.0645 [+0.0143, +0.1094]** |
| absimb_900 | 4813 | −0.0278 [−0.0785, +0.0275] | 0.4961 [0.4632, 0.5275] | −0.0073 [−0.0850, +0.0584] |
| **rv_900** | 4630 | +0.0235 [−0.0711, +0.1078] | **0.5489 [0.5024, 0.6055]** | **+0.2214 [+0.0747, +0.3352]** |
| **tapret_900** | 4813 | −0.0220 [−0.0510, +0.0064] | 0.4775 [0.4542, 0.5029] | **−0.0644 [−0.1075, −0.0173]** |
| imb_signed_3600 | 5002 | −0.0025 [−0.0765, +0.0781] | 0.4919 [0.4724, 0.5202] | −0.0090 [−0.0570, +0.0562] |
| logn_3600 | 5002 | +0.0312 [−0.0480, +0.1284] | 0.4766 [0.4194, 0.5446] | −0.0029 [−0.1272, +0.1045] |
| **mktshare_3600** | 5002 | **+0.0716 [+0.0291, +0.1213]** | 0.5217 [0.4883, 0.5521] | +0.0390 [−0.0101, +0.0869] |
| absimb_3600 | 5002 | −0.0148 [−0.0601, +0.0214] | 0.4968 [0.4771, 0.5129] | −0.0539 [−0.1225, +0.0230] |
| **rv_3600** | 4986 | +0.0043 [−0.1286, +0.1123] | 0.5465 [0.4936, 0.5955] | **+0.2004 [+0.0546, +0.3405]** |
| tapret_3600 | 5002 | −0.0482 [−0.1091, +0.0170] | 0.4659 [0.4188, 0.5236] | −0.0949 [−0.2265, +0.0311] |

**Real: 12 of 72 cells exclude the null** (Spearman 3, dir-AUC 2,
cost-quintile 7) against a MEASURED chance expectation of 9.2.

Every Spearman |ρ| in the table is below 0.075. At n_eff ≈ 1,326 an ρ of 0.07
explains 0.5% of rank variance — even at face value none of these is a
tradable magnitude signal.

## 3. Placebo table (feature recomputed at `signal_ts ± 86,400 s`, SAME rows, SAME target, SAME days)

| run | rows | days | cells excluding null (of 72) | features flagged |
|---|---|---|---|---|
| **real (shift 0)** | 5,003 | 9 | **12** | absimb_60 (SP,AUC) · rv_60 (Q) · imb_signed_300 (Q) · rv_300 (Q) · mktshare_900 (SP,Q) · rv_900 (AUC,Q) · tapret_900 (Q) · mktshare_3600 (SP) · rv_3600 (Q) |
| placebo −86,400 s | 5,003 | 9 | **12** | imb_signed_60 (SP,AUC) · rv_300 (Q) · tapret_300 (SP,AUC) · rv_900 (Q) · tapret_900 (SP,AUC,Q) · mktshare_3600 (SP) · rv_3600 (Q) · tapret_3600 (SP) |
| placebo +86,400 s | 5,003 | 9 | **9** | rv_60 (SP,AUC,Q) · absimb_300 (Q) · rv_300 (AUC,Q) · rv_900 (AUC,Q) · rv_3600 (Q) |
| **measured chance** | — | — | **9.2** | (2.2 SP + 3.4 AUC + 3.6 Q; §1) |

Per-cell placebo on every real flag:

| feature/target | real | placebo −24h | placebo +24h | verdict |
|---|---|---|---|---|
| absimb_60 Spearman | **+0.0398 [+0.0079, +0.0630]** | +0.0203 [−0.0592, +0.0858] | +0.0222 [−0.0246, +0.0667] | not reproduced |
| absimb_60 dir AUC | **0.5305 [0.5114, 0.5468]** | 0.5201 [0.4779, 0.5687] | 0.5179 [0.4877, 0.5500] | not reproduced (same sign, wider) |
| mktshare_900 Spearman | **+0.0703 [+0.0229, +0.1104]** | +0.0220 [−0.0122, +0.0625] | +0.0331 [−0.0246, +0.1062] | placebos same sign, ~⅓–½ size |
| mktshare_3600 Spearman | **+0.0716 [+0.0291, +0.1213]** | **+0.0539 [+0.0086, +0.1015]** | +0.0524 [−0.0140, +0.1373] | **reproduced at −24h** |
| rv_60 Q5−Q1 | **+0.1331 [+0.0241, +0.2341]** | +0.1239 [−0.0147, +0.2149] | **+0.1857 [+0.0900, +0.2947]** | **reproduced LARGER at +24h** |
| rv_300 Q5−Q1 | **+0.1573 [+0.0314, +0.2654]** | **+0.1530 [+0.0142, +0.2857]** | **+0.2252 [+0.0694, +0.3825]** | **reproduced by BOTH** |
| rv_900 Q5−Q1 | **+0.2214 [+0.0747, +0.3352]** | **+0.1469 [+0.0218, +0.3140]** | **+0.2538 [+0.0946, +0.4276]** | **reproduced by BOTH** |
| rv_900 dir AUC | **0.5489 [0.5024, 0.6055]** | 0.5519 [0.4999, 0.6166] | **0.5895 [0.5256, 0.6660]** | **reproduced LARGER at +24h** |
| rv_3600 Q5−Q1 | **+0.2004 [+0.0546, +0.3405]** | **+0.1891 [+0.0245, +0.3443]** | **+0.2405 [+0.0783, +0.4010]** | **reproduced by BOTH** |
| mktshare_900 Q5−Q1 | **+0.0645 [+0.0143, +0.1094]** | +0.0189 [−0.0419, +0.1010] | +0.0416 [−0.0600, +0.1494] | not reproduced, but |ρ| tiny |
| imb_signed_300 Q5−Q1 | **−0.0373 [−0.0742, −0.0043]** | −0.0187 [−0.0807, +0.0440] | +0.0242 [−0.0386, +0.0612] | sign flips |
| tapret_900 Q5−Q1 | **−0.0644 [−0.1075, −0.0173]** | **−0.0622 [−0.1023, −0.0171]** | −0.0072 [−0.0531, +0.0352] | **reproduced at −24h** |

The whole `rv_*` cost-clearance column is reproduced by the placebos at equal
or larger size — volatility a day before or a day after the trade separates
the outcome quintiles as well as volatility at the trade. That is a
multi-day regime co-movement, not timing information, and it is the clearest
single result in the exercise.

## 4. The one cell the placebo does not kill — and why it is still not a finding

`absimb_60` is the only real flag that clears both the direction check
(AUC CI excludes 0.5) and both placebos. It still fails on grounds that have
nothing to do with the CI:

1. **The feature is unsigned.** `absimb = |buy−sell|/(buy+sell)` has no side
   dependence. It cannot express "go long" or "go short"; at most it says
   "trades taken while the tape is one-sided resolve better *whichever way we
   went*". A position-quality filter at best, not direction.
2. **It is 1 of 24 features on one of three targets**, and the MEASURED
   direction-AUC null rate is 14% — 3.4 exclusions expected among 24 by
   chance. Observing this one is the null.
3. **It does not hold across pairs.** Direction AUC per asset (resolved,
   n≥100): ETH 0.5566, DOT 0.5358, MINA 0.5431, LINK 0.5240, SUI 0.5105,
   SOL 0.4841, DOGE 0.4898, BTC 0.4523, XRP 0.4534, **ARB 0.3934** — 5 of 10
   above 0.5, one strongly inverted, and the pooled number is carried by ETH.
   The per-asset Spearman is the same story (ARB −0.324, MINA +0.141).
4. **Its cost-clearance cell is null** (+0.0205 [−0.0440, +0.0690]).
5. **9 day blocks**, whose realized coverage is now measured (§1) and is
   1.8–3.0× anti-conservative.

Corroborating the barrier-geometry rule rather than defeating it: the
RESOLUTION channel is where the large numbers still are. On the PRODUCTION
corpus (different loader, different rows: 12,171 tb rows / 25 days, read
2026-09-02T02:27:23Z, `scripts/label_decomposition_report.py --json`), the
loudest features are resolution loaders with DIRECTION sitting on 0.5 —
`sigma_bar_pct` RES 0.7495 [0.6378, 0.8785] with DIR 0.5182 [0.4757, 0.5660],
`spread_bps` RES 0.6617 [0.6287, 0.7025] / DIR 0.5040, `th_grid` RES 0.6035 /
DIR 0.5126, `manip_suspect` RES 0.5959 / DIR 0.4854 — all four now flagged
RESOLUTION-ONLY (that instrument's flag rule was repaired the same session:
it used to file them NULL). The continuous target does not change that.
NOTE: the `--extra-csv` cross-route was NOT re-run on the repaired feature
CSV, because that instrument's join key is `(asset, signal_ts)` and cannot
carry `side` — the same non-unique-key defect as correction 2, at the other
end of the join. Its revision-1 numbers are therefore withdrawn from this
memo rather than restated.

---

## 5. Interpretation (one paragraph, confined to what survived)

**Nothing survives.** Seventy-two cells were scored; twelve excluded the
null against a *measured* chance expectation of 9.2 on this corpus's block
structure — not the nominal 3.6, which revision 1 quoted and which is wrong
by a factor of 2.6 at nine day blocks. The two placebos, now computed on the
identical 5,003 rows and the identical nine day blocks, produced twelve and
nine. A real run that flags exactly as many cells as its own −24h placebo has
established that the flag count is noise, not that the tape is silent; those
are different claims and only the first is established here. The cells with
the largest point estimates — the entire `rv_*` cost-clearance column — are
the ones the placebos *reproduce*, at equal or larger size, which identifies
them as slow-moving regime co-movement: the feature and the outcome share a
multi-day market state, so shifting the feature a day does not break the
association. The single cell the placebos do not reproduce, `absimb_60`'s
direction AUC of 0.531, is unsigned and therefore cannot direct a trade, is
one flag where 3.4 are expected by chance on that channel alone, and reverses
on ARB, XRP and BTC. Revision 1's `rv_60` Spearman flag was a numerical
artifact of an unstable variance and is gone. The answer to the question
asked — does a tape feature carry expectancy information the 1-bit label
cannot score — is **no, not in this corpus**, and the corpus is the binding
constraint: 5,003 rows over **9 UTC days** with n_eff ≈ 1,326 after a Kish
deff of 3.77. The market is allowed to be boring, and on this evidence it is.

---

## 6. What this could not see

- **9 day blocks.** Coverage at that block count is now MEASURED (§1) and is
  anti-conservative by 1.8–3.0× per statistic; the correction is applied to
  the baseline, not to the intervals themselves, which are still 9-block
  percentile intervals. A wider corpus could both create and destroy flags.
- **Coverage moves under the instrument.** FLOW and most of BTC were absent
  when revision 1 ran and are present now; ±24h coverage still costs 587 of
  5,590 rows, concentrated at the right edge of each pair's tape. Any re-run
  scores a different row set — quote the stamp, never "current".
- **Executed trades only.** The Kraken trades tape carries fills, not quotes
  or cancellations. Every feature here is blind to resting/pulled liquidity.
- **`label_ret_pct` is the barrier outcome**, not realized P&L, and it is
  gross of the fee stack; the cost-clearance target uses the *label's* 0.6%
  round trip (`ml.label_round_trip_cost_pct`), not booked fees.
- **The `exit_sim` era was excluded**, so nothing here speaks to it.
- **No search was run** over feature transforms, interactions, or other
  windows. This was a pre-specified 6 × 4 × 3 grid, scored once (twice, after
  the repair). It is not a claim that no tape feature exists — it is a null
  on this grid.
- **The direction-AUC and quintile channels' null rates were measured with
  100 draws each** (binomial SE ≈ 0.03); the baseline 9.2 is ±~2 flags.

## 7. Positive control — the scan is not broken

Re-run through the repaired scorer (read 2026-09-02T02:34:43Z). A
dose-response signal was planted into the target:
`y = label_ret_pct + k · z · sd(label_ret_pct)` where `z` is the centred
percentile rank of `mktshare_3600`, scored by the **same** functions that
produced §2 (imported, not reimplemented), same 400-rep day-block bootstrap,
same seed:

| dose k | Spearman | dir AUC | ΔP(ret>0.6) Q5−Q1 |
|---|---|---|---|
| 0.00 (unplanted) | +0.072 \* | +0.522 | +0.039 |
| 0.25 | +0.250 \* | +0.522 | +0.079 \* |
| 0.50 | +0.352 \* | +0.522 | +0.127 \* |
| 1.00 | +0.509 \* | +0.545 \* | +0.454 \* |
| 2.00 | +0.773 \* | +0.855 \* | +0.862 \* |

\* = 95% day-block CI excludes the null. All three targets rise monotonically
with dose and cross into significance; the direction-AUC channel is the
coarsest (it only reads `sign(y)`, so small doses do not move it) and fires
at k=1.0. **The established observation is "the effects are absent", not
"the scan is dead".** The k=0.00 row reproduces the real `mktshare_3600`
Spearman flag from §2 — one of the twelve.

**Provenance.** All numbers re-derived 2026-09-02 from
`outputs/signal_history.csv` (feature build read 02:32:01Z; scoring reads
02:32:27Z / 02:32:39Z / 02:32:51Z; null calibration reads 02:36:42Z and
02:38:15Z; positive control 02:34:43Z), `outputs/ticks/kraken/**` (coverage
02:32:09Z) and `config.json` `ml.label_round_trip_cost_pct`. Scratch scripts
(not in the repo, session scratchpad): `t3_features.py`, `t3_score.py`,
`t3_tables.py`, `t3_nullrate.py`, `t3_planted.py`, `t3_absimb.py`;
revision-1 copies kept beside them as `*.py.bak`.

---

## ADDENDUM (2026-09-02T10:37Z) - RE-RUN ON COMPLETE COVERAGE, THROUGH THE SHIPPED INSTRUMENT

This memo's own caveat said to re-run once the BTC backfill finished. It has, and
FLOW is no longer absent, so the re-run was done properly: features rebuilt on the
full tape and scored through the COMMITTED, mutation-verified
`scripts/label_decomposition_report.py --extra-csv` rather than through scratch
scoring code.

**What changed.** Coverage 5,054 -> 22,159 signal rows built (99.4% of all signals);
join rate into the production corpus 41.5% -> **98.9%** (12,286 of 12,422 rows
matched, 0 duplicate CSV keys). All 15 assets now have tape reaching ~2026-09-02T02Z.
Twenty tape features (signed imbalance, |imbalance|, log trade count, market-order
share, tape return - each at 60/300/900/3600 s) were scored beside the 64 stored
features on the same rows: 84 features, 12,422 rows, 25 day blocks.

**Result: NOT ONE of the 20 tape features is DIRECTIONAL.** Every one is NULL or
RESOLUTION-ONLY. The single cell this memo kept - `absimb_60`, direction AUC 0.5308
on the partial-coverage sample - reads **0.505 [0.486, 0.525]** on full coverage,
a CI comfortably spanning 0.5. It does not survive.

**And the chance baseline is now measured rather than assumed.** `--null-calibration
200` (200 pure N(0,1) features against the real targets, rows and day blocks) gives a
realized DIRECTION exclusion rate of **12.5%**, so at 84 features chance alone yields
**10.5** directional flags. The run produced **6**. The count of "significant"
features is BELOW what pure noise produces on this corpus. The nominal 5% figure this
memo and its predecessors quoted was never the right comparator.

**The resolution channel is confirmed for tape features too**, which is the finding:
`tape_absimb_300` RESOLUTION 0.619 [0.578, 0.667] against DIRECTION 0.509;
`tape_absimb_60` 0.602 against 0.505. They sit beside the stored loaders
`sigma_bar_pct` 0.751 and `spread_bps` 0.662. Activity, spread and volatility all
predict whether a path reaches a barrier; nothing predicts which one.

**Status of this memo: its verdict stands and is now much better supported.** The
earlier "nothing survives" rested on a 9-day-block sample with a placebo comparison
across three different row sets. This rests on 25 day blocks, 99% coverage, a
measured null baseline, and an instrument with 17 pins and nine mutation-verified
defects. The owed re-run is DONE; do not re-run again on coverage grounds.

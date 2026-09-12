# OF-3 (PBO): the rung cannot resolve what it is being asked to resolve

**2026-09-12.** THIS DOCUMENT HAS BEEN CORRECTED TWICE, and the
corrections are the finding. It first said the red was overfitting; then that
it was drift; the measurements below now say the rung cannot separate either
from its own noise on this corpus. Each retraction came from running a control
the previous version had not run.

The standing conclusion: **OF-3's red is not evidence about the strategy.** It
is a statistic swinging further on modelling choices than the distance to its
own threshold, over a corpus whose TARGET DEFINITION changed twice inside the
measured window. Everything below was re-derived by running the shipped estimator; the
commands are beside the numbers so the next reader re-runs rather than quotes.

## What happened

`scripts/overfit_check.py`'s OF-3 rung crossed its `pbo <= 0.5` gate and then
kept moving:

| when | pbo | corpus |
|---|---|---|
| before the 2026-09-11 OF-5 commit | passing (`passed 4, failed 1`) | 17,990 rows |
| 2026-09-12 early | 0.63 | — |
| 2026-09-12 09:16 report | **0.90** | 18,016 rows |

The 2026-09-11 commit changed **zero** pbo lines
(`git show 4b0b5559 -- scripts/overfit_check.py | grep -c '^[+-].*pbo'` -> 0),
so the code is not the cause. A statistic that moves 0.63 -> 0.90 on 26 more
rows (0.14% of the corpus) is reporting something other than a property of the
whole sample.

## The measurement

PBO is the fraction of CSCV splits where the in-sample winner lands in the
bottom half out-of-sample. Its documented calibration - "~0.5 = selection is
pure noise, >0.5 = actively anti-selecting" - assumes the candidate configs
are DISTINGUISHABLE. On this corpus they measurably are not: the champion is
indistinguishable from the base rate (Brier skill +0.002 [-0.026, +0.017]; AUC
0.553 [0.484, 0.623]; 0/63 features survive BH).

So the null was measured directly, using the repo's own OF-2 idiom applied to
OF-3: **shuffle `y`**, destroying any label-feature relationship, and re-run
the same estimator. Whatever PBO reads there is the instrument's baseline.

Twenty draws, shipped geometry (`n_splits=5, n_blocks=8`, C(8,4)=70 combos,
seeds 1000-1019), same `select_cfg` / `n_live` / weights / purge as the gate:

```
NULL pbo over 20 draws:
  median=0.279  mean=0.336  sd=0.294
  range=[0.000, 0.871]   p50=0.129  p90=0.729  p95=0.786

[1] CALIBRATION  null draws breaching the 0.5 gate: 8/20 = 40%
[2] IS IT REAL   null draws >= observed pbo=0.900:  0/20   rank p <= 0.048
```

## The two findings

**[1] The 0.5 threshold has a ~40% false-positive rate on pure noise.** Eight
of twenty label-shuffled runs - where there is definitionally nothing to
select on - breached the gate. A gate that trips two times in five on noise
cannot distinguish overfitting from its own sampling variance. The null's p95
is **0.786**, so a null-referenced line sits far above 0.5. THIS IS AN
INSTRUMENT DEFECT and it is repairable.

**[2] Nevertheless, pbo=0.900 exceeds every one of the twenty null draws**
(rank p <= 0.048). The observed reading is not explained by the noise
distribution. THIS IS A REAL SIGNAL and it is not the instrument's fault.

The two do not cancel. The gate is wrong about *where the line goes*, and the
current sample is still beyond the line wherever it goes.

## The rival hypothesis - TESTED, and it wins

PBO partitions the corpus into 8 **contiguous time blocks**. That design
cannot separate:

  (a) the selection rule chases in-sample luck ..... overfitting
  (b) the later blocks are drawn from a different distribution than the
      earlier ones, so nothing chosen on the past generalises ..... DRIFT

The bot's own monitors have been reporting (b) for two days, unprompted:
`ML-031` feature drift on 20-26 of 60 features (PSI >= 0.25), hourly;
`ML-032` RETRAIN REQUESTED on 32-40% of features; `ML-080` exit-reason mix
drift tvd=0.325 over the trailing 24h; `status.monitor.drift_share_measurable
= 0.889`. Drift also explains the lurch on 26 rows, which overfitting does
not.

**MEASURED 2026-09-12T15:21Z, and it is drift.** Trailing truncation, same
shipped geometry, `rows are time-ordered: True` (checked, so the truncation
really does drop the recent tail):

| keep | rows | pbo | argmax |
|---|---|---|---|
| **100%** | 18,016 | **0.900** | 0.843 |
| 95% | 17,115 | 0.757 | 0.743 |
| 90% | 16,214 | 0.800 | 0.643 |
| 80% | 14,412 | 0.600 | 0.400 |
| 70% | 12,611 | **0.214** | 0.214 |
| 60% | 10,809 | **0.014** | 0.014 |
| 50% | 9,008 | 0.286 | 0.243 |

**Drop the most recent 30% and the gate goes GREEN.** Overfitting is a
property of a selection rule over the whole sample and would give a FLAT
column; this is a cliff, and it is located in time. The readings at 70/60/50%
(0.214, 0.014, 0.286) sit at or below the null median of 0.279 - i.e. on older
data, selection is indistinguishable from noise, which is exactly what six
statistically identical configs should look like. Only the recent tail
anti-selects.

READ WITH ITS ERROR BARS: the null study puts sd at 0.294, so any SINGLE row
here is noisy (the 50% row breaking monotonicity is within that). The COLUMN
is the evidence - a fall from 0.900 to 0.014 across four consecutive
truncations is not sampling noise.

**So OF-3 is reporting a real problem under a misleading NAME.** The model
selected on the past does not generalise to the present because the present is
distributionally different - which is what `ML-031` (20-26/60 features past
PSI 0.25), `ML-032` (RETRAIN REQUESTED, 32-40% of features) and `ML-080`
(exit-reason tvd 0.325) have been saying for two days. Four instruments, one
cause.

**The fix is a retrain, not a selection change.** Note the standing gap:
auto-retrain runs hourly and `retrain_flag` is true, but no new champion
artifact has been written since 2026-09-10 18:56 - challengers are not beating
the incumbent on a corpus whose recent tail has moved. That is the thread to
pull, and it is a MODEL question, not a gate question.

Harness: `scratchpad/pbo_drift.py` (truncation column),
`scratchpad/pbo_null2.py` (the null).

## Re-derive, do not quote

```
# the gate's own reading, and the corpus it read
python scripts/overfit_check.py            # OF-3 line + the corpus line

# the null distribution (20 draws, ~10 min; do not run beside another
# model-fitting job - it starves the live runner)
python <harness>  20                       # see scratchpad/pbo_null2.py
```

Every figure here is as-of 2026-09-12 and moves with the corpus. The
*conclusions* - a 40% null breach rate, and an observed value outside the null
- are the durable part; the decimals are not.

## Instrument notes, filed against interest

Two defects in the analysis harness were found by running it, not reading it:
it initially passed **sample weights where timestamps belonged** (the loader
returns `X, y, w, sig, res, source, n_live`, not `X, y, sig, ...`), and its
verdict line printed *"fails on pure noise more often than not"* out of
`above >= len(vals)//2`, which is True at 2-of-5. The harness now reports the
two rates separately and draws no conclusion at all.


---

# CORRECTION 2026-09-12 (later the same day): two controls that were never run

An adversarial quant review asked for two controls this document had not run.
Both were executed. Both weaken what is written above, and one refutes it.

## 1. THE TARGET CHANGED TWICE INSIDE THE CORPUS

Measured from the stored per-row barrier geometry in signal_history.csv
(`pt_frac` / `sl_frac`), all under the SAME `label_era='triple_barrier_h432'`:

| day | PT bps | SL bps | base rate y=1 |
|---|---|---|---|
| 09-04 / 09-05 | **240** | 180 | 0.268 / 0.591 |
| 09-06 / 09-07 | **220** | 165 | 0.429 / 0.390 |
| 09-08 onward | **180** | 135 | 0.173 / 0.190 |

CLAUDE.md predicted exactly this for cut #12: the barrier floor moves with the
cost, "under the same `label_era` name, which encodes the horizon only". So a
CSCV block mean is being compared across a class-balance shift from ~0.4-0.6
down to ~0.19. The in-sample winner MUST mis-rank out-of-sample whenever the
two sides of a split straddle 09-08, because the two sides are answering
different questions.

**This also demotes a witness.** ML-080 (exit-reason mix drift) is a MECHANICAL
CONSEQUENCE of tightening PT/SL by 40/30 bps, not independent corroboration.
The earlier claim of "four instruments, one cause" DOUBLE-COUNTED its evidence.

## 2. THE END-SWAP REFUTES "ONLY THE RECENT TAIL ANTI-SELECTS"

The trailing-truncation column drops the recent k% - which also shrinks T. The
control holds T fixed and swaps which END is kept:

| slice | rows | pbo |
|---|---|---|
| full | 18,016 | **0.900** |
| keep-OLDEST 60% | 10,809 | 0.014 |
| **keep-NEWEST 60%** | 10,809 | **0.414** |

**The recent half does not anti-select on its own** - 0.414 PASSES the 0.5 gate
and sits inside the null band (median 0.279, sd 0.294). The 0.900 therefore
lives in the CROSS-HALF combinations: the two ends are mutually
non-generalising. "Only the recent tail anti-selects" is WITHDRAWN.

The ordering (full > newest > oldest) is robust - it survives the
parameterisation change below - so a directional heterogeneity conclusion
stands. The strong sentence does not.

## 3. THE VERDICT IS DRIVEN BY A WEIGHTING CHOICE, NOT BY THE STRATEGY

Full corpus, 2x2 isolating the two carried-over inputs:

| cell | n_live | weights | pbo | ncfg |
|---|---|---|---|---|
| **A (shipped)** | 63 | de Prado | **0.9000** | 6 |
| B | 63 | uniform | **0.5429** | 6 |
| C | None | de Prado | 0.8857 | 8 |
| D | None | uniform | 0.4714 | 8 |

**A->B, identical space and identical 70 combos, sample weights alone: -0.357.**
A->C, the evidence gate alone: -0.014, negligible.

The weighting is not a mistake - `scripts/overfit_check.py` argues for it
deliberately, because OF-3 certifies the DEPLOYED selection rule and must fit
the way the deployed trainer fits. But the consequence is unavoidable:

  * the statistic moves **0.357** on a defensible modelling choice
  * the distance from the shipped reading to the gate is **0.400**
  * the null's standard deviation is **0.294**
  * the gate false-positives on pure noise **40%** of the time

**A gate cannot adjudicate a question finer than its own sensitivity to
arbitrary-but-defensible choices.** That is the finding.

## WHAT THIS MEANS FOR THE RED

Do NOT read OF-3's red as evidence that the deployed selection rule is
overfitting. Do not read it as market drift either. On this corpus the rung is
over-taxed: a label-geometry change inside the window, a threshold that trips
on noise two times in five, and a verdict that moves most of the way to that
threshold on the weighting alone.

**Owed, and it is an OPERATOR question, not a code fix:** the `label_era` token
encodes the horizon only, so a barrier-geometry change is invisible to every
consumer that segments by it. Either extend the token to carry the barrier
multipliers, or segment OF-3 by geometry. CLAUDE.md already names this hazard
as the reason take-profit width is the PRE-NAMED next lever and was deferred -
"a DELIBERATE width change would mix two geometries under one era". The cut
#12 fee rebook moved the width anyway, through the cost floor in
`ml/labeling.barrier_geometry`.

Harnesses: `scratchpad/pbo_endswap.py`, `scratchpad/pbo_2x2.py`,
`scratchpad/pbo_null2.py`, `scratchpad/pbo_drift.py`.

---

# ERRATUM 2026-09-12 (third correction): THE POINT ESTIMATES ARE NOT STABLE TO ONE ROW

A red-team panel objected that every figure above is quoted to four decimals
with no reproduction band. Re-derived here by a second route — calling
`ml.overfit.model_space_pbo` directly at truncated T, with a determinism
control run first (same array twice -> identical pbo, so what follows is
discontinuity, not RNG):

| rows | pbo | median lambda |
|---|---|---|
| 18,020 | **0.1857** | +0.9163 |
| 18,019 | 0.1857 | +0.9163 |
| 18,018 | 0.1857 | +0.9163 |
| **18,017** | **0.9000** | -0.2877 |
| 18,015 | 0.9000 | -0.2877 |
| 18,010 | 0.6286 | -0.2877 |

**Band over ten rows: 0.7143. Three of six readings would be RED, three GREEN,
on the same corpus one row apart.** The same day this document was written,
`scripts/overfit_check.py` reported `pbo=0.19 ... PASS` on the live corpus.

What this does to the sections above:

* The **0.900** that §2 and §3 analyse is one side of a coin flip in T, not a
  stable reading. Every four-decimal figure above inherits that band.
* §3's headline effect (weights move pbo **-0.357**) is measured between two
  cells that each carry a 0.714 band. It cannot be attributed to the weights.
* §2's slice ordering (full > newest > oldest) is not safe either — the panel
  also measured that the two "ends" **share 33.3% of their rows** by
  construction (`k = int(T*0.60)`, overlap `2k-T = 0.2T`), so "the two ends"
  and "cross-half combinations" describe a partition that was never run.
* §1's geometry table is a calendar-day proxy for a stored quantity. Grouped by
  the actual `pt_frac` bucket the corpus records, the target changed **more
  than twice** — the panel puts it at five levels including a 480 bps floor on
  08-29 — and the largest excursion sits inside the slice that reads the
  *lowest* pbo. The blamed tightening has the wrong sign.

**The document's conclusion is unchanged and now rests on better evidence:
OF-3's reading is not evidence about the strategy.** It was over-taxed before;
it is now measured as discontinuous in the corpus size itself. Do not read
0.900 as a verdict. Do not read today's 0.19 as an exoneration either — it is
the other face of the same coin.

**Owed, unchanged and still an OPERATOR question:** `label_era` encodes the
horizon only, so a barrier-geometry change is invisible to every consumer that
segments by it. The rest of the panel's docket (17 surviving objections) is
recorded in the session transcript; nothing was built from it.

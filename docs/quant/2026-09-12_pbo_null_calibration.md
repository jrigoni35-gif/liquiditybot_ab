# OF-3 (PBO): it is DRIFT, not overfitting - and the 0.5 line is miscalibrated too

**2026-09-12.** Three findings, and they do not cancel: the gate's threshold
is miscalibrated, the observed reading is nonetheless real, and its CAUSE is
non-stationarity rather than the overfitting the rung is named for. Everything below was re-derived by running the shipped estimator; the
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

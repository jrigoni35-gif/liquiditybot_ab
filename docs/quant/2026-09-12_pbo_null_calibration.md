# OF-3 (PBO): the gate's 0.5 line is miscalibrated, AND the reading is elevated

**2026-09-12.** Both statements are true at once and they have different
owners. Everything below was re-derived by running the shipped estimator; the
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

## The rival hypothesis, NOT yet tested

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

**OWED:** recompute pbo on trailing-truncated corpora (drop the most recent
k% and re-measure). A monotone fall locates the signal in the recent tail
(drift; the fix is a retrain, and OF-3 is reporting a real problem under a
misleading NAME). A flat column means the whole sample anti-selects
(selection; the strategy owns it). Harness written, not yet run:
`scratchpad/pbo_drift.py`.

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

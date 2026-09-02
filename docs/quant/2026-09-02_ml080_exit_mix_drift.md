# ML-080 exit-reason mix drift — why it fires

**Date:** 2026-09-02 · **Class:** SAFE (read-only investigation; this memo is the
only write) · **Verdict: UNINFORMATIVE ALARM.** The threshold is a guess, and the
metric it is compared against carries a permanent structural offset from a
2026-07-26 label-vocabulary change. Not real drift; not a code bug.

All numbers below are re-derived in this session, never recalled. `outputs/` was
read only; every mutation was applied to an in-memory copy.

---

## 1. Mechanism (file:line)

| What | Where |
|---|---|
| Alarm | `ml/history.py:633` `_era_mix_drift_check(meta, tele_cfg)` |
| TVD | `ml/history.py:578` `_reason_mix_tvd(baseline, recent)` = `0.5 * sum_c abs(p_rec(c) - p_base(c))` over the union of category sets |
| "Exit reason" field | `meta[i][3]` = the **`barrier` column of `outputs/signal_history.csv`**, appended at `ml/history.py:1832` (`row.get("barrier") or ""`) |
| Window clock | `ml/history.py:660` `tmax = max(m[1] for m in meta)` — **max row `ts` in the corpus, not wall clock** |
| Recent window | `ml/history.py:665` `m[1] >= tmax - window_h*3600` |
| Baseline | `ml/history.py:663` — **the WHOLE surviving corpus, recent rows INCLUDED** (documented at :639 as deliberate, mirroring ML-074) |
| Fire test | `ml/history.py:673` `if tvd > thresh` |
| Config | `config.json:851-853` `era_mix_drift_window_h=24.0`, `_min_rows=30`, `_tvd_threshold=0.3` |
| Guard bounds | `core/config_guard.py:895-900` — accepts any threshold in `[0.05, 0.9]`; **a range check, not a calibration** |
| Code | `core/codes.py:312` `ML_BARRIER_MIX_DRIFT = "ML-080"` |
| Call site | `ml/history.py:1952`, into `last_load_stats["era_mix_drift"]` — report-only, runs on the pre-era-exclusion corpus |

So the two windows are **trailing 24h of corpus time** vs **the entire corpus
back to 2026-07-13**, and the baseline contains the recent window inside it.

## 2. Measured mixes — two routes

**Route A (shipped instrument).** `HistoryStore("outputs/signal_history.csv")
.load_training_data()`, read `last_load_stats["era_mix_drift"]`, read
2026-09-02T13:45:53Z (file mtime 13:35:12Z):
`{"tvd": 0.3847, "fired": true, "n_recent": 874, "n_total": 22685}`

**Route B (independent, pandas, no `ml.` import).** Raw CSV, `book != "long"`
only, read 2026-09-02T13:45:00Z: **tvd = 0.3856**, n_recent 880 / n_total 22857.
The 172-row gap is the loader's extra clash-dedup/dirty drops. **Routes agree to
0.001.** Corpus span 2026-07-13T12:35:47Z to 2026-09-02T13:35:13Z = 51.04 d.

Mix, Route B (`barrier`; shares within each window):

| reason | base n | base p | recent n | recent p | abs delta |
|---|---|---|---|---|---|
| tb_sl | 6975 | .3052 | 455 | .5170 | .2119 |
| tb_pt | 5484 | .2399 | 364 | .4136 | .1737 |
| tb_time | 5406 | .2365 | 58 | .0659 | .1706 |
| sl | 1935 | .0847 | 0 | 0 | **.0847** |
| *(empty)* | 1781 | .0779 | 0 | 0 | **.0779** |
| time_stop | 459 | .0201 | 0 | 0 | **.0201** |
| trail | 384 | .0168 | 0 | 0 | **.0168** |
| time | 177 | .0077 | 0 | 0 | **.0077** |
| realized | 256 | .0112 | 3 | .0034 | .0078 |
| | | | | | **TVD 0.3856** |

## 3. The instrument is the first suspect — and it is the answer

**No new category appeared.** The recent-minus-older set difference is **empty**.
The reverse is not: `{"", sl, time, time_stop, trail}` exist ONLY in the past.
Full-range first/last scan of every `barrier` value:

```
<empty>   n=1781 first 2026-07-13T12:35:47Z last 2026-07-19T23:19:29Z
time      n= 177 first 2026-07-19T23:32:46Z last 2026-07-23T14:50:10Z
trail     n= 384 first 2026-07-20T00:25:28Z last 2026-07-26T17:12:28Z
sl        n=1935 first 2026-07-20T06:35:31Z last 2026-07-26T20:07:05Z
time_stop n= 459 first 2026-07-23T17:03:42Z last 2026-07-26T20:01:26Z
tb_sl/tb_pt  first 2026-07-26T20:19:05Z   tb_time first 2026-07-27T01:30:48Z
realized  n= 256 first 2026-07-20T00:17:10Z last 2026-09-02T11:35:06Z (still live)
```

That is the **2026-07-26 `ml.label_mode` -> `triple_barrier` switch** (a schema
change, not a behaviour change). Its dead vocabulary is **4736 / 22857 = 0.2072
of the baseline** and can never again appear in any recent window. Because TVD
conserves mass, that share enters `sum abs(delta)` twice, so

> **TVD has a permanent structural floor of 0.2072 — 69% of the 0.30
> threshold — that no future behaviour can lower.**

Confirmed empirically: the minimum TVD over all 1202 historical 24h windows is
**0.207**, exactly the floor.

Second confound, not yet biting: `label_era` shows `triple_barrier_h432` (12487
rows) vs `triple_barrier` (5287) — a horizon change with the SAME `tb_*`
vocabulary, so invisible to TVD but a real mix mover (`tb_time` share 62.2% in
`triple_barrier` vs 16.7% in `triple_barrier_h432`).

## 4. Null distribution — the power question

Every 24h window ending on an hourly grid across the full corpus, TVD vs the
whole corpus (the shipped comparison), `n>=30`:

| population | n windows | day-blocks | min | p50 | p95 | max | **frac > 0.30** |
|---|---|---|---|---|---|---|---|
| all windows | 1202 | 51 | .207 | .395 | .922 | .922 | **0.799** |
| ends >= 2026-07-28 | 878 | 37 | .207 | .354 | .676 | .743 | **0.724** |
| live-vocab only, >= 07-28 | 878 | 37 | .024 | .234 | .614 | .697 | 0.318 |

Effective n: these windows overlap 24x; they are drawn from **37 distinct UTC
day-blocks** post-schema, not 878 independent draws. Day-block bootstrap (2000
resamples of the 37 blocks) on the post-null p95: **0.676, CI95 [0.480, 0.711]** —
the threshold that would give a 5% false-positive rate lies somewhere in
0.48–0.71, i.e. **1.6x to 2.4x the shipped 0.30**.

**The alarm's false-positive rate under its own null is 72%.** It has been
continuously over 0.30 since **2026-09-01T19:35:47Z** and fires on most of
history. Its minimum detectable effect is correspondingly poor: to clear a 0.676
p95 from a 0.207 floor, a genuine mix shift must move roughly 47 points of
probability mass before it is distinguishable from an ordinary Tuesday.

Strip the schema artifact (live vocabulary `tb_*` + `realized` only,
renormalized): **current window TVD = 0.2431, the 53.4th percentile of the
post-schema null.** Dead centre. Daily `tb_*` shares over the last 14 days swing
`tb_time` from 0.000 (08-20) to 0.932 (08-29); today's 0.028 is inside that
ordinary range.

## 5. Instrument validation (defect + placebo, in memory, `outputs/` untouched)

Calling the shipped `_era_mix_drift_check` on copies of the meta list
(read 2026-09-02T13:46:56Z):

| arm | tvd | fired |
|---|---|---|
| control | 0.3869 | yes |
| **defect:** all recent reasons -> novel category `"NOVEL"` | **0.9614** | yes |
| **placebo:** recent reasons resampled i.i.d. from the whole corpus | **0.0168** | **no** |
| **placebo:** time-shifted, corpus truncated to -10 d | **0.5040** | yes |

The metric code is **correct** — it detects a planted shift and stays silent on a
by-construction-null one. The time-shift arm is the verdict: a window from ten
days ago fires *harder* than today. Nothing was drifting then either.

## 6. Verdict

**UNINFORMATIVE ALARM.** Components, in order of size: (a) a 0.2072 structural
floor from retired label vocabulary — an artifact of the 2026-07-26 schema
change, permanent and dependent on a baseline that never forgets; (b) ordinary
day-to-day `tb_*` variance, which alone exceeds 0.30 in 32% of windows; (c) no
detectable regime change in how positions exit. `0.30` is a **guess** —
`config_guard` range-checks it into `[0.05, 0.9]` and nothing has ever calibrated
it against a null.

**What would change my mind:** a new `barrier` value appearing in a recent window
(the recent-minus-older set difference is currently empty); live-vocab-only TVD
above the post-schema p95 of 0.614 for several consecutive non-overlapping
windows; or a `tb_time` share sustained outside the 0.00–0.93 daily envelope for
more than three days.

**Not done here (would be BOUNDARY or out of scope):** no config change, no
threshold retune, no code edit. If it is ever changed, the two candidate fixes
are (i) restrict the baseline to the current label vocabulary/era, and (ii) set
the threshold from the day-block-bootstrapped null p95 rather than a literal.
Both are `ml/` edits — operator adjudication, and per CLAUDE.md the threshold
must not simply be widened to silence the log line.

## 7. What this could not see

Corpus is `outputs/signal_history.csv` only (22857–22861 rows depending on read
time; the runner was writing throughout — Route A 13:45:53Z, Route B 13:45:00Z,
mutation arms 13:46:56Z). The null sweep uses hourly window ends, so sub-hourly
structure is invisible. `scipy` is absent; the bootstrap is a numpy percentile
over 2000 draws, seed 7 (bootstrap) / 11 (placebo resample). I did not reproduce
the two log lines quoted in the task (tvd 0.380/0.389, 974-1011 of ~22,618 rows)
from their original processes — those were earlier corpus snapshots; 0.3847 is
the same statistic at a later read time, not the same number.

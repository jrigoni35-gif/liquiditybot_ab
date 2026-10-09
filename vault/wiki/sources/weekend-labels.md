---
title: Weekend Labels Learning Note (2026-07-19)
category: source
summary: The quiet-weekend label batch was honest data from a working pipeline, but the pipeline was counting it wrong; AFML-prescribed corrections shipped
tags: [labeling, sample-weights, afml, uniqueness]
sources: 1
updated: 2026-08-01
---

# Weekend Labels Learning Note (2026-07-19)

**Raw source:** `raw/research/2026-07-19_weekend_labels.md`

## Framing
"Nothing was mislabeled and nothing needed deleting" — **the defect is in counting, not collecting**.
See [[concepts/honest-data-framing]].

## What happened
Over the low-volatility weekend of Jul 18-19 the corpus grew by ~200 candidate rows whose labels were
**~97% zero**, mostly from the VERTICAL (time) barrier. All entered training at full weight.

## The measurement that mattered
- Mean average-uniqueness **0.0655** on 1,741 rows — the average row shares its return window with
  ~15 other rows on the same asset.
- **Kish effective sample size: 1,624 -> 239.** "The corpus knew ~7x less than its row count claimed."
  See [[concepts/average-uniqueness-and-ess]].
- Trailing-24h label prior 0.153 vs corpus prior 0.264.

## Four things wrong
1. **No average-uniqueness weighting — AFML pitfall #7.** Fixed per AFML ch.4: per-(asset, 5-min-bar)
   concurrency; each row's weight scales by mean(1/c_t) over its lifespan. **Mass-preserving** — it
   redistributes loss weight rather than removing it. Worked example: ~13 concurrent candidates ->
   each weighted ~0.077, so the weekend batch counts as **~1 fact**.
2. **Time-barrier zeros pooled with stop-hit zeros.** A no-touch expiry ("price went nowhere") is
   weaker evidence than a realized stop-out ("price went against"). New `barrier` corpus column;
   label-0 `time` rows take weight 0.7.
3. **One-sided batches were invisible.** New ML-074 detector compares trailing-window prior to corpus
   prior — **detection only, never silent reweighting**.
4. **Evidence gate counted dirty rows.** `n_live` now comes from the load's own clean pass.

## Three things already right
Triple-barrier labeling for candidates (AFML Table 1.2 lists fixed-time-horizon labeling as pitfall
#5); banking live labels; the three existing weight legs (recency decay, candidate down-weight, manip
discount).

## Deliberate rejections
Selection stays on **raw Brier** (the calibrated-selection experiment was reverted for CSCV
cross-block leakage); no sequential bootstrap until a bagged family wins on merit; no neutral third
class (binary win/no-win is load-bearing across the EV gate); decay stays chronological.

## Sources
Lopez de Prado, *Advances in Financial Machine Learning* (Wiley 2018), ch.3, ch.4 §4.2-4.5, Table
1.2; Wu et al., *Entropy* 22(10):1162 (2020); Kovacevic et al., *IEEE Access* (2023); Peduzzi et al.
(1996).

## Related
[[entities/lopez-de-prado]] · [[entities/historystore]]

# Learning note — the quiet-weekend label batch (2026-07-19)

A peer-reviewed review of the labeling + sample-weighting pipeline, triggered
by the bot's first weekend of data. Framing up front: the weekend batch was
HONEST data collected by a correctly-functioning pipeline — nothing was
mislabeled and nothing needed deleting. What the review found is that the
pipeline was counting that data wrong, and the literature says exactly how to
count it right. That correction is now shipped (config `ml.sample_weights`).

## What happened

Over the low-volatility weekend of Jul 18–19 the corpus grew by ~200
candidate rows whose labels were ~97% `0`, mostly from the VERTICAL
(time) barrier — price touched neither profit nor stop inside the ~8h
horizon — plus a handful of realized-loss live rows (ML-073 label-banking
closures). All entered training at full weight. Measured on the real corpus
(1,741 rows) at ship time:

- mean average-uniqueness: **0.0655** — the average row shares its return
  window with ~15 other rows on the same asset;
- Kish effective sample size: **1,624 → 239** once overlap is accounted for.
  The corpus "knew" ~7x less than its row count claimed;
- trailing-24h label prior 0.153 vs corpus prior 0.264 — a real (weekend)
  prior swing, below the alarm threshold once diluted by history.

## What was already RIGHT (keep doing it)

1. **Triple-barrier labeling for candidates.** AFML Table 1.2 lists
   fixed-time-horizon labeling as pitfall #5 and prescribes the
   triple-barrier method (ch.3) as the remedy — the bot's labeler is the
   textbook-endorsed choice, corroborated by the peer-reviewed trend-labeling
   literature (Wu et al., Entropy 2020; Kovačević et al., IEEE Access 2023).
2. **Banking live labels** (ML-073) — realized-PnL ground truth is the
   gold standard the evidence gate is built on.
3. **Recency decay, candidate down-weight, manip discount** — all three
   weight legs are endorsed practice (non-stationarity; counterfactual
   caution; adversarial-data caution).

## What was WRONG and is now corrected

1. **No average-uniqueness weighting (AFML pitfall #7 — the big one).**
   Overlapping labels on one asset share the same underlying return path;
   they are one fact, not N facts. de Prado: "the series of labels {y_i}
   are not IID whenever there is an overlap between any two consecutive
   outcomes." Fix (AFML ch.4 §4.2–4.5): per-(asset, 5-min-bar) concurrency
   c_t; each row's weight scales by mean(1/c_t) over its [signal_ts, ts]
   lifespan. Mass-preserving: the correction REDISTRIBUTES loss weight, so
   total regularization balance is unchanged; ratios and ESS carry the fix.
   Worked example from the actual weekend: ~13 concurrent candidates → each
   weighted ~1/13 ≈ 0.077 of a lone signal, so the batch counts as ~1 fact.
2. **Time-barrier zeros pooled with stop-hit zeros.** A no-touch expiry
   ("price went nowhere") is weaker evidence against a signal than a
   realized stop-out ("price went against"). New `barrier` corpus column
   (pt/sl/time/tier/trail/floor for candidates, `realized` for live rows);
   label-0 `time` rows take `time_barrier_zero_weight` (0.7). Wu et al.
   2020: pooling no-touch expiries with directional losses mislabels trend
   structure.
3. **One-sided batches were invisible.** An all-zero window shifts the class
   prior under the calibrator (prior drift degrades calibrated win-probs
   even when ranking/AUC is intact). New ML-074 DETECTOR: trailing-window
   prior vs corpus prior, logged + surfaced in `last_load_stats` — detection
   only, never silent reweighting.
4. **Evidence gate counted dirty rows.** `n_live` now comes from the load's
   own clean pass (`last_load_stats.live_clean`), so model capacity is
   earned on exactly the rows entering the fit.

## Deliberately NOT changed (and why)

- **Selection stays on raw Brier** via the simplicity ladder — the
  calibrated-selection experiment was reverted earlier for CSCV cross-block
  leakage; the calibration gap remains a reported diagnostic.
- **No sequential bootstrap yet** — worth revisiting when a bagged model
  family (adaptive_gbt) wins selection on merit.
- **No neutral third class** — binary win/no-win is load-bearing across the
  EV gate; the barrier column + weight distinction captures the signal
  without a label-schema break.
- **Decay stays chronological** for now — de Prado's cumulative-uniqueness
  decay axis needs the uniqueness machinery to season first (it depends on
  step 1's outputs); revisit at the next re-baseline with more live rows.

## Sources

- López de Prado, *Advances in Financial Machine Learning* (Wiley 2018):
  ch.3 (triple-barrier), ch.4 (overlapping outcomes, concurrency, average
  uniqueness, sequential bootstrap), Table 1.2 pitfalls #5/#7.
- Wu, D. et al. "A Labeling Method for Financial Time Series Prediction
  Based on Trends," *Entropy* 22(10):1162, 2020.
- Kovačević, T. et al. "Effect of Labeling Algorithms on Financial
  Performance Metrics," *IEEE Access*, 2023.
- Peduzzi, P. et al. (1996) events-per-variable floors — already cited by
  the evidence gate (`ml.model_selection`).

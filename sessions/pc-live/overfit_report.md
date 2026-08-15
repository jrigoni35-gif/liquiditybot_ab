# Overfit audit — 2026-08-15 13:18 UTC

Dataset: SYNTHETIC benchmark (loaded rows=346 < 640) — validating machinery, not market

- **PASS** gap[logistic]: OOF gap within memorization band — train_auc=0.645 oof_auc=0.619 gap=+0.026
- **PASS** gap[gbt]: OOF gap within memorization band — train_auc=0.686 oof_auc=0.605 gap=+0.081
- **PASS** gap[mlp]: OOF gap within memorization band — train_auc=0.704 oof_auc=0.631 gap=+0.074
- **INFO** null-floor[logistic] — OOF Brier 0.2388 vs base-rate constant 0.2499 (base=0.491, n=2130) — BEATS the null
- **INFO** null-floor[gbt] — OOF Brier 0.2423 vs base-rate constant 0.2499 (base=0.491, n=2130) — BEATS the null
- **INFO** null-floor[mlp] — OOF Brier 0.2389 vs base-rate constant 0.2499 (base=0.491, n=2130) — BEATS the null
- **PASS** shuffle: destroyed labels learn nothing OOF — mean_auc=0.500 z=0.0 (limit 3.0)
- **INFO** pbo space — ml.adaptive_gbt.enabled=true — the adaptive rung is IN the measured selection space
- **PASS** pbo: DEPLOYED selection (simplicity ladder) not dominated by luck — pbo=0.04 over 8 configs / 70 splits (mean winner: mlp_small)
- **INFO** pbo argmax stress — raw argmax selection pbo=0.04 — the worst-case rule the ladder exists to avoid; gate is on the rule the bot actually runs
- **PASS** purge: never manufactures out-of-sample edge — unpurged=0.486 purged=0.492 leak_closed=-0.006
- **INFO** purge note — expanding-window design keeps boundary leak ~0 by construction; shuffle-null [OF-2] is the leak gate
- **PASS** dof: not starved (>=10 rows per feature) — rows/feature=40.0 (2560 rows / 64 features)
- **INFO** dof: dead-feature fraction (synthetic — informational) — dead_frac=0.92 (59 near-zero-importance features) — expected: benchmark plants signal in ~6/36
- **INFO** dof note — low/zero-importance: ['direction', 'ret_12_dir', 'ret_48_dir', 'sigma_bar_pct', 'vol_percentile', 'spread_bps'] ...
- **INFO** plateau[position_sizer.min_p_win] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[profit_taking.chandelier_k] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[pretrade.min_edge_cost_ratio] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** dsr — DEFERRED — 22 conviction-marked live trades < 30 (mixed n=327); mixed-sample dsr=0.000 sr=-0.48; probes are EV-mixed by design (PT-050); gate arms as conviction labels accrue
- **INFO** regime diagnostic caveat — stratum auc/brier below are concatenated-OOF over all scored rows, while the pooled figures they're compared against are MEAN-OF-FOLDS (OF-1's own convention) — the delta is indicative, not a rebasing of the same statistic
- **INFO** regime diagnostic — SYNTHETIC benchmark dataset — candidate/live split & base rate n/a (no signal_history.csv correspondence); OOF numbers below validate the machinery on the planted-signal benchmark, not a market read
- **INFO** regime[bull_quiet] oof — oof_n=1097 auc=0.629 (pooled 0.605, delta_auc=+0.024) brier=0.2387 (pooled 0.2423, delta_brier=-0.0036)
- **INFO** regime[unknown] oof — oof_n=1033 auc=0.579 (pooled 0.605, delta_auc=-0.026) brier=0.2461 (pooled 0.2423, delta_brier=+0.0038)
- **INFO** learning curve — SYNTHETIC benchmark dataset — corpus-size trend has no market meaning; skipped
- **INFO** extras liveness — SYNTHETIC benchmark dataset — feed liveness has no meaning; skipped

7 passed, 0 failed (32s)

Corpus: SYNTHETIC benchmark (loaded rows=346 < 640) — validating machinery, not market

> **This green validates the OVERFIT MACHINERY, not the market.** It is not evidence that the deployed strategy is un-overfit.

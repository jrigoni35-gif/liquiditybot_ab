# Overfit audit — 2026-07-28 11:27 UTC

Dataset: live history (661 rows)

- **FAIL** gap[logistic]: OOF gap within memorization band — train_auc=0.881 oof_auc=0.562 gap=+0.319
- **FAIL** gap[gbt]: OOF gap within memorization band — train_auc=0.899 oof_auc=0.553 gap=+0.346
- **FAIL** gap[mlp]: OOF gap within memorization band — train_auc=0.853 oof_auc=0.415 gap=+0.438
- **PASS** shuffle: destroyed labels learn nothing OOF — mean_auc=0.508 z=0.6 (limit 3.0)
- **INFO** pbo space — ml.adaptive_gbt.enabled=true — the adaptive rung is IN the measured selection space
- **INFO** pbo — evidence-gated to a single family (no model selection to overfit at this live-row count) (space=['logistic'])
- **PASS** purge: never manufactures out-of-sample edge — unpurged=0.486 purged=0.492 leak_closed=-0.006
- **INFO** purge note — expanding-window design keeps boundary leak ~0 by construction; shuffle-null [OF-2] is the leak gate
- **PASS** dof: not starved (>=10 rows per feature) — rows/feature=10.7 (661 rows / 62 features)
- **FAIL** dof: dead-feature fraction under 55% (live data) — dead_frac=0.58 (36 near-zero-importance features)
- **INFO** dof note — low/zero-importance: ['depth_ratio', 'sigma_bar_pct', 'corr_fast', 'dominance_delta', 'pat_hammer_dir', 'corr_shift'] ...
- **INFO** plateau[position_sizer.min_p_win] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[profit_taking.chandelier_k] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[pretrade.min_edge_cost_ratio] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** dsr — DEFERRED — 8 conviction-marked live trades < 30 (mixed n=248); mixed-sample dsr=0.000 sr=-0.68; probes are EV-mixed by design (PT-050); gate arms as conviction labels accrue
- **INFO** regime diagnostic caveat — stratum auc/brier below are concatenated-OOF over all scored rows, while the pooled figures they're compared against are MEAN-OF-FOLDS (OF-1's own convention) — the delta is indicative, not a rebasing of the same statistic
- **INFO** regime diagnostic caveat — n= below is a raw signal_history.csv count (candidate+live); oof_n= is the deduped/purged X actually OOF-scored — two different counting passes over related but non-identical data
- **INFO** regime[bull_quiet] — n=0 — absent from corpus
- **INFO** regime[bull_vol] — n=0 — absent from corpus
- **INFO** regime[range] — n=4717 (candidate=4475 live=242) base_rate=0.195
- **INFO** regime[range] oof — oof_n=248 auc=0.573 (pooled 0.553, delta_auc=+0.020) brier=0.2306 (pooled 0.2340, delta_brier=-0.0034)
- **INFO** regime[bear] — n=883 (candidate=877 live=6) base_rate=0.160
- **INFO** regime[bear] FLAG — insufficient live coverage (6 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[bear] oof — oof_n=192 auc=0.481 (pooled 0.553, delta_auc=-0.072) brier=0.2384 (pooled 0.2340, delta_brier=+0.0044)
- **INFO** regime[crisis] — n=0 — absent from corpus
- **INFO** regime[unknown] — n=0 — absent from corpus

3 passed, 4 failed (14s)

# Overfit audit — 2026-07-28 13:08 UTC

Dataset: live history (697 rows)

- **FAIL** gap[logistic]: OOF gap within memorization band — train_auc=0.863 oof_auc=0.545 gap=+0.318
- **FAIL** gap[gbt]: OOF gap within memorization band — train_auc=0.910 oof_auc=0.566 gap=+0.344
- **FAIL** gap[mlp]: OOF gap within memorization band — train_auc=0.824 oof_auc=0.454 gap=+0.370
- **PASS** shuffle: destroyed labels learn nothing OOF — mean_auc=0.506 z=0.5 (limit 3.0)
- **INFO** pbo space — ml.adaptive_gbt.enabled=true — the adaptive rung is IN the measured selection space
- **INFO** pbo — evidence-gated to a single family (no model selection to overfit at this live-row count) (space=['logistic'])
- **PASS** purge: never manufactures out-of-sample edge — unpurged=0.486 purged=0.492 leak_closed=-0.006
- **INFO** purge note — expanding-window design keeps boundary leak ~0 by construction; shuffle-null [OF-2] is the leak gate
- **PASS** dof: not starved (>=10 rows per feature) — rows/feature=11.2 (697 rows / 62 features)
- **PASS** dof: dead-feature fraction under 55% (live data) — dead_frac=0.40 (25 near-zero-importance features)
- **INFO** dof note — low/zero-importance: ['ret_12_dir', 'funding_dir', 'pat_marubozu_dir', 'regime_bull_quiet', 'regime_bull_vol', 'regime_range'] ...
- **INFO** plateau[position_sizer.min_p_win] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[profit_taking.chandelier_k] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[pretrade.min_edge_cost_ratio] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** dsr — DEFERRED — 8 conviction-marked live trades < 30 (mixed n=248); mixed-sample dsr=0.000 sr=-0.68; probes are EV-mixed by design (PT-050); gate arms as conviction labels accrue
- **INFO** regime diagnostic caveat — stratum auc/brier below are concatenated-OOF over all scored rows, while the pooled figures they're compared against are MEAN-OF-FOLDS (OF-1's own convention) — the delta is indicative, not a rebasing of the same statistic
- **INFO** regime diagnostic caveat — n= below is a raw signal_history.csv count (candidate+live); oof_n= is the deduped/purged X actually OOF-scored — two different counting passes over related but non-identical data
- **INFO** regime[bull_quiet] — n=0 — absent from corpus
- **INFO** regime[bull_vol] — n=0 — absent from corpus
- **INFO** regime[range] — n=4748 (candidate=4506 live=242) base_rate=0.195
- **INFO** regime[range] oof — oof_n=276 auc=0.601 (pooled 0.566, delta_auc=+0.035) brier=0.2420 (pooled 0.2403, delta_brier=+0.0017)
- **INFO** regime[bear] — n=888 (candidate=882 live=6) base_rate=0.161
- **INFO** regime[bear] FLAG — insufficient live coverage (6 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[bear] oof — oof_n=188 auc=0.514 (pooled 0.566, delta_auc=-0.052) brier=0.2378 (pooled 0.2403, delta_brier=-0.0025)
- **INFO** regime[crisis] — n=0 — absent from corpus
- **INFO** regime[unknown] — n=0 — absent from corpus

4 passed, 3 failed (16s)

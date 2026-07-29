# Overfit audit — 2026-07-28 23:25 UTC

Dataset: live history (951 rows)

- **FAIL** gap[logistic]: OOF gap within memorization band — train_auc=0.808 oof_auc=0.485 gap=+0.323
- **FAIL** gap[gbt]: OOF gap within memorization band — train_auc=0.809 oof_auc=0.504 gap=+0.305
- **FAIL** gap[mlp]: OOF gap within memorization band — train_auc=0.761 oof_auc=0.466 gap=+0.296
- **PASS** shuffle: destroyed labels learn nothing OOF — mean_auc=0.491 z=0.8 (limit 3.0)
- **INFO** pbo space — ml.adaptive_gbt.enabled=true — the adaptive rung is IN the measured selection space
- **INFO** pbo — evidence-gated to a single family (no model selection to overfit at this live-row count) (space=['logistic'])
- **PASS** purge: never manufactures out-of-sample edge — unpurged=0.486 purged=0.492 leak_closed=-0.006
- **INFO** purge note — expanding-window design keeps boundary leak ~0 by construction; shuffle-null [OF-2] is the leak gate
- **PASS** dof: not starved (>=10 rows per feature) — rows/feature=15.3 (951 rows / 62 features)
- **FAIL** dof: dead-feature fraction under 55% (live data) — dead_frac=0.79 (49 near-zero-importance features)
- **INFO** dof note — low/zero-importance: ['vol_percentile', 'drawdown_pct', 'va_pos', 'corr_shift', 'fvg_pull', 'manip_suspect'] ...
- **INFO** plateau[position_sizer.min_p_win] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[profit_taking.chandelier_k] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[pretrade.min_edge_cost_ratio] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** dsr — DEFERRED — 9 conviction-marked live trades < 30 (mixed n=250); mixed-sample dsr=0.000 sr=-0.69; probes are EV-mixed by design (PT-050); gate arms as conviction labels accrue
- **INFO** regime diagnostic caveat — stratum auc/brier below are concatenated-OOF over all scored rows, while the pooled figures they're compared against are MEAN-OF-FOLDS (OF-1's own convention) — the delta is indicative, not a rebasing of the same statistic
- **INFO** regime diagnostic caveat — n= below is a raw signal_history.csv count (candidate+live); oof_n= is the deduped/purged X actually OOF-scored — two different counting passes over related but non-identical data
- **INFO** regime[bull_quiet] — n=0 — absent from corpus
- **INFO** regime[bull_vol] — n=0 — absent from corpus
- **INFO** regime[range] — n=4875 (candidate=4631 live=244) base_rate=0.201
- **INFO** regime[range] oof — oof_n=361 auc=0.564 (pooled 0.504, delta_auc=+0.060) brier=0.2316 (pooled 0.2337, delta_brier=-0.0021)
- **INFO** regime[bear] — n=1018 (candidate=1012 live=6) base_rate=0.177
- **INFO** regime[bear] FLAG — insufficient live coverage (6 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[bear] oof — oof_n=271 auc=0.440 (pooled 0.504, delta_auc=-0.064) brier=0.2364 (pooled 0.2337, delta_brier=+0.0028)
- **INFO** regime[crisis] — n=0 — absent from corpus
- **INFO** regime[unknown] — n=0 — absent from corpus

3 passed, 4 failed (13s)

# Overfit audit — 2026-07-30 23:09 UTC

Dataset: live history (1968 rows)

- **FAIL** gap[logistic]: OOF gap within memorization band — train_auc=0.748 oof_auc=0.519 gap=+0.229
- **FAIL** gap[gbt]: OOF gap within memorization band — train_auc=0.667 oof_auc=0.508 gap=+0.160
- **FAIL** gap[mlp]: OOF gap within memorization band — train_auc=0.721 oof_auc=0.519 gap=+0.202
- **PASS** shuffle: destroyed labels learn nothing OOF — mean_auc=0.494 z=0.7 (limit 3.0)
- **INFO** pbo space — ml.adaptive_gbt.enabled=true — the adaptive rung is IN the measured selection space
- **INFO** pbo — evidence-gated to a single family (no model selection to overfit at this live-row count) (space=['logistic'])
- **PASS** purge: never manufactures out-of-sample edge — unpurged=0.486 purged=0.492 leak_closed=-0.006
- **INFO** purge note — expanding-window design keeps boundary leak ~0 by construction; shuffle-null [OF-2] is the leak gate
- **PASS** dof: not starved (>=10 rows per feature) — rows/feature=31.7 (1968 rows / 62 features)
- **FAIL** dof: dead-feature fraction under 55% (live data) — dead_frac=0.66 (41 near-zero-importance features)
- **INFO** dof note — low/zero-importance: ['direction', 'th_stopzone', 'mom_dir', 'corr_fast', 'imbalance_delta_dir', 'pat_marubozu_dir'] ...
- **INFO** plateau[position_sizer.min_p_win] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[profit_taking.chandelier_k] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[pretrade.min_edge_cost_ratio] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** dsr — DEFERRED — 9 conviction-marked live trades < 30 (mixed n=255); mixed-sample dsr=0.000 sr=-0.69; probes are EV-mixed by design (PT-050); gate arms as conviction labels accrue
- **INFO** regime diagnostic caveat — stratum auc/brier below are concatenated-OOF over all scored rows, while the pooled figures they're compared against are MEAN-OF-FOLDS (OF-1's own convention) — the delta is indicative, not a rebasing of the same statistic
- **INFO** regime diagnostic caveat — n= below is a raw signal_history.csv count (candidate+live); oof_n= is the deduped/purged X actually OOF-scored — two different counting passes over related but non-identical data
- **INFO** regime[bull_quiet] — n=0 — absent from corpus
- **INFO** regime[bull_vol] — n=0 — absent from corpus
- **INFO** regime[range] — n=5392 (candidate=5145 live=247) base_rate=0.199
- **INFO** regime[range] oof — oof_n=867 auc=0.473 (pooled 0.508, delta_auc=-0.035) brier=0.2481 (pooled 0.2492, delta_brier=-0.0011)
- **INFO** regime[bear] — n=1525 (candidate=1517 live=8) base_rate=0.208
- **INFO** regime[bear] FLAG — insufficient live coverage (8 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[bear] oof — oof_n=773 auc=0.524 (pooled 0.508, delta_auc=+0.017) brier=0.2504 (pooled 0.2492, delta_brier=+0.0012)
- **INFO** regime[crisis] — n=0 — absent from corpus
- **INFO** regime[unknown] — n=0 — absent from corpus
- **INFO** learning curve caveat — each point refits gbt on a chronological PREFIX of the corpus (time-purged OOF, deployed protocol) — points are the same statistic across sizes, but none is OF-1's own pooled number
- **INFO** lc[n=492] — oof_n=410 auc=0.484 brier=0.2506
- **INFO** lc[n=787] — oof_n=655 auc=0.529 brier=0.2412
- **INFO** lc[n=1082] — oof_n=900 auc=0.437 brier=0.2495
- **INFO** lc[n=1378] — oof_n=1145 auc=0.488 brier=0.2412
- **INFO** lc[n=1673] — oof_n=1390 auc=0.477 brier=0.2450
- **INFO** lc[n=1968] — oof_n=1640 auc=0.475 brier=0.2485
- **INFO** learning curve trend FLAG — DECLINING (delta_auc=-0.030 < -0.03) — later rows are HURTING skill: regime/era drift inside the training window (check ML-080 mix drift and era_exclusion)
- **INFO** extras[equity_risk_z] — at-neutral share 100.0% (n=1968) — feed effectively dark corpus-wide (dead column)
- **INFO** extras[opt_pcr_z] — at-neutral share 100.0% (n=1968) — feed effectively dark corpus-wide (dead column)
- **INFO** extras[opt_oi_pcr_z] — at-neutral share 100.0% (n=1968) — feed effectively dark corpus-wide (dead column)
- **INFO** extras[dominance_delta] — at-neutral share 8.3% (n=1968) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[sent_fear] — at-neutral share 100.0% (n=1968) — feed effectively dark corpus-wide (dead column)
- **INFO** extras[fear_greed] — at-neutral share 0.0% (n=1968) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance

3 passed, 4 failed (28s)

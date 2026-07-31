# Overfit audit — 2026-07-31 11:50 UTC

Dataset: live history (2132 rows)

- **FAIL** gap[logistic]: OOF gap within memorization band — train_auc=0.745 oof_auc=0.519 gap=+0.225
- **FAIL** gap[gbt]: OOF gap within memorization band — train_auc=0.762 oof_auc=0.523 gap=+0.239
- **FAIL** gap[mlp]: OOF gap within memorization band — train_auc=0.722 oof_auc=0.498 gap=+0.224
- **PASS** shuffle: destroyed labels learn nothing OOF — mean_auc=0.485 z=1.9 (limit 3.0)
- **INFO** pbo space — ml.adaptive_gbt.enabled=true — the adaptive rung is IN the measured selection space
- **INFO** pbo — evidence-gated to a single family (no model selection to overfit at this live-row count) (space=['logistic'])
- **PASS** purge: never manufactures out-of-sample edge — unpurged=0.486 purged=0.492 leak_closed=-0.006
- **INFO** purge note — expanding-window design keeps boundary leak ~0 by construction; shuffle-null [OF-2] is the leak gate
- **PASS** dof: not starved (>=10 rows per feature) — rows/feature=33.3 (2132 rows / 64 features)
- **FAIL** dof: dead-feature fraction under 55% (live data) — dead_frac=0.77 (49 near-zero-importance features)
- **INFO** dof note — low/zero-importance: ['pd_zone', 'th_stopzone', 'flow_tox', 'poc_dist', 'imbalance_delta_dir', 'gate_confidence'] ...
- **INFO** plateau[position_sizer.min_p_win] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[profit_taking.chandelier_k] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[pretrade.min_edge_cost_ratio] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** dsr — DEFERRED — 9 conviction-marked live trades < 30 (mixed n=256); mixed-sample dsr=0.000 sr=-0.69; probes are EV-mixed by design (PT-050); gate arms as conviction labels accrue
- **INFO** regime diagnostic caveat — stratum auc/brier below are concatenated-OOF over all scored rows, while the pooled figures they're compared against are MEAN-OF-FOLDS (OF-1's own convention) — the delta is indicative, not a rebasing of the same statistic
- **INFO** regime diagnostic caveat — n= below is a raw signal_history.csv count (candidate+live); oof_n= is the deduped/purged X actually OOF-scored — two different counting passes over related but non-identical data
- **INFO** regime[bull_quiet] — n=0 — absent from corpus
- **INFO** regime[bull_vol] — n=0 — absent from corpus
- **INFO** regime[range] — n=5487 (candidate=5240 live=247) base_rate=0.198
- **INFO** regime[range] oof — oof_n=933 auc=0.454 (pooled 0.523, delta_auc=-0.069) brier=0.2338 (pooled 0.2383, delta_brier=-0.0045)
- **INFO** regime[bear] — n=1595 (candidate=1586 live=9) base_rate=0.208
- **INFO** regime[bear] FLAG — insufficient live coverage (9 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[bear] oof — oof_n=842 auc=0.516 (pooled 0.523, delta_auc=-0.007) brier=0.2433 (pooled 0.2383, delta_brier=+0.0050)
- **INFO** regime[crisis] — n=0 — absent from corpus
- **INFO** regime[unknown] — n=0 — absent from corpus
- **INFO** learning curve caveat — each point refits gbt on a chronological PREFIX of the corpus (time-purged OOF, deployed protocol) — points are the same statistic across sizes, but none is OF-1's own pooled number
- **INFO** lc[n=533] — oof_n=440 auc=0.507 brier=0.2402
- **INFO** lc[n=853] — oof_n=710 auc=0.502 brier=0.2544
- **INFO** lc[n=1173] — oof_n=975 auc=0.436 brier=0.2529
- **INFO** lc[n=1492] — oof_n=1240 auc=0.489 brier=0.2444
- **INFO** lc[n=1812] — oof_n=1510 auc=0.456 brier=0.2536
- **INFO** lc[n=2132] — oof_n=1775 auc=0.494 brier=0.2466
- **INFO** learning curve trend FLAG — DECLINING (delta_auc=-0.030 < -0.03) — later rows are HURTING skill: regime/era drift inside the training window (check ML-080 mix drift and era_exclusion)
- **INFO** extras[equity_risk_z] — at-neutral share 100.0% (n=2132) — feed effectively dark corpus-wide (dead column)
- **INFO** extras[opt_pcr_z] — at-neutral share 100.0% (n=2132) — feed effectively dark corpus-wide (dead column)
- **INFO** extras[opt_oi_pcr_z] — at-neutral share 100.0% (n=2132) — feed effectively dark corpus-wide (dead column)
- **INFO** extras[dominance_delta] — at-neutral share 8.3% (n=2132) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[sent_fear] — at-neutral share 100.0% (n=2132) — feed effectively dark corpus-wide (dead column)
- **INFO** extras[fear_greed] — at-neutral share 0.0% (n=2132) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance

3 passed, 4 failed (53s)

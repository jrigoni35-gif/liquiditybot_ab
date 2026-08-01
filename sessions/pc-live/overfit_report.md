# Overfit audit — 2026-08-01 17:46 UTC

Dataset: live history (2141 rows)

- **FAIL** gap[logistic]: OOF gap within memorization band — train_auc=0.744 oof_auc=0.520 gap=+0.224
- **FAIL** gap[gbt]: OOF gap within memorization band — train_auc=0.756 oof_auc=0.532 gap=+0.223
- **FAIL** gap[mlp]: OOF gap within memorization band — train_auc=0.745 oof_auc=0.504 gap=+0.241
- **INFO** null-floor[logistic] — OOF Brier 0.2910 vs base-rate constant 0.1861 (base=0.247, n=1780) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **INFO** null-floor[gbt] — OOF Brier 0.2378 vs base-rate constant 0.1861 (base=0.247, n=1780) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **INFO** null-floor[mlp] — OOF Brier 0.2797 vs base-rate constant 0.1861 (base=0.247, n=1780) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **PASS** shuffle: destroyed labels learn nothing OOF — mean_auc=0.494 z=0.7 (limit 3.0)
- **INFO** pbo space — ml.adaptive_gbt.enabled=true — the adaptive rung is IN the measured selection space
- **INFO** pbo — evidence-gated to a single family (no model selection to overfit at this live-row count) (space=['logistic'])
- **PASS** purge: never manufactures out-of-sample edge — unpurged=0.486 purged=0.492 leak_closed=-0.006
- **INFO** purge note — expanding-window design keeps boundary leak ~0 by construction; shuffle-null [OF-2] is the leak gate
- **PASS** dof: not starved (>=10 rows per feature) — rows/feature=33.5 (2141 rows / 64 features)
- **FAIL** dof: dead-feature fraction under 55% (live data) — dead_frac=0.77 (49 near-zero-importance features)
- **INFO** dof note — low/zero-importance: ['spread_bps', 'other_ret_6_dir', 'funding_dir', 'fvg_pull', 'ret_12_dir', 'poc_dist'] ...
- **INFO** plateau[position_sizer.min_p_win] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[profit_taking.chandelier_k] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[pretrade.min_edge_cost_ratio] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** dsr — DEFERRED — 17 conviction-marked live trades < 30 (mixed n=275); mixed-sample dsr=0.000 sr=-0.54; probes are EV-mixed by design (PT-050); gate arms as conviction labels accrue
- **INFO** regime diagnostic caveat — stratum auc/brier below are concatenated-OOF over all scored rows, while the pooled figures they're compared against are MEAN-OF-FOLDS (OF-1's own convention) — the delta is indicative, not a rebasing of the same statistic
- **INFO** regime diagnostic caveat — n= below is a raw signal_history.csv count (candidate+live); oof_n= is the deduped/purged X actually OOF-scored — two different counting passes over related but non-identical data
- **INFO** regime[bull_quiet] — n=0 — absent from corpus
- **INFO** regime[bull_vol] — n=5 (candidate=5 live=0) base_rate=0.200
- **INFO** regime[bull_vol] FLAG — insufficient live coverage (0 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[bull_vol] oof — oof_n=0 < 30 — insufficient OOF evidence, not scored
- **INFO** regime[range] — n=6014 (candidate=5758 live=256) base_rate=0.195
- **INFO** regime[range] oof — oof_n=937 auc=0.459 (pooled 0.532, delta_auc=-0.074) brier=0.2338 (pooled 0.2378, delta_brier=-0.0040)
- **INFO** regime[bear] — n=2178 (candidate=2159 live=19) base_rate=0.191
- **INFO** regime[bear] FLAG — insufficient live coverage (19 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[bear] oof — oof_n=843 auc=0.536 (pooled 0.532, delta_auc=+0.003) brier=0.2422 (pooled 0.2378, delta_brier=+0.0044)
- **INFO** regime[crisis] — n=0 — absent from corpus
- **INFO** regime[unknown] — n=0 — absent from corpus
- **INFO** learning curve caveat — each point refits gbt on a chronological PREFIX of the corpus (time-purged OOF, deployed protocol) — points are the same statistic across sizes, but none is OF-1's own pooled number
- **INFO** lc[n=535] — oof_n=445 auc=0.535 brier=0.2457
- **INFO** lc[n=856] — oof_n=710 auc=0.502 brier=0.2544
- **INFO** lc[n=1178] — oof_n=980 auc=0.444 brier=0.2481
- **INFO** lc[n=1499] — oof_n=1245 auc=0.494 brier=0.2432
- **INFO** lc[n=1820] — oof_n=1515 auc=0.466 brier=0.2504
- **INFO** lc[n=2141] — oof_n=1780 auc=0.499 brier=0.2601
- **INFO** learning curve trend FLAG — DECLINING (delta_auc=-0.036 < -0.03) — later rows are HURTING skill: regime/era drift inside the training window (check ML-080 mix drift and era_exclusion)
- **INFO** extras[equity_risk_z] — at-neutral share 100.0% (n=2141) — feed effectively dark corpus-wide (dead column)
- **INFO** extras[opt_pcr_z] — at-neutral share 100.0% (n=2141) — feed effectively dark corpus-wide (dead column)
- **INFO** extras[opt_oi_pcr_z] — at-neutral share 100.0% (n=2141) — feed effectively dark corpus-wide (dead column)
- **INFO** extras[dominance_delta] — at-neutral share 8.4% (n=2141) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[sent_fear] — at-neutral share 100.0% (n=2141) — feed effectively dark corpus-wide (dead column)
- **INFO** extras[fear_greed] — at-neutral share 0.0% (n=2141) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance

3 passed, 4 failed (41s)

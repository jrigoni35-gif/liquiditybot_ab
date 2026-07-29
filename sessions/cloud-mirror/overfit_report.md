# Overfit audit — 2026-07-29 23:26 UTC

Dataset: live history (1516 rows)

- **FAIL** gap[logistic]: OOF gap within memorization band — train_auc=0.791 oof_auc=0.482 gap=+0.309
- **FAIL** gap[gbt]: OOF gap within memorization band — train_auc=0.767 oof_auc=0.525 gap=+0.242
- **FAIL** gap[mlp]: OOF gap within memorization band — train_auc=0.726 oof_auc=0.475 gap=+0.251
- **PASS** shuffle: destroyed labels learn nothing OOF — mean_auc=0.483 z=1.8 (limit 3.0)
- **INFO** pbo space — ml.adaptive_gbt.enabled=true — the adaptive rung is IN the measured selection space
- **INFO** pbo — evidence-gated to a single family (no model selection to overfit at this live-row count) (space=['logistic'])
- **PASS** purge: never manufactures out-of-sample edge — unpurged=0.486 purged=0.492 leak_closed=-0.006
- **INFO** purge note — expanding-window design keeps boundary leak ~0 by construction; shuffle-null [OF-2] is the leak gate
- **PASS** dof: not starved (>=10 rows per feature) — rows/feature=24.4 (1516 rows / 62 features)
- **FAIL** dof: dead-feature fraction under 55% (live data) — dead_frac=0.82 (51 near-zero-importance features)
- **INFO** dof note — low/zero-importance: ['va_pos', 'ret_1_dir', 'ret_12_dir', 'imbalance_dir', 'spread_bps', 'depth_log'] ...
- **INFO** plateau[position_sizer.min_p_win] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[profit_taking.chandelier_k] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[pretrade.min_edge_cost_ratio] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** dsr — DEFERRED — 9 conviction-marked live trades < 30 (mixed n=253); mixed-sample dsr=0.000 sr=-0.69; probes are EV-mixed by design (PT-050); gate arms as conviction labels accrue
- **INFO** regime diagnostic caveat — stratum auc/brier below are concatenated-OOF over all scored rows, while the pooled figures they're compared against are MEAN-OF-FOLDS (OF-1's own convention) — the delta is indicative, not a rebasing of the same statistic
- **INFO** regime diagnostic caveat — n= below is a raw signal_history.csv count (candidate+live); oof_n= is the deduped/purged X actually OOF-scored — two different counting passes over related but non-identical data
- **INFO** regime[bull_quiet] — n=0 — absent from corpus
- **INFO** regime[bull_vol] — n=0 — absent from corpus
- **INFO** regime[range] — n=5173 (candidate=4927 live=246) base_rate=0.200
- **INFO** regime[range] oof — oof_n=684 auc=0.446 (pooled 0.525, delta_auc=-0.078) brier=0.2670 (pooled 0.2555, delta_brier=+0.0115)
- **INFO** regime[bear] — n=1289 (candidate=1282 live=7) base_rate=0.202
- **INFO** regime[bear] FLAG — insufficient live coverage (7 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[bear] oof — oof_n=576 auc=0.555 (pooled 0.525, delta_auc=+0.030) brier=0.2419 (pooled 0.2555, delta_brier=-0.0137)
- **INFO** regime[crisis] — n=0 — absent from corpus
- **INFO** regime[unknown] — n=0 — absent from corpus
- **INFO** learning curve caveat — each point refits gbt on a chronological PREFIX of the corpus (time-purged OOF, deployed protocol) — points are the same statistic across sizes, but none is OF-1's own pooled number
- **INFO** lc[n=379] — oof_n=252 auc=0.591 brier=0.2351
- **INFO** lc[n=606] — oof_n=505 auc=0.492 brier=0.2472
- **INFO** lc[n=834] — oof_n=695 auc=0.467 brier=0.2614
- **INFO** lc[n=1061] — oof_n=880 auc=0.484 brier=0.2415
- **INFO** lc[n=1289] — oof_n=1070 auc=0.501 brier=0.2420
- **INFO** lc[n=1516] — oof_n=1260 auc=0.482 brier=0.2409
- **INFO** learning curve trend FLAG — DECLINING (delta_auc=-0.049 < -0.03) — later rows are HURTING skill: regime/era drift inside the training window (check ML-080 mix drift and era_exclusion)
- **INFO** extras[equity_risk_z] — at-neutral share 100.0% (n=1516) — feed effectively dark corpus-wide (dead column)
- **INFO** extras[opt_pcr_z] — at-neutral share 100.0% (n=1516) — feed effectively dark corpus-wide (dead column)
- **INFO** extras[opt_oi_pcr_z] — at-neutral share 100.0% (n=1516) — feed effectively dark corpus-wide (dead column)
- **INFO** extras[dominance_delta] — at-neutral share 8.8% (n=1516) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[sent_fear] — at-neutral share 100.0% (n=1516) — feed effectively dark corpus-wide (dead column)
- **INFO** extras[fear_greed] — at-neutral share 0.0% (n=1516) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance

3 passed, 4 failed (23s)

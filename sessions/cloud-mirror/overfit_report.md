# Overfit audit — 2026-07-29 17:13 UTC

Dataset: live history (1314 rows)

- **FAIL** gap[logistic]: OOF gap within memorization band — train_auc=0.820 oof_auc=0.479 gap=+0.341
- **FAIL** gap[gbt]: OOF gap within memorization band — train_auc=0.753 oof_auc=0.495 gap=+0.258
- **FAIL** gap[mlp]: OOF gap within memorization band — train_auc=0.733 oof_auc=0.502 gap=+0.231
- **PASS** shuffle: destroyed labels learn nothing OOF — mean_auc=0.490 z=1.0 (limit 3.0)
- **INFO** pbo space — ml.adaptive_gbt.enabled=true — the adaptive rung is IN the measured selection space
- **INFO** pbo — evidence-gated to a single family (no model selection to overfit at this live-row count) (space=['logistic'])
- **PASS** purge: never manufactures out-of-sample edge — unpurged=0.486 purged=0.492 leak_closed=-0.006
- **INFO** purge note — expanding-window design keeps boundary leak ~0 by construction; shuffle-null [OF-2] is the leak gate
- **PASS** dof: not starved (>=10 rows per feature) — rows/feature=21.2 (1314 rows / 62 features)
- **FAIL** dof: dead-feature fraction under 55% (live data) — dead_frac=0.65 (40 near-zero-importance features)
- **INFO** dof note — low/zero-importance: ['manip_suspect', 'other_ret_6_dir', 'poc_dist', 'spread_bps', 'basis_dir', 'gate_confidence'] ...
- **INFO** plateau[position_sizer.min_p_win] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[profit_taking.chandelier_k] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[pretrade.min_edge_cost_ratio] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** dsr — DEFERRED — 9 conviction-marked live trades < 30 (mixed n=253); mixed-sample dsr=0.000 sr=-0.69; probes are EV-mixed by design (PT-050); gate arms as conviction labels accrue
- **INFO** regime diagnostic caveat — stratum auc/brier below are concatenated-OOF over all scored rows, while the pooled figures they're compared against are MEAN-OF-FOLDS (OF-1's own convention) — the delta is indicative, not a rebasing of the same statistic
- **INFO** regime diagnostic caveat — n= below is a raw signal_history.csv count (candidate+live); oof_n= is the deduped/purged X actually OOF-scored — two different counting passes over related but non-identical data
- **INFO** regime[bull_quiet] — n=0 — absent from corpus
- **INFO** regime[bull_vol] — n=0 — absent from corpus
- **INFO** regime[range] — n=5084 (candidate=4838 live=246) base_rate=0.200
- **INFO** regime[range] oof — oof_n=609 auc=0.484 (pooled 0.495, delta_auc=-0.011) brier=0.2370 (pooled 0.2392, delta_brier=-0.0022)
- **INFO** regime[bear] — n=1176 (candidate=1169 live=7) base_rate=0.183
- **INFO** regime[bear] FLAG — insufficient live coverage (7 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[bear] oof — oof_n=486 auc=0.417 (pooled 0.495, delta_auc=-0.078) brier=0.2420 (pooled 0.2392, delta_brier=+0.0028)
- **INFO** regime[crisis] — n=0 — absent from corpus
- **INFO** regime[unknown] — n=0 — absent from corpus
- **INFO** learning curve caveat — each point refits gbt on a chronological PREFIX of the corpus (time-purged OOF, deployed protocol) — points are the same statistic across sizes, but none is OF-1's own pooled number
- **INFO** lc[n=328] — oof_n=216 auc=0.482 brier=0.2532
- **INFO** lc[n=526] — oof_n=435 auc=0.524 brier=0.2419
- **INFO** lc[n=723] — oof_n=600 auc=0.499 brier=0.2409
- **INFO** lc[n=920] — oof_n=765 auc=0.495 brier=0.2412
- **INFO** lc[n=1117] — oof_n=930 auc=0.448 brier=0.2594
- **INFO** lc[n=1314] — oof_n=1095 auc=0.461 brier=0.2428
- **INFO** learning curve trend FLAG — DECLINING (delta_auc=-0.049 < -0.03) — later rows are HURTING skill: regime/era drift inside the training window (check ML-080 mix drift and era_exclusion)

3 passed, 4 failed (21s)

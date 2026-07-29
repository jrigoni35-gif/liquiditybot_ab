# Overfit audit — 2026-07-29 03:26 UTC

Dataset: live history (1020 rows)

- **FAIL** gap[logistic]: OOF gap within memorization band — train_auc=0.844 oof_auc=0.463 gap=+0.380
- **FAIL** gap[gbt]: OOF gap within memorization band — train_auc=0.706 oof_auc=0.533 gap=+0.173
- **FAIL** gap[mlp]: OOF gap within memorization band — train_auc=0.740 oof_auc=0.478 gap=+0.261
- **PASS** shuffle: destroyed labels learn nothing OOF — mean_auc=0.495 z=0.5 (limit 3.0)
- **INFO** pbo space — ml.adaptive_gbt.enabled=true — the adaptive rung is IN the measured selection space
- **INFO** pbo — evidence-gated to a single family (no model selection to overfit at this live-row count) (space=['logistic'])
- **PASS** purge: never manufactures out-of-sample edge — unpurged=0.486 purged=0.492 leak_closed=-0.006
- **INFO** purge note — expanding-window design keeps boundary leak ~0 by construction; shuffle-null [OF-2] is the leak gate
- **PASS** dof: not starved (>=10 rows per feature) — rows/feature=16.4 (1020 rows / 62 features)
- **FAIL** dof: dead-feature fraction under 55% (live data) — dead_frac=0.97 (60 near-zero-importance features)
- **INFO** dof note — low/zero-importance: ['ret_1_dir', 'ret_6_dir', 'ret_12_dir', 'ret_48_dir', 'vol_percentile', 'imbalance_dir'] ...
- **INFO** plateau[position_sizer.min_p_win] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[profit_taking.chandelier_k] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[pretrade.min_edge_cost_ratio] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** dsr — DEFERRED — 9 conviction-marked live trades < 30 (mixed n=251); mixed-sample dsr=0.000 sr=-0.69; probes are EV-mixed by design (PT-050); gate arms as conviction labels accrue
- **INFO** regime diagnostic caveat — stratum auc/brier below are concatenated-OOF over all scored rows, while the pooled figures they're compared against are MEAN-OF-FOLDS (OF-1's own convention) — the delta is indicative, not a rebasing of the same statistic
- **INFO** regime diagnostic caveat — n= below is a raw signal_history.csv count (candidate+live); oof_n= is the deduped/purged X actually OOF-scored — two different counting passes over related but non-identical data
- **INFO** regime[bull_quiet] — n=0 — absent from corpus
- **INFO** regime[bull_vol] — n=0 — absent from corpus
- **INFO** regime[range] — n=4892 (candidate=4647 live=245) base_rate=0.201
- **INFO** regime[range] oof — oof_n=437 auc=0.545 (pooled 0.533, delta_auc=+0.012) brier=0.2437 (pooled 0.2468, delta_brier=-0.0031)
- **INFO** regime[bear] — n=1071 (candidate=1065 live=6) base_rate=0.176
- **INFO** regime[bear] FLAG — insufficient live coverage (6 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[bear] oof — oof_n=413 auc=0.439 (pooled 0.533, delta_auc=-0.095) brier=0.2500 (pooled 0.2468, delta_brier=+0.0033)
- **INFO** regime[crisis] — n=0 — absent from corpus
- **INFO** regime[unknown] — n=0 — absent from corpus
- **INFO** learning curve caveat — each point refits gbt on a chronological PREFIX of the corpus (time-purged OOF, deployed protocol) — points are the same statistic across sizes, but none is OF-1's own pooled number
- **INFO** lc[n=255] — oof_n=168 auc=0.504 brier=0.2447
- **INFO** lc[n=408] — oof_n=340 auc=0.551 brier=0.2325
- **INFO** lc[n=561] — oof_n=465 auc=0.499 brier=0.2534
- **INFO** lc[n=714] — oof_n=595 auc=0.509 brier=0.2473
- **INFO** lc[n=867] — oof_n=720 auc=0.489 brier=0.2555
- **INFO** lc[n=1020] — oof_n=850 auc=0.523 brier=0.2366
- **INFO** learning curve trend — FLAT (|delta_auc=-0.022| <= 0.03) — representation-limited: more rows alone are not buying skill; feature/label quality is the binding constraint, not corpus size

3 passed, 4 failed (23s)

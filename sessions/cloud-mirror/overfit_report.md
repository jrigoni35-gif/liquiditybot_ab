# Overfit audit — 2026-07-29 10:15 UTC

Dataset: live history (1169 rows)

- **FAIL** gap[logistic]: OOF gap within memorization band — train_auc=0.827 oof_auc=0.452 gap=+0.376
- **FAIL** gap[gbt]: OOF gap within memorization band — train_auc=0.725 oof_auc=0.466 gap=+0.258
- **FAIL** gap[mlp]: OOF gap within memorization band — train_auc=0.836 oof_auc=0.461 gap=+0.375
- **PASS** shuffle: destroyed labels learn nothing OOF — mean_auc=0.500 z=0.0 (limit 3.0)
- **INFO** pbo space — ml.adaptive_gbt.enabled=true — the adaptive rung is IN the measured selection space
- **INFO** pbo — evidence-gated to a single family (no model selection to overfit at this live-row count) (space=['logistic'])
- **PASS** purge: never manufactures out-of-sample edge — unpurged=0.486 purged=0.492 leak_closed=-0.006
- **INFO** purge note — expanding-window design keeps boundary leak ~0 by construction; shuffle-null [OF-2] is the leak gate
- **PASS** dof: not starved (>=10 rows per feature) — rows/feature=18.9 (1169 rows / 62 features)
- **FAIL** dof: dead-feature fraction under 55% (live data) — dead_frac=0.76 (47 near-zero-importance features)
- **INFO** dof note — low/zero-importance: ['sigma_bar_pct', 'dominance_delta', 'liq_pocket_pull', 'ret_6_dir', 'ret_1_dir', 'ret_12_dir'] ...
- **INFO** plateau[position_sizer.min_p_win] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[profit_taking.chandelier_k] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[pretrade.min_edge_cost_ratio] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** dsr — DEFERRED — 9 conviction-marked live trades < 30 (mixed n=252); mixed-sample dsr=0.000 sr=-0.69; probes are EV-mixed by design (PT-050); gate arms as conviction labels accrue
- **INFO** regime diagnostic caveat — stratum auc/brier below are concatenated-OOF over all scored rows, while the pooled figures they're compared against are MEAN-OF-FOLDS (OF-1's own convention) — the delta is indicative, not a rebasing of the same statistic
- **INFO** regime diagnostic caveat — n= below is a raw signal_history.csv count (candidate+live); oof_n= is the deduped/purged X actually OOF-scored — two different counting passes over related but non-identical data
- **INFO** regime[bull_quiet] — n=0 — absent from corpus
- **INFO** regime[bull_vol] — n=0 — absent from corpus
- **INFO** regime[range] — n=4998 (candidate=4752 live=246) base_rate=0.201
- **INFO** regime[range] oof — oof_n=531 auc=0.419 (pooled 0.466, delta_auc=-0.048) brier=0.2632 (pooled 0.2533, delta_brier=+0.0099)
- **INFO** regime[bear] — n=1115 (candidate=1109 live=6) base_rate=0.180
- **INFO** regime[bear] FLAG — insufficient live coverage (6 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[bear] oof — oof_n=439 auc=0.413 (pooled 0.466, delta_auc=-0.054) brier=0.2413 (pooled 0.2533, delta_brier=-0.0120)
- **INFO** regime[crisis] — n=0 — absent from corpus
- **INFO** regime[unknown] — n=0 — absent from corpus
- **INFO** learning curve caveat — each point refits gbt on a chronological PREFIX of the corpus (time-purged OOF, deployed protocol) — points are the same statistic across sizes, but none is OF-1's own pooled number
- **INFO** lc[n=292] — oof_n=192 auc=0.503 brier=0.2588
- **INFO** lc[n=468] — oof_n=390 auc=0.486 brier=0.2507
- **INFO** lc[n=643] — oof_n=535 auc=0.501 brier=0.2398
- **INFO** lc[n=818] — oof_n=680 auc=0.494 brier=0.2458
- **INFO** lc[n=994] — oof_n=825 auc=0.538 brier=0.2350
- **INFO** lc[n=1169] — oof_n=970 auc=0.450 brier=0.2497
- **INFO** learning curve trend — FLAT (|delta_auc=-0.001| <= 0.03) — representation-limited: more rows alone are not buying skill; feature/label quality is the binding constraint, not corpus size

3 passed, 4 failed (30s)

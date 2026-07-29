# Overfit audit — 2026-07-29 14:36 UTC

Dataset: live history (1227 rows)

- **FAIL** gap[logistic]: OOF gap within memorization band — train_auc=0.822 oof_auc=0.474 gap=+0.348
- **FAIL** gap[gbt]: OOF gap within memorization band — train_auc=0.674 oof_auc=0.501 gap=+0.173
- **FAIL** gap[mlp]: OOF gap within memorization band — train_auc=0.759 oof_auc=0.482 gap=+0.277
- **PASS** shuffle: destroyed labels learn nothing OOF — mean_auc=0.508 z=0.7 (limit 3.0)
- **INFO** pbo space — ml.adaptive_gbt.enabled=true — the adaptive rung is IN the measured selection space
- **INFO** pbo — evidence-gated to a single family (no model selection to overfit at this live-row count) (space=['logistic'])
- **PASS** purge: never manufactures out-of-sample edge — unpurged=0.486 purged=0.492 leak_closed=-0.006
- **INFO** purge note — expanding-window design keeps boundary leak ~0 by construction; shuffle-null [OF-2] is the leak gate
- **PASS** dof: not starved (>=10 rows per feature) — rows/feature=19.8 (1227 rows / 62 features)
- **FAIL** dof: dead-feature fraction under 55% (live data) — dead_frac=0.76 (47 near-zero-importance features)
- **INFO** dof note — low/zero-importance: ['depth_log', 'th_stopzone', 'drawdown_pct', 'ret_1_dir', 'ret_12_dir', 'spread_bps'] ...
- **INFO** plateau[position_sizer.min_p_win] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[profit_taking.chandelier_k] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[pretrade.min_edge_cost_ratio] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** dsr — DEFERRED — 9 conviction-marked live trades < 30 (mixed n=252); mixed-sample dsr=0.000 sr=-0.69; probes are EV-mixed by design (PT-050); gate arms as conviction labels accrue
- **INFO** regime diagnostic caveat — stratum auc/brier below are concatenated-OOF over all scored rows, while the pooled figures they're compared against are MEAN-OF-FOLDS (OF-1's own convention) — the delta is indicative, not a rebasing of the same statistic
- **INFO** regime diagnostic caveat — n= below is a raw signal_history.csv count (candidate+live); oof_n= is the deduped/purged X actually OOF-scored — two different counting passes over related but non-identical data
- **INFO** regime[bull_quiet] — n=0 — absent from corpus
- **INFO** regime[bull_vol] — n=0 — absent from corpus
- **INFO** regime[range] — n=5044 (candidate=4798 live=246) base_rate=0.201
- **INFO** regime[range] oof — oof_n=577 auc=0.494 (pooled 0.501, delta_auc=-0.007) brier=0.2336 (pooled 0.2344, delta_brier=-0.0008)
- **INFO** regime[bear] — n=1127 (candidate=1121 live=6) base_rate=0.182
- **INFO** regime[bear] FLAG — insufficient live coverage (6 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[bear] oof — oof_n=443 auc=0.448 (pooled 0.501, delta_auc=-0.054) brier=0.2354 (pooled 0.2344, delta_brier=+0.0010)
- **INFO** regime[crisis] — n=0 — absent from corpus
- **INFO** regime[unknown] — n=0 — absent from corpus
- **INFO** learning curve caveat — each point refits gbt on a chronological PREFIX of the corpus (time-purged OOF, deployed protocol) — points are the same statistic across sizes, but none is OF-1's own pooled number
- **INFO** lc[n=307] — oof_n=204 auc=0.520 brier=0.2444
- **INFO** lc[n=491] — oof_n=405 auc=0.471 brier=0.2550
- **INFO** lc[n=675] — oof_n=560 auc=0.492 brier=0.2417
- **INFO** lc[n=859] — oof_n=715 auc=0.495 brier=0.2506
- **INFO** lc[n=1043] — oof_n=865 auc=0.493 brier=0.2404
- **INFO** lc[n=1227] — oof_n=1020 auc=0.471 brier=0.2509
- **INFO** learning curve trend — FLAT (|delta_auc=-0.013| <= 0.03) — representation-limited: more rows alone are not buying skill; feature/label quality is the binding constraint, not corpus size

3 passed, 4 failed (22s)

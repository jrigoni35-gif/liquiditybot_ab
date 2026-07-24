# Overfit audit — 2026-07-24 17:51 UTC

Dataset: live history (3830 rows)

- **FAIL** gap[logistic]: OOF gap within memorization band — train_auc=0.743 oof_auc=0.567 gap=+0.177
- **FAIL** gap[gbt]: OOF gap within memorization band — train_auc=0.755 oof_auc=0.576 gap=+0.179
- **FAIL** gap[mlp]: OOF gap within memorization band — train_auc=0.730 oof_auc=0.509 gap=+0.221
- **PASS** shuffle: destroyed labels learn nothing OOF — mean_auc=0.507 z=1.0 (limit 3.0)
- **INFO** pbo space — ml.adaptive_gbt.enabled=true — the adaptive rung is IN the measured selection space
- **PASS** pbo: DEPLOYED selection (simplicity ladder) not dominated by luck — pbo=0.47 over 7 configs / 70 splits (mean winner: gbt_d4_lr05)
- **INFO** pbo argmax stress — raw argmax selection pbo=0.33 — the worst-case rule the ladder exists to avoid; gate is on the rule the bot actually runs
- **INFO** pbo note — 0.2 < pbo <= 0.5: selection has luck in it — expected at this sample size; keep the simplicity-ladder margin
- **PASS** purge: never manufactures out-of-sample edge — unpurged=0.486 purged=0.492 leak_closed=-0.006
- **INFO** purge note — expanding-window design keeps boundary leak ~0 by construction; shuffle-null [OF-2] is the leak gate
- **PASS** dof: not starved (>=10 rows per feature) — rows/feature=61.8 (3830 rows / 62 features)
- **FAIL** dof: dead-feature fraction under 55% (live data) — dead_frac=0.65 (40 near-zero-importance features)
- **INFO** dof note — low/zero-importance: ['regime_age', 'fv_edge_bps', 'gate_confidence', 'liq_pocket_pull', 'imbalance_delta_dir', 'volume_z'] ...
- **INFO** plateau[position_sizer.min_p_win] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[profit_taking.chandelier_k] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[pretrade.min_edge_cost_ratio] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** dsr — DEFERRED — 4 conviction-marked live trades < 30 (mixed n=240); mixed-sample dsr=0.000 sr=-0.69; probes are EV-mixed by design (PT-050); gate arms as conviction labels accrue
- **INFO** regime diagnostic caveat — stratum auc/brier below are concatenated-OOF over all scored rows, while the pooled figures they're compared against are MEAN-OF-FOLDS (OF-1's own convention) — the delta is indicative, not a rebasing of the same statistic
- **INFO** regime diagnostic caveat — n= below is a raw signal_history.csv count (candidate+live); oof_n= is the deduped/purged X actually OOF-scored — two different counting passes over related but non-identical data
- **INFO** regime[bull_quiet] — n=0 — absent from corpus
- **INFO** regime[bull_vol] — n=0 — absent from corpus
- **INFO** regime[range] — n=3792 (candidate=3556 live=236) base_rate=0.204
- **INFO** regime[range] oof — oof_n=3093 auc=0.612 (pooled 0.576, delta_auc=+0.037) brier=0.2480 (pooled 0.2475, delta_brier=+0.0005)
- **INFO** regime[bear] — n=118 (candidate=114 live=4) base_rate=0.220
- **INFO** regime[bear] FLAG — insufficient live coverage (4 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[bear] oof — oof_n=97 auc=0.641 (pooled 0.576, delta_auc=+0.065) brier=0.2305 (pooled 0.2475, delta_brier=-0.0170)
- **INFO** regime[crisis] — n=0 — absent from corpus
- **INFO** regime[unknown] — n=0 — absent from corpus

4 passed, 4 failed (86s)

# Overfit audit — 2026-07-23 16:17 UTC

Dataset: live history (3272 rows)

- **FAIL** gap[logistic]: OOF gap within memorization band — train_auc=0.765 oof_auc=0.507 gap=+0.258
- **FAIL** gap[gbt]: OOF gap within memorization band — train_auc=0.839 oof_auc=0.520 gap=+0.319
- **FAIL** gap[mlp]: OOF gap within memorization band — train_auc=0.815 oof_auc=0.509 gap=+0.306
- **PASS** shuffle: destroyed labels learn nothing OOF — mean_auc=0.505 z=0.7 (limit 3.0)
- **INFO** pbo space — ml.adaptive_gbt.enabled=true — the adaptive rung is IN the measured selection space
- **FAIL** pbo: DEPLOYED selection (simplicity ladder) not dominated by luck — pbo=0.63 over 7 configs / 70 splits (mean winner: gbt_d4_lr05)
- **INFO** pbo argmax stress — raw argmax selection pbo=0.57 — the worst-case rule the ladder exists to avoid; gate is on the rule the bot actually runs
- **INFO** pbo note — 0.2 < pbo <= 0.5: selection has luck in it — expected at this sample size; keep the simplicity-ladder margin
- **PASS** purge: never manufactures out-of-sample edge — unpurged=0.486 purged=0.492 leak_closed=-0.006
- **INFO** purge note — expanding-window design keeps boundary leak ~0 by construction; shuffle-null [OF-2] is the leak gate
- **PASS** dof: not starved (>=10 rows per feature) — rows/feature=52.8 (3272 rows / 62 features)
- **FAIL** dof: dead-feature fraction under 55% (live data) — dead_frac=0.82 (51 near-zero-importance features)
- **INFO** dof note — low/zero-importance: ['regime_age', 'imbalance_delta_dir', 'ret_1_dir', 'ret_6_dir', 'ret_12_dir', 'ret_48_dir'] ...
- **INFO** plateau[position_sizer.min_p_win] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[profit_taking.chandelier_k] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[pretrade.min_edge_cost_ratio] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** dsr — DEFERRED — 4 conviction-marked live trades < 30 (mixed n=214); mixed-sample dsr=0.000 sr=-0.75; probes are EV-mixed by design (PT-050); gate arms as conviction labels accrue

3 passed, 5 failed (45s)

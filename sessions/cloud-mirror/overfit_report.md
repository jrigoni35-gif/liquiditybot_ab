# Overfit audit — 2026-07-22 01:05 UTC

Dataset: live history (2309 rows)

- **FAIL** gap[logistic]: OOF gap within memorization band — train_auc=0.775 oof_auc=0.466 gap=+0.309
- **FAIL** gap[gbt]: OOF gap within memorization band — train_auc=0.747 oof_auc=0.426 gap=+0.321
- **FAIL** gap[mlp]: OOF gap within memorization band — train_auc=0.821 oof_auc=0.487 gap=+0.334
- **PASS** shuffle: destroyed labels learn nothing OOF — mean_auc=0.517 z=2.2 (limit 3.0)
- **INFO** pbo space — ml.adaptive_gbt.enabled=true — the adaptive rung is IN the measured selection space
- **PASS** pbo: DEPLOYED selection (simplicity ladder) not dominated by luck — pbo=0.10 over 6 configs / 70 splits (mean winner: gbt_d2_lr05)
- **INFO** pbo argmax stress — raw argmax selection pbo=0.10 — the worst-case rule the ladder exists to avoid; gate is on the rule the bot actually runs
- **PASS** purge: never manufactures out-of-sample edge — unpurged=0.486 purged=0.492 leak_closed=-0.006
- **INFO** purge note — expanding-window design keeps boundary leak ~0 by construction; shuffle-null [OF-2] is the leak gate
- **PASS** dof: not starved (>=10 rows per feature) — rows/feature=37.2 (2309 rows / 62 features)
- **FAIL** dof: dead-feature fraction under 55% (live data) — dead_frac=0.87 (54 near-zero-importance features)
- **INFO** dof note — low/zero-importance: ['pat_marubozu_dir', 'funding_dist', 'ret_6_dir', 'liq_pocket_pull', 'ret_1_dir', 'imbalance_dir'] ...
- **INFO** plateau[position_sizer.min_p_win] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[profit_taking.chandelier_k] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[pretrade.min_edge_cost_ratio] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** dsr — DEFERRED — 4 conviction-marked live trades < 30 (mixed n=103); mixed-sample dsr=0.000 sr=-0.69; probes are EV-mixed by design (PT-050); gate arms as conviction labels accrue

4 passed, 4 failed (75s)

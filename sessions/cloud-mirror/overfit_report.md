# Overfit audit — 2026-07-18 21:09 UTC

Dataset: live history (1342 rows)

- **FAIL** gap[logistic]: OOF gap within memorization band — train_auc=0.902 oof_auc=0.464 gap=+0.438
- **FAIL** gap[gbt]: OOF gap within memorization band — train_auc=0.856 oof_auc=0.482 gap=+0.374
- **FAIL** gap[mlp]: OOF gap within memorization band — train_auc=0.778 oof_auc=0.510 gap=+0.268
- **PASS** shuffle: destroyed labels learn nothing OOF — mean_auc=0.484 z=1.6 (limit 3.0)
- **INFO** pbo space — ml.adaptive_gbt.enabled=true — the adaptive rung is IN the measured selection space
- **PASS** pbo: DEPLOYED selection (simplicity ladder) not dominated by luck — pbo=0.24 over 8 configs / 70 splits (mean winner: gbt_d2_lr10)
- **INFO** pbo argmax stress — raw argmax selection pbo=0.14 — the worst-case rule the ladder exists to avoid; gate is on the rule the bot actually runs
- **INFO** pbo note — 0.2 < pbo <= 0.5: selection has luck in it — expected at this sample size; keep the simplicity-ladder margin
- **PASS** purge: never manufactures out-of-sample edge — unpurged=0.486 purged=0.492 leak_closed=-0.006
- **INFO** purge note — expanding-window design keeps boundary leak ~0 by construction; shuffle-null [OF-2] is the leak gate
- **PASS** dof: not starved (>=10 rows per feature) — rows/feature=23.1 (1342 rows / 58 features)
- **FAIL** dof: dead-feature fraction under 55% (live data) — dead_frac=0.57 (33 near-zero-importance features)
- **INFO** dof note — low/zero-importance: ['th_grid', 'volume_z', 'ret_6_dir', 'mtf_align', 'hour_sin', 'depth_ratio'] ...
- **INFO** plateau[position_sizer.min_p_win] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[profit_taking.chandelier_k] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[pretrade.min_edge_cost_ratio] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** dsr — INFORMATIONAL during exploration phase — dsr=0.000 sr=-0.58 n=35; live sample is EV-mixed by design (PT-050 probes); gate arms when ml.exploration.enabled is false

4 passed, 4 failed (31s)

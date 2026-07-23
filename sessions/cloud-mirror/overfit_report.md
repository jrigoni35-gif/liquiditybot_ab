# Overfit audit — 2026-07-23 21:17 UTC

Dataset: live history (3395 rows)

- **FAIL** gap[logistic]: OOF gap within memorization band — train_auc=0.760 oof_auc=0.520 gap=+0.241
- **FAIL** gap[gbt]: OOF gap within memorization band — train_auc=0.805 oof_auc=0.528 gap=+0.277
- **FAIL** gap[mlp]: OOF gap within memorization band — train_auc=0.767 oof_auc=0.517 gap=+0.250
- **PASS** shuffle: destroyed labels learn nothing OOF — mean_auc=0.498 z=0.3 (limit 3.0)
- **INFO** pbo space — ml.adaptive_gbt.enabled=true — the adaptive rung is IN the measured selection space
- **FAIL** pbo: DEPLOYED selection (simplicity ladder) not dominated by luck — pbo=0.76 over 7 configs / 70 splits (mean winner: gbt_d4_lr05)
- **INFO** pbo argmax stress — raw argmax selection pbo=0.70 — the worst-case rule the ladder exists to avoid; gate is on the rule the bot actually runs
- **INFO** pbo note — 0.2 < pbo <= 0.5: selection has luck in it — expected at this sample size; keep the simplicity-ladder margin
- **PASS** purge: never manufactures out-of-sample edge — unpurged=0.486 purged=0.492 leak_closed=-0.006
- **INFO** purge note — expanding-window design keeps boundary leak ~0 by construction; shuffle-null [OF-2] is the leak gate
- **PASS** dof: not starved (>=10 rows per feature) — rows/feature=54.8 (3395 rows / 62 features)
- **FAIL** dof: dead-feature fraction under 55% (live data) — dead_frac=0.73 (45 near-zero-importance features)
- **INFO** dof note — low/zero-importance: ['funding_dist', 'corr_fast', 'th_barclose', 'ret_6_dir', 'ret_1_dir', 'ret_12_dir'] ...
- **INFO** plateau[position_sizer.min_p_win] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[profit_taking.chandelier_k] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[pretrade.min_edge_cost_ratio] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** dsr — DEFERRED — 4 conviction-marked live trades < 30 (mixed n=231); mixed-sample dsr=0.000 sr=-0.68; probes are EV-mixed by design (PT-050); gate arms as conviction labels accrue
- **INFO** regime diagnostic caveat — stratum auc/brier below are concatenated-OOF over all scored rows, while the pooled figures they're compared against are MEAN-OF-FOLDS (OF-1's own convention) — the delta is indicative, not a rebasing of the same statistic
- **INFO** regime diagnostic caveat — n= below is a raw signal_history.csv count (candidate+live); oof_n= is the deduped/purged X actually OOF-scored — two different counting passes over related but non-identical data
- **INFO** regime[bull_quiet] — n=0 — absent from corpus
- **INFO** regime[bull_vol] — n=0 — absent from corpus
- **INFO** regime[range] — n=3381 (candidate=3154 live=227) base_rate=0.220
- **INFO** regime[range] oof — oof_n=2754 auc=0.556 (pooled 0.528, delta_auc=+0.028) brier=0.2400 (pooled 0.2403, delta_brier=-0.0003)
- **INFO** regime[bear] — n=90 (candidate=86 live=4) base_rate=0.289
- **INFO** regime[bear] FLAG — insufficient live coverage (4 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[bear] oof — oof_n=71 auc=0.552 (pooled 0.528, delta_auc=+0.025) brier=0.2530 (pooled 0.2403, delta_brier=+0.0127)
- **INFO** regime[crisis] — n=0 — absent from corpus
- **INFO** regime[unknown] — n=0 — absent from corpus

3 passed, 5 failed (60s)

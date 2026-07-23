# Overfit audit — 2026-07-23 23:43 UTC

Dataset: live history (3474 rows)

- **FAIL** gap[logistic]: OOF gap within memorization band — train_auc=0.753 oof_auc=0.523 gap=+0.230
- **FAIL** gap[gbt]: OOF gap within memorization band — train_auc=0.809 oof_auc=0.526 gap=+0.282
- **FAIL** gap[mlp]: OOF gap within memorization band — train_auc=0.726 oof_auc=0.495 gap=+0.231
- **PASS** shuffle: destroyed labels learn nothing OOF — mean_auc=0.498 z=0.3 (limit 3.0)
- **INFO** pbo space — ml.adaptive_gbt.enabled=true — the adaptive rung is IN the measured selection space
- **PASS** pbo: DEPLOYED selection (simplicity ladder) not dominated by luck — pbo=0.36 over 7 configs / 70 splits (mean winner: gbt_d4_lr05)
- **INFO** pbo argmax stress — raw argmax selection pbo=0.23 — the worst-case rule the ladder exists to avoid; gate is on the rule the bot actually runs
- **INFO** pbo note — 0.2 < pbo <= 0.5: selection has luck in it — expected at this sample size; keep the simplicity-ladder margin
- **PASS** purge: never manufactures out-of-sample edge — unpurged=0.486 purged=0.492 leak_closed=-0.006
- **INFO** purge note — expanding-window design keeps boundary leak ~0 by construction; shuffle-null [OF-2] is the leak gate
- **PASS** dof: not starved (>=10 rows per feature) — rows/feature=56.0 (3474 rows / 62 features)
- **FAIL** dof: dead-feature fraction under 55% (live data) — dead_frac=0.65 (40 near-zero-importance features)
- **INFO** dof note — low/zero-importance: ['spread_bps', 'opt_iv_skew', 'other_ret_6_dir', 'th_stopzone', 'basis_dir', 'corr_fast'] ...
- **INFO** plateau[position_sizer.min_p_win] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[profit_taking.chandelier_k] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[pretrade.min_edge_cost_ratio] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** dsr — DEFERRED — 4 conviction-marked live trades < 30 (mixed n=237); mixed-sample dsr=0.000 sr=-0.69; probes are EV-mixed by design (PT-050); gate arms as conviction labels accrue
- **INFO** regime diagnostic caveat — stratum auc/brier below are concatenated-OOF over all scored rows, while the pooled figures they're compared against are MEAN-OF-FOLDS (OF-1's own convention) — the delta is indicative, not a rebasing of the same statistic
- **INFO** regime diagnostic caveat — n= below is a raw signal_history.csv count (candidate+live); oof_n= is the deduped/purged X actually OOF-scored — two different counting passes over related but non-identical data
- **INFO** regime[bull_quiet] — n=0 — absent from corpus
- **INFO** regime[bull_vol] — n=0 — absent from corpus
- **INFO** regime[range] — n=3463 (candidate=3230 live=233) base_rate=0.215
- **INFO** regime[range] oof — oof_n=2824 auc=0.554 (pooled 0.526, delta_auc=+0.028) brier=0.2354 (pooled 0.2356, delta_brier=-0.0002)
- **INFO** regime[bear] — n=90 (candidate=86 live=4) base_rate=0.289
- **INFO** regime[bear] FLAG — insufficient live coverage (4 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[bear] oof — oof_n=71 auc=0.532 (pooled 0.526, delta_auc=+0.006) brier=0.2448 (pooled 0.2356, delta_brier=+0.0092)
- **INFO** regime[crisis] — n=0 — absent from corpus
- **INFO** regime[unknown] — n=0 — absent from corpus

4 passed, 4 failed (90s)

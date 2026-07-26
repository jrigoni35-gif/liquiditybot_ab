# Overfit audit — 2026-07-26 19:35 UTC

Dataset: live history (4815 rows)

- **FAIL** gap[logistic]: OOF gap within memorization band — train_auc=0.729 oof_auc=0.540 gap=+0.189
- **FAIL** gap[gbt]: OOF gap within memorization band — train_auc=0.813 oof_auc=0.538 gap=+0.275
- **FAIL** gap[mlp]: OOF gap within memorization band — train_auc=0.725 oof_auc=0.514 gap=+0.210
- **PASS** shuffle: destroyed labels learn nothing OOF — mean_auc=0.511 z=1.7 (limit 3.0)
- **INFO** pbo space — ml.adaptive_gbt.enabled=true — the adaptive rung is IN the measured selection space
- **PASS** pbo: DEPLOYED selection (simplicity ladder) not dominated by luck — pbo=0.41 over 7 configs / 70 splits (mean winner: gbt_d3_lr05)
- **INFO** pbo argmax stress — raw argmax selection pbo=0.40 — the worst-case rule the ladder exists to avoid; gate is on the rule the bot actually runs
- **INFO** pbo note — 0.2 < pbo <= 0.5: selection has luck in it — expected at this sample size; keep the simplicity-ladder margin
- **PASS** purge: never manufactures out-of-sample edge — unpurged=0.486 purged=0.492 leak_closed=-0.006
- **INFO** purge note — expanding-window design keeps boundary leak ~0 by construction; shuffle-null [OF-2] is the leak gate
- **PASS** dof: not starved (>=10 rows per feature) — rows/feature=77.7 (4815 rows / 62 features)
- **PASS** dof: dead-feature fraction under 55% (live data) — dead_frac=0.47 (29 near-zero-importance features)
- **INFO** dof note — low/zero-importance: ['regime_age', 'opt_iv_skew', 'corr_shift', 'pat_marubozu_dir', 'sent_dir', 'volume_z'] ...
- **INFO** plateau[position_sizer.min_p_win] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[profit_taking.chandelier_k] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[pretrade.min_edge_cost_ratio] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** dsr — DEFERRED — 5 conviction-marked live trades < 30 (mixed n=242); mixed-sample dsr=0.000 sr=-0.69; probes are EV-mixed by design (PT-050); gate arms as conviction labels accrue
- **INFO** regime diagnostic caveat — stratum auc/brier below are concatenated-OOF over all scored rows, while the pooled figures they're compared against are MEAN-OF-FOLDS (OF-1's own convention) — the delta is indicative, not a rebasing of the same statistic
- **INFO** regime diagnostic caveat — n= below is a raw signal_history.csv count (candidate+live); oof_n= is the deduped/purged X actually OOF-scored — two different counting passes over related but non-identical data
- **INFO** regime[bull_quiet] — n=0 — absent from corpus
- **INFO** regime[bull_vol] — n=0 — absent from corpus
- **INFO** regime[range] — n=4337 (candidate=4099 live=238) base_rate=0.182
- **INFO** regime[range] oof — oof_n=3470 auc=0.576 (pooled 0.538, delta_auc=+0.037) brier=0.2054 (pooled 0.1959, delta_brier=+0.0095)
- **INFO** regime[bear] — n=560 (candidate=556 live=4) base_rate=0.077
- **INFO** regime[bear] FLAG — insufficient live coverage (4 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[bear] oof — oof_n=540 auc=0.635 (pooled 0.538, delta_auc=+0.097) brier=0.1347 (pooled 0.1959, delta_brier=-0.0612)
- **INFO** regime[crisis] — n=0 — absent from corpus
- **INFO** regime[unknown] — n=0 — absent from corpus

5 passed, 3 failed (73s)

# Overfit audit — 2026-07-24 06:15 UTC

Dataset: live history (3571 rows)

- **FAIL** gap[logistic]: OOF gap within memorization band — train_auc=0.767 oof_auc=0.567 gap=+0.199
- **FAIL** gap[gbt]: OOF gap within memorization band — train_auc=0.807 oof_auc=0.502 gap=+0.305
- **FAIL** gap[mlp]: OOF gap within memorization band — train_auc=0.884 oof_auc=0.462 gap=+0.422
- **PASS** shuffle: destroyed labels learn nothing OOF — mean_auc=0.507 z=0.8 (limit 3.0)
- **INFO** pbo space — ml.adaptive_gbt.enabled=true — the adaptive rung is IN the measured selection space
- **PASS** pbo: DEPLOYED selection (simplicity ladder) not dominated by luck — pbo=0.15 over 7 configs / 20 splits (mean winner: gbt_d4_lr05)
- **INFO** pbo argmax stress — raw argmax selection pbo=0.10 — the worst-case rule the ladder exists to avoid; gate is on the rule the bot actually runs
- **PASS** purge: never manufactures out-of-sample edge — unpurged=0.486 purged=0.492 leak_closed=-0.006
- **INFO** purge note — expanding-window design keeps boundary leak ~0 by construction; shuffle-null [OF-2] is the leak gate
- **PASS** dof: not starved (>=10 rows per feature) — rows/feature=57.6 (3571 rows / 62 features)
- **FAIL** dof: dead-feature fraction under 55% (live data) — dead_frac=0.69 (43 near-zero-importance features)
- **INFO** dof note — low/zero-importance: ['fvg_liq_confluence', 'th_stopzone', 'basis_dir', 'funding_dist', 'other_ret_6_dir', 'depth_log'] ...
- **INFO** plateau[position_sizer.min_p_win] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** dsr — DEFERRED — 4 conviction-marked live trades < 30 (mixed n=240); mixed-sample dsr=0.000 sr=-0.69; probes are EV-mixed by design (PT-050); gate arms as conviction labels accrue
- **INFO** regime diagnostic caveat — stratum auc/brier below are concatenated-OOF over all scored rows, while the pooled figures they're compared against are MEAN-OF-FOLDS (OF-1's own convention) — the delta is indicative, not a rebasing of the same statistic
- **INFO** regime diagnostic caveat — n= below is a raw signal_history.csv count (candidate+live); oof_n= is the deduped/purged X actually OOF-scored — two different counting passes over related but non-identical data
- **INFO** regime[bull_quiet] — n=0 — absent from corpus
- **INFO** regime[bull_vol] — n=0 — absent from corpus
- **INFO** regime[range] — n=3556 (candidate=3320 live=236) base_rate=0.211
- **INFO** regime[range] oof — oof_n=2600 auc=0.512 (pooled 0.502, delta_auc=+0.009) brier=0.2662 (pooled 0.2663, delta_brier=-0.0000)
- **INFO** regime[bear] — n=95 (candidate=91 live=4) base_rate=0.274
- **INFO** regime[bear] FLAG — insufficient live coverage (4 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[bear] oof — oof_n=76 auc=0.509 (pooled 0.502, delta_auc=+0.007) brier=0.2679 (pooled 0.2663, delta_brier=+0.0016)
- **INFO** regime[crisis] — n=0 — absent from corpus
- **INFO** regime[unknown] — n=0 — absent from corpus

4 passed, 4 failed (79s)

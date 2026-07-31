# Overfit audit — 2026-07-31 02:13 UTC

Dataset: live history (2022 rows)

- **FAIL** gap[logistic]: OOF gap within memorization band — train_auc=0.744 oof_auc=0.510 gap=+0.233
- **FAIL** gap[gbt]: OOF gap within memorization band — train_auc=0.723 oof_auc=0.521 gap=+0.201
- **FAIL** gap[mlp]: OOF gap within memorization band — train_auc=0.730 oof_auc=0.514 gap=+0.216
- **PASS** shuffle: destroyed labels learn nothing OOF — mean_auc=0.502 z=0.3 (limit 3.0)
- **INFO** pbo space — ml.adaptive_gbt.enabled=true — the adaptive rung is IN the measured selection space
- **INFO** pbo — evidence-gated to a single family (no model selection to overfit at this live-row count) (space=['logistic'])
- **PASS** purge: never manufactures out-of-sample edge — unpurged=0.486 purged=0.492 leak_closed=-0.006
- **INFO** purge note — expanding-window design keeps boundary leak ~0 by construction; shuffle-null [OF-2] is the leak gate
- **PASS** dof: not starved (>=10 rows per feature) — rows/feature=32.6 (2022 rows / 62 features)
- **FAIL** dof: dead-feature fraction under 55% (live data) — dead_frac=0.65 (40 near-zero-importance features)
- **INFO** dof note — low/zero-importance: ['funding_dist', 'spread_bps', 'manip_suspect', 'book_touch_share', 'other_ret_6_dir', 'ret_1_dir'] ...
- **INFO** plateau[position_sizer.min_p_win] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[profit_taking.chandelier_k] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[pretrade.min_edge_cost_ratio] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** dsr — DEFERRED — 9 conviction-marked live trades < 30 (mixed n=255); mixed-sample dsr=0.000 sr=-0.69; probes are EV-mixed by design (PT-050); gate arms as conviction labels accrue
- **INFO** regime diagnostic caveat — stratum auc/brier below are concatenated-OOF over all scored rows, while the pooled figures they're compared against are MEAN-OF-FOLDS (OF-1's own convention) — the delta is indicative, not a rebasing of the same statistic
- **INFO** regime diagnostic caveat — n= below is a raw signal_history.csv count (candidate+live); oof_n= is the deduped/purged X actually OOF-scored — two different counting passes over related but non-identical data
- **INFO** regime[bull_quiet] — n=0 — absent from corpus
- **INFO** regime[bull_vol] — n=0 — absent from corpus
- **INFO** regime[range] — n=5414 (candidate=5167 live=247) base_rate=0.199
- **INFO** regime[range] oof — oof_n=880 auc=0.494 (pooled 0.521, delta_auc=-0.028) brier=0.2431 (pooled 0.2460, delta_brier=-0.0029)
- **INFO** regime[bear] — n=1557 (candidate=1549 live=8) base_rate=0.208
- **INFO** regime[bear] FLAG — insufficient live coverage (8 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[bear] oof — oof_n=805 auc=0.516 (pooled 0.521, delta_auc=-0.006) brier=0.2492 (pooled 0.2460, delta_brier=+0.0032)
- **INFO** regime[crisis] — n=0 — absent from corpus
- **INFO** regime[unknown] — n=0 — absent from corpus
- **INFO** learning curve caveat — each point refits gbt on a chronological PREFIX of the corpus (time-purged OOF, deployed protocol) — points are the same statistic across sizes, but none is OF-1's own pooled number
- **INFO** lc[n=506] — oof_n=420 auc=0.491 brier=0.2484
- **INFO** lc[n=809] — oof_n=670 auc=0.538 brier=0.2403
- **INFO** lc[n=1112] — oof_n=925 auc=0.445 brier=0.2576
- **INFO** lc[n=1415] — oof_n=1175 auc=0.482 brier=0.2425
- **INFO** lc[n=1719] — oof_n=1430 auc=0.498 brier=0.2410
- **INFO** lc[n=2022] — oof_n=1685 auc=0.481 brier=0.2484
- **INFO** learning curve trend — FLAT (|delta_auc=-0.025| <= 0.03) — representation-limited: more rows alone are not buying skill; feature/label quality is the binding constraint, not corpus size
- **INFO** extras[equity_risk_z] — at-neutral share 100.0% (n=2022) — feed effectively dark corpus-wide (dead column)
- **INFO** extras[opt_pcr_z] — at-neutral share 100.0% (n=2022) — feed effectively dark corpus-wide (dead column)
- **INFO** extras[opt_oi_pcr_z] — at-neutral share 100.0% (n=2022) — feed effectively dark corpus-wide (dead column)
- **INFO** extras[dominance_delta] — at-neutral share 8.3% (n=2022) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[sent_fear] — at-neutral share 100.0% (n=2022) — feed effectively dark corpus-wide (dead column)
- **INFO** extras[fear_greed] — at-neutral share 0.0% (n=2022) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance

3 passed, 4 failed (36s)

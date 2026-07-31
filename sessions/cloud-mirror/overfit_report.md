# Overfit audit — 2026-07-30 23:52 UTC

Dataset: live history (1990 rows)

- **FAIL** gap[logistic]: OOF gap within memorization band — train_auc=0.745 oof_auc=0.521 gap=+0.225
- **FAIL** gap[gbt]: OOF gap within memorization band — train_auc=0.705 oof_auc=0.502 gap=+0.203
- **FAIL** gap[mlp]: OOF gap within memorization band — train_auc=0.724 oof_auc=0.520 gap=+0.205
- **PASS** shuffle: destroyed labels learn nothing OOF — mean_auc=0.500 z=0.0 (limit 3.0)
- **INFO** pbo space — ml.adaptive_gbt.enabled=true — the adaptive rung is IN the measured selection space
- **INFO** pbo — evidence-gated to a single family (no model selection to overfit at this live-row count) (space=['logistic'])
- **PASS** purge: never manufactures out-of-sample edge — unpurged=0.486 purged=0.492 leak_closed=-0.006
- **INFO** purge note — expanding-window design keeps boundary leak ~0 by construction; shuffle-null [OF-2] is the leak gate
- **PASS** dof: not starved (>=10 rows per feature) — rows/feature=32.1 (1990 rows / 62 features)
- **FAIL** dof: dead-feature fraction under 55% (live data) — dead_frac=0.58 (36 near-zero-importance features)
- **INFO** dof note — low/zero-importance: ['other_ret_6_dir', 'imbalance_delta_dir', 'th_barclose', 'hour_sin', 'th_stopzone', 'fv_edge_bps'] ...
- **INFO** plateau[position_sizer.min_p_win] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[profit_taking.chandelier_k] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[pretrade.min_edge_cost_ratio] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** dsr — DEFERRED — 9 conviction-marked live trades < 30 (mixed n=255); mixed-sample dsr=0.000 sr=-0.69; probes are EV-mixed by design (PT-050); gate arms as conviction labels accrue
- **INFO** regime diagnostic caveat — stratum auc/brier below are concatenated-OOF over all scored rows, while the pooled figures they're compared against are MEAN-OF-FOLDS (OF-1's own convention) — the delta is indicative, not a rebasing of the same statistic
- **INFO** regime diagnostic caveat — n= below is a raw signal_history.csv count (candidate+live); oof_n= is the deduped/purged X actually OOF-scored — two different counting passes over related but non-identical data
- **INFO** regime[bull_quiet] — n=0 — absent from corpus
- **INFO** regime[bull_vol] — n=0 — absent from corpus
- **INFO** regime[range] — n=5403 (candidate=5156 live=247) base_rate=0.198
- **INFO** regime[range] oof — oof_n=875 auc=0.474 (pooled 0.502, delta_auc=-0.028) brier=0.2446 (pooled 0.2470, delta_brier=-0.0023)
- **INFO** regime[bear] — n=1536 (candidate=1528 live=8) base_rate=0.207
- **INFO** regime[bear] FLAG — insufficient live coverage (8 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[bear] oof — oof_n=780 auc=0.511 (pooled 0.502, delta_auc=+0.009) brier=0.2496 (pooled 0.2470, delta_brier=+0.0026)
- **INFO** regime[crisis] — n=0 — absent from corpus
- **INFO** regime[unknown] — n=0 — absent from corpus
- **INFO** learning curve caveat — each point refits gbt on a chronological PREFIX of the corpus (time-purged OOF, deployed protocol) — points are the same statistic across sizes, but none is OF-1's own pooled number
- **INFO** lc[n=498] — oof_n=415 auc=0.473 brier=0.2509
- **INFO** lc[n=796] — oof_n=660 auc=0.532 brier=0.2415
- **INFO** lc[n=1094] — oof_n=910 auc=0.440 brier=0.2489
- **INFO** lc[n=1393] — oof_n=1160 auc=0.508 brier=0.2395
- **INFO** lc[n=1692] — oof_n=1410 auc=0.513 brier=0.2344
- **INFO** lc[n=1990] — oof_n=1655 auc=0.495 brier=0.2482
- **INFO** learning curve trend — FLAT (|delta_auc=+0.001| <= 0.03) — representation-limited: more rows alone are not buying skill; feature/label quality is the binding constraint, not corpus size
- **INFO** extras[equity_risk_z] — at-neutral share 100.0% (n=1990) — feed effectively dark corpus-wide (dead column)
- **INFO** extras[opt_pcr_z] — at-neutral share 100.0% (n=1990) — feed effectively dark corpus-wide (dead column)
- **INFO** extras[opt_oi_pcr_z] — at-neutral share 100.0% (n=1990) — feed effectively dark corpus-wide (dead column)
- **INFO** extras[dominance_delta] — at-neutral share 8.2% (n=1990) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[sent_fear] — at-neutral share 100.0% (n=1990) — feed effectively dark corpus-wide (dead column)
- **INFO** extras[fear_greed] — at-neutral share 0.0% (n=1990) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance

3 passed, 4 failed (31s)

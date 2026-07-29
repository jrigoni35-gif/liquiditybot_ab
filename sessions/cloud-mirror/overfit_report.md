# Overfit audit — 2026-07-29 21:48 UTC

Dataset: live history (1490 rows)

- **FAIL** gap[logistic]: OOF gap within memorization band — train_auc=0.791 oof_auc=0.492 gap=+0.299
- **FAIL** gap[gbt]: OOF gap within memorization band — train_auc=0.759 oof_auc=0.516 gap=+0.243
- **FAIL** gap[mlp]: OOF gap within memorization band — train_auc=0.753 oof_auc=0.464 gap=+0.289
- **PASS** shuffle: destroyed labels learn nothing OOF — mean_auc=0.506 z=0.6 (limit 3.0)
- **INFO** pbo space — ml.adaptive_gbt.enabled=true — the adaptive rung is IN the measured selection space
- **INFO** pbo — evidence-gated to a single family (no model selection to overfit at this live-row count) (space=['logistic'])
- **PASS** purge: never manufactures out-of-sample edge — unpurged=0.486 purged=0.492 leak_closed=-0.006
- **INFO** purge note — expanding-window design keeps boundary leak ~0 by construction; shuffle-null [OF-2] is the leak gate
- **PASS** dof: not starved (>=10 rows per feature) — rows/feature=24.0 (1490 rows / 62 features)
- **FAIL** dof: dead-feature fraction under 55% (live data) — dead_frac=0.71 (44 near-zero-importance features)
- **INFO** dof note — low/zero-importance: ['fv_edge_bps', 'funding_dir', 'gate_confidence', 'mom_dir', 'ret_1_dir', 'ret_12_dir'] ...
- **INFO** plateau[position_sizer.min_p_win] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[profit_taking.chandelier_k] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[pretrade.min_edge_cost_ratio] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** dsr — DEFERRED — 9 conviction-marked live trades < 30 (mixed n=253); mixed-sample dsr=0.000 sr=-0.69; probes are EV-mixed by design (PT-050); gate arms as conviction labels accrue
- **INFO** regime diagnostic caveat — stratum auc/brier below are concatenated-OOF over all scored rows, while the pooled figures they're compared against are MEAN-OF-FOLDS (OF-1's own convention) — the delta is indicative, not a rebasing of the same statistic
- **INFO** regime diagnostic caveat — n= below is a raw signal_history.csv count (candidate+live); oof_n= is the deduped/purged X actually OOF-scored — two different counting passes over related but non-identical data
- **INFO** regime[bull_quiet] — n=0 — absent from corpus
- **INFO** regime[bull_vol] — n=0 — absent from corpus
- **INFO** regime[range] — n=5154 (candidate=4908 live=246) base_rate=0.200
- **INFO** regime[range] oof — oof_n=669 auc=0.501 (pooled 0.516, delta_auc=-0.015) brier=0.2613 (pooled 0.2559, delta_brier=+0.0053)
- **INFO** regime[bear] — n=1282 (candidate=1275 live=7) base_rate=0.202
- **INFO** regime[bear] FLAG — insufficient live coverage (7 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[bear] oof — oof_n=571 auc=0.539 (pooled 0.516, delta_auc=+0.023) brier=0.2497 (pooled 0.2559, delta_brier=-0.0063)
- **INFO** regime[crisis] — n=0 — absent from corpus
- **INFO** regime[unknown] — n=0 — absent from corpus
- **INFO** learning curve caveat — each point refits gbt on a chronological PREFIX of the corpus (time-purged OOF, deployed protocol) — points are the same statistic across sizes, but none is OF-1's own pooled number
- **INFO** lc[n=372] — oof_n=248 auc=0.555 brier=0.2393
- **INFO** lc[n=596] — oof_n=495 auc=0.467 brier=0.2503
- **INFO** lc[n=820] — oof_n=680 auc=0.494 brier=0.2458
- **INFO** lc[n=1043] — oof_n=865 auc=0.493 brier=0.2404
- **INFO** lc[n=1266] — oof_n=1055 auc=0.505 brier=0.2412
- **INFO** lc[n=1490] — oof_n=1240 auc=0.492 brier=0.2422
- **INFO** learning curve trend — FLAT (|delta_auc=-0.013| <= 0.03) — representation-limited: more rows alone are not buying skill; feature/label quality is the binding constraint, not corpus size
- **INFO** extras[equity_risk_z] — at-neutral share 100.0% (n=1490) — feed effectively dark corpus-wide (dead column)
- **INFO** extras[opt_pcr_z] — at-neutral share 100.0% (n=1490) — feed effectively dark corpus-wide (dead column)
- **INFO** extras[opt_oi_pcr_z] — at-neutral share 100.0% (n=1490) — feed effectively dark corpus-wide (dead column)
- **INFO** extras[dominance_delta] — at-neutral share 8.9% (n=1490) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[sent_fear] — at-neutral share 100.0% (n=1490) — feed effectively dark corpus-wide (dead column)
- **INFO** extras[fear_greed] — at-neutral share 0.0% (n=1490) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance

3 passed, 4 failed (21s)

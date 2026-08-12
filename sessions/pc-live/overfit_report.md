# Overfit audit — 2026-08-12 00:28 UTC

Dataset: live history (1054 rows)

- **INFO** gap[logistic] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.833 oof_auc=0.431 gap=+0.401; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** gap[gbt] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.823 oof_auc=0.461 gap=+0.362; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** gap[mlp] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.854 oof_auc=0.460 gap=+0.394; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** null-floor[logistic] — OOF Brier 0.4003 vs base-rate constant 0.2373 (base=0.387, n=700) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **INFO** null-floor[gbt] — OOF Brier 0.2694 vs base-rate constant 0.2373 (base=0.387, n=700) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **INFO** null-floor[mlp] — OOF Brier 0.4302 vs base-rate constant 0.2373 (base=0.387, n=700) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **PASS** shuffle: destroyed labels learn nothing OOF — mean_auc=0.505 z=0.5 (limit 3.0)
- **INFO** pbo space — ml.adaptive_gbt.enabled=true — the adaptive rung is IN the measured selection space
- **INFO** pbo — evidence-gated to a single family (no model selection to overfit at this live-row count) (space=['logistic'])
- **PASS** purge: never manufactures out-of-sample edge — unpurged=0.486 purged=0.492 leak_closed=-0.006
- **INFO** purge note — expanding-window design keeps boundary leak ~0 by construction; shuffle-null [OF-2] is the leak gate
- **PASS** dof: not starved (>=10 rows per feature) — rows/feature=16.5 (1054 rows / 64 features)
- **INFO** dof: dead-feature fraction (exploration — informational) — dead_frac=0.58 (37 near-zero-importance features) — arms when ml.exploration.enabled is false; reduce the schema (prune experiment) or grow the corpus
- **INFO** dof note — low/zero-importance: ['fv_edge_bps', 'depth_log', 'basis_dir', 'th_barclose', 'flow_tox', 'funding_dir'] ...
- **INFO** plateau[position_sizer.min_p_win] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[profit_taking.chandelier_k] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[pretrade.min_edge_cost_ratio] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** dsr — DEFERRED — 21 conviction-marked live trades < 30 (mixed n=313); mixed-sample dsr=0.000 sr=-0.50; probes are EV-mixed by design (PT-050); gate arms as conviction labels accrue
- **INFO** regime diagnostic caveat — stratum auc/brier below are concatenated-OOF over all scored rows, while the pooled figures they're compared against are MEAN-OF-FOLDS (OF-1's own convention) — the delta is indicative, not a rebasing of the same statistic
- **INFO** regime diagnostic caveat — n= below is a raw signal_history.csv count (candidate+live); oof_n= is the deduped/purged X actually OOF-scored — two different counting passes over related but non-identical data
- **INFO** regime[bull_quiet] — n=90 (candidate=88 live=2) base_rate=0.256
- **INFO** regime[bull_quiet] FLAG — insufficient live coverage (2 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[bull_quiet] oof — oof_n=89 auc=0.637 (pooled 0.461, delta_auc=+0.176) brier=0.2424 (pooled 0.2694, delta_brier=-0.0271)
- **INFO** regime[bull_vol] — n=8 (candidate=8 live=0) base_rate=0.375
- **INFO** regime[bull_vol] FLAG — insufficient live coverage (0 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[bull_vol] oof — oof_n=1 < 30 — insufficient OOF evidence, not scored
- **INFO** regime[range] — n=6637 (candidate=6365 live=272) base_rate=0.205
- **INFO** regime[range] oof — oof_n=231 auc=0.472 (pooled 0.461, delta_auc=+0.011) brier=0.2549 (pooled 0.2694, delta_brier=-0.0145)
- **INFO** regime[bear] — n=3512 (candidate=3473 live=39) base_rate=0.222
- **INFO** regime[bear] oof — oof_n=379 auc=0.422 (pooled 0.461, delta_auc=-0.039) brier=0.2851 (pooled 0.2694, delta_brier=+0.0157)
- **INFO** regime[crisis] — n=0 — absent from corpus
- **INFO** regime[unknown] — n=0 — absent from corpus
- **INFO** learning curve caveat — each point refits gbt on a chronological PREFIX of the corpus (time-purged OOF, deployed protocol) — points are the same statistic across sizes, but none is OF-1's own pooled number
- **INFO** lc[n=264] — oof_n=44 auc=0.415 brier=0.3837
- **INFO** lc[n=422] — oof_n=210 auc=0.450 brier=0.3093
- **INFO** lc[n=580] — oof_n=288 auc=0.463 brier=0.3004
- **INFO** lc[n=738] — oof_n=492 auc=0.471 brier=0.2839
- **INFO** lc[n=896] — oof_n=596 auc=0.408 brier=0.2828
- **INFO** lc[n=1054] — oof_n=700 auc=0.461 brier=0.2694
- **INFO** learning curve trend — FLAT (|delta_auc=+0.002| <= 0.03) — representation-limited: more rows alone are not buying skill; feature/label quality is the binding constraint, not corpus size
- **INFO** extras[equity_risk_z] — at-neutral share 81.1% (n=1054)
- **INFO** extras[opt_pcr_z] — at-neutral share 82.7% (n=1054)
- **INFO** extras[opt_oi_pcr_z] — at-neutral share 90.9% (n=1054)
- **INFO** extras[dominance_delta] — at-neutral share 6.0% (n=1054) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[sent_fear] — at-neutral share 100.0% (n=1054) — feed effectively dark corpus-wide (dead column)
- **INFO** extras[fear_greed] — at-neutral share 0.0% (n=1054) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance

3 passed, 0 failed (47s)

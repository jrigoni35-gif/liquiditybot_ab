# Overfit audit — 2026-08-11 01:32 UTC

Dataset: live history (968 rows)

- **INFO** gap[logistic] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.833 oof_auc=0.455 gap=+0.378; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** gap[gbt] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.818 oof_auc=0.421 gap=+0.397; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** gap[mlp] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.903 oof_auc=0.472 gap=+0.431; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** null-floor[logistic] — OOF Brier 0.4104 vs base-rate constant 0.2330 (base=0.370, n=644) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **INFO** null-floor[gbt] — OOF Brier 0.2743 vs base-rate constant 0.2330 (base=0.370, n=644) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **INFO** null-floor[mlp] — OOF Brier 0.4310 vs base-rate constant 0.2330 (base=0.370, n=644) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **PASS** shuffle: destroyed labels learn nothing OOF — mean_auc=0.500 z=0.0 (limit 3.0)
- **INFO** pbo space — ml.adaptive_gbt.enabled=true — the adaptive rung is IN the measured selection space
- **INFO** pbo — evidence-gated to a single family (no model selection to overfit at this live-row count) (space=['logistic'])
- **PASS** purge: never manufactures out-of-sample edge — unpurged=0.486 purged=0.492 leak_closed=-0.006
- **INFO** purge note — expanding-window design keeps boundary leak ~0 by construction; shuffle-null [OF-2] is the leak gate
- **PASS** dof: not starved (>=10 rows per feature) — rows/feature=15.1 (968 rows / 64 features)
- **INFO** dof: dead-feature fraction (exploration — informational) — dead_frac=0.58 (37 near-zero-importance features) — arms when ml.exploration.enabled is false; reduce the schema (prune experiment) or grow the corpus
- **INFO** dof note — low/zero-importance: ['basis_mom_dir', 'regime_bear', 'depth_ratio', 'regime_range', 'mkt_ret_6_dir', 'mom_dir'] ...
- **INFO** plateau[position_sizer.min_p_win] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[profit_taking.chandelier_k] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[pretrade.min_edge_cost_ratio] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** dsr — DEFERRED — 21 conviction-marked live trades < 30 (mixed n=313); mixed-sample dsr=0.000 sr=-0.50; probes are EV-mixed by design (PT-050); gate arms as conviction labels accrue
- **INFO** regime diagnostic caveat — stratum auc/brier below are concatenated-OOF over all scored rows, while the pooled figures they're compared against are MEAN-OF-FOLDS (OF-1's own convention) — the delta is indicative, not a rebasing of the same statistic
- **INFO** regime diagnostic caveat — n= below is a raw signal_history.csv count (candidate+live); oof_n= is the deduped/purged X actually OOF-scored — two different counting passes over related but non-identical data
- **INFO** regime[bull_quiet] — n=88 (candidate=86 live=2) base_rate=0.239
- **INFO** regime[bull_quiet] FLAG — insufficient live coverage (2 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[bull_quiet] oof — oof_n=87 auc=0.577 (pooled 0.421, delta_auc=+0.156) brier=0.2536 (pooled 0.2743, delta_brier=-0.0206)
- **INFO** regime[bull_vol] — n=8 (candidate=8 live=0) base_rate=0.375
- **INFO** regime[bull_vol] FLAG — insufficient live coverage (0 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[bull_vol] oof — oof_n=1 < 30 — insufficient OOF evidence, not scored
- **INFO** regime[range] — n=6621 (candidate=6349 live=272) base_rate=0.204
- **INFO** regime[range] oof — oof_n=214 auc=0.371 (pooled 0.421, delta_auc=-0.050) brier=0.2660 (pooled 0.2743, delta_brier=-0.0082)
- **INFO** regime[bear] — n=3444 (candidate=3405 live=39) base_rate=0.219
- **INFO** regime[bear] oof — oof_n=342 auc=0.422 (pooled 0.421, delta_auc=+0.001) brier=0.2853 (pooled 0.2743, delta_brier=+0.0110)
- **INFO** regime[crisis] — n=0 — absent from corpus
- **INFO** regime[unknown] — n=0 — absent from corpus
- **INFO** learning curve caveat — each point refits gbt on a chronological PREFIX of the corpus (time-purged OOF, deployed protocol) — points are the same statistic across sizes, but none is OF-1's own pooled number
- **INFO** lc[n=242] — oof_n=40 auc=0.501 brier=0.3266
- **INFO** lc[n=387] — oof_n=128 auc=0.387 brier=0.3166
- **INFO** lc[n=532] — oof_n=264 auc=0.462 brier=0.3025
- **INFO** lc[n=678] — oof_n=452 auc=0.424 brier=0.2962
- **INFO** lc[n=823] — oof_n=548 auc=0.480 brier=0.2717
- **INFO** lc[n=968] — oof_n=644 auc=0.422 brier=0.2743
- **INFO** learning curve trend — FLAT (|delta_auc=+0.006| <= 0.03) — representation-limited: more rows alone are not buying skill; feature/label quality is the binding constraint, not corpus size
- **INFO** extras[equity_risk_z] — at-neutral share 87.2% (n=968)
- **INFO** extras[opt_pcr_z] — at-neutral share 88.8% (n=968)
- **INFO** extras[opt_oi_pcr_z] — at-neutral share 97.7% (n=968) — feed effectively dark corpus-wide (dead column)
- **INFO** extras[dominance_delta] — at-neutral share 5.6% (n=968) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[sent_fear] — at-neutral share 100.0% (n=968) — feed effectively dark corpus-wide (dead column)
- **INFO** extras[fear_greed] — at-neutral share 0.0% (n=968) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance

3 passed, 0 failed (41s)

# Overfit audit — 2026-08-19 21:25 UTC

Dataset: live history (2410 rows)

- **INFO** gap[logistic] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.774 oof_auc=0.412 gap=+0.363; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** gap[gbt] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.862 oof_auc=0.414 gap=+0.448; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** gap[mlp] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.900 oof_auc=0.522 gap=+0.378; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** null-floor[logistic] — OOF Brier 0.3665 vs base-rate constant 0.2488 (base=0.466, n=2005) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **INFO** null-floor[gbt] — OOF Brier 0.2754 vs base-rate constant 0.2488 (base=0.466, n=2005) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **INFO** null-floor[mlp] — OOF Brier 0.3586 vs base-rate constant 0.2488 (base=0.466, n=2005) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **PASS** shuffle: destroyed labels learn nothing OOF — mean_auc=0.497 z=0.4 (limit 3.0)
- **INFO** pbo space — ml.adaptive_gbt.enabled=true — the adaptive rung is IN the measured selection space
- **INFO** pbo — evidence-gated to a single family (no model selection to overfit at this live-row count) (space=['logistic'])
- **PASS** purge: never manufactures out-of-sample edge — unpurged=0.486 purged=0.492 leak_closed=-0.006
- **INFO** purge note — expanding-window design keeps boundary leak ~0 by construction; shuffle-null [OF-2] is the leak gate
- **PASS** dof: not starved (>=10 rows per feature) — rows/feature=37.7 (2410 rows / 64 features)
- **INFO** dof: dead-feature fraction (exploration — informational) — dead_frac=0.61 (39 near-zero-importance features) — arms when ml.exploration.enabled is false; reduce the schema (prune experiment) or grow the corpus
- **INFO** dof note — low/zero-importance: ['corr_fast', 'basis_dir', 'hour_sin', 'ret_12_dir', 'pd_zone', 'imbalance_dir'] ...
- **INFO** plateau[position_sizer.min_p_win] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[profit_taking.chandelier_k] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[pretrade.min_edge_cost_ratio] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** dsr — DEFERRED — 26 conviction-marked live trades < 30 (mixed n=343); mixed-sample dsr=0.000 sr=-0.37; probes are EV-mixed by design (PT-050); gate arms as conviction labels accrue
- **INFO** regime diagnostic caveat — stratum auc/brier below are concatenated-OOF over all scored rows, while the pooled figures they're compared against are MEAN-OF-FOLDS (OF-1's own convention) — the delta is indicative, not a rebasing of the same statistic
- **INFO** regime diagnostic caveat — n= below is a raw signal_history.csv count (candidate+live); oof_n= is the deduped/purged X actually OOF-scored — two different counting passes over related but non-identical data
- **INFO** regime[bull_quiet] — n=549 (candidate=542 live=7) base_rate=0.397
- **INFO** regime[bull_quiet] FLAG — insufficient live coverage (7 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[bull_quiet] oof — oof_n=381 auc=0.386 (pooled 0.414, delta_auc=-0.029) brier=0.2914 (pooled 0.2754, delta_brier=+0.0160)
- **INFO** regime[bull_vol] — n=12 (candidate=12 live=0) base_rate=0.250
- **INFO** regime[bull_vol] FLAG — insufficient live coverage (0 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[bull_vol] oof — oof_n=0 < 30 — insufficient OOF evidence, not scored
- **INFO** regime[range] — n=7303 (candidate=7018 live=285) base_rate=0.222
- **INFO** regime[range] oof — oof_n=501 auc=0.481 (pooled 0.414, delta_auc=+0.067) brier=0.2759 (pooled 0.2754, delta_brier=+0.0005)
- **INFO** regime[bear] — n=4864 (candidate=4813 live=51) base_rate=0.285
- **INFO** regime[bear] oof — oof_n=1123 auc=0.471 (pooled 0.414, delta_auc=+0.057) brier=0.2698 (pooled 0.2754, delta_brier=-0.0056)
- **INFO** regime[crisis] — n=0 — absent from corpus
- **INFO** regime[unknown] — n=0 — absent from corpus
- **INFO** learning curve caveat — each point refits gbt on a chronological PREFIX of the corpus (time-purged OOF, deployed protocol) — points are the same statistic across sizes, but none is OF-1's own pooled number
- **INFO** lc[n=602] — oof_n=400 auc=0.491 brier=0.2648
- **INFO** lc[n=964] — oof_n=800 auc=0.477 brier=0.2581
- **INFO** lc[n=1326] — oof_n=1105 auc=0.514 brier=0.2630
- **INFO** lc[n=1687] — oof_n=1405 auc=0.588 brier=0.2435
- **INFO** lc[n=2048] — oof_n=1705 auc=0.515 brier=0.2668
- **INFO** lc[n=2410] — oof_n=2005 auc=0.462 brier=0.2754
- **INFO** learning curve trend — FLAT (|delta_auc=+0.004| <= 0.03) — representation-limited: more rows alone are not buying skill; feature/label quality is the binding constraint, not corpus size
- **INFO** extras[equity_risk_z] — at-neutral share 55.3% (n=2410)
- **INFO** extras[opt_pcr_z] — at-neutral share 56.3% (n=2410)
- **INFO** extras[opt_oi_pcr_z] — at-neutral share 56.3% (n=2410)
- **INFO** extras[dominance_delta] — at-neutral share 5.8% (n=2410) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[sent_fear] — at-neutral share 100.0% (n=2410) — feed effectively dark corpus-wide (dead column)
- **INFO** extras[fear_greed] — at-neutral share 0.0% (n=2410) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance

3 passed, 0 failed (39s)

Corpus: live history (2410 rows)

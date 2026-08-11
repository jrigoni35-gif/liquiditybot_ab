# Overfit audit — 2026-08-11 02:58 UTC

Dataset: live history (972 rows)

- **INFO** gap[logistic] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.834 oof_auc=0.455 gap=+0.378; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** gap[gbt] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.829 oof_auc=0.421 gap=+0.409; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** gap[mlp] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.870 oof_auc=0.457 gap=+0.413; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** null-floor[logistic] — OOF Brier 0.4094 vs base-rate constant 0.2328 (base=0.369, n=648) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **INFO** null-floor[gbt] — OOF Brier 0.2819 vs base-rate constant 0.2328 (base=0.369, n=648) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **INFO** null-floor[mlp] — OOF Brier 0.4330 vs base-rate constant 0.2328 (base=0.369, n=648) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **PASS** shuffle: destroyed labels learn nothing OOF — mean_auc=0.519 z=1.7 (limit 3.0)
- **INFO** pbo space — ml.adaptive_gbt.enabled=true — the adaptive rung is IN the measured selection space
- **INFO** pbo — evidence-gated to a single family (no model selection to overfit at this live-row count) (space=['logistic'])
- **PASS** purge: never manufactures out-of-sample edge — unpurged=0.486 purged=0.492 leak_closed=-0.006
- **INFO** purge note — expanding-window design keeps boundary leak ~0 by construction; shuffle-null [OF-2] is the leak gate
- **PASS** dof: not starved (>=10 rows per feature) — rows/feature=15.2 (972 rows / 64 features)
- **INFO** dof: dead-feature fraction (exploration — informational) — dead_frac=0.58 (37 near-zero-importance features) — arms when ml.exploration.enabled is false; reduce the schema (prune experiment) or grow the corpus
- **INFO** dof note — low/zero-importance: ['imbalance_delta_dir', 'basis_mom_dir', 'depth_ratio', 'mom_dir', 'book_touch_share', 'th_barclose'] ...
- **INFO** plateau[position_sizer.min_p_win] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[profit_taking.chandelier_k] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[pretrade.min_edge_cost_ratio] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** dsr — DEFERRED — 21 conviction-marked live trades < 30 (mixed n=313); mixed-sample dsr=0.000 sr=-0.50; probes are EV-mixed by design (PT-050); gate arms as conviction labels accrue
- **INFO** regime diagnostic caveat — stratum auc/brier below are concatenated-OOF over all scored rows, while the pooled figures they're compared against are MEAN-OF-FOLDS (OF-1's own convention) — the delta is indicative, not a rebasing of the same statistic
- **INFO** regime diagnostic caveat — n= below is a raw signal_history.csv count (candidate+live); oof_n= is the deduped/purged X actually OOF-scored — two different counting passes over related but non-identical data
- **INFO** regime[bull_quiet] — n=88 (candidate=86 live=2) base_rate=0.239
- **INFO** regime[bull_quiet] FLAG — insufficient live coverage (2 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[bull_quiet] oof — oof_n=87 auc=0.394 (pooled 0.421, delta_auc=-0.027) brier=0.2815 (pooled 0.2819, delta_brier=-0.0004)
- **INFO** regime[bull_vol] — n=8 (candidate=8 live=0) base_rate=0.375
- **INFO** regime[bull_vol] FLAG — insufficient live coverage (0 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[bull_vol] oof — oof_n=1 < 30 — insufficient OOF evidence, not scored
- **INFO** regime[range] — n=6623 (candidate=6351 live=272) base_rate=0.204
- **INFO** regime[range] oof — oof_n=218 auc=0.405 (pooled 0.421, delta_auc=-0.016) brier=0.2702 (pooled 0.2819, delta_brier=-0.0117)
- **INFO** regime[bear] — n=3446 (candidate=3407 live=39) base_rate=0.219
- **INFO** regime[bear] oof — oof_n=342 auc=0.396 (pooled 0.421, delta_auc=-0.025) brier=0.2898 (pooled 0.2819, delta_brier=+0.0079)
- **INFO** regime[crisis] — n=0 — absent from corpus
- **INFO** regime[unknown] — n=0 — absent from corpus
- **INFO** learning curve caveat — each point refits gbt on a chronological PREFIX of the corpus (time-purged OOF, deployed protocol) — points are the same statistic across sizes, but none is OF-1's own pooled number
- **INFO** lc[n=243] — oof_n=40 auc=0.501 brier=0.3266
- **INFO** lc[n=389] — oof_n=128 auc=0.387 brier=0.3166
- **INFO** lc[n=535] — oof_n=267 auc=0.440 brier=0.3086
- **INFO** lc[n=680] — oof_n=452 auc=0.424 brier=0.2962
- **INFO** lc[n=826] — oof_n=548 auc=0.480 brier=0.2717
- **INFO** lc[n=972] — oof_n=648 auc=0.394 brier=0.2819
- **INFO** learning curve trend — FLAT (|delta_auc=-0.007| <= 0.03) — representation-limited: more rows alone are not buying skill; feature/label quality is the binding constraint, not corpus size
- **INFO** extras[equity_risk_z] — at-neutral share 86.9% (n=972)
- **INFO** extras[opt_pcr_z] — at-neutral share 88.6% (n=972)
- **INFO** extras[opt_oi_pcr_z] — at-neutral share 97.4% (n=972) — feed effectively dark corpus-wide (dead column)
- **INFO** extras[dominance_delta] — at-neutral share 5.7% (n=972) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[sent_fear] — at-neutral share 100.0% (n=972) — feed effectively dark corpus-wide (dead column)
- **INFO** extras[fear_greed] — at-neutral share 0.0% (n=972) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance

3 passed, 0 failed (39s)

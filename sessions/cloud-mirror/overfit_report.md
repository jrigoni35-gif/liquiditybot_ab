# Overfit audit — 2026-08-27 02:59 UTC

Dataset: live history (7211 rows)

- **INFO** gap[logistic] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.835 oof_auc=0.472 gap=+0.363; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** gap[gbt] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.856 oof_auc=0.569 gap=+0.287; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** gap[mlp] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.897 oof_auc=0.591 gap=+0.306; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** null-floor[logistic] — OOF Brier 0.3830 vs base-rate constant 0.2499 (base=0.511, n=6005) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **INFO** null-floor[gbt] — OOF Brier 0.2463 vs base-rate constant 0.2499 (base=0.511, n=6005) — BEATS the null
- **INFO** null-floor[mlp] — OOF Brier 0.2939 vs base-rate constant 0.2499 (base=0.511, n=6005) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **PASS** shuffle: destroyed labels learn nothing OOF — mean_auc=0.493 z=1.8 (limit 3.0)
- **INFO** pbo space — ml.adaptive_gbt.enabled=true — the adaptive rung is IN the measured selection space
- **INFO** pbo — evidence-gated to a single family (no model selection to overfit at this live-row count) (space=['logistic'])
- **PASS** purge: never manufactures out-of-sample edge — unpurged=0.486 purged=0.492 leak_closed=-0.006
- **INFO** purge note — expanding-window design keeps boundary leak ~0 by construction; shuffle-null [OF-2] is the leak gate
- **PASS** dof: not starved (>=10 rows per feature) — rows/feature=112.7 (7211 rows / 64 features)
- **INFO** dof: dead-feature fraction (exploration — informational) — dead_frac=0.83 (53 near-zero-importance features) — arms when ml.exploration.enabled is false; reduce the schema (prune experiment) or grow the corpus
- **INFO** dof note — low/zero-importance: ['ret_6_dir', 'ret_48_dir', 'equity_risk_z', 'ret_1_dir', 'ret_12_dir', 'imbalance_dir'] ...
- **INFO** plateau[position_sizer.min_p_win] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[profit_taking.chandelier_k] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[pretrade.min_edge_cost_ratio] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** dsr — DEFERRED — 26 conviction-marked live trades < 30 (mixed n=367); mixed-sample dsr=0.000 sr=-0.38; probes are EV-mixed by design (PT-050); gate arms as conviction labels accrue
- **INFO** regime diagnostic caveat — stratum auc/brier below are concatenated-OOF over all scored rows, while the pooled figures they're compared against are MEAN-OF-FOLDS (OF-1's own convention) — the delta is indicative, not a rebasing of the same statistic
- **INFO** regime diagnostic caveat — n= below is a raw signal_history.csv count (candidate+live); oof_n= is the deduped/purged X actually OOF-scored — two different counting passes over related but non-identical data
- **INFO** regime[bull_quiet] — n=862 (candidate=853 live=9) base_rate=0.361
- **INFO** regime[bull_quiet] FLAG — insufficient live coverage (9 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[bull_quiet] oof — oof_n=530 auc=0.602 (pooled 0.569, delta_auc=+0.033) brier=0.2461 (pooled 0.2463, delta_brier=-0.0002)
- **INFO** regime[bull_vol] — n=923 (candidate=916 live=7) base_rate=0.475
- **INFO** regime[bull_vol] FLAG — insufficient live coverage (7 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[bull_vol] oof — oof_n=823 auc=0.623 (pooled 0.569, delta_auc=+0.054) brier=0.2283 (pooled 0.2463, delta_brier=-0.0180)
- **INFO** regime[range] — n=8002 (candidate=7707 live=295) base_rate=0.238
- **INFO** regime[range] oof — oof_n=839 auc=0.584 (pooled 0.569, delta_auc=+0.015) brier=0.2499 (pooled 0.2463, delta_brier=+0.0036)
- **INFO** regime[bear] — n=5898 (candidate=5842 live=56) base_rate=0.321
- **INFO** regime[bear] oof — oof_n=1627 auc=0.482 (pooled 0.569, delta_auc=-0.087) brier=0.2527 (pooled 0.2463, delta_brier=+0.0064)
- **INFO** regime[crisis] — n=2187 (candidate=2187 live=0) base_rate=0.515
- **INFO** regime[crisis] FLAG — insufficient live coverage (0 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[crisis] oof — oof_n=2186 auc=0.597 (pooled 0.569, delta_auc=+0.028) brier=0.2470 (pooled 0.2463, delta_brier=+0.0007)
- **INFO** regime[unknown] — n=0 — absent from corpus
- **INFO** learning curve caveat — each point refits gbt on a chronological PREFIX of the corpus (time-purged OOF, deployed protocol) — points are the same statistic across sizes, but none is OF-1's own pooled number
- **INFO** lc[n=1803] — oof_n=1500 auc=0.517 brier=0.2681
- **INFO** lc[n=2884] — oof_n=2400 auc=0.594 brier=0.2438
- **INFO** lc[n=3966] — oof_n=3305 auc=0.620 brier=0.2325
- **INFO** lc[n=5048] — oof_n=4205 auc=0.616 brier=0.2455
- **INFO** lc[n=6129] — oof_n=5105 auc=0.578 brier=0.2581
- **INFO** lc[n=7211] — oof_n=6005 auc=0.590 brier=0.2463
- **INFO** learning curve trend — FLAT (|delta_auc=+0.028| <= 0.03) — representation-limited: more rows alone are not buying skill; feature/label quality is the binding constraint, not corpus size
- **INFO** extras[equity_risk_z] — at-neutral share 27.5% (n=7211) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[opt_pcr_z] — at-neutral share 28.0% (n=7211) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[opt_oi_pcr_z] — at-neutral share 28.0% (n=7211) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[dominance_delta] — at-neutral share 3.3% (n=7211) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[sent_fear] — at-neutral share 100.0% (n=7211) — feed effectively dark corpus-wide (dead column)
- **INFO** extras[fear_greed] — at-neutral share 0.0% (n=7211) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance

3 passed, 0 failed (45s)

Corpus: live history (7211 rows)

# Overfit audit — 2026-08-30 13:34 UTC

Dataset: live history (9468 rows)

- **INFO** gap[logistic] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.803 oof_auc=0.498 gap=+0.304; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** gap[gbt] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.826 oof_auc=0.474 gap=+0.352; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** gap[mlp] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.803 oof_auc=0.523 gap=+0.280; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** null-floor[logistic] — OOF Brier 0.3280 vs base-rate constant 0.2494 (base=0.476, n=7890) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **INFO** null-floor[gbt] — OOF Brier 0.2555 vs base-rate constant 0.2494 (base=0.476, n=7890) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **INFO** null-floor[mlp] — OOF Brier 0.3379 vs base-rate constant 0.2494 (base=0.476, n=7890) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **PASS** shuffle: destroyed labels learn nothing OOF — mean_auc=0.501 z=0.2 (limit 3.0)
- **INFO** pbo space — ml.adaptive_gbt.enabled=true — the adaptive rung is IN the measured selection space
- **INFO** pbo — evidence-gated to a single family (no model selection to overfit at this live-row count) (space=['logistic'])
- **PASS** purge: never manufactures out-of-sample edge — unpurged=0.486 purged=0.492 leak_closed=-0.006
- **INFO** purge note — expanding-window design keeps boundary leak ~0 by construction; shuffle-null [OF-2] is the leak gate
- **PASS** dof: not starved (>=10 rows per feature) — rows/feature=147.9 (9468 rows / 64 features)
- **INFO** dof: dead-feature fraction (exploration — informational) — dead_frac=0.98 (63 near-zero-importance features) — arms when ml.exploration.enabled is false; reduce the schema (prune experiment) or grow the corpus
- **INFO** dof note — low/zero-importance: ['ret_1_dir', 'ret_6_dir', 'ret_12_dir', 'ret_48_dir', 'sigma_bar_pct', 'vol_percentile'] ...
- **INFO** plateau[position_sizer.min_p_win] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[profit_taking.chandelier_k] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[pretrade.min_edge_cost_ratio] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** OF-5 trials: assumed N=7 (no ledger at C:\Users\haird\Documents\liquiditybot\liquiditybot_ab\outputs\trial_ledger.csv; var=SR^2 fallback)
- **INFO** dsr — DEFERRED — 26 conviction-marked live trades < 30 (mixed n=378); mixed-sample dsr=0.000 sr=-0.39; probes are EV-mixed by design (PT-050); gate arms as conviction labels accrue
- **INFO** regime diagnostic caveat — stratum auc/brier below are concatenated-OOF over all scored rows, while the pooled figures they're compared against are MEAN-OF-FOLDS (OF-1's own convention) — the delta is indicative, not a rebasing of the same statistic
- **INFO** regime diagnostic caveat — n= below is a raw signal_history.csv count (candidate+live); oof_n= is the deduped/purged X actually OOF-scored — two different counting passes over related but non-identical data
- **INFO** regime[bull_quiet] — n=1462 (candidate=1451 live=11) base_rate=0.363
- **INFO** regime[bull_quiet] FLAG — insufficient live coverage (11 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[bull_quiet] oof — oof_n=1099 auc=0.435 (pooled 0.474, delta_auc=-0.039) brier=0.2589 (pooled 0.2555, delta_brier=+0.0034)
- **INFO** regime[bull_vol] — n=1258 (candidate=1248 live=10) base_rate=0.446
- **INFO** regime[bull_vol] FLAG — insufficient live coverage (10 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[bull_vol] oof — oof_n=1236 auc=0.607 (pooled 0.474, delta_auc=+0.133) brier=0.2427 (pooled 0.2555, delta_brier=-0.0128)
- **INFO** regime[range] — n=8612 (candidate=8312 live=300) base_rate=0.260
- **INFO** regime[range] oof — oof_n=1494 auc=0.443 (pooled 0.474, delta_auc=-0.031) brier=0.2606 (pooled 0.2555, delta_brier=+0.0051)
- **INFO** regime[bear] — n=6310 (candidate=6253 live=57) base_rate=0.321
- **INFO** regime[bear] oof — oof_n=1874 auc=0.491 (pooled 0.474, delta_auc=+0.017) brier=0.2695 (pooled 0.2555, delta_brier=+0.0141)
- **INFO** regime[crisis] — n=2187 (candidate=2187 live=0) base_rate=0.515
- **INFO** regime[crisis] FLAG — insufficient live coverage (0 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[crisis] oof — oof_n=2187 auc=0.601 (pooled 0.474, delta_auc=+0.128) brier=0.2454 (pooled 0.2555, delta_brier=-0.0101)
- **INFO** regime[unknown] — n=0 — absent from corpus
- **INFO** learning curve caveat — each point refits gbt on a chronological PREFIX of the corpus (time-purged OOF, deployed protocol) — points are the same statistic across sizes, but none is OF-1's own pooled number
- **INFO** lc[n=2367] — oof_n=1970 auc=0.478 brier=0.2677
- **INFO** lc[n=3787] — oof_n=3155 auc=0.665 brier=0.2231
- **INFO** lc[n=5207] — oof_n=4335 auc=0.623 brier=0.2432
- **INFO** lc[n=6628] — oof_n=5520 auc=0.573 brier=0.2527
- **INFO** lc[n=8048] — oof_n=6705 auc=0.608 brier=0.2531
- **INFO** lc[n=9468] — oof_n=7890 auc=0.546 brier=0.2555
- **INFO** learning curve trend — FLAT (|delta_auc=+0.005| <= 0.03) — representation-limited: more rows alone are not buying skill; feature/label quality is the binding constraint, not corpus size
- **INFO** extras[equity_risk_z] — at-neutral share 32.4% (n=9468) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[opt_pcr_z] — at-neutral share 32.8% (n=9468) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[opt_oi_pcr_z] — at-neutral share 32.8% (n=9468) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[dominance_delta] — at-neutral share 3.1% (n=9468) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[sent_fear] — at-neutral share 100.0% (n=9468) — feed effectively dark corpus-wide (dead column)
- **INFO** extras[fear_greed] — at-neutral share 0.0% (n=9468) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance

3 passed, 0 failed (47s)

Corpus: live history (9468 rows)

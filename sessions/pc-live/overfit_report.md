# Overfit audit — 2026-08-28 02:59 UTC

Dataset: live history (8294 rows)

- **INFO** gap[logistic] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.823 oof_auc=0.489 gap=+0.334; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** gap[gbt] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.826 oof_auc=0.561 gap=+0.265; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** gap[mlp] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.855 oof_auc=0.531 gap=+0.325; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** null-floor[logistic] — OOF Brier 0.3589 vs base-rate constant 0.2500 (base=0.505, n=6910) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **INFO** null-floor[gbt] — OOF Brier 0.2569 vs base-rate constant 0.2500 (base=0.505, n=6910) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **INFO** null-floor[mlp] — OOF Brier 0.3736 vs base-rate constant 0.2500 (base=0.505, n=6910) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **PASS** shuffle: destroyed labels learn nothing OOF — mean_auc=0.504 z=1.0 (limit 3.0)
- **INFO** pbo space — ml.adaptive_gbt.enabled=true — the adaptive rung is IN the measured selection space
- **INFO** pbo — evidence-gated to a single family (no model selection to overfit at this live-row count) (space=['logistic'])
- **PASS** purge: never manufactures out-of-sample edge — unpurged=0.486 purged=0.492 leak_closed=-0.006
- **INFO** purge note — expanding-window design keeps boundary leak ~0 by construction; shuffle-null [OF-2] is the leak gate
- **PASS** dof: not starved (>=10 rows per feature) — rows/feature=129.6 (8294 rows / 64 features)
- **INFO** dof: dead-feature fraction (exploration — informational) — dead_frac=0.97 (62 near-zero-importance features) — arms when ml.exploration.enabled is false; reduce the schema (prune experiment) or grow the corpus
- **INFO** dof note — low/zero-importance: ['ret_1_dir', 'ret_6_dir', 'ret_12_dir', 'ret_48_dir', 'sigma_bar_pct', 'vol_percentile'] ...
- **INFO** plateau[position_sizer.min_p_win] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[profit_taking.chandelier_k] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[pretrade.min_edge_cost_ratio] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** dsr — DEFERRED — 26 conviction-marked live trades < 30 (mixed n=375); mixed-sample dsr=0.000 sr=-0.38; probes are EV-mixed by design (PT-050); gate arms as conviction labels accrue
- **INFO** regime diagnostic caveat — stratum auc/brier below are concatenated-OOF over all scored rows, while the pooled figures they're compared against are MEAN-OF-FOLDS (OF-1's own convention) — the delta is indicative, not a rebasing of the same statistic
- **INFO** regime diagnostic caveat — n= below is a raw signal_history.csv count (candidate+live); oof_n= is the deduped/purged X actually OOF-scored — two different counting passes over related but non-identical data
- **INFO** regime[bull_quiet] — n=1103 (candidate=1093 live=10) base_rate=0.399
- **INFO** regime[bull_quiet] FLAG — insufficient live coverage (10 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[bull_quiet] oof — oof_n=779 auc=0.632 (pooled 0.561, delta_auc=+0.071) brier=0.2480 (pooled 0.2569, delta_brier=-0.0089)
- **INFO** regime[bull_vol] — n=1057 (candidate=1048 live=9) base_rate=0.470
- **INFO** regime[bull_vol] FLAG — insufficient live coverage (9 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[bull_vol] oof — oof_n=1035 auc=0.586 (pooled 0.561, delta_auc=+0.026) brier=0.2424 (pooled 0.2569, delta_brier=-0.0145)
- **INFO** regime[range] — n=8298 (candidate=7999 live=299) base_rate=0.250
- **INFO** regime[range] oof — oof_n=1182 auc=0.550 (pooled 0.561, delta_auc=-0.011) brier=0.2612 (pooled 0.2569, delta_brier=+0.0043)
- **INFO** regime[bear] — n=6008 (candidate=5951 live=57) base_rate=0.326
- **INFO** regime[bear] oof — oof_n=1727 auc=0.504 (pooled 0.561, delta_auc=-0.057) brier=0.2621 (pooled 0.2569, delta_brier=+0.0051)
- **INFO** regime[crisis] — n=2187 (candidate=2187 live=0) base_rate=0.515
- **INFO** regime[crisis] FLAG — insufficient live coverage (0 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[crisis] oof — oof_n=2187 auc=0.565 (pooled 0.561, delta_auc=+0.004) brier=0.2606 (pooled 0.2569, delta_brier=+0.0037)
- **INFO** regime[unknown] — n=0 — absent from corpus
- **INFO** learning curve caveat — each point refits gbt on a chronological PREFIX of the corpus (time-purged OOF, deployed protocol) — points are the same statistic across sizes, but none is OF-1's own pooled number
- **INFO** lc[n=2074] — oof_n=1725 auc=0.491 brier=0.2651
- **INFO** lc[n=3318] — oof_n=2765 auc=0.643 brier=0.2335
- **INFO** lc[n=4562] — oof_n=3800 auc=0.660 brier=0.2273
- **INFO** lc[n=5806] — oof_n=4835 auc=0.611 brier=0.2445
- **INFO** lc[n=7050] — oof_n=5875 auc=0.529 brier=0.2572
- **INFO** lc[n=8294] — oof_n=6910 auc=0.598 brier=0.2569
- **INFO** learning curve trend — FLAT (|delta_auc=-0.003| <= 0.03) — representation-limited: more rows alone are not buying skill; feature/label quality is the binding constraint, not corpus size
- **INFO** extras[equity_risk_z] — at-neutral share 26.3% (n=8294) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[opt_pcr_z] — at-neutral share 26.8% (n=8294) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[opt_oi_pcr_z] — at-neutral share 26.8% (n=8294) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[dominance_delta] — at-neutral share 3.1% (n=8294) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[sent_fear] — at-neutral share 100.0% (n=8294) — feed effectively dark corpus-wide (dead column)
- **INFO** extras[fear_greed] — at-neutral share 0.0% (n=8294) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance

3 passed, 0 failed (50s)

Corpus: live history (8294 rows)

# Overfit audit — 2026-09-07 00:51 UTC

Dataset: live history (15719 rows)

- **INFO** gap[logistic] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.767 oof_auc=0.531 gap=+0.236; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** gap[gbt] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.769 oof_auc=0.570 gap=+0.199; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** gap[mlp] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.761 oof_auc=0.539 gap=+0.223; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** null-floor[logistic] — OOF Brier 0.3063 vs base-rate constant 0.2475 (base=0.450, n=13095) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **INFO** null-floor[gbt] — OOF Brier 0.2464 vs base-rate constant 0.2475 (base=0.450, n=13095) — BEATS the null
- **INFO** null-floor[mlp] — OOF Brier 0.3074 vs base-rate constant 0.2475 (base=0.450, n=13095) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **PASS** shuffle: destroyed labels learn nothing OOF — mean_auc=0.500 z=0.1 (limit 3.0)
- **INFO** pbo space — ml.adaptive_gbt.enabled=true — the adaptive rung is IN the measured selection space
- **INFO** pbo — evidence-gated to a single family (no model selection to overfit at this live-row count) (space=['logistic'])
- **PASS** purge: never manufactures out-of-sample edge — unpurged=0.486 purged=0.492 leak_closed=-0.006
- **INFO** purge note — expanding-window design keeps boundary leak ~0 by construction; shuffle-null [OF-2] is the leak gate
- **PASS** dof: not starved (>=10 rows per feature) — rows/feature=245.6 (15719 rows / 64 features)
- **INFO** dof COVERAGE — dead-feature scan UNINFORMATIVE: the fitted GBT consulted only 24/64 features (40 of the 57 'dead' were never split on at all). Read dead_feature_frac as the model's blindness, not the features' deadness; the clustered-MDA report (scripts/interpret_report.py) is the honest ranking.
- **INFO** dof: dead-feature fraction (exploration — informational) — dead_frac=0.89 (57 near-zero-importance features) — arms when ml.exploration.enabled is false; reduce the schema (prune experiment) or grow the corpus
- **INFO** dof note — low/zero-importance: ['basis_dir', 'va_pos', 'hour_sin', 'funding_dir', 'sigma_bar_pct', 'ret_1_dir'] ...
- **INFO** plateau[position_sizer.min_p_win] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[profit_taking.chandelier_k] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[pretrade.min_edge_cost_ratio] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** OF-5 trials: assumed N=7 (no ledger at C:\Users\haird\Documents\liquiditybot\liquiditybot_ab\outputs\trial_ledger.csv; var=SR^2 fallback)
- **INFO** dsr REACHABILITY — UNPASSABLE at N=7: the var_trial_sr=SR^2 fallback makes sr0 = 1.387x|SR|, so the rejection threshold scales with the statistic and dsr>=0.90 is attainable for NO sample (exhaustive sweep 2026-08-31: 0/518616 combinations pass at N=7, max dsr 0.4262). This gate cannot produce a green — read any OF-5 line below as INERT, not as evidence. Repair needs a var_trial_sr MEASURED from per-trial SR (trial_ledger v0.1 records none), never a threshold move.
- **INFO** dsr — DEFERRED — 28 conviction-marked live trades < 30 (mixed n=412); mixed-sample dsr=0.000 sr=-0.37; probes are EV-mixed by design (PT-050); gate arms as conviction labels accrue
- **INFO** regime diagnostic caveat — stratum auc/brier below are concatenated-OOF over all scored rows, while the pooled figures they're compared against are MEAN-OF-FOLDS (OF-1's own convention) — the delta is indicative, not a rebasing of the same statistic
- **INFO** regime diagnostic caveat — n= below is a raw signal_history.csv count (candidate+live); oof_n= is the deduped/purged X actually OOF-scored — two different counting passes over related but non-identical data
- **INFO** regime[bull_quiet] — n=3233 (candidate=3213 live=20) base_rate=0.407
- **INFO** regime[bull_quiet] FLAG — insufficient live coverage (20 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[bull_quiet] oof — oof_n=2654 auc=0.589 (pooled 0.570, delta_auc=+0.020) brier=0.2515 (pooled 0.2464, delta_brier=+0.0051)
- **INFO** regime[bull_vol] — n=1736 (candidate=1723 live=13) base_rate=0.455
- **INFO** regime[bull_vol] FLAG — insufficient live coverage (13 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[bull_vol] oof — oof_n=1711 auc=0.533 (pooled 0.570, delta_auc=-0.037) brier=0.2475 (pooled 0.2464, delta_brier=+0.0011)
- **INFO** regime[range] — n=10471 (candidate=10155 live=316) base_rate=0.300
- **INFO** regime[range] oof — oof_n=3092 auc=0.610 (pooled 0.570, delta_auc=+0.040) brier=0.2449 (pooled 0.2464, delta_brier=-0.0016)
- **INFO** regime[bear] — n=7139 (candidate=7076 live=63) base_rate=0.337
- **INFO** regime[bear] oof — oof_n=2144 auc=0.546 (pooled 0.570, delta_auc=-0.024) brier=0.2528 (pooled 0.2464, delta_brier=+0.0063)
- **INFO** regime[crisis] — n=3542 (candidate=3542 live=0) base_rate=0.465
- **INFO** regime[crisis] FLAG — insufficient live coverage (0 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[crisis] oof — oof_n=3494 auc=0.663 (pooled 0.570, delta_auc=+0.093) brier=0.2395 (pooled 0.2464, delta_brier=-0.0069)
- **INFO** regime[unknown] — n=0 — absent from corpus
- **INFO** learning curve caveat — each point refits gbt on a chronological PREFIX of the corpus (time-purged OOF, deployed protocol) — points are the same statistic across sizes, but none is OF-1's own pooled number
- **INFO** lc[n=3930] — oof_n=3275 auc=0.689 brier=0.2170
- **INFO** lc[n=6288] — oof_n=5240 auc=0.569 brier=0.2572
- **INFO** lc[n=8645] — oof_n=7200 auc=0.533 brier=0.2639
- **INFO** lc[n=11003] — oof_n=9165 auc=0.513 brier=0.2629
- **INFO** lc[n=13361] — oof_n=11130 auc=0.588 brier=0.2514
- **INFO** lc[n=15719] — oof_n=13095 auc=0.605 brier=0.2464
- **INFO** learning curve trend FLAG — DECLINING (delta_auc=-0.032 < -0.03) — later rows are HURTING skill: regime/era drift inside the training window (check ML-080 mix drift and era_exclusion)
- **INFO** extras[equity_risk_z] — at-neutral share 28.1% (n=15719) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[opt_pcr_z] — at-neutral share 28.5% (n=15719) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[opt_oi_pcr_z] — at-neutral share 28.5% (n=15719) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[dominance_delta] — at-neutral share 2.3% (n=15719) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[sent_fear] — at-neutral share 100.0% (n=15719) — feed effectively dark corpus-wide (dead column)
- **INFO** extras[fear_greed] — at-neutral share 0.0% (n=15719) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance

3 passed, 0 failed (78s)

Corpus: live history (15719 rows)

# Overfit audit — 2026-08-29 18:16 UTC

Dataset: live history (8961 rows)

- **INFO** gap[logistic] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.810 oof_auc=0.492 gap=+0.318; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** gap[gbt] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.846 oof_auc=0.502 gap=+0.344; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** gap[mlp] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.806 oof_auc=0.500 gap=+0.306; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** null-floor[logistic] — OOF Brier 0.3340 vs base-rate constant 0.2500 (base=0.495, n=7465) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **INFO** null-floor[gbt] — OOF Brier 0.2809 vs base-rate constant 0.2500 (base=0.495, n=7465) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **INFO** null-floor[mlp] — OOF Brier 0.3375 vs base-rate constant 0.2500 (base=0.495, n=7465) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **PASS** shuffle: destroyed labels learn nothing OOF — mean_auc=0.503 z=0.8 (limit 3.0)
- **INFO** pbo space — ml.adaptive_gbt.enabled=true — the adaptive rung is IN the measured selection space
- **INFO** pbo — evidence-gated to a single family (no model selection to overfit at this live-row count) (space=['logistic'])
- **PASS** purge: never manufactures out-of-sample edge — unpurged=0.486 purged=0.492 leak_closed=-0.006
- **INFO** purge note — expanding-window design keeps boundary leak ~0 by construction; shuffle-null [OF-2] is the leak gate
- **PASS** dof: not starved (>=10 rows per feature) — rows/feature=140.0 (8961 rows / 64 features)
- **INFO** dof: dead-feature fraction (exploration — informational) — dead_frac=0.97 (62 near-zero-importance features) — arms when ml.exploration.enabled is false; reduce the schema (prune experiment) or grow the corpus
- **INFO** dof note — low/zero-importance: ['ret_1_dir', 'ret_6_dir', 'ret_12_dir', 'ret_48_dir', 'sigma_bar_pct', 'vol_percentile'] ...
- **INFO** plateau[position_sizer.min_p_win] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[profit_taking.chandelier_k] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[pretrade.min_edge_cost_ratio] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** OF-5 trials: assumed N=7 (no ledger at C:\Users\haird\Documents\liquiditybot\liquiditybot_ab\outputs\trial_ledger.csv; var=SR^2 fallback)
- **INFO** dsr — DEFERRED — 26 conviction-marked live trades < 30 (mixed n=376); mixed-sample dsr=0.000 sr=-0.39; probes are EV-mixed by design (PT-050); gate arms as conviction labels accrue
- **INFO** regime diagnostic caveat — stratum auc/brier below are concatenated-OOF over all scored rows, while the pooled figures they're compared against are MEAN-OF-FOLDS (OF-1's own convention) — the delta is indicative, not a rebasing of the same statistic
- **INFO** regime diagnostic caveat — n= below is a raw signal_history.csv count (candidate+live); oof_n= is the deduped/purged X actually OOF-scored — two different counting passes over related but non-identical data
- **INFO** regime[bull_quiet] — n=1332 (candidate=1322 live=10) base_rate=0.372
- **INFO** regime[bull_quiet] FLAG — insufficient live coverage (10 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[bull_quiet] oof — oof_n=984 auc=0.400 (pooled 0.502, delta_auc=-0.102) brier=0.2892 (pooled 0.2809, delta_brier=+0.0082)
- **INFO** regime[bull_vol] — n=1185 (candidate=1176 live=9) base_rate=0.459
- **INFO** regime[bull_vol] FLAG — insufficient live coverage (9 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[bull_vol] oof — oof_n=1163 auc=0.574 (pooled 0.502, delta_auc=+0.072) brier=0.2723 (pooled 0.2809, delta_brier=-0.0086)
- **INFO** regime[range] — n=8546 (candidate=8246 live=300) base_rate=0.259
- **INFO** regime[range] oof — oof_n=1428 auc=0.431 (pooled 0.502, delta_auc=-0.071) brier=0.2905 (pooled 0.2809, delta_brier=+0.0096)
- **INFO** regime[bear] — n=6072 (candidate=6015 live=57) base_rate=0.327
- **INFO** regime[bear] oof — oof_n=1703 auc=0.414 (pooled 0.502, delta_auc=-0.088) brier=0.3067 (pooled 0.2809, delta_brier=+0.0257)
- **INFO** regime[crisis] — n=2187 (candidate=2187 live=0) base_rate=0.515
- **INFO** regime[crisis] FLAG — insufficient live coverage (0 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[crisis] oof — oof_n=2187 auc=0.545 (pooled 0.502, delta_auc=+0.043) brier=0.2555 (pooled 0.2809, delta_brier=-0.0254)
- **INFO** regime[unknown] — n=0 — absent from corpus
- **INFO** learning curve caveat — each point refits gbt on a chronological PREFIX of the corpus (time-purged OOF, deployed protocol) — points are the same statistic across sizes, but none is OF-1's own pooled number
- **INFO** lc[n=2240] — oof_n=1865 auc=0.491 brier=0.2761
- **INFO** lc[n=3584] — oof_n=2985 auc=0.539 brier=0.2625
- **INFO** lc[n=4929] — oof_n=4105 auc=0.546 brier=0.2791
- **INFO** lc[n=6273] — oof_n=5225 auc=0.568 brier=0.2612
- **INFO** lc[n=7617] — oof_n=6345 auc=0.634 brier=0.2408
- **INFO** lc[n=8961] — oof_n=7465 auc=0.500 brier=0.2809
- **INFO** learning curve trend — CLIMBING (delta_auc=+0.052 > +0.03) — data-starved: more rows are still buying skill; corpus growth is the highest-leverage learning input right now
- **INFO** extras[equity_risk_z] — at-neutral share 28.6% (n=8961) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[opt_pcr_z] — at-neutral share 29.0% (n=8961) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[opt_oi_pcr_z] — at-neutral share 29.0% (n=8961) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[dominance_delta] — at-neutral share 3.2% (n=8961) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[sent_fear] — at-neutral share 100.0% (n=8961) — feed effectively dark corpus-wide (dead column)
- **INFO** extras[fear_greed] — at-neutral share 0.0% (n=8961) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance

3 passed, 0 failed (47s)

Corpus: live history (8961 rows)

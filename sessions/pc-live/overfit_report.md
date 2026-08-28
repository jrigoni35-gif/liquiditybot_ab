# Overfit audit — 2026-08-28 22:29 UTC

Dataset: live history (8723 rows)

- **INFO** gap[logistic] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.809 oof_auc=0.494 gap=+0.315; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** gap[gbt] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.824 oof_auc=0.522 gap=+0.302; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** gap[mlp] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.817 oof_auc=0.524 gap=+0.293; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** null-floor[logistic] — OOF Brier 0.3287 vs base-rate constant 0.2499 (base=0.490, n=7265) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **INFO** null-floor[gbt] — OOF Brier 0.2622 vs base-rate constant 0.2499 (base=0.490, n=7265) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **INFO** null-floor[mlp] — OOF Brier 0.3616 vs base-rate constant 0.2499 (base=0.490, n=7265) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **PASS** shuffle: destroyed labels learn nothing OOF — mean_auc=0.499 z=0.2 (limit 3.0)
- **INFO** pbo space — ml.adaptive_gbt.enabled=true — the adaptive rung is IN the measured selection space
- **INFO** pbo — evidence-gated to a single family (no model selection to overfit at this live-row count) (space=['logistic'])
- **PASS** purge: never manufactures out-of-sample edge — unpurged=0.486 purged=0.492 leak_closed=-0.006
- **INFO** purge note — expanding-window design keeps boundary leak ~0 by construction; shuffle-null [OF-2] is the leak gate
- **PASS** dof: not starved (>=10 rows per feature) — rows/feature=136.3 (8723 rows / 64 features)
- **INFO** dof: dead-feature fraction (exploration — informational) — dead_frac=0.97 (62 near-zero-importance features) — arms when ml.exploration.enabled is false; reduce the schema (prune experiment) or grow the corpus
- **INFO** dof note — low/zero-importance: ['ret_1_dir', 'ret_6_dir', 'ret_12_dir', 'ret_48_dir', 'sigma_bar_pct', 'imbalance_dir'] ...
- **INFO** plateau[position_sizer.min_p_win] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[profit_taking.chandelier_k] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[pretrade.min_edge_cost_ratio] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** OF-5 trials: assumed N=7 (no ledger at C:\Users\haird\Documents\liquiditybot\liquiditybot_ab\outputs\trial_ledger.csv; var=SR^2 fallback)
- **INFO** dsr — DEFERRED — 26 conviction-marked live trades < 30 (mixed n=375); mixed-sample dsr=0.000 sr=-0.38; probes are EV-mixed by design (PT-050); gate arms as conviction labels accrue
- **INFO** regime diagnostic caveat — stratum auc/brier below are concatenated-OOF over all scored rows, while the pooled figures they're compared against are MEAN-OF-FOLDS (OF-1's own convention) — the delta is indicative, not a rebasing of the same statistic
- **INFO** regime diagnostic caveat — n= below is a raw signal_history.csv count (candidate+live); oof_n= is the deduped/purged X actually OOF-scored — two different counting passes over related but non-identical data
- **INFO** regime[bull_quiet] — n=1269 (candidate=1259 live=10) base_rate=0.354
- **INFO** regime[bull_quiet] FLAG — insufficient live coverage (10 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[bull_quiet] oof — oof_n=930 auc=0.450 (pooled 0.522, delta_auc=-0.072) brier=0.2826 (pooled 0.2622, delta_brier=+0.0204)
- **INFO** regime[bull_vol] — n=1116 (candidate=1107 live=9) base_rate=0.458
- **INFO** regime[bull_vol] FLAG — insufficient live coverage (9 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[bull_vol] oof — oof_n=1089 auc=0.597 (pooled 0.522, delta_auc=+0.075) brier=0.2321 (pooled 0.2622, delta_brier=-0.0301)
- **INFO** regime[range] — n=8463 (candidate=8164 live=299) base_rate=0.253
- **INFO** regime[range] oof — oof_n=1346 auc=0.445 (pooled 0.522, delta_auc=-0.078) brier=0.2699 (pooled 0.2622, delta_brier=+0.0076)
- **INFO** regime[bear] — n=6047 (candidate=5990 live=57) base_rate=0.325
- **INFO** regime[bear] oof — oof_n=1713 auc=0.414 (pooled 0.522, delta_auc=-0.108) brier=0.2879 (pooled 0.2622, delta_brier=+0.0257)
- **INFO** regime[crisis] — n=2187 (candidate=2187 live=0) base_rate=0.515
- **INFO** regime[crisis] FLAG — insufficient live coverage (0 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[crisis] oof — oof_n=2187 auc=0.574 (pooled 0.522, delta_auc=+0.052) brier=0.2438 (pooled 0.2622, delta_brier=-0.0185)
- **INFO** regime[unknown] — n=0 — absent from corpus
- **INFO** learning curve caveat — each point refits gbt on a chronological PREFIX of the corpus (time-purged OOF, deployed protocol) — points are the same statistic across sizes, but none is OF-1's own pooled number
- **INFO** lc[n=2181] — oof_n=1815 auc=0.478 brier=0.2813
- **INFO** lc[n=3489] — oof_n=2905 auc=0.601 brier=0.2396
- **INFO** lc[n=4798] — oof_n=3995 auc=0.593 brier=0.2529
- **INFO** lc[n=6106] — oof_n=5085 auc=0.587 brier=0.2560
- **INFO** lc[n=7415] — oof_n=6175 auc=0.559 brier=0.2541
- **INFO** lc[n=8723] — oof_n=7265 auc=0.538 brier=0.2622
- **INFO** learning curve trend — FLAT (|delta_auc=+0.009| <= 0.03) — representation-limited: more rows alone are not buying skill; feature/label quality is the binding constraint, not corpus size
- **INFO** extras[equity_risk_z] — at-neutral share 27.9% (n=8723) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[opt_pcr_z] — at-neutral share 28.3% (n=8723) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[opt_oi_pcr_z] — at-neutral share 28.3% (n=8723) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[dominance_delta] — at-neutral share 3.1% (n=8723) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[sent_fear] — at-neutral share 100.0% (n=8723) — feed effectively dark corpus-wide (dead column)
- **INFO** extras[fear_greed] — at-neutral share 0.0% (n=8723) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance

3 passed, 0 failed (50s)

Corpus: live history (8723 rows)

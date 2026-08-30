# Overfit audit — 2026-08-30 22:48 UTC

Dataset: live history (10416 rows)

- **INFO** gap[logistic] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.797 oof_auc=0.494 gap=+0.302; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** gap[gbt] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.809 oof_auc=0.519 gap=+0.290; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** gap[mlp] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.806 oof_auc=0.527 gap=+0.279; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** null-floor[logistic] — OOF Brier 0.3373 vs base-rate constant 0.2487 (base=0.463, n=8680) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **INFO** null-floor[gbt] — OOF Brier 0.2587 vs base-rate constant 0.2487 (base=0.463, n=8680) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **INFO** null-floor[mlp] — OOF Brier 0.3080 vs base-rate constant 0.2487 (base=0.463, n=8680) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **PASS** shuffle: destroyed labels learn nothing OOF — mean_auc=0.500 z=0.1 (limit 3.0)
- **INFO** pbo space — ml.adaptive_gbt.enabled=true — the adaptive rung is IN the measured selection space
- **INFO** pbo — evidence-gated to a single family (no model selection to overfit at this live-row count) (space=['logistic'])
- **PASS** purge: never manufactures out-of-sample edge — unpurged=0.486 purged=0.492 leak_closed=-0.006
- **INFO** purge note — expanding-window design keeps boundary leak ~0 by construction; shuffle-null [OF-2] is the leak gate
- **PASS** dof: not starved (>=10 rows per feature) — rows/feature=162.8 (10416 rows / 64 features)
- **INFO** dof: dead-feature fraction (exploration — informational) — dead_frac=0.97 (62 near-zero-importance features) — arms when ml.exploration.enabled is false; reduce the schema (prune experiment) or grow the corpus
- **INFO** dof note — low/zero-importance: ['ret_1_dir', 'ret_6_dir', 'ret_12_dir', 'ret_48_dir', 'sigma_bar_pct', 'vol_percentile'] ...
- **INFO** plateau[position_sizer.min_p_win] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[profit_taking.chandelier_k] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[pretrade.min_edge_cost_ratio] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** OF-5 trials: assumed N=7 (no ledger at C:\Users\haird\Documents\liquiditybot\liquiditybot_ab\outputs\trial_ledger.csv; var=SR^2 fallback)
- **INFO** dsr — DEFERRED — 26 conviction-marked live trades < 30 (mixed n=385); mixed-sample dsr=0.000 sr=-0.39; probes are EV-mixed by design (PT-050); gate arms as conviction labels accrue
- **INFO** regime diagnostic caveat — stratum auc/brier below are concatenated-OOF over all scored rows, while the pooled figures they're compared against are MEAN-OF-FOLDS (OF-1's own convention) — the delta is indicative, not a rebasing of the same statistic
- **INFO** regime diagnostic caveat — n= below is a raw signal_history.csv count (candidate+live); oof_n= is the deduped/purged X actually OOF-scored — two different counting passes over related but non-identical data
- **INFO** regime[bull_quiet] — n=1892 (candidate=1880 live=12) base_rate=0.360
- **INFO** regime[bull_quiet] FLAG — insufficient live coverage (12 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[bull_quiet] oof — oof_n=1491 auc=0.550 (pooled 0.519, delta_auc=+0.031) brier=0.2418 (pooled 0.2587, delta_brier=-0.0169)
- **INFO** regime[bull_vol] — n=1356 (candidate=1346 live=10) base_rate=0.460
- **INFO** regime[bull_vol] FLAG — insufficient live coverage (10 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[bull_vol] oof — oof_n=1334 auc=0.562 (pooled 0.519, delta_auc=+0.043) brier=0.2448 (pooled 0.2587, delta_brier=-0.0139)
- **INFO** regime[range] — n=8992 (candidate=8686 live=306) base_rate=0.262
- **INFO** regime[range] oof — oof_n=1802 auc=0.557 (pooled 0.519, delta_auc=+0.037) brier=0.2457 (pooled 0.2587, delta_brier=-0.0130)
- **INFO** regime[bear] — n=6359 (candidate=6302 live=57) base_rate=0.320
- **INFO** regime[bear] oof — oof_n=1866 auc=0.494 (pooled 0.519, delta_auc=-0.026) brier=0.2617 (pooled 0.2587, delta_brier=+0.0030)
- **INFO** regime[crisis] — n=2187 (candidate=2187 live=0) base_rate=0.515
- **INFO** regime[crisis] FLAG — insufficient live coverage (0 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[crisis] oof — oof_n=2187 auc=0.535 (pooled 0.519, delta_auc=+0.016) brier=0.2868 (pooled 0.2587, delta_brier=+0.0281)
- **INFO** regime[unknown] — n=0 — absent from corpus
- **INFO** learning curve caveat — each point refits gbt on a chronological PREFIX of the corpus (time-purged OOF, deployed protocol) — points are the same statistic across sizes, but none is OF-1's own pooled number
- **INFO** lc[n=2604] — oof_n=2170 auc=0.440 brier=0.2700
- **INFO** lc[n=4166] — oof_n=3470 auc=0.637 brier=0.2288
- **INFO** lc[n=5729] — oof_n=4770 auc=0.613 brier=0.2465
- **INFO** lc[n=7291] — oof_n=6075 auc=0.540 brier=0.2573
- **INFO** lc[n=8854] — oof_n=7375 auc=0.542 brier=0.2522
- **INFO** lc[n=10416] — oof_n=8680 auc=0.538 brier=0.2587
- **INFO** learning curve trend — FLAT (|delta_auc=+0.001| <= 0.03) — representation-limited: more rows alone are not buying skill; feature/label quality is the binding constraint, not corpus size
- **INFO** extras[equity_risk_z] — at-neutral share 38.5% (n=10416) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[opt_pcr_z] — at-neutral share 38.9% (n=10416) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[opt_oi_pcr_z] — at-neutral share 38.9% (n=10416) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[dominance_delta] — at-neutral share 2.9% (n=10416) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[sent_fear] — at-neutral share 100.0% (n=10416) — feed effectively dark corpus-wide (dead column)
- **INFO** extras[fear_greed] — at-neutral share 0.0% (n=10416) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance

3 passed, 0 failed (56s)

Corpus: live history (10416 rows)

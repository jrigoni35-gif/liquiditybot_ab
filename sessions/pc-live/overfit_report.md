# Overfit audit — 2026-09-10 10:41 UTC

Dataset: live history (17337 rows)

- **INFO** gap[logistic] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.762 oof_auc=0.547 gap=+0.216; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** gap[gbt] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.784 oof_auc=0.560 gap=+0.224; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** gap[mlp] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.764 oof_auc=0.544 gap=+0.220; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** null-floor[logistic] — OOF Brier 0.2689 vs base-rate constant 0.2446 (base=0.427, n=14445) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **INFO** null-floor[gbt] — OOF Brier 0.2436 vs base-rate constant 0.2446 (base=0.427, n=14445) — BEATS the null
- **INFO** null-floor[mlp] — OOF Brier 0.3028 vs base-rate constant 0.2446 (base=0.427, n=14445) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **PASS** shuffle: destroyed labels learn nothing OOF — mean_auc=0.501 z=0.3 (limit 3.0)
- **INFO** pbo space — ml.adaptive_gbt.enabled=true — the adaptive rung is IN the measured selection space
- **INFO** pbo — evidence-gated to a single family (no model selection to overfit at this live-row count) (space=['logistic'])
- **PASS** purge: never manufactures out-of-sample edge — unpurged=0.486 purged=0.492 leak_closed=-0.006
- **INFO** purge note — expanding-window design keeps boundary leak ~0 by construction; shuffle-null [OF-2] is the leak gate
- **PASS** dof: not starved (>=10 rows per feature) — rows/feature=270.9 (17337 rows / 64 features)
- **INFO** dof coverage — fitted GBT consulted 44/64 features - dead read taken on a model that actually looked
- **INFO** dof: dead-feature fraction (exploration — informational) — dead_frac=0.81 (52 near-zero-importance features) — arms when ml.exploration.enabled is false; reduce the schema (prune experiment) or grow the corpus
- **INFO** dof note — low/zero-importance: ['basis_dir', 'fv_edge_bps', 'equity_risk_z', 'mkt_ret_6_dir', 'ret_1_dir', 'funding_dir'] ...
- **INFO** plateau[position_sizer.min_p_win] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[profit_taking.chandelier_k] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[pretrade.min_edge_cost_ratio] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** OF-5 trials: assumed N=7 (no ledger at C:\Users\haird\Documents\liquiditybot\liquiditybot_ab\outputs\trial_ledger.csv; var=SR^2 fallback)
- **INFO** dsr REACHABILITY — UNPASSABLE at N=7: the var_trial_sr=SR^2 fallback makes sr0 = 1.387x|SR|, so the rejection threshold scales with the statistic and dsr>=0.90 is attainable for NO sample (exhaustive sweep 2026-08-31: 0/518616 combinations pass at N=7, max dsr 0.4262). This gate cannot produce a green — read any OF-5 line below as INERT, not as evidence. Repair needs a var_trial_sr MEASURED from per-trial SR (trial_ledger v0.1 records none), never a threshold move.
- **INFO** dsr — DEFERRED — 28 conviction-marked live trades < 30 (mixed n=422); mixed-sample dsr=0.000 sr=-0.37; probes are EV-mixed by design (PT-050); gate arms as conviction labels accrue
- **INFO** regime diagnostic caveat — stratum auc/brier below are concatenated-OOF over all scored rows, while the pooled figures they're compared against are MEAN-OF-FOLDS (OF-1's own convention) — the delta is indicative, not a rebasing of the same statistic
- **INFO** regime diagnostic caveat — n= below is a raw signal_history.csv count (candidate+live); oof_n= is the deduped/purged X actually OOF-scored — two different counting passes over related but non-identical data
- **INFO** regime[bull_quiet] — n=3797 (candidate=3772 live=25) base_rate=0.384
- **INFO** regime[bull_quiet] FLAG — insufficient live coverage (25 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[bull_quiet] oof — oof_n=3212 auc=0.577 (pooled 0.560, delta_auc=+0.017) brier=0.2481 (pooled 0.2436, delta_brier=+0.0045)
- **INFO** regime[bull_vol] — n=1746 (candidate=1733 live=13) base_rate=0.458
- **INFO** regime[bull_vol] FLAG — insufficient live coverage (13 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[bull_vol] oof — oof_n=1721 auc=0.629 (pooled 0.560, delta_auc=+0.069) brier=0.2304 (pooled 0.2436, delta_brier=-0.0132)
- **INFO** regime[range] — n=10817 (candidate=10496 live=321) base_rate=0.297
- **INFO** regime[range] oof — oof_n=3428 auc=0.636 (pooled 0.560, delta_auc=+0.076) brier=0.2376 (pooled 0.2436, delta_brier=-0.0060)
- **INFO** regime[bear] — n=7272 (candidate=7209 live=63) base_rate=0.341
- **INFO** regime[bear] oof — oof_n=2277 auc=0.575 (pooled 0.560, delta_auc=+0.015) brier=0.2569 (pooled 0.2436, delta_brier=+0.0133)
- **INFO** regime[crisis] — n=4120 (candidate=4120 live=0) base_rate=0.436
- **INFO** regime[crisis] FLAG — insufficient live coverage (0 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[crisis] oof — oof_n=3807 auc=0.649 (pooled 0.560, delta_auc=+0.089) brier=0.2432 (pooled 0.2436, delta_brier=-0.0004)
- **INFO** regime[unknown] — n=0 — absent from corpus
- **INFO** learning curve caveat — each point refits gbt on a chronological PREFIX of the corpus (time-purged OOF, deployed protocol) — points are the same statistic across sizes, but none is OF-1's own pooled number
- **INFO** lc[n=4334] — oof_n=3610 auc=0.672 brier=0.2254
- **INFO** lc[n=6935] — oof_n=5775 auc=0.526 brier=0.2678
- **INFO** lc[n=9535] — oof_n=7945 auc=0.539 brier=0.2572
- **INFO** lc[n=12136] — oof_n=10110 auc=0.499 brier=0.2752
- **INFO** lc[n=14736] — oof_n=12280 auc=0.535 brier=0.2498
- **INFO** lc[n=17337] — oof_n=14445 auc=0.623 brier=0.2436
- **INFO** learning curve trend — FLAT (|delta_auc=-0.020| <= 0.03) — representation-limited: more rows alone are not buying skill; feature/label quality is the binding constraint, not corpus size
- **INFO** extras[equity_risk_z] — at-neutral share 25.5% (n=17337) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[opt_pcr_z] — at-neutral share 25.8% (n=17337) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[opt_oi_pcr_z] — at-neutral share 25.8% (n=17337) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[dominance_delta] — at-neutral share 2.2% (n=17337) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[sent_fear] — at-neutral share 100.0% (n=17337) — feed effectively dark corpus-wide (dead column)
- **INFO** extras[fear_greed] — at-neutral share 0.0% (n=17337) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance

3 passed, 0 failed (70s)

Corpus: live history (17337 rows)

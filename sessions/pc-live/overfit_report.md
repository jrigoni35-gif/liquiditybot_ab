# Overfit audit — 2026-09-12 01:24 UTC

Dataset: live history (17991 rows)

- **INFO** gap[logistic] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.760 oof_auc=0.543 gap=+0.217; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** gap[gbt] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.826 oof_auc=0.549 gap=+0.277; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** gap[mlp] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.700 oof_auc=0.543 gap=+0.157; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** null-floor[logistic] — OOF Brier 0.2680 vs base-rate constant 0.2442 (base=0.424, n=14990) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **INFO** null-floor[gbt] — OOF Brier 0.2602 vs base-rate constant 0.2442 (base=0.424, n=14990) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **INFO** null-floor[mlp] — OOF Brier 0.2885 vs base-rate constant 0.2442 (base=0.424, n=14990) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **PASS** shuffle: destroyed labels learn nothing OOF — mean_auc=0.501 z=0.4 (limit 3.0)
- **INFO** pbo space — ml.adaptive_gbt.enabled=true — the adaptive rung is IN the measured selection space
- **PASS** pbo: DEPLOYED selection (simplicity ladder) not dominated by luck — pbo=0.24 over 6 configs / 70 splits (mean winner: gbt_d4_lr05)
- **INFO** pbo argmax stress — raw argmax selection pbo=0.16 — the worst-case rule the ladder exists to avoid; gate is on the rule the bot actually runs
- **INFO** pbo edge purge — label-window purge active: edge_purged_frac=0.144, combos_dropped=0
- **INFO** pbo note — 0.2 < pbo <= 0.5: selection has luck in it — expected at this sample size; keep the simplicity-ladder margin
- **PASS** purge: never manufactures out-of-sample edge — unpurged=0.486 purged=0.492 leak_closed=-0.006
- **INFO** purge note — expanding-window design keeps boundary leak ~0 by construction; shuffle-null [OF-2] is the leak gate
- **PASS** dof: not starved (>=10 rows per feature) — rows/feature=281.1 (17991 rows / 64 features)
- **INFO** dof COVERAGE — dead-feature scan UNINFORMATIVE: the fitted GBT consulted only 24/64 features (40 of the 55 'dead' were never split on at all). Read dead_feature_frac as the model's blindness, not the features' deadness; the clustered-MDA report (scripts/interpret_report.py) is the honest ranking.
- **INFO** dof: dead-feature fraction (exploration — informational) — dead_frac=0.86 (55 near-zero-importance features) — arms when ml.exploration.enabled is false; reduce the schema (prune experiment) or grow the corpus
- **INFO** dof note — low/zero-importance: ['hour_sin', 'weekend', 'va_pos', 'opt_oi_pcr_z', 'sigma_bar_pct', 'ret_48_dir'] ...
- **INFO** plateau[position_sizer.min_p_win] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[profit_taking.chandelier_k] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[pretrade.min_edge_cost_ratio] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** OF-5 trials: assumed N=7 (no ledger at C:\Users\haird\Documents\liquiditybot\liquiditybot_ab\outputs\trial_ledger.csv; var=1/n null fallback)
- **FAIL** dsr: P(true SR > sr0) on conviction-only sample — dsr=0.006 sr=-0.24 n=30 sr0=0.253 (probes excluded: 404)
- **INFO** dsr READ THIS WITH THE VERDICT — SIGN READING: PSR(SR*=0)=0.111 -> P(true SR < 0)=0.889. This, NOT the graded dsr, is the 'is the edge positive' number - dsr is P(true SR > sr0) where sr0 is the expected max under the null across N trials. A dsr FAIL beside a PSR near 0.5 means UNDERPOWERED, not harmful. || CORPUS: 30 conviction trips spanning 2026-07-20..2026-09-11 (53.2 days). NOT era-scoped: signal_history.csv has no exec_era column (the stamp lives in core/fill_ledger.py, keyed by position_id), so this sample pools every execution era it covers - different fee bookings AND different barrier geometries. CLAUDE.md: trips are 'citable AS their era, none poolable across a cut'. Read the verdict against THIS span, not against the deployed config.
- **INFO** dsr: deployed-era regression sentinel — DEFERRED - 0 conviction trips wholly inside era 12-10d4d0c2 < 10. The deployed configuration is not yet separately measurable; OF-5's pooled FAIL says NOTHING about it either way.
- **INFO** regime diagnostic caveat — stratum auc/brier below are concatenated-OOF over all scored rows, while the pooled figures they're compared against are MEAN-OF-FOLDS (OF-1's own convention) — the delta is indicative, not a rebasing of the same statistic
- **INFO** regime diagnostic caveat — n= below is a raw signal_history.csv count (candidate+live); oof_n= is the deduped/purged X actually OOF-scored — two different counting passes over related but non-identical data
- **INFO** regime[bull_quiet] — n=4066 (candidate=4037 live=29) base_rate=0.386
- **INFO** regime[bull_quiet] FLAG — insufficient live coverage (29 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[bull_quiet] oof — oof_n=3474 auc=0.557 (pooled 0.549, delta_auc=+0.009) brier=0.2570 (pooled 0.2602, delta_brier=-0.0032)
- **INFO** regime[bull_vol] — n=1804 (candidate=1790 live=14) base_rate=0.455
- **INFO** regime[bull_vol] FLAG — insufficient live coverage (14 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[bull_vol] oof — oof_n=1778 auc=0.545 (pooled 0.549, delta_auc=-0.003) brier=0.2693 (pooled 0.2602, delta_brier=+0.0091)
- **INFO** regime[range] — n=11124 (candidate=10797 live=327) base_rate=0.299
- **INFO** regime[range] oof — oof_n=3729 auc=0.554 (pooled 0.549, delta_auc=+0.005) brier=0.2603 (pooled 0.2602, delta_brier=+0.0001)
- **INFO** regime[bear] — n=7308 (candidate=7244 live=64) base_rate=0.343
- **INFO** regime[bear] oof — oof_n=2311 auc=0.533 (pooled 0.549, delta_auc=-0.016) brier=0.2751 (pooled 0.2602, delta_brier=+0.0149)
- **INFO** regime[crisis] — n=4120 (candidate=4120 live=0) base_rate=0.436
- **INFO** regime[crisis] FLAG — insufficient live coverage (0 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[crisis] oof — oof_n=3698 auc=0.612 (pooled 0.549, delta_auc=+0.064) brier=0.2494 (pooled 0.2602, delta_brier=-0.0108)
- **INFO** regime[unknown] — n=0 — absent from corpus
- **INFO** learning curve caveat — each point refits gbt on a chronological PREFIX of the corpus (time-purged OOF, deployed protocol) — points are the same statistic across sizes, but none is OF-1's own pooled number
- **INFO** lc[n=4498] — oof_n=3745 auc=0.632 brier=0.2402
- **INFO** lc[n=7196] — oof_n=5995 auc=0.517 brier=0.2704
- **INFO** lc[n=9895] — oof_n=8245 auc=0.495 brier=0.2699
- **INFO** lc[n=12594] — oof_n=10495 auc=0.522 brier=0.2589
- **INFO** lc[n=15292] — oof_n=12740 auc=0.590 brier=0.2437
- **INFO** lc[n=17991] — oof_n=14990 auc=0.566 brier=0.2602
- **INFO** learning curve trend — FLAT (|delta_auc=+0.003| <= 0.03) — representation-limited: more rows alone are not buying skill; feature/label quality is the binding constraint, not corpus size
- **INFO** extras[equity_risk_z] — at-neutral share 24.6% (n=17991) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[opt_pcr_z] — at-neutral share 24.9% (n=17991) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[opt_oi_pcr_z] — at-neutral share 24.9% (n=17991) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[dominance_delta] — at-neutral share 2.3% (n=17991) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[sent_fear] — at-neutral share 100.0% (n=17991) — feed effectively dark corpus-wide (dead column)
- **INFO** extras[fear_greed] — at-neutral share 0.0% (n=17991) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance

4 passed, 1 failed (152s)

Corpus: live history (17991 rows)

# Overfit audit — 2026-09-14 23:41 UTC

Dataset: live history (18956 rows)

- **INFO** gap[logistic] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.755 oof_auc=0.551 gap=+0.204; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** gap[gbt] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.789 oof_auc=0.531 gap=+0.257; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** gap[mlp] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.753 oof_auc=0.539 gap=+0.214; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** null-floor[logistic] — OOF Brier 0.2668 vs base-rate constant 0.2437 (base=0.421, n=15795) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **INFO** null-floor[gbt] — OOF Brier 0.2498 vs base-rate constant 0.2437 (base=0.421, n=15795) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **INFO** null-floor[mlp] — OOF Brier 0.2947 vs base-rate constant 0.2437 (base=0.421, n=15795) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **PASS** shuffle: destroyed labels learn nothing OOF — mean_auc=0.498 z=0.8 (limit 3.0)
- **INFO** pbo space — ml.adaptive_gbt.enabled=true — the adaptive rung is IN the measured selection space
- **PASS** pbo: DEPLOYED selection (simplicity ladder) not dominated by luck — pbo=0.13 over 6 configs / 70 splits (mean winner: gbt_d2_lr05)
- **INFO** pbo argmax stress — raw argmax selection pbo=0.20 — the worst-case rule the ladder exists to avoid; gate is on the rule the bot actually runs
- **INFO** pbo edge purge — label-window purge active: edge_purged_frac=0.119, combos_dropped=0
- **PASS** purge: never manufactures out-of-sample edge — unpurged=0.486 purged=0.492 leak_closed=-0.006
- **INFO** purge note — expanding-window design keeps boundary leak ~0 by construction; shuffle-null [OF-2] is the leak gate
- **PASS** dof: not starved (>=10 rows per feature) — rows/feature=296.2 (18956 rows / 64 features)
- **INFO** dof COVERAGE — dead-feature scan UNINFORMATIVE: the fitted GBT consulted only 11/64 features (53 of the 59 'dead' were never split on at all). Read dead_feature_frac as the model's blindness, not the features' deadness; the clustered-MDA report (scripts/interpret_report.py) is the honest ranking.
- **INFO** dof: dead-feature fraction (exploration — informational) — dead_frac=0.92 (59 near-zero-importance features) — arms when ml.exploration.enabled is false; reduce the schema (prune experiment) or grow the corpus
- **INFO** dof note — low/zero-importance: ['basis_dir', 'ret_1_dir', 'ret_6_dir', 'ret_12_dir', 'ret_48_dir', 'sigma_bar_pct'] ...
- **INFO** plateau[position_sizer.min_p_win] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[profit_taking.chandelier_k] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[pretrade.min_edge_cost_ratio] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** OF-5 trials: assumed N=7 (no ledger at C:\Users\haird\Documents\liquiditybot\liquiditybot_ab\outputs\trial_ledger.csv; var=1/n null fallback)
- **FAIL** dsr: P(true SR > sr0) on conviction-only sample — dsr=0.005 sr=-0.26 n=31 sr0=0.249 (probes excluded: 414)
- **INFO** dsr READ THIS WITH THE VERDICT — SIGN READING: PSR(SR*=0)=0.091 -> P(true SR < 0)=0.909. This, NOT the graded dsr, is the 'is the edge positive' number - dsr is P(true SR > sr0) where sr0 is the expected max under the null across N trials. A red dsr beside a PSR near 0.5 means UNDERPOWERED, not harmful. || CORPUS: 31 conviction trips spanning 2026-07-20..2026-09-13 (54.9 days). NOT era-scoped: signal_history.csv has no exec_era column (the stamp lives in core/fill_ledger.py, keyed by position_id), so this sample pools every execution era it covers - different fee bookings AND different barrier geometries. CLAUDE.md: trips are 'citable AS their era, none poolable across a cut'. Read the verdict against THIS span, not against the deployed config.
- **INFO** dsr: deployed-era regression sentinel — DEFERRED - 1 conviction trips wholly inside era 12-10d4d0c2 < 10. The deployed configuration is not yet separately measurable; OF-5's pooled verdict says NOTHING about it either way. [19 conviction trip(s) EXCLUDED (impure_era=19); $-18.91 of PnL is not in this statistic - an exclusion that removes losers is itself a silencing channel, so read this count]
- **INFO** regime diagnostic caveat — stratum auc/brier below are concatenated-OOF over all scored rows, while the pooled figures they're compared against are MEAN-OF-FOLDS (OF-1's own convention) — the delta is indicative, not a rebasing of the same statistic
- **INFO** regime diagnostic caveat — n= below is a raw signal_history.csv count (candidate+live); oof_n= is the deduped/purged X actually OOF-scored — two different counting passes over related but non-identical data
- **INFO** regime[bull_quiet] — n=4425 (candidate=4393 live=32) base_rate=0.389
- **INFO** regime[bull_quiet] oof — oof_n=3831 auc=0.547 (pooled 0.531, delta_auc=+0.016) brier=0.2531 (pooled 0.2498, delta_brier=+0.0034)
- **INFO** regime[bull_vol] — n=1804 (candidate=1790 live=14) base_rate=0.455
- **INFO** regime[bull_vol] FLAG — insufficient live coverage (14 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[bull_vol] oof — oof_n=1778 auc=0.592 (pooled 0.531, delta_auc=+0.061) brier=0.2443 (pooled 0.2498, delta_brier=-0.0054)
- **INFO** regime[range] — n=11625 (candidate=11291 live=334) base_rate=0.303
- **INFO** regime[range] oof — oof_n=4201 auc=0.605 (pooled 0.531, delta_auc=+0.074) brier=0.2439 (pooled 0.2498, delta_brier=-0.0058)
- **INFO** regime[bear] — n=7432 (candidate=7367 live=65) base_rate=0.347
- **INFO** regime[bear] oof — oof_n=2432 auc=0.555 (pooled 0.531, delta_auc=+0.024) brier=0.2588 (pooled 0.2498, delta_brier=+0.0090)
- **INFO** regime[crisis] — n=4120 (candidate=4120 live=0) base_rate=0.436
- **INFO** regime[crisis] FLAG — insufficient live coverage (0 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[crisis] oof — oof_n=3553 auc=0.606 (pooled 0.531, delta_auc=+0.075) brier=0.2496 (pooled 0.2498, delta_brier=-0.0002)
- **INFO** regime[unknown] — n=0 — absent from corpus
- **INFO** learning curve caveat — each point refits gbt on a chronological PREFIX of the corpus (time-purged OOF, deployed protocol) — points are the same statistic across sizes, but none is OF-1's own pooled number
- **INFO** lc[n=4739] — oof_n=3945 auc=0.593 brier=0.2542
- **INFO** lc[n=7582] — oof_n=6315 auc=0.648 brier=0.2449
- **INFO** lc[n=10426] — oof_n=8685 auc=0.532 brier=0.2606
- **INFO** lc[n=13269] — oof_n=11055 auc=0.578 brier=0.2511
- **INFO** lc[n=16113] — oof_n=13425 auc=0.610 brier=0.2432
- **INFO** lc[n=18956] — oof_n=15795 auc=0.586 brier=0.2498
- **INFO** learning curve trend — FLAT (|delta_auc=-0.023| <= 0.03) — representation-limited: more rows alone are not buying skill; feature/label quality is the binding constraint, not corpus size
- **INFO** extras[equity_risk_z] — at-neutral share 23.4% (n=18956) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[opt_pcr_z] — at-neutral share 23.7% (n=18956) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[opt_oi_pcr_z] — at-neutral share 23.7% (n=18956) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[dominance_delta] — at-neutral share 2.2% (n=18956) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[sent_fear] — at-neutral share 100.0% (n=18956) — feed effectively dark corpus-wide (dead column)
- **INFO** extras[fear_greed] — at-neutral share 0.0% (n=18956) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance

4 passed, 1 failed (104s)

Corpus: live history (18956 rows)

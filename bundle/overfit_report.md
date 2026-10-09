# Overfit audit — 2026-09-21 02:39 UTC

Dataset: live history (21193 rows)

- **INFO** gap[logistic] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.752 oof_auc=0.578 gap=+0.174; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** gap[gbt] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.771 oof_auc=0.549 gap=+0.222; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** gap[mlp] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.791 oof_auc=0.572 gap=+0.219; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** null-floor[logistic] — OOF Brier 0.2681 vs base-rate constant 0.2445 (base=0.426, n=17660) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **INFO** null-floor[gbt] — OOF Brier 0.2668 vs base-rate constant 0.2445 (base=0.426, n=17660) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **INFO** null-floor[mlp] — OOF Brier 0.2881 vs base-rate constant 0.2445 (base=0.426, n=17660) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **PASS** shuffle: destroyed labels learn nothing OOF — mean_auc=0.497 z=1.3 (limit 3.0)
- **INFO** pbo space — ml.adaptive_gbt.enabled=true — the adaptive rung is IN the measured selection space
- **FAIL** pbo: DEPLOYED selection (simplicity ladder) not dominated by luck — pbo=0.51 over 6 configs / 70 splits (mean winner: gbt_d2_lr10)
- **INFO** pbo argmax stress — raw argmax selection pbo=0.50 — the worst-case rule the ladder exists to avoid; gate is on the rule the bot actually runs
- **INFO** pbo edge purge — label-window purge active: edge_purged_frac=0.103, combos_dropped=0
- **INFO** pbo note — 0.2 < pbo <= 0.5: selection has luck in it — expected at this sample size; keep the simplicity-ladder margin
- **PASS** purge: never manufactures out-of-sample edge — unpurged=0.486 purged=0.492 leak_closed=-0.006
- **INFO** purge note — expanding-window design keeps boundary leak ~0 by construction; shuffle-null [OF-2] is the leak gate
- **PASS** dof: not starved (>=10 rows per feature) — rows/feature=331.1 (21193 rows / 64 features)
- **INFO** dof EFFECTIVE n (report-only; the gate above reads NOMINAL) — rows/feature nominal=331.14 vs effective=1.10 (n=21193 -> n_eff=70.4, mean uniqueness 0.003); an SE on nominal n is optimistic by x17.35. Route: asset-blind (lower bound on n_eff) — the floor of 10 is NOT applied to it and nothing here moves PASS/FAIL.
- **INFO** dof EFFECTIVE n — THE OTHER ROUTE (read the PAIR) — per-asset rows/feature=26.66 (n_eff=1706.0, from the production loader's own mean_uniqueness, which keys concurrency per (asset, 5m bar) as this seam cannot). The routes differ by x24.2 on the SAME corpus and NEITHER is adjudicated — asset-blind is a lower bound, per-asset an upper. Quote the PAIR with its routes, never one number.
- **INFO** dof COVERAGE — dead-feature scan UNINFORMATIVE: the fitted GBT consulted only 10/64 features (54 of the 57 'dead' were never split on at all). Read dead_feature_frac as the model's blindness, not the features' deadness; the clustered-MDA report (scripts/interpret_report.py) is the honest ranking.
- **INFO** dof: dead-feature fraction (exploration — informational) — dead_frac=0.89 (57 near-zero-importance features) — arms when ml.exploration.enabled is false; reduce the schema (prune experiment) or grow the corpus
- **INFO** dof note — low/zero-importance: ['ret_1_dir', 'ret_6_dir', 'ret_12_dir', 'ret_48_dir', 'sigma_bar_pct', 'vol_percentile'] ...
- **INFO** plateau[position_sizer.min_p_win] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[profit_taking.chandelier_k] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[pretrade.min_edge_cost_ratio] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** OF-5 trials: assumed N=7 (no ledger at C:\Users\haird\Documents\liquiditybot\liquiditybot_ab\outputs\trial_ledger.csv; var=1/n null fallback)
- **FAIL** dsr: P(true SR > sr0) on conviction-only sample — dsr=0.006 sr=-0.22 n=35 sr0=0.234 (probes excluded: 443)
- **INFO** dsr READ THIS WITH THE VERDICT — SIGN READING: PSR(SR*=0)=0.113 -> P(true SR < 0)=0.887. This, NOT the graded dsr, is the 'is the edge positive' number - dsr is P(true SR > sr0) where sr0 is the expected max under the null across N trials. A red dsr beside a PSR near 0.5 means UNDERPOWERED, not harmful. || CORPUS: 35 conviction trips spanning 2026-07-20..2026-09-19 (61.2 days). NOT era-scoped: signal_history.csv has no exec_era column (the stamp lives in core/fill_ledger.py, keyed by position_id), so this sample pools every execution era it covers - different fee bookings AND different barrier geometries. CLAUDE.md: trips are 'citable AS their era, none poolable across a cut'. Read the verdict against THIS span, not against the deployed config.
- **INFO** dsr: deployed-era regression sentinel — DEFERRED - 5 conviction trips wholly inside era 12-10d4d0c2 < 10. The deployed configuration is not yet separately measurable; OF-5's pooled verdict says NOTHING about it either way. [19 conviction trip(s) EXCLUDED (impure_era=19); $-18.91 of PnL is not in this statistic - an exclusion that removes losers is itself a silencing channel, so read this count]
- **INFO** regime diagnostic caveat — stratum auc/brier below are concatenated-OOF over all scored rows, while the pooled figures they're compared against are MEAN-OF-FOLDS (OF-1's own convention) — the delta is indicative, not a rebasing of the same statistic
- **INFO** regime diagnostic caveat — n= below is a raw signal_history.csv count (candidate+live); oof_n= is the deduped/purged X actually OOF-scored — two different counting passes over related but non-identical data
- **INFO** regime[bull_quiet] — n=5057 (candidate=5015 live=42) base_rate=0.400
- **INFO** regime[bull_quiet] oof — oof_n=4444 auc=0.510 (pooled 0.549, delta_auc=-0.039) brier=0.2731 (pooled 0.2668, delta_brier=+0.0062)
- **INFO** regime[bull_vol] — n=1849 (candidate=1834 live=15) base_rate=0.451
- **INFO** regime[bull_vol] FLAG — insufficient live coverage (15 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[bull_vol] oof — oof_n=1803 auc=0.570 (pooled 0.549, delta_auc=+0.021) brier=0.2686 (pooled 0.2668, delta_brier=+0.0018)
- **INFO** regime[range] — n=12754 (candidate=12402 live=352) base_rate=0.318
- **INFO** regime[range] oof — oof_n=5298 auc=0.597 (pooled 0.549, delta_auc=+0.048) brier=0.2525 (pooled 0.2668, delta_brier=-0.0143)
- **INFO** regime[bear] — n=7902 (candidate=7833 live=69) base_rate=0.367
- **INFO** regime[bear] oof — oof_n=2874 auc=0.512 (pooled 0.549, delta_auc=-0.037) brier=0.2794 (pooled 0.2668, delta_brier=+0.0125)
- **INFO** regime[crisis] — n=4120 (candidate=4120 live=0) base_rate=0.436
- **INFO** regime[crisis] FLAG — insufficient live coverage (0 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[crisis] oof — oof_n=3241 auc=0.539 (pooled 0.549, delta_auc=-0.010) brier=0.2695 (pooled 0.2668, delta_brier=+0.0027)
- **INFO** regime[unknown] — n=0 — absent from corpus
- **INFO** learning curve caveat — each point refits gbt on a chronological PREFIX of the corpus (time-purged OOF, deployed protocol) — points are the same statistic across sizes, but none is OF-1's own pooled number
- **INFO** lc[n=5298] — oof_n=4415 auc=0.590 brier=0.2550
- **INFO** lc[n=8477] — oof_n=7060 auc=0.553 brier=0.2560
- **INFO** lc[n=11656] — oof_n=9710 auc=0.505 brier=0.2631
- **INFO** lc[n=14835] — oof_n=12360 auc=0.564 brier=0.2469
- **INFO** lc[n=18014] — oof_n=15010 auc=0.575 brier=0.2544
- **INFO** lc[n=21193] — oof_n=17660 auc=0.547 brier=0.2668
- **INFO** learning curve trend — FLAT (|delta_auc=-0.011| <= 0.03) — representation-limited: more rows alone are not buying skill; feature/label quality is the binding constraint, not corpus size
- **INFO** extras[equity_risk_z] — at-neutral share 27.8% (n=21193) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[opt_pcr_z] — at-neutral share 28.0% (n=21193) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[opt_oi_pcr_z] — at-neutral share 28.0% (n=21193) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[dominance_delta] — at-neutral share 2.1% (n=21193) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[sent_fear] — at-neutral share 100.0% (n=21193) — feed effectively dark corpus-wide (dead column)
- **INFO** extras[fear_greed] — at-neutral share 1.5% (n=21193) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance

3 passed, 2 failed (206s)

Corpus: live history (21193 rows)

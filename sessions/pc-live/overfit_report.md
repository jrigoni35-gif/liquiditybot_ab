# Overfit audit — 2026-08-28 01:39 UTC

Dataset: live history (8220 rows)

- **INFO** gap[logistic] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.824 oof_auc=0.493 gap=+0.331; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** gap[gbt] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.831 oof_auc=0.551 gap=+0.281; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** gap[mlp] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.858 oof_auc=0.539 gap=+0.319; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** null-floor[logistic] — OOF Brier 0.3508 vs base-rate constant 0.2500 (base=0.506, n=6850) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **INFO** null-floor[gbt] — OOF Brier 0.2576 vs base-rate constant 0.2500 (base=0.506, n=6850) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **INFO** null-floor[mlp] — OOF Brier 0.3699 vs base-rate constant 0.2500 (base=0.506, n=6850) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **PASS** shuffle: destroyed labels learn nothing OOF — mean_auc=0.502 z=0.6 (limit 3.0)
- **INFO** pbo space — ml.adaptive_gbt.enabled=true — the adaptive rung is IN the measured selection space
- **INFO** pbo — evidence-gated to a single family (no model selection to overfit at this live-row count) (space=['logistic'])
- **PASS** purge: never manufactures out-of-sample edge — unpurged=0.486 purged=0.492 leak_closed=-0.006
- **INFO** purge note — expanding-window design keeps boundary leak ~0 by construction; shuffle-null [OF-2] is the leak gate
- **PASS** dof: not starved (>=10 rows per feature) — rows/feature=128.4 (8220 rows / 64 features)
- **INFO** dof: dead-feature fraction (exploration — informational) — dead_frac=0.98 (63 near-zero-importance features) — arms when ml.exploration.enabled is false; reduce the schema (prune experiment) or grow the corpus
- **INFO** dof note — low/zero-importance: ['ret_1_dir', 'ret_6_dir', 'ret_12_dir', 'ret_48_dir', 'sigma_bar_pct', 'vol_percentile'] ...
- **INFO** plateau[position_sizer.min_p_win] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[profit_taking.chandelier_k] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[pretrade.min_edge_cost_ratio] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** dsr — DEFERRED — 26 conviction-marked live trades < 30 (mixed n=373); mixed-sample dsr=0.000 sr=-0.38; probes are EV-mixed by design (PT-050); gate arms as conviction labels accrue
- **INFO** regime diagnostic caveat — stratum auc/brier below are concatenated-OOF over all scored rows, while the pooled figures they're compared against are MEAN-OF-FOLDS (OF-1's own convention) — the delta is indicative, not a rebasing of the same statistic
- **INFO** regime diagnostic caveat — n= below is a raw signal_history.csv count (candidate+live); oof_n= is the deduped/purged X actually OOF-scored — two different counting passes over related but non-identical data
- **INFO** regime[bull_quiet] — n=1080 (candidate=1071 live=9) base_rate=0.404
- **INFO** regime[bull_quiet] FLAG — insufficient live coverage (9 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[bull_quiet] oof — oof_n=759 auc=0.607 (pooled 0.551, delta_auc=+0.056) brier=0.2491 (pooled 0.2576, delta_brier=-0.0085)
- **INFO** regime[bull_vol] — n=1056 (candidate=1047 live=9) base_rate=0.470
- **INFO** regime[bull_vol] FLAG — insufficient live coverage (9 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[bull_vol] oof — oof_n=1034 auc=0.575 (pooled 0.551, delta_auc=+0.024) brier=0.2425 (pooled 0.2576, delta_brier=-0.0151)
- **INFO** regime[range] — n=8273 (candidate=7975 live=298) base_rate=0.249
- **INFO** regime[range] oof — oof_n=1158 auc=0.539 (pooled 0.551, delta_auc=-0.011) brier=0.2601 (pooled 0.2576, delta_brier=+0.0026)
- **INFO** regime[bear] — n=5982 (candidate=5925 live=57) base_rate=0.325
- **INFO** regime[bear] oof — oof_n=1712 auc=0.513 (pooled 0.551, delta_auc=-0.038) brier=0.2599 (pooled 0.2576, delta_brier=+0.0023)
- **INFO** regime[crisis] — n=2187 (candidate=2187 live=0) base_rate=0.515
- **INFO** regime[crisis] FLAG — insufficient live coverage (0 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[crisis] oof — oof_n=2187 auc=0.560 (pooled 0.551, delta_auc=+0.010) brier=0.2645 (pooled 0.2576, delta_brier=+0.0069)
- **INFO** regime[unknown] — n=0 — absent from corpus
- **INFO** learning curve caveat — each point refits gbt on a chronological PREFIX of the corpus (time-purged OOF, deployed protocol) — points are the same statistic across sizes, but none is OF-1's own pooled number
- **INFO** lc[n=2055] — oof_n=1710 auc=0.509 brier=0.2677
- **INFO** lc[n=3288] — oof_n=2740 auc=0.628 brier=0.2404
- **INFO** lc[n=4521] — oof_n=3765 auc=0.636 brier=0.2406
- **INFO** lc[n=5754] — oof_n=4795 auc=0.582 brier=0.2572
- **INFO** lc[n=6987] — oof_n=5820 auc=0.520 brier=0.2703
- **INFO** lc[n=8220] — oof_n=6850 auc=0.592 brier=0.2576
- **INFO** learning curve trend — FLAT (|delta_auc=-0.012| <= 0.03) — representation-limited: more rows alone are not buying skill; feature/label quality is the binding constraint, not corpus size
- **INFO** extras[equity_risk_z] — at-neutral share 26.5% (n=8220) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[opt_pcr_z] — at-neutral share 26.9% (n=8220) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[opt_oi_pcr_z] — at-neutral share 26.9% (n=8220) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[dominance_delta] — at-neutral share 3.1% (n=8220) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[sent_fear] — at-neutral share 100.0% (n=8220) — feed effectively dark corpus-wide (dead column)
- **INFO** extras[fear_greed] — at-neutral share 0.0% (n=8220) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance

3 passed, 0 failed (50s)

Corpus: live history (8220 rows)

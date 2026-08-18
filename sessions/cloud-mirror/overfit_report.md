# Overfit audit — 2026-08-18 04:14 UTC

Dataset: live history (758 rows)

- **INFO** gap[logistic] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.825 oof_auc=0.519 gap=+0.306; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** gap[gbt] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.794 oof_auc=0.465 gap=+0.329; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** gap[mlp] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.867 oof_auc=0.551 gap=+0.316; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** null-floor[logistic] — OOF Brier 0.4019 vs base-rate constant 0.1649 (base=0.208, n=504) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **INFO** null-floor[gbt] — OOF Brier 0.2811 vs base-rate constant 0.1649 (base=0.208, n=504) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **INFO** null-floor[mlp] — OOF Brier 0.4350 vs base-rate constant 0.1649 (base=0.208, n=504) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **PASS** shuffle: destroyed labels learn nothing OOF — mean_auc=0.492 z=0.5 (limit 3.0)
- **INFO** pbo space — ml.adaptive_gbt.enabled=true — the adaptive rung is IN the measured selection space
- **INFO** pbo — evidence-gated to a single family (no model selection to overfit at this live-row count) (space=['logistic'])
- **PASS** purge: never manufactures out-of-sample edge — unpurged=0.486 purged=0.492 leak_closed=-0.006
- **INFO** purge note — expanding-window design keeps boundary leak ~0 by construction; shuffle-null [OF-2] is the leak gate
- **PASS** dof: not starved (>=10 rows per feature) — rows/feature=11.8 (758 rows / 64 features)
- **INFO** dof: dead-feature fraction (exploration — informational) — dead_frac=0.45 (29 near-zero-importance features) — arms when ml.exploration.enabled is false; reduce the schema (prune experiment) or grow the corpus
- **INFO** dof note — low/zero-importance: ['depth_ratio', 'funding_dist', 'volume_z', 'sigma_bar_pct', 'fv_edge_bps', 'funding_dir'] ...
- **INFO** plateau[position_sizer.min_p_win] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[profit_taking.chandelier_k] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[pretrade.min_edge_cost_ratio] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** dsr — DEFERRED — 24 conviction-marked live trades < 30 (mixed n=333); mixed-sample dsr=0.000 sr=-0.47; probes are EV-mixed by design (PT-050); gate arms as conviction labels accrue
- **INFO** regime diagnostic caveat — stratum auc/brier below are concatenated-OOF over all scored rows, while the pooled figures they're compared against are MEAN-OF-FOLDS (OF-1's own convention) — the delta is indicative, not a rebasing of the same statistic
- **INFO** regime diagnostic caveat — n= below is a raw signal_history.csv count (candidate+live); oof_n= is the deduped/purged X actually OOF-scored — two different counting passes over related but non-identical data
- **INFO** regime[bull_quiet] — n=207 (candidate=203 live=4) base_rate=0.203
- **INFO** regime[bull_quiet] FLAG — insufficient live coverage (4 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[bull_quiet] oof — oof_n=61 auc=0.486 (pooled 0.465, delta_auc=+0.021) brier=0.2998 (pooled 0.2811, delta_brier=+0.0186)
- **INFO** regime[bull_vol] — n=12 (candidate=12 live=0) base_rate=0.250
- **INFO** regime[bull_vol] FLAG — insufficient live coverage (0 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[bull_vol] oof — oof_n=0 < 30 — insufficient OOF evidence, not scored
- **INFO** regime[range] — n=6908 (candidate=6627 live=281) base_rate=0.206
- **INFO** regime[range] oof — oof_n=182 auc=0.397 (pooled 0.465, delta_auc=-0.068) brier=0.2800 (pooled 0.2811, delta_brier=-0.0011)
- **INFO** regime[bear] — n=3940 (candidate=3892 live=48) base_rate=0.225
- **INFO** regime[bear] oof — oof_n=261 auc=0.469 (pooled 0.465, delta_auc=+0.004) brier=0.2775 (pooled 0.2811, delta_brier=-0.0036)
- **INFO** regime[crisis] — n=0 — absent from corpus
- **INFO** regime[unknown] — n=0 — absent from corpus
- **INFO** learning curve caveat — each point refits gbt on a chronological PREFIX of the corpus (time-purged OOF, deployed protocol) — points are the same statistic across sizes, but none is OF-1's own pooled number
- **INFO** lc[n=190] — oof_n=31 < 40 — not scored
- **INFO** lc[n=303] — oof_n=150 auc=0.408 brier=0.2449
- **INFO** lc[n=417] — oof_n=276 auc=0.384 brier=0.2492
- **INFO** lc[n=531] — oof_n=352 auc=0.474 brier=0.2620
- **INFO** lc[n=644] — oof_n=428 auc=0.493 brier=0.2592
- **INFO** lc[n=758] — oof_n=504 auc=0.449 brier=0.2811
- **INFO** learning curve trend — CLIMBING (delta_auc=+0.075 > +0.03) — data-starved: more rows are still buying skill; corpus growth is the highest-leverage learning input right now
- **INFO** extras[equity_risk_z] — at-neutral share 84.7% (n=758)
- **INFO** extras[opt_pcr_z] — at-neutral share 84.7% (n=758)
- **INFO** extras[opt_oi_pcr_z] — at-neutral share 84.7% (n=758)
- **INFO** extras[dominance_delta] — at-neutral share 7.4% (n=758) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[sent_fear] — at-neutral share 100.0% (n=758) — feed effectively dark corpus-wide (dead column)
- **INFO** extras[fear_greed] — at-neutral share 0.0% (n=758) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance

3 passed, 0 failed (26s)

Corpus: live history (758 rows)

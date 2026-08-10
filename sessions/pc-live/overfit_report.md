# Overfit audit — 2026-08-10 23:03 UTC

Dataset: live history (936 rows)

- **INFO** gap[logistic] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.833 oof_auc=0.457 gap=+0.375; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** gap[gbt] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.863 oof_auc=0.470 gap=+0.393; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** gap[mlp] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.848 oof_auc=0.479 gap=+0.369; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** null-floor[logistic] — OOF Brier 0.4037 vs base-rate constant 0.2297 (base=0.357, n=624) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **INFO** null-floor[gbt] — OOF Brier 0.2777 vs base-rate constant 0.2297 (base=0.357, n=624) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **INFO** null-floor[mlp] — OOF Brier 0.4256 vs base-rate constant 0.2297 (base=0.357, n=624) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **PASS** shuffle: destroyed labels learn nothing OOF — mean_auc=0.521 z=1.8 (limit 3.0)
- **INFO** pbo space — ml.adaptive_gbt.enabled=true — the adaptive rung is IN the measured selection space
- **INFO** pbo — evidence-gated to a single family (no model selection to overfit at this live-row count) (space=['logistic'])
- **PASS** purge: never manufactures out-of-sample edge — unpurged=0.486 purged=0.492 leak_closed=-0.006
- **INFO** purge note — expanding-window design keeps boundary leak ~0 by construction; shuffle-null [OF-2] is the leak gate
- **PASS** dof: not starved (>=10 rows per feature) — rows/feature=14.6 (936 rows / 64 features)
- **INFO** dof: dead-feature fraction (exploration — informational) — dead_frac=0.69 (44 near-zero-importance features) — arms when ml.exploration.enabled is false; reduce the schema (prune experiment) or grow the corpus
- **INFO** dof note — low/zero-importance: ['th_barclose', 'dominance_delta', 'depth_ratio', 'va_pos', 'mkt_ret_6_dir', 'imbalance_dir'] ...
- **INFO** plateau[position_sizer.min_p_win] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[profit_taking.chandelier_k] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[pretrade.min_edge_cost_ratio] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** dsr — DEFERRED — 19 conviction-marked live trades < 30 (mixed n=310); mixed-sample dsr=0.000 sr=-0.49; probes are EV-mixed by design (PT-050); gate arms as conviction labels accrue
- **INFO** regime diagnostic caveat — stratum auc/brier below are concatenated-OOF over all scored rows, while the pooled figures they're compared against are MEAN-OF-FOLDS (OF-1's own convention) — the delta is indicative, not a rebasing of the same statistic
- **INFO** regime diagnostic caveat — n= below is a raw signal_history.csv count (candidate+live); oof_n= is the deduped/purged X actually OOF-scored — two different counting passes over related but non-identical data
- **INFO** regime[bull_quiet] — n=87 (candidate=85 live=2) base_rate=0.241
- **INFO** regime[bull_quiet] FLAG — insufficient live coverage (2 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[bull_quiet] oof — oof_n=86 auc=0.546 (pooled 0.470, delta_auc=+0.076) brier=0.2736 (pooled 0.2777, delta_brier=-0.0041)
- **INFO** regime[bull_vol] — n=8 (candidate=8 live=0) base_rate=0.375
- **INFO** regime[bull_vol] FLAG — insufficient live coverage (0 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[bull_vol] oof — oof_n=1 < 30 — insufficient OOF evidence, not scored
- **INFO** regime[range] — n=6599 (candidate=6328 live=271) base_rate=0.202
- **INFO** regime[range] oof — oof_n=195 auc=0.378 (pooled 0.470, delta_auc=-0.092) brier=0.2709 (pooled 0.2777, delta_brier=-0.0068)
- **INFO** regime[bear] — n=3432 (candidate=3395 live=37) base_rate=0.218
- **INFO** regime[bear] oof — oof_n=342 auc=0.450 (pooled 0.470, delta_auc=-0.020) brier=0.2833 (pooled 0.2777, delta_brier=+0.0055)
- **INFO** regime[crisis] — n=0 — absent from corpus
- **INFO** regime[unknown] — n=0 — absent from corpus
- **INFO** learning curve caveat — each point refits gbt on a chronological PREFIX of the corpus (time-purged OOF, deployed protocol) — points are the same statistic across sizes, but none is OF-1's own pooled number
- **INFO** lc[n=234] — oof_n=0 < 40 — not scored
- **INFO** lc[n=374] — oof_n=124 auc=0.353 brier=0.3240
- **INFO** lc[n=515] — oof_n=255 auc=0.472 brier=0.3015
- **INFO** lc[n=655] — oof_n=436 auc=0.473 brier=0.2863
- **INFO** lc[n=796] — oof_n=528 auc=0.457 brier=0.2884
- **INFO** lc[n=936] — oof_n=624 auc=0.435 brier=0.2777
- **INFO** learning curve trend — CLIMBING (delta_auc=+0.034 > +0.03) — data-starved: more rows are still buying skill; corpus growth is the highest-leverage learning input right now
- **INFO** extras[equity_risk_z] — at-neutral share 88.7% (n=936)
- **INFO** extras[opt_pcr_z] — at-neutral share 90.4% (n=936)
- **INFO** extras[opt_oi_pcr_z] — at-neutral share 99.6% (n=936) — feed effectively dark corpus-wide (dead column)
- **INFO** extras[dominance_delta] — at-neutral share 5.6% (n=936) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[sent_fear] — at-neutral share 100.0% (n=936) — feed effectively dark corpus-wide (dead column)
- **INFO** extras[fear_greed] — at-neutral share 0.0% (n=936) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance

3 passed, 0 failed (43s)

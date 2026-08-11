# Overfit audit — 2026-08-11 00:15 UTC

Dataset: live history (949 rows)

- **INFO** gap[logistic] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.831 oof_auc=0.439 gap=+0.393; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** gap[gbt] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.896 oof_auc=0.478 gap=+0.418; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** gap[mlp] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.892 oof_auc=0.460 gap=+0.432; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** null-floor[logistic] — OOF Brier 0.4191 vs base-rate constant 0.2315 (base=0.364, n=632) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **INFO** null-floor[gbt] — OOF Brier 0.2802 vs base-rate constant 0.2315 (base=0.364, n=632) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **INFO** null-floor[mlp] — OOF Brier 0.4242 vs base-rate constant 0.2315 (base=0.364, n=632) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **PASS** shuffle: destroyed labels learn nothing OOF — mean_auc=0.481 z=1.6 (limit 3.0)
- **INFO** pbo space — ml.adaptive_gbt.enabled=true — the adaptive rung is IN the measured selection space
- **INFO** pbo — evidence-gated to a single family (no model selection to overfit at this live-row count) (space=['logistic'])
- **PASS** purge: never manufactures out-of-sample edge — unpurged=0.486 purged=0.492 leak_closed=-0.006
- **INFO** purge note — expanding-window design keeps boundary leak ~0 by construction; shuffle-null [OF-2] is the leak gate
- **PASS** dof: not starved (>=10 rows per feature) — rows/feature=14.8 (949 rows / 64 features)
- **INFO** dof: dead-feature fraction (exploration — informational) — dead_frac=0.86 (55 near-zero-importance features) — arms when ml.exploration.enabled is false; reduce the schema (prune experiment) or grow the corpus
- **INFO** dof note — low/zero-importance: ['ret_1_dir', 'ret_6_dir', 'ret_12_dir', 'ret_48_dir', 'sigma_bar_pct', 'spread_bps'] ...
- **INFO** plateau[position_sizer.min_p_win] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[profit_taking.chandelier_k] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[pretrade.min_edge_cost_ratio] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** dsr — DEFERRED — 21 conviction-marked live trades < 30 (mixed n=313); mixed-sample dsr=0.000 sr=-0.50; probes are EV-mixed by design (PT-050); gate arms as conviction labels accrue
- **INFO** regime diagnostic caveat — stratum auc/brier below are concatenated-OOF over all scored rows, while the pooled figures they're compared against are MEAN-OF-FOLDS (OF-1's own convention) — the delta is indicative, not a rebasing of the same statistic
- **INFO** regime diagnostic caveat — n= below is a raw signal_history.csv count (candidate+live); oof_n= is the deduped/purged X actually OOF-scored — two different counting passes over related but non-identical data
- **INFO** regime[bull_quiet] — n=87 (candidate=85 live=2) base_rate=0.241
- **INFO** regime[bull_quiet] FLAG — insufficient live coverage (2 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[bull_quiet] oof — oof_n=86 auc=0.492 (pooled 0.478, delta_auc=+0.014) brier=0.2759 (pooled 0.2802, delta_brier=-0.0043)
- **INFO** regime[bull_vol] — n=8 (candidate=8 live=0) base_rate=0.375
- **INFO** regime[bull_vol] FLAG — insufficient live coverage (0 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[bull_vol] oof — oof_n=1 < 30 — insufficient OOF evidence, not scored
- **INFO** regime[range] — n=6610 (candidate=6338 live=272) base_rate=0.203
- **INFO** regime[range] oof — oof_n=204 auc=0.409 (pooled 0.478, delta_auc=-0.069) brier=0.2749 (pooled 0.2802, delta_brier=-0.0053)
- **INFO** regime[bear] — n=3437 (candidate=3398 live=39) base_rate=0.218
- **INFO** regime[bear] oof — oof_n=341 auc=0.451 (pooled 0.478, delta_auc=-0.027) brier=0.2852 (pooled 0.2802, delta_brier=+0.0050)
- **INFO** regime[crisis] — n=0 — absent from corpus
- **INFO** regime[unknown] — n=0 — absent from corpus
- **INFO** learning curve caveat — each point refits gbt on a chronological PREFIX of the corpus (time-purged OOF, deployed protocol) — points are the same statistic across sizes, but none is OF-1's own pooled number
- **INFO** lc[n=237] — oof_n=0 < 40 — not scored
- **INFO** lc[n=380] — oof_n=126 auc=0.359 brier=0.3248
- **INFO** lc[n=522] — oof_n=261 auc=0.487 brier=0.2947
- **INFO** lc[n=664] — oof_n=440 auc=0.442 brier=0.2938
- **INFO** lc[n=807] — oof_n=536 auc=0.509 brier=0.2583
- **INFO** lc[n=949] — oof_n=632 auc=0.438 brier=0.2802
- **INFO** learning curve trend — CLIMBING (delta_auc=+0.050 > +0.03) — data-starved: more rows are still buying skill; corpus growth is the highest-leverage learning input right now
- **INFO** extras[equity_risk_z] — at-neutral share 87.9% (n=949)
- **INFO** extras[opt_pcr_z] — at-neutral share 89.6% (n=949)
- **INFO** extras[opt_oi_pcr_z] — at-neutral share 98.6% (n=949) — feed effectively dark corpus-wide (dead column)
- **INFO** extras[dominance_delta] — at-neutral share 5.6% (n=949) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[sent_fear] — at-neutral share 100.0% (n=949) — feed effectively dark corpus-wide (dead column)
- **INFO** extras[fear_greed] — at-neutral share 0.0% (n=949) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance

3 passed, 0 failed (45s)

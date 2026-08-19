# Overfit audit — 2026-08-19 01:21 UTC

Dataset: live history (1074 rows)

- **INFO** gap[logistic] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.826 oof_auc=0.586 gap=+0.241; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** gap[gbt] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.891 oof_auc=0.528 gap=+0.363; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** gap[mlp] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.915 oof_auc=0.545 gap=+0.369; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** null-floor[logistic] — OOF Brier 0.3408 vs base-rate constant 0.1808 (base=0.237, n=895) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **INFO** null-floor[gbt] — OOF Brier 0.2728 vs base-rate constant 0.1808 (base=0.237, n=895) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **INFO** null-floor[mlp] — OOF Brier 0.3791 vs base-rate constant 0.1808 (base=0.237, n=895) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **PASS** shuffle: destroyed labels learn nothing OOF — mean_auc=0.503 z=0.2 (limit 3.0)
- **INFO** pbo space — ml.adaptive_gbt.enabled=true — the adaptive rung is IN the measured selection space
- **INFO** pbo — evidence-gated to a single family (no model selection to overfit at this live-row count) (space=['logistic'])
- **PASS** purge: never manufactures out-of-sample edge — unpurged=0.486 purged=0.492 leak_closed=-0.006
- **INFO** purge note — expanding-window design keeps boundary leak ~0 by construction; shuffle-null [OF-2] is the leak gate
- **PASS** dof: not starved (>=10 rows per feature) — rows/feature=16.8 (1074 rows / 64 features)
- **INFO** dof: dead-feature fraction (exploration — informational) — dead_frac=0.64 (41 near-zero-importance features) — arms when ml.exploration.enabled is false; reduce the schema (prune experiment) or grow the corpus
- **INFO** dof note — low/zero-importance: ['vol_percentile', 'spread_bps', 'mom_dir', 'ret_12_dir', 'basis_dir', 'volume_z'] ...
- **INFO** plateau[position_sizer.min_p_win] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[profit_taking.chandelier_k] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[pretrade.min_edge_cost_ratio] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** dsr — DEFERRED — 24 conviction-marked live trades < 30 (mixed n=334); mixed-sample dsr=0.000 sr=-0.47; probes are EV-mixed by design (PT-050); gate arms as conviction labels accrue
- **INFO** regime diagnostic caveat — stratum auc/brier below are concatenated-OOF over all scored rows, while the pooled figures they're compared against are MEAN-OF-FOLDS (OF-1's own convention) — the delta is indicative, not a rebasing of the same statistic
- **INFO** regime diagnostic caveat — n= below is a raw signal_history.csv count (candidate+live); oof_n= is the deduped/purged X actually OOF-scored — two different counting passes over related but non-identical data
- **INFO** regime[bull_quiet] — n=273 (candidate=269 live=4) base_rate=0.168
- **INFO** regime[bull_quiet] FLAG — insufficient live coverage (4 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[bull_quiet] oof — oof_n=158 auc=0.485 (pooled 0.528, delta_auc=-0.043) brier=0.2553 (pooled 0.2728, delta_brier=-0.0174)
- **INFO** regime[bull_vol] — n=12 (candidate=12 live=0) base_rate=0.250
- **INFO** regime[bull_vol] FLAG — insufficient live coverage (0 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[bull_vol] oof — oof_n=0 < 30 — insufficient OOF evidence, not scored
- **INFO** regime[range] — n=7016 (candidate=6734 live=282) base_rate=0.207
- **INFO** regime[range] oof — oof_n=299 auc=0.473 (pooled 0.528, delta_auc=-0.055) brier=0.2855 (pooled 0.2728, delta_brier=+0.0128)
- **INFO** regime[bear] — n=4083 (candidate=4035 live=48) base_rate=0.228
- **INFO** regime[bear] oof — oof_n=438 auc=0.484 (pooled 0.528, delta_auc=-0.043) brier=0.2703 (pooled 0.2728, delta_brier=-0.0024)
- **INFO** regime[crisis] — n=0 — absent from corpus
- **INFO** regime[unknown] — n=0 — absent from corpus
- **INFO** learning curve caveat — each point refits gbt on a chronological PREFIX of the corpus (time-purged OOF, deployed protocol) — points are the same statistic across sizes, but none is OF-1's own pooled number
- **INFO** lc[n=268] — oof_n=132 auc=0.529 brier=0.2352
- **INFO** lc[n=430] — oof_n=284 auc=0.443 brier=0.2453
- **INFO** lc[n=591] — oof_n=392 auc=0.471 brier=0.2615
- **INFO** lc[n=752] — oof_n=500 auc=0.468 brier=0.2810
- **INFO** lc[n=913] — oof_n=760 auc=0.434 brier=0.2581
- **INFO** lc[n=1074] — oof_n=895 auc=0.488 brier=0.2728
- **INFO** learning curve trend — FLAT (|delta_auc=-0.025| <= 0.03) — representation-limited: more rows alone are not buying skill; feature/label quality is the binding constraint, not corpus size
- **INFO** extras[equity_risk_z] — at-neutral share 88.4% (n=1074)
- **INFO** extras[opt_pcr_z] — at-neutral share 88.5% (n=1074)
- **INFO** extras[opt_oi_pcr_z] — at-neutral share 88.5% (n=1074)
- **INFO** extras[dominance_delta] — at-neutral share 8.1% (n=1074) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[sent_fear] — at-neutral share 100.0% (n=1074) — feed effectively dark corpus-wide (dead column)
- **INFO** extras[fear_greed] — at-neutral share 0.0% (n=1074) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance

3 passed, 0 failed (49s)

Corpus: live history (1074 rows)

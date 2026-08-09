# Overfit audit — 2026-08-09 21:05 UTC

Dataset: live history (729 rows)

- **INFO** gap[logistic] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.881 oof_auc=0.496 gap=+0.385; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** gap[gbt] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.867 oof_auc=0.543 gap=+0.324; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** gap[mlp] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.946 oof_auc=0.445 gap=+0.501; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** null-floor[logistic] — OOF Brier 0.3939 vs base-rate constant 0.2393 (base=0.397, n=484) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **INFO** null-floor[gbt] — OOF Brier 0.2852 vs base-rate constant 0.2393 (base=0.397, n=484) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **INFO** null-floor[mlp] — OOF Brier 0.4588 vs base-rate constant 0.2393 (base=0.397, n=484) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **PASS** shuffle: destroyed labels learn nothing OOF — mean_auc=0.486 z=1.1 (limit 3.0)
- **INFO** pbo space — ml.adaptive_gbt.enabled=true — the adaptive rung is IN the measured selection space
- **INFO** pbo — evidence-gated to a single family (no model selection to overfit at this live-row count) (space=['logistic'])
- **PASS** purge: never manufactures out-of-sample edge — unpurged=0.486 purged=0.492 leak_closed=-0.006
- **INFO** purge note — expanding-window design keeps boundary leak ~0 by construction; shuffle-null [OF-2] is the leak gate
- **PASS** dof: not starved (>=10 rows per feature) — rows/feature=11.4 (729 rows / 64 features)
- **INFO** dof: dead-feature fraction (exploration — informational) — dead_frac=0.81 (52 near-zero-importance features) — arms when ml.exploration.enabled is false; reduce the schema (prune experiment) or grow the corpus
- **INFO** dof note — low/zero-importance: ['ret_12_dir', 'ret_1_dir', 'ret_6_dir', 'ret_48_dir', 'sigma_bar_pct', 'imbalance_dir'] ...
- **INFO** plateau[position_sizer.min_p_win] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[profit_taking.chandelier_k] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[pretrade.min_edge_cost_ratio] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** dsr — DEFERRED — 19 conviction-marked live trades < 30 (mixed n=306); mixed-sample dsr=0.000 sr=-0.49; probes are EV-mixed by design (PT-050); gate arms as conviction labels accrue
- **INFO** regime diagnostic caveat — stratum auc/brier below are concatenated-OOF over all scored rows, while the pooled figures they're compared against are MEAN-OF-FOLDS (OF-1's own convention) — the delta is indicative, not a rebasing of the same statistic
- **INFO** regime diagnostic caveat — n= below is a raw signal_history.csv count (candidate+live); oof_n= is the deduped/purged X actually OOF-scored — two different counting passes over related but non-identical data
- **INFO** regime[bull_quiet] — n=46 (candidate=44 live=2) base_rate=0.261
- **INFO** regime[bull_quiet] FLAG — insufficient live coverage (2 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[bull_quiet] oof — oof_n=45 auc=0.570 (pooled 0.543, delta_auc=+0.027) brier=0.2499 (pooled 0.2852, delta_brier=-0.0354)
- **INFO** regime[bull_vol] — n=8 (candidate=8 live=0) base_rate=0.375
- **INFO** regime[bull_vol] FLAG — insufficient live coverage (0 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[bull_vol] oof — oof_n=1 < 30 — insufficient OOF evidence, not scored
- **INFO** regime[range] — n=6507 (candidate=6239 live=268) base_rate=0.202
- **INFO** regime[range] oof — oof_n=102 auc=0.592 (pooled 0.543, delta_auc=+0.049) brier=0.2446 (pooled 0.2852, delta_brier=-0.0406)
- **INFO** regime[bear] — n=3356 (candidate=3320 live=36) base_rate=0.215
- **INFO** regime[bear] oof — oof_n=336 auc=0.434 (pooled 0.543, delta_auc=-0.109) brier=0.3027 (pooled 0.2852, delta_brier=+0.0175)
- **INFO** regime[crisis] — n=0 — absent from corpus
- **INFO** regime[unknown] — n=0 — absent from corpus
- **INFO** learning curve caveat — each point refits gbt on a chronological PREFIX of the corpus (time-purged OOF, deployed protocol) — points are the same statistic across sizes, but none is OF-1's own pooled number
- **INFO** lc[n=182] — oof_n=0 < 40 — not scored
- **INFO** lc[n=292] — oof_n=48 auc=0.256 brier=0.3734
- **INFO** lc[n=401] — oof_n=198 auc=0.443 brier=0.3034
- **INFO** lc[n=510] — oof_n=255 auc=0.472 brier=0.3015
- **INFO** lc[n=620] — oof_n=412 auc=0.484 brier=0.2910
- **INFO** lc[n=729] — oof_n=484 auc=0.477 brier=0.2852
- **INFO** learning curve trend — CLIMBING (delta_auc=+0.131 > +0.03) — data-starved: more rows are still buying skill; corpus growth is the highest-leverage learning input right now
- **INFO** extras[equity_risk_z] — at-neutral share 87.2% (n=729)
- **INFO** extras[opt_pcr_z] — at-neutral share 88.6% (n=729)
- **INFO** extras[opt_oi_pcr_z] — at-neutral share 99.7% (n=729) — feed effectively dark corpus-wide (dead column)
- **INFO** extras[dominance_delta] — at-neutral share 4.1% (n=729) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[sent_fear] — at-neutral share 100.0% (n=729) — feed effectively dark corpus-wide (dead column)
- **INFO** extras[fear_greed] — at-neutral share 0.0% (n=729) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance

3 passed, 0 failed (38s)

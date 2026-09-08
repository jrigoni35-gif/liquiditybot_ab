# Overfit audit — 2026-09-08 23:32 UTC

Dataset: live history (16990 rows)

- **INFO** gap[logistic] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.767 oof_auc=0.552 gap=+0.215; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** gap[gbt] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.817 oof_auc=0.553 gap=+0.264; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** gap[mlp] — INFORMATIONAL (OVER the 0.12 memorization band) - train_auc=0.771 oof_auc=0.552 gap=+0.219; exploration is ON so the corpus is EV-mixed by design (PT-050) - model trust stays enforced by the selection evidence floors + the live governor; this gate arms when ml.exploration.enabled is false
- **INFO** null-floor[logistic] — OOF Brier 0.2712 vs base-rate constant 0.2456 (base=0.433, n=14155) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **INFO** null-floor[gbt] — OOF Brier 0.2483 vs base-rate constant 0.2456 (base=0.433, n=14155) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **INFO** null-floor[mlp] — OOF Brier 0.2988 vs base-rate constant 0.2456 (base=0.433, n=14155) — LOSES TO THE NULL: negative skill, sizing on this model's p(win) is worse than sizing on the base rate
- **PASS** shuffle: destroyed labels learn nothing OOF — mean_auc=0.498 z=0.7 (limit 3.0)
- **INFO** pbo space — ml.adaptive_gbt.enabled=true — the adaptive rung is IN the measured selection space
- **INFO** pbo — evidence-gated to a single family (no model selection to overfit at this live-row count) (space=['logistic'])
- **PASS** purge: never manufactures out-of-sample edge — unpurged=0.486 purged=0.492 leak_closed=-0.006
- **INFO** purge note — expanding-window design keeps boundary leak ~0 by construction; shuffle-null [OF-2] is the leak gate
- **PASS** dof: not starved (>=10 rows per feature) — rows/feature=265.5 (16990 rows / 64 features)
- **INFO** dof coverage — fitted GBT consulted 39/64 features - dead read taken on a model that actually looked
- **INFO** dof: dead-feature fraction (exploration — informational) — dead_frac=0.83 (53 near-zero-importance features) — arms when ml.exploration.enabled is false; reduce the schema (prune experiment) or grow the corpus
- **INFO** dof note — low/zero-importance: ['basis_dir', 'sigma_bar_pct', 'th_barclose', 'equity_risk_z', 'funding_dir', 'dominance_delta'] ...
- **INFO** plateau[position_sizer.min_p_win] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[profit_taking.chandelier_k] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** plateau[pretrade.min_edge_cost_ratio] — flat surface (pnl [0.0, 0.0, 0.0], entries [0, 0, 0]) — parameter inert on this recording
- **INFO** OF-5 trials: assumed N=7 (no ledger at C:\Users\haird\Documents\liquiditybot\liquiditybot_ab\outputs\trial_ledger.csv; var=SR^2 fallback)
- **INFO** dsr REACHABILITY — UNPASSABLE at N=7: the var_trial_sr=SR^2 fallback makes sr0 = 1.387x|SR|, so the rejection threshold scales with the statistic and dsr>=0.90 is attainable for NO sample (exhaustive sweep 2026-08-31: 0/518616 combinations pass at N=7, max dsr 0.4262). This gate cannot produce a green — read any OF-5 line below as INERT, not as evidence. Repair needs a var_trial_sr MEASURED from per-trial SR (trial_ledger v0.1 records none), never a threshold move.
- **INFO** dsr — DEFERRED — 28 conviction-marked live trades < 30 (mixed n=418); mixed-sample dsr=0.000 sr=-0.38; probes are EV-mixed by design (PT-050); gate arms as conviction labels accrue
- **INFO** regime diagnostic caveat — stratum auc/brier below are concatenated-OOF over all scored rows, while the pooled figures they're compared against are MEAN-OF-FOLDS (OF-1's own convention) — the delta is indicative, not a rebasing of the same statistic
- **INFO** regime diagnostic caveat — n= below is a raw signal_history.csv count (candidate+live); oof_n= is the deduped/purged X actually OOF-scored — two different counting passes over related but non-identical data
- **INFO** regime[bull_quiet] — n=3590 (candidate=3567 live=23) base_rate=0.395
- **INFO** regime[bull_quiet] FLAG — insufficient live coverage (23 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[bull_quiet] oof — oof_n=3004 auc=0.589 (pooled 0.553, delta_auc=+0.036) brier=0.2530 (pooled 0.2483, delta_brier=+0.0047)
- **INFO** regime[bull_vol] — n=1746 (candidate=1733 live=13) base_rate=0.458
- **INFO** regime[bull_vol] FLAG — insufficient live coverage (13 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[bull_vol] oof — oof_n=1721 auc=0.617 (pooled 0.553, delta_auc=+0.064) brier=0.2347 (pooled 0.2483, delta_brier=-0.0136)
- **INFO** regime[range] — n=10682 (candidate=10363 live=319) base_rate=0.299
- **INFO** regime[range] oof — oof_n=3298 auc=0.612 (pooled 0.553, delta_auc=+0.059) brier=0.2416 (pooled 0.2483, delta_brier=-0.0067)
- **INFO** regime[bear] — n=7262 (candidate=7199 live=63) base_rate=0.341
- **INFO** regime[bear] oof — oof_n=2267 auc=0.561 (pooled 0.553, delta_auc=+0.007) brier=0.2618 (pooled 0.2483, delta_brier=+0.0135)
- **INFO** regime[crisis] — n=4120 (candidate=4120 live=0) base_rate=0.436
- **INFO** regime[crisis] FLAG — insufficient live coverage (0 live < 30) — operator rationale for #103 T4's regime-coverage probe term
- **INFO** regime[crisis] oof — oof_n=3865 auc=0.618 (pooled 0.553, delta_auc=+0.065) brier=0.2484 (pooled 0.2483, delta_brier=+0.0002)
- **INFO** regime[unknown] — n=0 — absent from corpus
- **INFO** learning curve caveat — each point refits gbt on a chronological PREFIX of the corpus (time-purged OOF, deployed protocol) — points are the same statistic across sizes, but none is OF-1's own pooled number
- **INFO** lc[n=4248] — oof_n=3540 auc=0.613 brier=0.2396
- **INFO** lc[n=6796] — oof_n=5660 auc=0.550 brier=0.2566
- **INFO** lc[n=9344] — oof_n=7785 auc=0.535 brier=0.2655
- **INFO** lc[n=11893] — oof_n=9910 auc=0.478 brier=0.2753
- **INFO** lc[n=14442] — oof_n=12035 auc=0.574 brier=0.2519
- **INFO** lc[n=16990] — oof_n=14155 auc=0.606 brier=0.2483
- **INFO** learning curve trend — FLAT (|delta_auc=+0.008| <= 0.03) — representation-limited: more rows alone are not buying skill; feature/label quality is the binding constraint, not corpus size
- **INFO** extras[equity_risk_z] — at-neutral share 26.0% (n=16990) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[opt_pcr_z] — at-neutral share 26.4% (n=16990) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[opt_oi_pcr_z] — at-neutral share 26.4% (n=16990) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[dominance_delta] — at-neutral share 2.2% (n=16990) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance
- **INFO** extras[sent_fear] — at-neutral share 100.0% (n=16990) — feed effectively dark corpus-wide (dead column)
- **INFO** extras[fear_greed] — at-neutral share 0.0% (n=16990) — feed live for most of the corpus; consider the missingness-indicator column (schema bump) if this family earns model importance

3 passed, 0 failed (123s)

Corpus: live history (16990 rows)

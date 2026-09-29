# Model program 1–3 — decision record (operator ruling 2026-09-29)

- authority: operator lifted the 2026-08-10 model freeze ("Lift the model freeze"),
  then "Fit 1-3 into the bot", then chose the REVISED plan below over reopening the
  2026-07-26 label ruling.
- recorder: Claude Code session "Claude RC". Cohort: this ships as a fork
  (`core/cohort.py`); its fingerprint is stamped at the boot that adopts it.

## Why the plan was revised before building

The first framing of item 1 — "label on the traded exit" — is `ml.label_mode:
exit_policy`, which already exists and was turned off by the 2026-07-26 ruling on
measured evidence (`docs/quant/2026-07-26_label_signal_quality.md`: exit-policy
labels recorded WHICH EXIT FIRED; barrier-alone AUC 0.769 beat the 62-feature
model's 0.597). Re-running it would re-litigate a settled decision with nothing new.

## 1a — the traded bracket is the labeled bet (SHIPPED)

Measured (era-9, signal_history.csv, read 2026-09-29T14:15Z): candidate LABEL rows
median PT/SL **181.1 / 135.8 bps** (n=6,830) vs live TRADE rows **199.9 / 150.6**
(n=80). Cause: the labeler fed `barrier_geometry` `rt_cost + capped spread`; the
bracket fed it the pretrade `est_cost` (fees + spread + impact + adverse selection).
Fix: one pure function `ml.labeling.label_cost_pct`, called by both, on the same
spread registration passes. The 34k existing labels are untouched (no relabel, no new
label era, no schema change); the bracket moves to the label geometry. The pretrade
`est_cost` stays the entry VETO's input. Positions carry `bracket_label_cost_pct` so
the ML-082 comparator nets the same cost. Mutation-verified; persistence pinned.

## 1b + 3 — the shadow traded-value rule (SHIPPED, decides nothing)

`ml/shadow_policy.py` logs the model's p at every real candidate registration (the
corpus never stored p-at-entry; rescoring old trades with today's champion would leak).
`scripts/shadow_policy_report.py` joins outcomes and grades *enter iff predicted value
> 0* walk-forward (no look-ahead — mutation-proven), CS-1 reconciled, against live.
Promotion only under `docs/law/shadow_policy_promotion.md` (≥200 would-enter
outcomes, day-block CI > 0, beats live, overfit battery green, operator record).
Purity pinned: no order-path module reads the store. At ship time the report reads
`NOT YET 0/200` — the store starts at the adopting boot.

## 2 — feature research (RUN; finding: no stable out-of-sample signal)

`scripts/feature_stability.py --label-span 432` (the purge span matches the real
432-bar horizon; the default 96 would under-purge), snapshot
`outputs/feature_reports/stability_20260929-180403`: corpus 24,228 rows (105 live),
9 seed×split combos. **58–66 of ~68 features dead per combo; 44 always dead;
stability ratio 0.698.** Five dead on all 43 dated snapshots (prune candidates):
`ofi_dir, pat_engulf_dir, sent_fear, th_clockwork, th_metronome`. Consistent with the
2026-09-01 edge-hunter result (no stored or tape feature directional).
**Conclusion: the lever is NEW information, not a new model on these features.**
Pruning the five is deferred (a schema change for little gain; the v9→v10 bump cost a
72-minute cold start). New feature ideas enter as shadow columns under the existing
promotion law (`ml/features.py`: 3 stable snapshots, overfit battery green, markout
delta on ≥200 entries), judged by this same screen.

## What was NOT changed

Labels, exit geometry beyond the 1a cost basis, sizing, the p-bar entry rule (until the
shadow rule is promoted), and the 2026-07-26 label ruling.

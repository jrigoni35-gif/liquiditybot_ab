---
title: Era Exclusion Decision (2026-07-26)
category: source
summary: Ships an era-gated load-time training filter that auto-activates at 150 new-era rows and removes every old-era row, with an absolute nothing-is-ever-deleted bound
tags: [era-exclusion, label-era, corpus, ml-081]
sources: 1
updated: 2026-08-01
---

# Era Exclusion Decision (2026-07-26)

**Raw source:** `raw/quant/2026-07-26_era_exclusion.md`

## What shipped
An **era-gated, load-time-only training exclusion**: once 150 new-era `triple_barrier` rows exist,
the filter auto-activates and removes every old-era row (candidate AND live) from the training view.
See [[concepts/era-exclusion]].

## The absolute bound
**Nothing is ever deleted.** Exclusion happens at LOAD time, in the training view only. Every row
stays byte-for-byte in `outputs/signal_history.csv`, the audit trail, and every bundle.
`_apply_era_exclusion` runs as the very LAST step of `load_training_data`; when inactive it returns
the pre-existing lists unchanged, by reference.

## Two conscious overrides
1. **Old-era exclusion covers LIVE rows too**, overriding the Phase-3 T3.6 term "candidate rows ONLY
   excludable (live rows NEVER, any era)" — because all 242 measured live rows are themselves
   old-era, so keeping them "would shrink the corpus without cleaning it."
2. **Ships gated and INERT**, auto-activating at a row threshold, because there were ZERO new-era
   rows at decision time. "Never a manual flip."

## Corpus as measured (4,897 rows, all old-era)
`exit_sim`/candidate 2481 @ 0.1391 | `legacy`/candidate 1734 @ 0.2572 | `exit_sim_time_stop`/candidate
440 @ 0.0068 | `exit_sim`/live 195 @ 0.1026 | `legacy`/live 47 @ 0.4043. New-era rows: **0**.

## Design details
- **Era-based, not time-based** — keys off the row's own `barrier` string, never a clock. A backfill
  written today under the old labeler is excluded on its era.
- `LABEL_ERA_UNKNOWN` is treated as OLD-era (excludable) — a conservative choice.
- Threshold `min_new_era_rows = 150` is **derived, not invented**: it equals `ml.min_train_rows` and
  `ml.model_selection.min_total_rows["gbt"]/["blend"]`.
- `armed` and `active` surface INDEPENDENTLY so an operator can tell "threshold met but rolled back"
  from "not yet met". Reason code **ML-081** fires once on the inactive->active transition.
- `forced_off` is the rollback lever and always wins over `forced_on`; `config_guard` FATALs on both
  true, and on `forced_on` while `ml.label_mode != "triple_barrier"`.

## Cross-consumer wiring
All real consumers wired **in the same commit** (`main.py:4626`, `overfit_check.py:179`,
`train_meta.py:146`, `interpret_report.py:151`, `feature_stability.py:277`, plus
`learning_curve.py:336`), with `smoke_test.py:1006` and `bench_hotpath.py:41` consciously EXEMPTED.
Rationale: unlike `ml.epoch`, this filter auto-activates on row counts with no human flip, so an
unwired consumer could silently measure a stale corpus the moment the threshold crosses on disk.
This resolves the prerequisite [[sources/pbo-admission-policy]] had merely recorded, and finds two
call sites that doc's enumeration missed.

## Consequence
Activated 2026-07-28 at 663 new-era rows — recorded as the eighth transition in
[[sources/of3-pbo-data-shift]]. Its later interaction with a horizon-qualified era is the
"fix that hid the fix" in [[sources/live-label-era-deadlock]].

## Related
[[entities/historystore]] · [[comparisons/era-exclusion-vs-epoch-filter]]

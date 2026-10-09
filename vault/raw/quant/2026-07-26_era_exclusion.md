# Era-gated training exclusion (2026-07-26)

Operator decision, taken with the measured corpus in front of them. Two
choices were made explicitly and BOTH consciously override earlier
defaults/terms — neither is softened here, neither is re-litigated.

1. **Old-era exclusion covers LIVE rows too.** This overrides the Phase-3
   T3.6 term "candidate rows ONLY excludable (live rows NEVER, any era)"
   (`docs/quant/pbo_admission_policy.md`'s sibling filter, `ml.epoch`).
   Rationale the operator accepted: all 242 measured live rows are
   themselves old-era, so keeping them would leave a small corpus that
   still carries the exit-policy label poison — shrinking the corpus
   without cleaning it.
2. **Ships gated and inert; auto-activates at a row threshold.** There
   were ZERO new-era rows measured at decision time, so activating
   immediately would train on an empty set. The filter arms itself only
   once enough new-era rows exist to be worth training on — never a
   manual flip.

## THE ABSOLUTE BOUND — unchanged, non-negotiable

**Nothing is ever deleted.** Exclusion happens at LOAD time, in the
training view only. Every row stays byte-for-byte in
`outputs/signal_history.csv`, in the audit trail, and in every bundle.
Flipping the config back off (`forced_off: true`, or the corpus falling
back below threshold) restores the previous training set EXACTLY — see
`tests/test_era_exclusion.py::test_round_trip_forced_off_restores_pre_exclusion_baseline`,
the load-bearing proof.

The implementation guarantees this structurally, not by convention: the
era filter (`ml/history.py` `_apply_era_exclusion`) runs as the very LAST
step of `load_training_data`, after every existing weight/stat computation
(uniqueness correction, mass-preserving rescale, prior-skew detector,
label-era/mix-drift telemetry, lineage/divergence stats). When inactive it
returns the pre-existing `X`/`y`/`w`/`sig`/`meta` lists **unchanged, by
reference** — a below-threshold or rolled-back load is byte-identical to a
load with no `era_cfg` at all, because no code path between "build the row"
and "return it" is any different.

## Corpus as measured (2026-07-26, 4,897 rows) — all of it old-era

| era | source | rows | label rate |
|---|---|---|---|
| `exit_sim` | candidate | 2481 | 0.1391 |
| `legacy` | candidate | 1734 | 0.2572 |
| `exit_sim_time_stop` | candidate | 440 | 0.0068 |
| `exit_sim` | live | 195 | 0.1026 |
| `legacy` | live | 47 | 0.4043 |

New-era (`triple_barrier`, the 2026-07-26 signal-quality relabel, commit
`d5a9859`) rows measured at decision time: **0**.

## The mechanism

Era-based, not time-based. Exclusion keys off the row's `label_era` tag
(`ml/history.py`, `label_era_of`/`_row_label_era`), never a clock — a
backfill or replay written today under the old labeler is excluded on its
era, and a re-simulated old row cannot sneak in on a fresh timestamp. This
is a DIFFERENT mechanism from the existing time-based filter
(`ml.epoch.exclude_old_candidates`, shipped `false`, `candidate_cutoff_ts`
marker) — that one stays untouched, unmerged, unremoved.

The era tag is a persisted CSV column (`label_era`, written explicitly by
`HistoryStore._append_row` for every row since commit `a063fe0`) with a
load-time fallback for rows written before that column existed
(`_row_label_era` re-derives from the row's own `barrier` cell). Both paths
feed the SAME exclusion decision —
`tests/test_era_exclusion.py::test_pre_task_row_without_label_era_column_still_excludable`
pins that a column-less legacy row is excluded exactly like a
persisted-column row.

### `LABEL_ERA_UNKNOWN`: treated as OLD-era, a conscious choice

An unrecognized barrier string is not evidence that a row is new-era — it
is evidence only that `label_era_of` has never seen that barrier before
(a future labeler variant, a hand-edited row, a bug). The conservative
reading — treat `unknown` as OLD-era, excludable once the filter is active
— is what ships (`_apply_era_exclusion` only *keeps* a row when its era is
exactly `LABEL_ERA_TRIPLE_BARRIER`; every other era, including `unknown`,
is excluded). The alternative (treat `unknown` as new-era, i.e. keep it)
would let an unrecognized/malformed barrier ride into the "clean" new-era
training set on nothing but the absence of a match — exactly backwards
from the conservative posture this whole task is built on. Pinned:
`tests/test_era_exclusion.py::test_at_threshold_excludes_every_old_era_row_including_live`
asserts an `unknown`-barrier row is excluded when the filter is active.

### Threshold: `ml.era_exclusion.min_new_era_rows = 150`

Not an invented round figure. It equals:

- `ml.min_train_rows` (150) — the floor below which `ml/meta_model.py` and
  `scripts/train_meta.py` refuse to fit ANY model at all, on ANY corpus.
- `ml.model_selection.min_total_rows["gbt"]` / `["blend"]` (150) — the
  evidence-gate floor (`ml/walkforward.py`, `docs/quant/...` model_selection
  doc) for the first non-trivial rung above `logistic`, which per that
  gate's own doc is "always admissible and defines the simplicity floor"
  with no additional row requirement of its own beyond the global
  `min_train_rows`.

So 150 is "enough to train the simplest admissible family" in the most
literal sense available: it is the SAME floor the corpus already has to
clear to train anything whatsoever, applied to the new-era subset alone.
Training on fewer new-era rows than the corpus itself requires to produce
a model at all would not be "worth training on" by the project's own
existing standard — there was no need to invent a new number.

### Activation rule

```
new_era_rows = count of rows tagged LABEL_ERA_TRIPLE_BARRIER that already
               survived every OTHER admissibility check the loader applies
               (book=="long" exclusion, dirty-row drop, clash-dedup, the
               ml.epoch filter)
armed  = new_era_rows >= min_new_era_rows
active = (armed OR forced_on) AND NOT forced_off
```

- `forced_off` (config, default `false`): the **rollback lever**. Forces
  the filter OFF regardless of the threshold. Always wins over
  `forced_on` (`config_guard` FATALs the contradiction of both being
  true).
- `forced_on` (config, default `false`, **never flipped true in this
  commit's shipped config**): a manual override lever that forces the
  filter ON regardless of the threshold. The threshold arms this feature,
  not an operator flipping a switch — `forced_on` exists as a lever (for
  the rollback's mirror-image and for tests), not as a shipped behavior.
  `config_guard` FATALs `forced_on: true` unless `ml.label_mode ==
  "triple_barrier"`: forcing the filter active while the labeler can never
  produce the era it selects for (label_mode reverted to `"exit_policy"`)
  would train on zero rows forever — the era tag this filter needs is
  unavailable under that label mode.

Both `armed` and `active` are surfaced independently in
`last_load_stats["era_exclusion"]` precisely so an operator can observe
"threshold met but rolled back" (armed=true, active=false) as a distinct
state from "not yet met" (armed=false, active=false) — see
`tests/test_era_exclusion.py::test_round_trip_forced_off_restores_pre_exclusion_baseline`.

### `last_load_stats["era_exclusion"]` shape

```json
{
  "armed": true,
  "active": true,
  "forced_off": false,
  "forced_on": false,
  "min_new_era_rows": 150,
  "new_era_rows": 187,
  "excluded": {
    "total": 4897,
    "by_era_source": {
      "exit_sim": {"candidate": 2481, "live": 195},
      "legacy": {"candidate": 1734, "live": 47},
      "exit_sim_time_stop": {"candidate": 440}
    }
  }
}
```

Present in ALL three states (below threshold / at-or-above threshold /
forced off) with `excluded == {"total": 0, "by_era_source": {}}` whenever
`active` is false — the operator can watch the transition happen in
`status.json` rather than infer it.

### Registered reason code

`Code.ML_ERA_EXCLUSION_ACTIVE` (`ML-081`, `core/codes.py`) fires once on
the inactive→active transition, never once per load — edge-triggered on a
per-`HistoryStore`-instance flag
(`HistoryStore._era_exclusion_active_seen`). A rollback (`forced_off`) then
a later re-arm is a NEW transition and logs again (pinned:
`test_activation_code_relogs_after_rollback_and_rearm`). Pinned that it
never fires below threshold
(`test_below_threshold_never_logs_activation`) and never spams across
repeated active loads (`test_activation_code_fires_once_on_transition_not_per_load`).

## Composition with `ml.epoch.exclude_old_candidates`

Two independent filters, both real production consumers of
`ml/history.py load_training_data`:

- `ml.epoch` — TIME-based. Excludes CANDIDATE rows (never live) whose
  resolve `ts` predates `candidate_cutoff_ts` (2026-07-23T18:20:55Z /
  epoch seconds `1784830855`). Shipped `false`.
- `ml.era_exclusion` — ERA-based. Excludes every OLD-era row (any source,
  including live) once armed. Threshold-armed, auto-activating.

Both may be active simultaneously. **Composition is coherent by
construction**: the epoch filter runs first (per-row, inside the main
loop), the era filter runs last (post-hoc, over the full survivor set).
With both on: a row survives only if it clears BOTH — (candidate with
`ts >= cutoff`, OR live) AND era == `triple_barrier`. Because every
`triple_barrier`-tagged row can only exist from 2026-07-26 onward (the
relabel's own commit date), and the epoch cutoff predates that by three
days, **no `triple_barrier` row can ever be epoch-excluded today** — so
with both filters on, the resulting corpus is identical to running the
era filter alone. This composition was verified structurally, not just
asserted: the epoch check's own guarantee (`_row_epoch_excluded`,
`ml/history.py`) is that it only ever runs inside the `source ==
"candidate"` branch, so it can only ever make the pre-era-filter survivor
set SMALLER or equal — it cannot un-exclude anything the era filter would
otherwise keep, and (given the timestamp fact above) it cannot exclude
anything the era filter would otherwise keep either.

## Cross-consumer wiring (the prerequisite that sank the epoch filter)

`docs/quant/pbo_admission_policy.md` records that only 1 of 6
training-corpus consumers received `ml.epoch`'s `epoch_cfg` at all. That
gap was tolerable for `ml.epoch` because it ships `false` forever until a
future, conscious flip. It is NOT tolerable here: `ml.era_exclusion`
auto-activates on the corpus's own row counts with no human flip required,
so an unwired consumer could silently start measuring/training a stale
corpus the moment the threshold crosses on disk. Resolved in this same
commit, not deferred:

| consumer | wired? | reason |
|---|---|---|
| `main.py:4626` (production retrain path) | **yes** | the deployed champion must train on the filtered view when active |
| `scripts/overfit_check.py:179` (OF-3 PBO measurement) | **yes** | PBO must measure the rule the system actually runs (the exact invariant this doc's cross-reference protects) |
| `scripts/train_meta.py:146` (standalone retrain CLI) | **yes** | produces a real deployable model artifact |
| `scripts/interpret_report.py:151` (post-hoc interpretability) | **yes** | attribution must be computed over the rows the champion actually trained on |
| `scripts/feature_stability.py:277` (T3.1 dead-feature screen) | **yes** | prune/keep decisions must reflect the deployed corpus |
| `scripts/smoke_test.py:1006` (`test_candidate_labeling`) | **exempted** | a synthetic, single-row candidate fixture with no `config.json` in scope at all — structurally incapable of ever reaching any sane `min_new_era_rows` threshold. Same exemption precedent `docs/quant/pbo_admission_policy.md` already applies to this exact consumer for `ml.epoch`. |

Two MORE `load_training_data` call sites turned up during implementation that
`docs/quant/pbo_admission_policy.md`'s existing enumeration (written for
`ml.epoch`) does not list — handled with the same wire-or-exempt discipline
rather than silently left inconsistent:

| consumer | wired? | reason |
|---|---|---|
| `scripts/learning_curve.py:336` (T2.3 learning-curve report) | **yes** | its own docstring's stated premise is "refits the DEPLOYED walkforward selector" — a curve computed over a different row set than what actually deploys is not a learning curve for the deployed process. |
| `scripts/bench_hotpath.py:41` (`bench_load_training_data`) | **exempted** | a `timeit` microbenchmark over synthetic random rows with no `config.json` read at all — times the parse+hygiene cost of the call, makes no selection/PBO/report decision from the data, so there is no config coupling to wire in the first place. |

See `docs/quant/pbo_admission_policy.md`'s "Cross-reference: `ml.era_exclusion`"
section for the reverse pointer.

## Rollback procedure

Set `ml.era_exclusion.forced_off = true` in `config.json` and restart (or,
if the corpus has not yet crossed `min_new_era_rows`, do nothing — the
filter is already inactive). No data migration in either direction: every
row's `label`, `barrier`, and `label_era` stand exactly as written, and
`_apply_era_exclusion`'s inactive branch returns the pre-existing training
view unchanged, by reference — restoring the pre-exclusion training set
byte-for-byte is the DEFAULT behavior of turning the filter off, not a
special case that needed separate engineering.

## What did NOT change

- `outputs/signal_history.csv`: no row rewritten, reweighted, reordered, or
  deleted, in any era, for any reason.
- `ml.epoch.exclude_old_candidates` / `candidate_cutoff_ts`: untouched,
  unmerged, unremoved — a different mechanism, still shipped `false`.
- `BRIER_MARGIN`, the evidence floors, the simplicity ladder, any
  quant-trial/overfit gate threshold.
- The uniqueness correction, mass-preserving rescale, prior-skew detector,
  label-era/mix-drift telemetry, and lineage/divergence stats: all still
  computed over the FULL pre-exclusion corpus (the era filter runs after
  all of them) — their meaning as full-corpus report-only instruments is
  unchanged by this task.
- `scripts/overfit_check.py`'s OF-1..OF-8 gate results: measured **5
  passed, 3 failed before AND after this task** (the same pre-existing
  OF-1 gap trio the 2026-07-26 label-redefinition task also reported
  unmoved) — the corpus has 0 new-era rows, so the filter stays inactive
  (`armed=false`) regardless of wiring; see the task report for the full
  run output.

## Task reference

`.superpowers/sdd/task-eraexclude-brief.md`,
`.superpowers/sdd/task-eraexclude-report.md`.

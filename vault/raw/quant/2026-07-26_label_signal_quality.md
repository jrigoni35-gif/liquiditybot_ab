# Label redefinition: signal quality, not exit policy (2026-07-26)

Operator decision, consciously overriding commit `c36aa90` ("flip label
default to exit-policy replay — train on the bet we trade"). That decision
was defensible; the operator weighed it against measured evidence below and
chose the other side. `ml.label_mode` is now `"triple_barrier"` in
`config.json`; `"exit_policy"` remains a supported value (rollback path / A-B
arm), config_guard-validated.

## Why (measured, deep-dive evidence — binding, not re-derived)

The label was produced by replaying the live exit engine
(`simulate_exit_policy`), so it recorded WHICH EXIT FIRED rather than
whether the signal was any good. Label rate by exit reason spans 100x:

| exit reason | label rate |
|---|---|
| `time_stop` | **0.0071** |
| `sl` | 0.0364 |
| `time` | 0.0686 |
| `realized` | 0.1036 |
| `trail` | **0.6867** |

`trail` — the only winning bucket — fell from 49.5% of daily rows to 0.0%
while `sl` + `time_stop` grew to 100%, which is what collapsed the base rate
from ~0.31 to ~0.03. `time_stop` alone reached 43.8% of rows at a 0.71% win
rate, and its first appearance (07-23 17:03Z) is 14 minutes after commit
`5f26d3f` taught the label simulator to mirror the P2 time-stop. A time-stop
is a RISK CONTROL ("we chose not to wait"), not an OUTCOME ("the signal was
wrong"). Downstream consequences measured: barrier-alone AUC 0.769 beats the
62-feature model's own 0.597, a pure clock scores 0.667, and BSS is negative
for both champion and challenger — the model was learning the barrier, not
the signal.

## The change

`ml.label_mode = "triple_barrier"`. That labeler (`ml/labeling.py:363`,
`triple_barrier()`) yields barriers that are all market- or
horizon-determined — profit target, stop, vertical — with the existing
net-of-cost rule unchanged (`label_pt_vol_mult=8`, `label_sl_vol_mult=6`,
`label_round_trip_cost_pct=0.5`). No policy exit reason (`time_stop`,
`trail`, `tier`, `floor`, `realized`) can enter the label under this mode:
`CandidateLabeler._label`'s triple_barrier branch never calls
`simulate_exit_policy` at all (`ml/history.py`).

## The era-collision blocker, and how it was resolved

`label_era_of()` (`ml/history.py`) derives each row's label-definition era
purely from its own `barrier` string — deliberately, so a backfill or replay
tags correctly regardless of which config was live when it ran. Before this
task the vocabulary was: blank/`pt` → `legacy`; `{trail, realized, tier,
floor, sl, time}` → `exit_sim`; `time_stop` → `exit_sim_time_stop`.

`triple_barrier()` itself emits bare `pt`/`sl`/`time` — the SAME strings
`legacy` and `exit_sim` already claim. Flipping `label_mode` alone would have
silently mis-tagged every new row as one of those two OLD, incompatible
populations — exactly the failure the era instrument exists to catch (a
mix-drift alarm firing on a mix it mis-attributes, per-era label rates
blending incompatible definitions).

**Fix:** `CandidateLabeler._label` (`ml/history.py`) prefixes
`triple_barrier()`'s own bare barrier with `tb_` — `tb_pt` / `tb_sl` /
`tb_time` — at the one call site whose output reaches the persisted corpus
(`_emit_label` → `HistoryStore._append_row`'s `barrier` cell). This is the
ONLY call site that persists a `triple_barrier()` outcome:
`_record_shadow_horizons` and `bootstrap_dataset` also call
`triple_barrier()` directly, but neither ever writes its `.barrier` field to
disk, so they needed no change. `triple_barrier()` itself is untouched (its
bare vocabulary is depended on directly by other tests/callers) — the prefix
is threaded at the dispatch call site, not forked into the labeler.

A new era constant, `LABEL_ERA_TRIPLE_BARRIER = "triple_barrier"`, is
distinct from all four existing values (`legacy`, `exit_sim`,
`exit_sim_time_stop`, `unknown`) by construction. `label_era_of` maps
`{tb_pt, tb_sl, tb_time}` to it and nothing else; `_EXIT_SIM_BARRIERS` and
the pre-existing era constants are untouched. `label_era_of` remains a pure
function of the row's own `barrier` cell — no config or calendar lookup.

Proof (see `tests/test_label_era.py`,
`test_label_era_of_barrier_vocabulary` and
`test_triple_barrier_vocabulary_never_collides_with_legacy_or_exit_sim`):
before this fix, `from ml.history import LABEL_ERA_TRIPLE_BARRIER` fails
(`ImportError`) — RED. After, `label_era_of("tb_pt")` ==
`LABEL_ERA_TRIPLE_BARRIER`, and explicitly `!= LABEL_ERA_LEGACY` and `!=
LABEL_ERA_EXIT_SIM` — GREEN.

## What did NOT change

- `simulate_exit_policy` itself: untouched, still correct for what it
  models (execution) — it just no longer feeds the label.
- The existing ~4900-row corpus (`outputs/signal_history.csv`, gitignored):
  **no row is rewritten, reweighted, excluded, or deleted, in any era, for
  any reason.** Every row's `label`, `barrier`, and `label_era` stand exactly
  as written. The `legacy`/`exit_sim`/`exit_sim_time_stop` populations keep
  their old labels — this task governs only rows written from here on.
  Whether to exclude the old eras from training is a SEPARATE operator
  decision this task leaves open (excluding them would collapse the corpus
  below the evidence floors).
- `BRIER_MARGIN`, the evidence floors, the simplicity ladder, and every
  quant-trial/overfit gate: unchanged, not retuned.
- `scripts/overfit_check.py`: reads the frozen historical corpus, which is
  label-mode-agnostic (rows already carry their own `barrier`/`label_era`).
  Before and after this change: **5 passed, 3 failed** (report content
  byte-identical but for the run timestamp/duration) — the pre-existing
  OF-1 gap trio, corpus-driven, not moved by this task.

## Rollback

Set `ml.label_mode` back to `"exit_policy"` in `config.json` and restart.
`config_guard` FATALs on any value other than `"exit_policy"` or
`"triple_barrier"` (previously unvalidated — a typo silently fell back to
`triple_barrier` with no error). No data migration is needed either
direction: both label definitions coexist in the corpus, tagged by
`label_era`, and `label_era_of` re-derives correctly for any row regardless
of which mode produced it.

## Task reference

`.superpowers/sdd/task-signalquality-brief.md`,
`.superpowers/sdd/task-signalquality-report.md`.

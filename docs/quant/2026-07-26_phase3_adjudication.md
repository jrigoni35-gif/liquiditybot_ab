# Phase 3 experiment adjudication — T3.6

Date: 2026-07-26 · Status: MEASURED. **All production flags remain OFF**
(`ml.gbt_mono.enabled`, `ml.epoch.exclude_old_candidates`, and every other
Phase 3 flag) **pending operator sign-off** — nothing in this document
flips a config default. This closes Phase 3 by actually running the
instruments Tasks 1–5 shipped inert and adjudicating them against the
binding rule in `docs/quant/pbo_admission_policy.md`.

Scope of "inert", stated precisely: with the shipped config, deployed
behavior is identical to the pre-phase main (`e843b92`) — proven by
running that commit in a worktree against today's corpus and getting
md5-identical OF verdict lines (`f68296e3775e3787f3c473c461563a92`, all
eight checks), and separately by an `evaluate_and_select` retrain-path
comparison that is md5-identical per family. There is exactly ONE
observable difference: `last_load_stats` now always carries
`epoch_excluded` (0 while the filter is off), and `runner.py` writes
`last_load_stats` verbatim into `status.json`, so `status.json` gains one
additive key. No consumer reads it; the "extend, don't break" schema rule
permits it. Recorded here so no later reader takes "changes nothing"
literally and is surprised by a new status key.

Corpus for every reading below: `outputs/signal_history.csv`, 4,642 rows
(240 live), unchanged across all three stability snapshots and all four
OF-3 experiment runs — every comparison in this document is apples-to-
apples on one static corpus. `outputs/` is gitignored, so the raw
snapshot/report/prune JSON files referenced below stay local; every
number that matters is pasted inline here.

## 1. Feature-stability: three dated snapshots

`scripts/feature_stability.py` run three times (seeds×n_splits = 3×3 = 9
combos each run, unchanged defaults otherwise):

| snapshot | seeds | corpus | n_live | always_dead (n) |
|---|---|---|---|---|
| `stability_20260726-063915.json` (pre-existing) | 7,11,13 | 4642 | 240 | 13 |
| `stability_20260726-105913.json` | 17,19,23 | 4642 | 240 | 10 |
| `stability_20260726-105959.json` | 29,31,37 | 4642 | 240 | 10 |

Snapshot 1's 13: `corr_shift, depth_ratio, dominance_delta, equity_risk_z,
imbalance_delta_dir, liq_pocket_pull, opt_oi_pcr_z, pat_engulf_dir,
pat_marubozu_dir, ret_12_dir, sent_fear, th_clockwork, th_metronome`.

Snapshot 2's 10: `corr_shift, depth_ratio, equity_risk_z, opt_oi_pcr_z,
opt_pcr_z, pat_engulf_dir, pat_hammer_dir, sent_fear, th_clockwork,
th_metronome`.

Snapshot 3's 10: `corr_shift, depth_ratio, equity_risk_z, opt_oi_pcr_z,
pat_engulf_dir, pat_hammer_dir, sent_fear, th_clockwork, th_metronome,
volume_z`.

**Three-way stable intersection** (script's own `candidate_prune_list`,
computed by snapshot 3 against both priors; cross-date persistence =
1.000 for every one of these 8, confirmed in snapshot 3's persistence
table) — **NOT empty**, so step 2 (coverage-floor screen) applies:

```
corr_shift, depth_ratio, equity_risk_z, opt_oi_pcr_z, pat_engulf_dir,
sent_fear, th_clockwork, th_metronome
```

(`dominance_delta, imbalance_delta_dir, liq_pocket_pull, pat_marubozu_dir,
ret_12_dir` from snapshot 1 and `opt_pcr_z, pat_hammer_dir, volume_z` from
snapshots 2/3 dropped out — not always-dead in every snapshot, so not
stable.)

## 2. Coverage-floor screen (binding — `pbo_admission_policy.md`)

The admission policy is explicit: **`always_dead` membership alone does
not make a feature prune-eligible.** A feature that is dead because the
corpus hasn't yet seen its triggering condition is capability held in
reserve, not dead weight — pruning it blinds the bot exactly when the
condition (a regime shift, a manipulation onset) starts to matter. Of the
8 stable candidates above, the policy doc already named 3 of snapshot 1's
13 as dormant/coverage-starved and NOT prune-eligible: `sent_fear`
(feed-constant), and the THALES manipulation detectors `th_clockwork` /
`th_metronome`.

Independently recomputed against the live corpus (not copied from the
policy doc — a fresh pass, `ml.history.HistoryStore` via
`config.json`'s `ml.history_path`/`ml.sample_weights`, same load path
`feature_stability.py` uses):

| feature | nonzero_frac | n_unique | std | verdict |
|---|---:|---:|---:|---|
| corr_shift | 0.8912 | 3909 | 0.1546 | cleared — prune-eligible |
| depth_ratio | 1.0000 | 4486 | 0.4260 | cleared — prune-eligible |
| equity_risk_z | 0.1094 | 293 | 0.3691 | cleared — prune-eligible |
| opt_oi_pcr_z | 0.0545 | 60 | 0.3295 | cleared — prune-eligible |
| pat_engulf_dir | 0.1243 | 193 | 0.3200 | cleared — prune-eligible |
| sent_fear | 0.0000 | 1 | 0.0000 | **DORMANT — not prune-eligible** |
| th_clockwork | 0.0134 | 59 | 0.0424 | **DORMANT — not prune-eligible** |
| th_metronome | 0.0149 | 68 | 0.0437 | **DORMANT — not prune-eligible** |

Median nonzero-fraction across all 62 `FEATURE_NAMES` columns: **0.8912**
(matches the ~89% cited in the policy doc). These numbers match
`pbo_admission_policy.md`'s own Task-5 probe exactly (same corpus, same
computation) — recomputing independently rather than trusting the prior
doc is the point of this step, and it reproduced byte-for-byte.

`sent_fear`/`th_clockwork`/`th_metronome` are excluded per the binding
rule (dormant, not inert — a feed-constant and two anti-manipulation
detectors waiting for their trigger condition, never safe to prune on an
`always_dead` reading alone). `equity_risk_z` and `opt_oi_pcr_z` clear
despite similarly low coverage (10.94%/5.45%) — the policy doc's own
"Inert" bucket already classifies these as real-variance/legitimate-
prune-candidate, not condition-gated capability, a judgment this task
treats as given (Task 5's call, binding here, not re-litigated).

**Policy-cleared prune list (5)** — the one a verdict may be based on:
```
corr_shift, depth_ratio, equity_risk_z, opt_oi_pcr_z, pat_engulf_dir
```
Written to `outputs/feature_reports/prune_policy_cleared_20260726-110412.json`
(local only, gitignored — `{"always_dead": [...]}`, not a hand-edit of any
dated snapshot).

**Raw stable list (8, contrast only — NOT a valid verdict basis)**:
adds `sent_fear, th_clockwork, th_metronome` back in. Written to
`outputs/feature_reports/prune_raw_stable_20260726-110412.json`. Run
below for contrast, clearly labelled; see §3's divergence note — it is
exactly the failure mode the coverage floor exists to catch.

## 3. Experiment 1 — OF-3 `--schema-ab`

Both runs: real corpus (live history, 4642 rows), non-`--quick`
(`n_splits=5`, `n_blocks=8`), `ml.adaptive_gbt.enabled=true` in the
measured space (evidence-gated back out at `n_live=240 < 250` in every
run below, so 8 configs measured, not 9, in every schema/epoch/gbt_mono
run — `logistic` + 6 `gbt_*` variants + `mlp_small`, `adaptive_gbt`
absent).

### 3a. Policy-cleared list (verdict basis)

`--schema-ab outputs/feature_reports/prune_policy_cleared_20260726-110412.json`
(prunes 5/62 columns for the `gbt_d3_lr05_schema_ab` arm):

- Widened-space pbo = **0.21** over 8 configs / 70 splits (mean winner
  `gbt_d4_lr05`; argmax-stress pbo = 0.17)
- `experiment[gbt_d3_lr05_schema_ab]`: base=`gbt_d3_lr05`, pairwise
  pbo=**0.94**, **ladder_winner=`gbt_d3_lr05`** (the BASE, full-feature
  config), mean_winner=`gbt_d3_lr05_schema_ab` (the pruned arm wins on
  raw mean Brier only, not by the `BRIER_MARGIN` the deployed ladder
  requires to climb)

**Verdict: DEFER.** The deployed simplicity-ladder rule (never argmax)
does not pick the schema-pruned arm — the full-feature base wins. Rule
5's ADOPT bar ("win under the deployed rule AND not degrade pbo") fails
at the first clause; the pairwise pbo=0.94 (arm decisively worse OOS
under this pairing) reinforces it.

### 3b. Raw stable list (contrast only, NOT a verdict basis)

`--schema-ab outputs/feature_reports/prune_raw_stable_20260726-110412.json`
(prunes 8/62 columns, includes the 3 dormant features):

- Widened-space pbo = **0.17** over 8 configs / 70 splits (argmax-stress
  pbo=0.07)
- `experiment[gbt_d3_lr05_schema_ab]`: base=`gbt_d3_lr05`, pairwise
  pbo=**0.07**, **ladder_winner=`gbt_d3_lr05_schema_ab`** (the pruned arm
  wins), mean_winner=`gbt_d3_lr05_schema_ab`

This reading, read on its own, looks ADOPT-shaped: the arm wins under
the deployed ladder rule and pbo drops (0.23 baseline → 0.17). It is
**not eligible as a verdict basis** per `pbo_admission_policy.md`'s
coverage floor: winning this pairing requires dropping `sent_fear`,
`th_clockwork`, and `th_metronome` — the two THALES manipulation
detectors and the sentiment feed — permanently, on the strength of a
corpus that has barely seen their trigger conditions fire (1.34%/1.49%/
0.00% nonzero). The apparent PBO improvement here is mechanical: pruning
nearly-all-zero columns lowers the model's effective degrees of freedom,
which improves CSCV's selection-bias reading almost by construction, not
because those columns are dead weight. **This divergence (raw list wins,
policy-cleared list does not) is itself the demonstration of why the
coverage floor is binding** — a naive PBO-only read would push toward
adopting a prune that blinds the anti-predation layer at exactly the
moment it's needed.

## 4. Experiment 2 — OF-3 `--epoch-ab`

`ml.epoch.candidate_cutoff_ts=1784830855` (already configured, `false`
gate untouched): 1,456/4,642 rows kept for the `gbt_d3_lr05_epoch_ab`
arm's training (3,186 pre-cutoff candidate rows excluded from training
only; scoring still uses the full shared OOF rows). One fold (fold 0)
degraded to the full unmasked window — its row-masked training set was
too thin (n=19) to fit at all.

- Widened-space pbo = **0.37** over 8 configs / 70 splits (mean winner
  `gbt_d4_lr05`; argmax-stress pbo=0.31)
- `experiment[gbt_d3_lr05_epoch_ab]`: base=`gbt_d3_lr05`, pairwise
  pbo=**0.47**, **ladder_winner=`gbt_d3_lr05`** (the base),
  mean_winner=`gbt_d3_lr05` (the base wins on raw mean too — the arm
  loses both ways)

**Verdict: DEFER**, and unambiguously so: the arm does not win under the
deployed rule, AND the widened-space pbo degrades materially versus the
0.23 unflagged baseline (0.23 → 0.37) — both halves of the ADOPT bar
fail. Row-epoch filtering the corpus at this cutoff does not currently
earn its complexity.

## 5. Experiment 3 — `gbt_mono` +1 rung (re-baselined space reading)

`gbt_mono` has **no CLI path into OF-3** by design (T3.5: wiring it would
make OF-3 measure the widened space by default — that widening is itself
the conscious re-baseline reserved for this adjudication). Measured via
a throwaway script (scratchpad only, never added to the repo) that
imports `load_dataset` from `scripts.overfit_check` and `model_space_pbo`
from `ml.overfit`, mirroring `scripts/overfit_check.py`'s own OF-3 call
site byte-for-byte on every shared parameter (`n_splits=5`, `n_blocks=8`,
`sig`, `n_live`, `select_cfg`, `include_adaptive`/`adaptive_cfg` resolved
the same way from config) plus `include_gbt_mono=True` and `gbt_mono_cfg`
built from `config.json`'s `ml.gbt_mono.constraints` block (resolved
feature-name → `FEATURE_NAMES` index, exactly as
`model_space_pbo`'s docstring specifies the caller must do — confirmed
by an initial `ValueError` when the raw name-keyed dict was tried
unresolved, then fixed).

- Widened-space pbo = **0.1286** over 8 configs / 70 splits (mean winner
  `gbt_d4_lr05` — `gbt_mono` is not even the mean-argmax; argmax-stress
  pbo=0.0857)
- Configs measured: `logistic, gbt_d2_lr05, gbt_d3_lr05, gbt_d3_lr10,
  gbt_d4_lr05, gbt_d2_lr10, gbt_mono, mlp_small` (`adaptive_gbt` evidence-
  gated out at `n_live=240 < 250`, same as every other run this document
  reports — unaffected by gbt_mono's presence)
- **Pairwise `gbt_mono` vs `gbt_d4_lr05`** — `gbt_mono`'s designated
  next-complex step in `model_space_pbo`'s `_BASE_ORDER` only (`_BASE_ORDER`
  places `gbt_mono` directly after `gbt_d4_lr05`). This is a NARROWER,
  CONFOUNDED claim than it may read: in `ml.walkforward._COMPLEXITY` — the
  ladder the bot actually runs — `gbt_mono`'s predecessor is plain `gbt`
  (the untuned depth-2/lr-0.03 default), not `gbt_d4_lr05`, and `gbt` has
  no counterpart of its own in the measured PBO space. So this pairing
  measures an architecture change (added monotone constraints) AND a
  hyperparameter change (depth 2→4, lr 0.03→0.05) TOGETHER, not the
  monotone constraint in isolation — the clean same-hyperparameter
  comparison (`gbt` vs `gbt_mono`, both depth-2/lr-0.03, the pairing
  `_COMPLEXITY` actually runs) was NOT measured here. Computed by reusing
  the actual production helpers (`_fit_predict_arm`, `pbo_cscv`,
  `BRIER_MARGIN` — not a reimplementation, so this can't silently drift
  from what the shipped code does for the other two arms): mean
  neg-Brier `gbt_d4_lr05=-0.165588` vs `gbt_mono=-0.197256` (Δ=-0.0317,
  `gbt_mono` **worse**, far outside the ±0.002 margin either direction),
  **ladder_winner=`gbt_d4_lr05`** (the base — `gbt_mono` does not clear
  `BRIER_MARGIN`, nor even beat the base on raw mean), pairwise pbo=0.0
  (the pairing never varies — `gbt_mono` never wins a single block).

**Verdict: DEFER.** `gbt_mono` as coded (default depth-2/lr-0.03
architecture plus the 5 monotone sign constraints — not `gbt_d4_lr05`'s
tuned hyperparameters) loses decisively to its ladder predecessor at this
data scale; it does not clear the deployed rule's ADOPT bar. The widened
aggregate pbo did fall (0.23 → 0.1286) — noted for completeness, since a
weak added candidate that the ladder never selects can only leave the
selection-bias reading flat or lower — but that is irrelevant once the
primary "must win" clause has already failed. No re-baseline decision
follows from a DEFER; the +1-rung reading is filed here as the measured
answer, not adopted. **Caveat carried into §7's summary row**: because
the pairing above measures architecture and hyperparameters together
(`_BASE_ORDER`'s predecessor, not `_COMPLEXITY`'s), this reading must
not later be cited as "monotone constraints were measured [against their
actual `_COMPLEXITY` predecessor, `gbt`] and lost" — that clean
same-hyperparameter comparison was not measured this round.

## 6. Ambient baseline noise — not Phase 3's doing

`scripts/overfit_check.py` on the live/unflagged path (this document's
own baseline run, before any experiment flag): **4 passed, 4 failed** —
`gap[logistic/gbt/mlp]` (OF-1, the pre-existing memorization-gap trio)
and `dof: dead-feature fraction` (OF-7, `dead_frac=0.60`, 37/62
features). `docs/quant/2026-07-24_of3_pbo_data_shift.md`'s last logged
conscious baseline (5 passed/3 failed at 4,692 rows, 2026-07-26 morning)
predates this session's corpus state (4,642 rows now) and is stale
relative to it — that watch-doc's next crossing entry and any re-
baseline decision belong to the controller, per the inertness protocol
that doc itself establishes; nothing here re-baselines it. Both of
today's fails are confirmed NOT Phase 3-caused: `ml.gbt_mono.enabled`
and `ml.epoch.exclude_old_candidates` both ship `false`, and
`scripts/overfit_check.py` never passes `epoch_cfg` on its default path,
so the shipped-disabled code paths have zero footprint on this reading.
Baseline OF-3 pbo (no experiment flags) = **0.23** over 7 configs (no
`gbt_mono`, no schema/epoch arm) / 70 splits, mean winner `gbt_d4_lr05` —
the reference point every widened-space pbo above is compared against.

## 7. Verdict summary

| experiment | arms | deployed-rule winner | pbo | verdict |
|---|---|---|---|---|
| unflagged baseline | 7 configs (no arm) | `gbt_d4_lr05` | 0.23 | (reference) |
| schema-ab, policy-cleared (5 feat) | `gbt_d3_lr05` vs `gbt_d3_lr05_schema_ab` | **gbt_d3_lr05 (base)** | widened 0.21 / pairwise 0.94 | **DEFER** |
| schema-ab, raw (8 feat, contrast only) | same pair | gbt_d3_lr05_schema_ab (arm) | widened 0.17 / pairwise 0.07 | not a valid verdict basis (coverage floor) |
| epoch-ab | `gbt_d3_lr05` vs `gbt_d3_lr05_epoch_ab` | **gbt_d3_lr05 (base)** | widened 0.37 / pairwise 0.47 | **DEFER** (degrades pbo too) |
| gbt_mono +1 rung | `gbt_d4_lr05` vs `gbt_mono`¹ | **gbt_d4_lr05 (base)** | widened 0.1286 / pairwise 0.0 | **DEFER** |

¹ Confounded pairing (see §5): `gbt_d4_lr05` is `gbt_mono`'s predecessor
in `model_space_pbo`'s `_BASE_ORDER` only, NOT in `ml.walkforward.
_COMPLEXITY` (the ladder actually run), where `gbt_mono`'s predecessor is
plain `gbt` (untuned depth-2/lr-0.03) — a family absent from the measured
PBO space. This row therefore measures the monotone constraint AND a
hyperparameter change together; the clean same-hyperparameter comparison
was NOT measured, and this DEFER must not be cited as "monotone
constraints were measured [against `gbt`] and lost".

**Verdict rule applied throughout**: ADOPT requires the variant to win
under the DEPLOYED simplicity-ladder rule (`BRIER_MARGIN` climb, never
argmax — `ml/walkforward.py`'s ladder, mirrored inside
`model_space_pbo`) AND not degrade pbo. Every arm measured this round
either lost under the deployed rule outright (schema-ab policy-cleared,
epoch-ab, gbt_mono) or only "won" under a reading the binding coverage-
floor policy disqualifies as a verdict basis (schema-ab raw). **All four
readings are DEFER.** A DEFER verdict is a successful, informative
outcome of this measurement exercise — not a failure of it; nothing here
was stretched to manufacture an ADOPT.

## 8. Closing statement

**All production flags remain OFF**: `ml.gbt_mono.enabled=false`,
`ml.epoch.exclude_old_candidates=false`, and no other Phase 3 flag was
touched, flipped, or committed in any state other than its shipped
default, at any point in this measurement session. Every reading in this
document is a report-only, offline CSCV measurement — none of it altered
`config.json`, model artifacts, or any production code path. Any future
ADOPT of any of these challengers requires an explicit operator sign-off
commit, on its own, separate from this document.

## Appendix — commands run

```
.venv/bin/python scripts/feature_stability.py --seeds 17,19,23
.venv/bin/python scripts/feature_stability.py --seeds 29,31,37
.venv/bin/python scripts/overfit_check.py --report-path outputs/overfit_report_baseline.md
.venv/bin/python scripts/overfit_check.py --schema-ab outputs/feature_reports/prune_policy_cleared_20260726-110412.json --report-path outputs/overfit_report_schema_ab_policy.md
.venv/bin/python scripts/overfit_check.py --schema-ab outputs/feature_reports/prune_raw_stable_20260726-110412.json --report-path outputs/overfit_report_schema_ab_raw.md
.venv/bin/python scripts/overfit_check.py --epoch-ab --report-path outputs/overfit_report_epoch_ab.md
.venv/bin/python <scratchpad>/gbt_mono_pbo_probe.py   # throwaway, not in repo
```

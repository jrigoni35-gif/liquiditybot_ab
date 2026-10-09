# PBO-admission policy (the Gort rule) — T3.5

Date: 2026-07-26 · Status: BINDING (governs every future policy-class
challenger to the deployed model: new model family, schema variant,
row-inclusion variant, constraint variant).

## The rule

A policy-class challenger may not become champion-swap eligible until it
has been **measured**, not merely coded. Concretely:

1. **CSCV entry gates champion-swap eligibility.** Any policy-class
   challenger — new model family, schema variant (column subset/superset),
   row-inclusion variant (which rows train), constraint variant
   (monotone/other structural constraint) — enters OF-3's CSCV
   (combinatorially-symmetric cross-validation, `ml.overfit.model_space_pbo`)
   as a measured config **before** it may be considered for a champion
   swap. Shipping the code path disabled is not, by itself, admission —
   it is the prerequisite that makes admission possible later, on its own
   conscious commit.
2. **Every space expansion is a conscious re-baseline.** Adding an arm to
   `model_space_pbo` changes what CSCV measures. The resulting PBO shift
   (up or down) is investigated with the same inertness protocol this
   phase has used repeatedly (docs/quant/2026-07-24_of3_pbo_data_shift.md):
   reproduce the prior baseline commit against the current corpus in a
   scratch worktree; if it reproduces the identical result, the shift is
   corpus-driven, not code-driven. Re-baselines are **documented in
   `docs/quant/`** — never silently absorbed into "PBO is what it is
   this week."
3. **The deployed simplicity-ladder rule is the only selection read.**
   PBO measures the rule the system actually runs
   (`ml/walkforward.py`'s `_COMPLEXITY` ladder, simple → complex, entered
   only where the evidence gate clears) — **never `argmax`** over the
   measured space. A challenger that would win on argmax but isn't what
   the deployed rule would have picked is not evidence for anything; it
   is exactly the overfitting CSCV exists to catch.
4. **Live-label evidence floors gate family admission ahead of any PBO
   reading.** `ml.model_selection` (`min_live_rows` / `min_total_rows`
   per family) decides whether a higher-capacity family is even
   *admissible* into the selection ladder — a family fit on too few real
   closed-trade labels only manufactures a lucky winner, which inflates
   PBO for no real reason. Evidence-floor admission is checked first;
   PBO is read only over families the evidence floor already let in.

## Precedents (this repo, chronological)

| Challenger | Ladder effect | Commit / date | Status |
|---|---|---|---|
| `adaptive_gbt` | `+1` rung (bagged, warm-updatable boosted trees) | `ab6d816`, 2026-07-18 | opt-in, ships disabled; evidence-gated (`min_live_rows=250`) |
| `gbt_mono` | `+1` rung (bound-propagated monotone constraints) | `702a7a9`, this phase (T3.4) | opt-in, ships disabled |
| schema/epoch arms | opt-in A/B **experiment** axes inside `model_space_pbo` (not ladder rungs) | `c8efc06`/`bd92339`, this phase (T3.2/T3.6a) | opt-in, **report-only** — measured inside CSCV, never a production selection path |

The schema/epoch arms are the sharpest illustration of rule 1: they are
opt-in flags to `model_space_pbo` that measure "what would PBO look like
if the corpus were column-pruned / row-epoch-filtered" — entirely inside
the CSCV instrument, with zero production-path effect. That measurement
existing is what makes a *later* production flip (e.g. this phase's T3.6
loader seam, `ml.epoch.exclude_old_candidates`, shipped `false`) a
conscious, evidence-backed commit instead of a guess.

## Coverage floor gates prune admission

A measured finding from this phase, now binding policy: **`always_dead`
alone is not sufficient evidence to prune a feature.**

Task 1's first feature-stability snapshot named 13 always-dead features
in the 4,642×62 corpus (`FEATURE_SCHEMA_VERSION` 8). A coverage/variance
probe over the same corpus (median coverage 89.12% nonzero) splits those
13 into two populations that must be treated differently:

- **Dormant / coverage-starved** — dead because the corpus has not yet
  *seen* the condition, exactly like the five regime one-hots already
  exempt from pruning by construction. Confirmed dormant in this
  snapshot: `sent_fear` (0.00% nonzero, 1 unique value — feed constant),
  `th_clockwork` (1.34% nonzero), `th_metronome` (1.49% nonzero).
  `th_clockwork`/`th_metronome` are THALES manipulation detectors —
  pruning them would permanently blind the anti-predation layer at
  exactly the moment manipulation begins to fire. **Dormant features are
  not prune-eligible**, full stop.
- **Inert** — real variance, well covered, still zero measured degrees
  of freedom. These are legitimate prune candidates: `depth_ratio` (100%
  coverage, 4,486 distinct values), `liq_pocket_pull` (99.66%),
  `ret_12_dir` (98.73%), `corr_shift` (89.12%), `pat_marubozu_dir`
  (87.83%), `imbalance_delta_dir` (81.39%), `dominance_delta` (79.41%
  coverage but std 0.0143 — near-constant; treat as scale-suspect, not
  clearly inert, until that's resolved), `pat_engulf_dir` (12.43%),
  `equity_risk_z` (10.94%), `opt_oi_pcr_z` (5.45%).

**The rule, stated generally:** the regime-one-hot exemption is not a
special case — it is an instance of a general principle. A feature that
is dead for lack of exposure is a capability held in reserve, not a
capability proven useless; pruning it converts a temporary blind spot
into a permanent one, at precisely the moment (regime shift, manipulation
onset, tail event) the feature would start to matter. Any prune admission
must therefore clear a **coverage floor** in addition to appearing in
`always_dead`, and the burden of proof sits with the prune, not with the
feature.

The coverage floor is currently applied by hand, case by case, not read
off a fixed number: `opt_oi_pcr_z` cleared it at 5.45% nonzero coverage,
`th_metronome` did not at 1.49%. Its only load-bearing use is to BLOCK a
prune, so the ambiguity errs safe (when in doubt, don't prune) — but this
doc is BINDING, so that judgment call must be made explicit rather than
left implicit: **there is no numeric coverage threshold.** Every
coverage-floor call is a judgment call and requires a named, written
justification in the doc/commit that applies it (which is what §2 of
`docs/quant/2026-07-26_phase3_adjudication.md` did for `equity_risk_z`/
`opt_oi_pcr_z` vs. `sent_fear`/`th_clockwork`/`th_metronome`) — never a
bare `nonzero_frac > X` cutoff applied without that reasoning attached.

## Required steps before flipping `ml.epoch.exclude_old_candidates`

Precedent above (rule 1: "a policy-class challenger enters OF-3's CSCV
as a measured config before it may become champion-swap eligible")
applies here with a sharper edge than usual: as of this phase, only 1 of
6 training-corpus consumers in this repo receives `epoch_cfg` at all —
`main.py:4626` (the production retrain path) passes it through to
`ml/history.py`'s `load_training_data`. The other five load the corpus
UNFILTERED, with no `epoch_cfg` argument, regardless of what
`ml.epoch.exclude_old_candidates` says:

1. `scripts/overfit_check.py:179` — OF-3's own corpus load (`load_dataset`)
2. `scripts/train_meta.py:146` — the standalone retrain CLI
3. `scripts/interpret_report.py:151` — the post-hoc interpretability report
4. `scripts/feature_stability.py:277` — T3.1's dead-feature stability screen
5. `scripts/smoke_test.py:1006` — the smoke-test corpus load

This is harmless today because the flag ships `false` (every consumer
loads the identical unfiltered corpus, filtered or not is moot). It stops
being harmless the moment `ml.epoch.exclude_old_candidates` flips to
`true`: `main.py` would then train the deployed champion on a
row-epoch-filtered corpus while `scripts/overfit_check.py` (OF-3, the
PBO measurement) keeps measuring the OLD unfiltered corpus — a direct
violation of the project invariant that **PBO measures the rule the
system actually runs**, not a rule it used to run or a superset of it.
An adoption reading taken under that mismatch would certify a selection
process the bot no longer trains on.

**Before `ml.epoch.exclude_old_candidates` may be flipped to `true` in
any shipped config, every one of the five consumers above must be made
CONSISTENT with the production loader** — either updated to thread the
same `ml.epoch` config through to its own `load_training_data` call, or
consciously EXEMPTED with a named, written reason (e.g.
`scripts/smoke_test.py`'s synthetic fixtures may have no real
`ml.epoch.candidate_cutoff_ts`-relevant rows to filter, making the
inconsistency moot for that consumer specifically — but that judgment
must be written down at the time of the flip, not assumed). This is a
documentation/consistency prerequisite, not a code change owed by this
phase: the flag stays `false` and none of the five call sites above are
touched by this fix.

## Cross-reference: `ml.era_exclusion` (2026-07-26)

`docs/quant/2026-07-26_era_exclusion.md` records a SECOND, era-based
(never time-based) production-corpus filter over the same six
`load_training_data` consumers, gated by `ml.era_exclusion` rather than
`ml.epoch`. It hit this exact prerequisite — and resolved it immediately
rather than deferring it — because unlike `ml.epoch.exclude_old_candidates`
(shipped `false` and flipped only by a future, conscious commit),
`ml.era_exclusion` auto-activates on the corpus's own row counts with no
human flip required, so a consumer left unwired could silently start
measuring a stale corpus the moment the threshold crosses on disk, not on
some later flip-day. All five real consumers above (`main.py`,
`overfit_check.py`, `train_meta.py`, `interpret_report.py`,
`feature_stability.py`) now thread `ml.era_exclusion` through to their own
`load_training_data` call; `scripts/smoke_test.py`'s synthetic one-row
candidate fixture is exempted for the same reason given above (no
`config.json` in scope, structurally incapable of reaching any sane
threshold). Both filters may be active simultaneously — see
`docs/quant/2026-07-26_era_exclusion.md`'s composition note.

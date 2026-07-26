# Learnaccel Phase 3 — Measured Headroom Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Ship spec §4 (T3.1–T3.6): dead-feature stability screening with
dated retention, schema/row A/B experiments inside OF-3's PBO, monotone
constraints in the owned GBT, the PBO-admission policy page, and the
operator-approved epoch-cut experiment — every selection event measured,
nothing flipped by default.

**Operator decisions (2026-07-26, binding):** T3.6 approved as: candidate
rows ONLY may be epoch-excluded (live rows NEVER excluded, any era);
candidate cutoff = resolve-time (`ts`) 2026-07-23T18:20:55Z = epoch
**1784830855** (verified: `git show -s --format=%ct 95501ed`); tag =
config-derivation at load (no schema column);
adjudication inside OF-3 PBO only; retrain_history.jsonl writer KEPT
(redaction declined — T2.1 instrument, degeneracy is livelock-era);
archival deferred unless the experiment wins (then operator sign-off,
outputs/archive/ manual-restore convention).

**Scout maps (read the relevant one before your task):**
`/tmp/claude-0/-home-user-liquiditybot-ab/c6d473e4-1320-5144-8fa7-88f0c50f903d/scratchpad/p3_scout_deadlist.raw`
(T3.1-T3.3 anchors) and `.../p3_scout_monotone.raw` (T3.4 anchors). Key
verified anchors are restated inline per task.

## Global Constraints

- CLAUDE.md hard invariants 1–7. Every selection event inside OF-3's
  measured CSCV space; decisions by the deployed simplicity-ladder rule
  (BRIER_MARGIN climb), NEVER argmax. No default-behavior flips: every
  experiment arm is opt-in via flag/config, report-only until a
  documented conscious adoption.
- The five regime one-hots (`regime_bull_quiet, regime_bull_vol,
  regime_range, regime_bear, regime_crisis` — FEATURE_NAMES idx 15-19)
  are EXEMPT from dead-listing/pruning (dead by coverage, not
  uselessness).
- Corpus width is 62 features (FEATURE_SCHEMA_VERSION 8) — not 70; any
  doc text saying otherwise is stale.
- New tunables config-lifted + config_guard FATALs (+ `_doc` keys).
  Seeding: `np.random.default_rng(seed)`, constructor kwargs. numpy-only
  in ml/. pyright shipped scope 0 errors. Engine time only in decision
  paths.
- PBO-space changes (gbt_mono +1; experiment arms when flagged on) are
  CONSCIOUS re-baselines: documented in docs/quant/, never silent.
- Full battery at Task 6; per-task gate = covering tests. Foreground
  commands; full-suite timeout 600000ms; if auto-backgrounded READ the
  completed log synchronously — never stop to wait (five implementers
  stalled that way).
- Committer identity per commit: `git config user.email
  noreply@anthropic.com && git config user.name Claude`; verify
  `git log -1 --format='%ae %ce'`. Trailers verbatim last lines:

```
Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01TgfcWLtZtVMQhbiPZCCV8h
```

- Commit on claude/remote-control-e3h815; do NOT push; do NOT touch main.

---

### Task 1: T3.1 — feature-stability screen + dated retention

**Files:** Create `scripts/feature_stability.py`,
`tests/test_feature_stability.py`.

**Anchors:** `ml/overfit.py:428-460` `feature_dof_report(X, y,
feature_names, label_span=96, n_splits=5, seed=7, ...)` (exposes seed +
n_splits, battery never varies them); `ml/interpret.py:203-232`
`grouped_permutation_importance`; loader via
`scripts/overfit_check.py:134 load_dataset()` pattern (reuse it or
mirror its HistoryStore call). NO dated retention exists anywhere today
— this task builds it.

**Binding behaviors:**
- CLI (interpret_report.py skeleton): `--seeds 7,11,13` (≥3 defaults),
  `--n-splits-list 4,5,6`, `--out-dir outputs/feature_reports`,
  `--min-rows` floor. For every (seed × n_splits) combo run
  `feature_dof_report` on the real corpus; record each combo's dead set.
- Output ONE dated snapshot per run:
  `outputs/feature_reports/stability_<UTCYYYYMMDD-HHMMSS>.json` with
  {corpus_rows, n_live, combos:[{seed,n_splits,dead:[...]}],
  always_dead:[...] (intersection across combos, REGIME ONE-HOTS
  REMOVED even if present), ever_dead:[...] (union), flip_features:[...]
  (union minus intersection), stability_ratio: |intersection|/|union|}
  — plus a small md twin. Snapshot files are append-only history: never
  overwrite an existing snapshot (timestamped names guarantee it).
- If ≥2 prior snapshots exist in the dir, also emit a cross-DATE
  section: membership persistence per feature across snapshots (the
  spec's "≥3 report dates" screen accrues run by run).
- The CANDIDATE prune list = features in `always_dead` across every
  combo of THIS run AND present in every prior snapshot's always_dead
  (if priors exist). Regime one-hots excluded by hard code, commented.
- Determinism: identical corpus + identical seed list → identical dead
  sets (test-pinned with a small synthetic corpus).
- Wall-clock allowed ONLY in the snapshot filename/metadata (offline
  script), never in the measured content.

**Steps:** tests RED (module missing; then behavior tests on a synthetic
corpus: exemption enforced, intersection/union math, no-overwrite,
determinism) → implement → GREEN → run ONCE for real (paste md into
report; note the corpus row-count and dead counts) → commit
`feat(scripts): dated feature-stability screen (T3.1)`.

---

### Task 2: T3.2/T3.6a harness — variant axes inside model_space_pbo

**Files:** Modify `ml/overfit.py` (`model_space_pbo`),
`scripts/overfit_check.py` (OF-3 block + flags), `config.json` +
`core/config_guard.py` (epoch cutoff block). Create
`tests/test_pbo_variants.py`.

**Anchors:** `ml/overfit.py:208-319` — `space` dict at :236-249 (name →
factory closure over ONE shared X); fit loop :274-292; `order`
:299-302; `ladder()` :304-309 (BRIER_MARGIN climb — the deployed rule);
`pbo_cscv(M, ..., select=ladder)` :311. `scripts/overfit_check.py:479-521`
caller with the `include_adaptive` conditional precedent.

**Binding behaviors:**
- Extend each `space` entry from `factory` to `(factory, col_idx |
  None, row_mask | None)` (or an equivalent small dataclass): fit uses
  `X[np.ix_(rows_tr, cols)]`-style selection; OOF index/folds stay
  SHARED and row-mask arms score only their included rows' OOF cells —
  DESIGN NOTE: simplest correct approach is per-arm performance columns
  over the SAME OOF rows where a row-masked arm trains on
  `tr ∩ mask` but still predicts/scores the full shared OOF row set
  (test rows are never masked — the comparison must be like-for-like on
  identical evaluation rows; only TRAINING data varies). This is
  binding: evaluation rows identical across arms.
- Baseline 7(8)-config space and its PBO output must be BYTE-IDENTICAL
  when no variant flags are given (regression-pinned).
- Two opt-in experiment groups, each adding paired arms to the space +
  `order` (variant name directly after its base family so the ladder
  treats it as the next-complex step): `--schema-ab <prunefile.json>`
  (cols = all minus the prune list; loads Task 1's snapshot
  `always_dead` — regime one-hots re-checked exempt at load) and
  `--epoch-ab` (row mask = candidate rows with resolve-ts ≥ cutoff plus
  ALL live rows; mask built from the RAW CSV columns `source`/`ts`
  aligned to loader survivors — alignment note: build the mask inside
  the same load pass, mirroring how learning_curve derives per-row
  metadata).
- Config: `ml.epoch { "candidate_cutoff_ts": <verified epoch seconds of
  95501ed>, "_epoch_doc": ... }` + guard: FATAL if cutoff outside the
  corpus's plausible range [1752000000, 1900000000] or not a number.
  The loader itself is NOT modified in this task (no production-path
  row exclusion anywhere — the mask lives only in the experiment).
- Output: OF-3 report gains INFO lines per experiment arm (pbo, ladder
  winner, mean winner) — gating checks UNCHANGED (experiments never
  gate).

**Steps:** RED (baseline byte-identity pin first — capture current
model_space_pbo output on a synthetic corpus, then refactor must keep it
byte-identical; variant tests: eval-rows-identical property, schema arm
drops exactly the prune list, epoch arm keeps all live rows) →
implement → GREEN → commit `feat(ml): variant axes (schema/row) in
model_space_pbo, opt-in A/B arms (T3.2/T3.6a)`.

---

### Task 3: T3.4 — monotone constraints in GradientBoostedStumps

**Files:** Modify `ml/models.py`, `ml/walkforward.py`, `ml/overfit.py`,
`main.py` (extra_models wiring), `config.json` + `core/config_guard.py`.
Create `tests/test_gbt_monotone.py`.

**Anchors:** `ml/models.py:433-542` (`_best_split` :494-527, `_leaf`
:529-530, `_grow` :532-542 — node dicts `{"f","t","L","R"}`/`{"v"}`, L =
lower feature values); depth default 2 so ROOT children are subtrees —
bound-propagation REQUIRED (leaf-reorder alone cannot guarantee
monotonicity at depth 2; the property test below would fail it).
`_factories()` `ml/walkforward.py:200-213`; `_COMPLEXITY` :57 (gbt_mono
goes DIRECTLY AFTER "gbt" — silently-last placement is wrong);
`pbo_family` :109-110 already prefix-maps gbt_mono→gbt. Wiring
precedent main.py:4650-4651/4672-4673. PBO space dict
`ml/overfit.py:236-249` + `order` :299-302 (add "gbt_mono" after the
gbt_* block). Guard precedent: adaptive_gbt block
`core/config_guard.py:600-620`; FATAL-on-unknown via a LAZY
`from ml.features import FEATURE_NAMES` INSIDE the guard block (keep
config_guard module-level import-free — first cross-package import must
not be at module scope; comment why).

**Binding behaviors:**
- `GradientBoostedStumps(..., monotone_constraints: dict[int, int] |
  None = None)` — {feature_index: +1|-1}. Enforcement =
  bound-propagation: `_grow` threads `(lo, hi)` value bounds; every leaf
  value is clamped `min(max(v, lo), hi)`; on a split over a flagged
  feature, compute the mid = weighted (by hessian mass) mean of the two
  UNCLAMPED child tentative values, then for +1: L child inherits
  (lo, mid), R child (mid, hi) (reversed for -1); unflagged splits pass
  bounds through unchanged. Root starts (-inf, +inf). Document the
  equations in the class docstring (the reviewer checks code vs stated
  math). Serialization: `monotone_constraints` persisted in
  to_dict/from_dict (string keys JSON-safe → convert back to int).
- `monotone_constraints=None` → BYTE-IDENTICAL behavior (regression pin:
  same seed/corpus → identical to_dict before/after this change).
- Config: `ml.gbt_mono { "enabled": false, "constraints":
  {"gate_confidence": 1, "spread_bps": -1, "fv_edge_bps": 1,
  "flow_tox": -1, "manip_suspect": -1}, "_gbt_mono_doc": ... }` —
  SHIPPED DISABLED (entering the deployed ladder flips PBO space; the
  conscious enable happens at Task 6 adjudication or later, per T3.5's
  rule). Guard: FATAL unknown feature name (vs FEATURE_NAMES, lazy
  import), FATAL value not in {1,-1}, WARN if >12 constraints (sign
  confidence degrades).
- Ladder wiring mirrors adaptive_gbt: `_factories()` gains "gbt_mono"
  (constraints resolved from config names → indices at factory-build
  time in evaluate_and_select's caller wiring), `_COMPLEXITY` slot after
  "gbt", main.py `_extra` tuple appends "gbt_mono" when enabled,
  `model_space_pbo` space + order gain a "gbt_mono" entry gated the same
  way (include flag mirroring include_adaptive).
- Tests (all RED-first where meaningful): (1) PROPERTY SWEEP — fit on a
  synthetic corpus engineered so unconstrained GBT VIOLATES
  monotonicity in a flagged feature (verify the violation first — that
  is the RED half), then with constraints assert for a grid of probe
  rows that predict_proba is monotone non-decreasing (+1) /
  non-increasing (-1) as ONLY the flagged feature varies across its
  range, all else fixed — sweep several base rows; (2) determinism pin
  (same seed → identical to_dict); (3) None → byte-identity; (4)
  two-sided mutation proof in the report: disable the clamp → property
  test FAILS; restore → passes; (5) guard tests (unknown feature FATAL,
  bad sign FATAL); (6) AdaptiveGBT propagation smoke (constraints kwarg
  reaches members via gbt_kwargs).

**Steps:** RED → implement → GREEN → commit `feat(ml): bound-propagated
monotone constraints in owned GBT + gbt_mono ladder rung (T3.4, shipped
disabled)`.

---

### Task 4: T3.6 loader seam — config-gated candidate epoch filter

**Files:** Modify `ml/history.py` (`load_training_data`), `main.py`
(thread config), `config.json` (extend ml.epoch), `core/config_guard.py`.
Extend `tests/test_lineage_agreement.py` or new
`tests/test_epoch_filter.py`.

**Binding behaviors:**
- `load_training_data(..., epoch_cfg: dict | None = None)` trailing
  kwarg (interface-extend precedent: telemetry_cfg). When
  `epoch_cfg.get("exclude_old_candidates")` is truthy AND
  `candidate_cutoff_ts` present: skip candidate-source rows whose
  resolve `ts` < cutoff (the same continue-idiom as book=="long";
  LIVE ROWS NEVER FILTERED — enforced structurally: the check is inside
  the `source=="candidate"` branch only). Count excluded rows into
  `last_load_stats["epoch_excluded"]`.
- config: `ml.epoch.exclude_old_candidates: false` (SHIPPED FALSE — the
  production flip, if ever, follows the Task 6 experiment verdict + its
  own conscious commit). Guard: FATAL if exclude_old_candidates true
  while candidate_cutoff_ts missing/invalid.
- Tests: filter off → byte-identical X/y/w (pin); filter on → candidate
  rows before cutoff dropped, live rows before cutoff KEPT (the
  operator's live-rows-never rule pinned as a test), stats key correct.

**Steps:** RED → implement → GREEN → commit `feat(ml): config-gated
candidate epoch filter, shipped off (T3.6, operator-decided)`.

---

### Task 5: T3.5 — PBO-admission policy page

**Files:** Create `docs/quant/pbo_admission_policy.md`.

One page, binding content: any policy-class challenger (new model
family, schema variant, row-inclusion variant, constraint variant)
enters OF-3's CSCV as a measured config BEFORE it may become
champion-swap eligible; every space expansion is a conscious re-baseline
documented in docs/quant/; the deployed simplicity-ladder rule (never
argmax) is the only selection read; live-label evidence floors
(ml.model_selection) gate family admission ahead of any PBO reading.
Cite the concrete precedents: adaptive_gbt (+1, 2026-07-2x), gbt_mono
(+1, this phase), schema/epoch arms (opt-in, report-only). Commit
`docs(quant): PBO-admission policy (Gort rule, T3.5)`.

(Small docs task — fold into the Task 4 implementer's dispatch as a
second deliverable if convenient, else standalone.)

---

### Task 6: Experiments, adjudication, battery

**Steps (controller or implementer, all outputs pasted in report):**
1. Run `scripts/feature_stability.py` (defaults) TWICE more with
   different `--seeds` sets (e.g. 17,19,23 and 29,31,37) so ≥3
   snapshots exist; report the stable prune candidate list (may be
   empty — that is a valid verdict: "no stable dead set yet, pruning
   deferred").
2. If a non-empty stable list: run OF-3 with `--schema-ab` on the real
   corpus; record pbo/winner per arm.
3. Run OF-3 with `--epoch-ab`; record.
4. Run OF-3 with gbt_mono included (its include flag); record the +1
   re-baselined space reading.
5. Write `docs/quant/2026-07-26_phase3_adjudication.md`: per experiment
   — arms, deployed-rule winner, pbo, verdict (ADOPT needs the variant
   to win under the deployed rule AND not degrade pbo; otherwise
   DEFER), and the explicit statement that all production flags remain
   OFF pending operator sign-off on any ADOPT verdicts. Update the OF
   conscious-baseline doc if the check counts shift (inertness protocol
   belongs to the controller).
6. Full battery. Commit docs. Report DONE with the adjudication table.
   NO pushes, NO main ff — whole-phase review follows.

# Learning-acceleration program — design (2026-07-25)

Status: operator-directed ("implement all the best and useful profit
techniques and more importantly learning curves to accelerate the
corpus's brain"), grill-adjudicated, model-stack section separately
operator-approved. Sources of record (session workspace, learnaccel/):
stack_inventory.md, lit_llm_trading.md, lit_sample_efficiency.md,
paper_review_neurosymbolic.md, model_stack_decision.md,
faster_integration.md, grill_synthesis.md (the adversarial synthesis;
its verdict ledger governs scope). Artifact: "The Grill".

## §0 Verdict ledger (what may be built)

C1 livelock-permanence WEAKENED · C2 livelock-repair-is-lawful CONFIRMED
· C3 candidate-fed governor recovery REFUTED · C4 sim-to-live
reweighting WEAKENED (detection-only survives) · C5 directed probing
REFUTED · C6 win-rate pooled prior REFUTED-as-specced (EV-decomposed
form deferred) · C7 calibration A/B REFUTED (gap-surfacing fragment
survives) · C8 smalls re-ranked. Only claims surviving the grill, in
their surviving forms, are in scope. Rule zero: nothing learns while no
labels flow — Phase 1 leads.

## §1 Invariants (unchanged, binding)

CLAUDE.md hard invariants 1-7. Board family stays four
(logistic/gbt/blend/mlp; adaptive_gbt config-gated outside the ladder).
Every selection event inside OF-3's measured CSCV space. Every detector
report-before-enforce (ML-074 pattern). Every tunable config-lifted
with config_guard coherence checks. New behavior = new registered
reason code + same-commit test. Full battery green per task commit.
Replay determinism: no wall-clock in decision paths.

## §2 Phase 1 — RESTORE FLOW (livelock repair, C2)

The SZ-047 probe-share window (probes ≥14/40, fixed denominator,
advanced only by admissions) interlocks with SZ-030 (prior 0.56 <
net-Kelly breakeven ~0.632 while the model is governor-benched) into a
mechanical entry freeze. Repair roads (operator chooses via T1.1 memo,
bleed priced: probes were −$22.87 of −$31.68 net; 69% of closes):

- T1.1 Decision memo: F0a (config lever — raise max_probe_share and/or
  reset persisted window; zero code, reversible) vs F0b (preferred:
  drought-scoped deterministic probe floor). Operator decision recorded
  in docs/quant/.
- T1.2 (F0b) Drought floor, all eight C2 conditions binding: activates
  only when zero admissions of ANY kind ≥ N spans (reuse ML-073
  `_last_entry_admit_ts` drought clock) AND share cap is the binding
  denial; span/count-keyed, never wall-clock; `exploration.drought_spans`
  + `exploration.floor_rate` in config.json, config_guard derivation
  tied to the 8h label horizon (≤ K probes per horizon); new SZ-* code
  for floor admissions, recorded into the window; non-drought behavior
  byte-identical (test-pinned); conviction-never-throttled invariant
  untouched; all existing probe bounds intact. REJECTED variants:
  window time-decay (breaks replay determinism), counting denials in
  the denominator (widens in all states).
- T1.3 Snapshot semantics: pre-P3 snapshot restore yields an empty
  window (14 free probes) — choose, document, test the semantics.
- T1.4 Audit hygiene: test-harness SZ-047 events (window=10/0.3) must
  not write to production outputs/audit.jsonl.

Accept: battery green; new tests pin (i) non-drought byte-identity,
(ii) floor fires only under drought+binding-cap, (iii) determinism,
(iv) conviction untouched.

## §3 Phase 2 — FREE TELEMETRY (report-only, parallel with Phase 1)

- T2.1 Calib-gap surfacing: already-computed `calibration_gap` written
  to retrain_history.jsonl + status (extend schema, don't break).
- T2.2 Sim-to-live detectors (C4 surviving form): (a) divergence score
  within live-covered time windows only + coverage stat; (b)
  lineage-pair agreement stat (dedup-discarded twins; 80 pairs, 86.3%
  agreement, Wilson95 [0.77,0.92], ~8/day accrual) with CI +
  gate-passing-only caveat. New ML-* codes; knobs config-guarded.
- T2.3 Learning-curve report: retrain_history.jsonl is degenerate (156
  byte-identical entries) — curve from TIME-PREFIX REFITS of
  signal_history.csv via the deployed walkforward; stratified by probe
  share + regime; extrapolation capped 2× observed live-N. Offline
  script; no config thresholds. Prices the probe label for T1.1.
- T2.4 fast-er linkage estimator (operator-directed integration):
  ml/linkage.py — seeded deterministic Fellegi-Sunter EM (credited;
  upstream unseeded-RNG + print() removed), numeric discretizers;
  scripts/corpus_linkage_report.py expands T2.2(b)'s pair set
  probabilistically. `linkage.*` config block, guarded; synthetic-truth
  + determinism tests. Report-only; feeds weights ONLY via the Phase-4
  density-ratio item's own gates.

## §4 Phase 3 — MEASURED HEADROOM

- T3.1 Dead-list stability screen: dead-feature membership across ≥3
  report dates × folds × seeds, training-side only; all five regime
  one-hots exempt (dead by coverage, not uselessness).
- T3.2 Schema A/B inside PBO: full vs stability-pruned schema as two
  configs in OF-3's CSCV; decision by the deployed rule, never argmax;
  dead-frac never cited as justification.
- T3.3 Schema rotation (if T3.2 passes): conscious FEATURE_SCHEMA
  bump; recover_local_baks verified on a copy; zero live-label loss
  reconciled.
- T3.4 Monotonic constraints in the owned Newton GBT (operator-approved
  model-stack decision §1): per-feature economic-sign flags in config
  (config_guard FATAL on unknown feature); enforcement orders child
  leaf values on flagged splits; enters the ladder as a variant = PBO
  space +1, consciously re-baselined. Tests: monotonicity property
  sweep (RED-first), determinism pin, two-sided mutation proof.
- T3.5 PBO-admission page (Gort rule): one docs page; future
  policy-class challengers enter OF-3's CSCV before champion-swap
  eligibility.

## §5 Phase 4 — GATED BACKLOG (entry conditions printed; brainstorm per item at entry)

- EB pooled prior: EV-decomposed only; after geometry adjudication +
  F1 discount measured; report-mode shadow; below-breakeven posterior =
  operator-visible designed no-trade state.
- Calibration redesign: after flow resumes; nested per-fold; live-close
  distribution reweighting attempted first (the real ML-030 gap).
- Density-ratio candidate weights: ≥ ~2k continuous-coverage live rows;
  per-fold discriminator inside PBO; clipped, guarded; propensity
  confound bounded via the pair stat.
- ACI abstention shadow: after live closes resume; judged on live
  closes only; promotion via report→enforce + proof of catches.
- Directed probing: propensity logging from first directed probe;
  discriminator stratifiable; corpus 2-3× with real regime coverage;
  sizing-invariance mutation test.
- News-sentiment feature: after T3 pruning + OF-1 pass + flow resumed +
  sent_fear certified alive; until then only zero-DoF fear_filter
  asymmetry.
- LightGBM challenger (operator-approved model-stack decision §2):
  dormant until live labels ≥ 250 (adaptive floor); version-pinned
  deterministic mode (deterministic=true, force_row_wise,
  num_threads=1, fixed seed); OPTIONAL import (absent = family
  inadmissible; import-integrity clean); monotone constraints native;
  PBO-space expansion re-baselined at activation per T3.5's rule;
  champion swap only by OOF Brier under the deployed folds.

## §6 Rejected forever

LLM decision layers / multi-persona debate / online LLM APIs in the
loop; end-to-end DRL sizing; deep sequence models at this N;
GAN/warp augmentation; curriculum learning; per-asset fragmentation;
sequential bootstrap at this N; regret-weighted blending; candidate-fed
governor recovery WITH AUTHORITY (C3); win-rate pooled prior in the
serving path (C6); isotonic-vs-Platt argmin as specced (C7); any gate
widening; any fitted literal in a decision path.

## §7 Acceptance (program)

Phase 1 merged with battery green and the operator's F0 decision
recorded; Phase 2 instruments emitting in production telemetry with
zero authority paths (grep-provable); Phase 3 experiments adjudicated
inside PBO with conscious re-baselines documented in docs/quant/;
Phase 4 untouched except items whose printed conditions are met and
re-approved. Main fast-forwarded per merge; PC deploys via the
battery-gated auto-updater.

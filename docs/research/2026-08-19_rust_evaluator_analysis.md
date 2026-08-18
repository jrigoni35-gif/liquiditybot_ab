# Rust cross-evaluator — analysis only (no implementation)

*2026-08-19, operator-requested. Question: what would a Rust program that
evaluates this bot compute, and how would the bot's learning methods be
sequenced so Rust's properties yield ACCURATE results? Analysis only by
explicit instruction; also consistent with the model freeze — nothing here
touches a decision path.*

## 1. What a Rust evaluator is actually FOR here

Not speed-of-trading (the bot's cycle is 0.84s against a 5s poll — Python
is not the bottleneck) and not a second brain. Its value is as an
**independent referee**: a from-scratch reimplementation of the *scoring*
math that must agree with the Python pipeline bit-for-bit within declared
tolerances. Agreement corroborates the Python; disagreement localizes a
bug to a specific stage. This is differential testing, the same logic as
the repo's own OF-battery ("validate the machinery"), extended across a
language boundary so shared-library bugs (pandas coercions, silent NaN
propagation, dtype promotion) cannot hide in both implementations at
once.

Where Rust's properties genuinely bind:

| Property | Concrete payoff in THIS repo |
|---|---|
| No silent NaN/None coercion (`Option<f64>`, checked parsing) | pandas turns a torn CSV cell into NaN and keeps averaging; serde+csv REJECTS the row loudly — the exact failure `_read_csv`'s drop-malformed law patches by hand |
| Exact decimal arithmetic (`rust_decimal`) | fee/equity reconciliation: 45k audit records × f64 accumulation drifts; the ledger identity (equity_end − equity_start = Σrealized − Σfees ± marks) checked in decimal is either exact or a FINDING |
| Deterministic summation order | Python sums follow insertion/chunk order; a Rust evaluator can pin Neumaier summation so re-runs are bit-identical — a precondition for calling any diff a bug |
| Fearless parallelism (rayon) | the resampling tier (block bootstrap, permutation nulls, PBO) at 10k+ resamples over 11k rows: minutes→seconds, which makes the honest (large-B) versions of these tests routine instead of occasional |
| Exhaustive enums | reason codes (SZ-*/OM-*/ML-*...) as a Rust enum: an unknown code in the audit stream is a compile-time-shaped runtime error, not a silently-uncounted string |

Where Rust does NOT help: it cannot fix small n (44/50 cohort), cannot
make a biased p(win) honest, and adds a second toolchain to a Windows box
whose deploy gate is Python-only. Verdict on placement: **offline analyst
tool, never on the PC's critical path, never a DoD gate** — same trust
tier as a report script.

## 2. The evaluation the program would compute (staged, each stage checkable)

Inputs: the six telemetry streams (`audit.jsonl`, `events.jsonl`,
`equity.csv`, `signal_history.csv`, `postmortem_summary.csv`,
`state.json`) plus `config.json`. Read-only. Reference values to diff
against: the Python pipeline's own numbers (as of 2026-08-18: champion
Brier 0.169, retrain calib gap 0.031, baseline win 26.5% [24.7, 28.5]
n=2061, admitted 24.7% n=2100, gross expectancy −0.7327%/barrier path).

- **Stage 0 — strict ingest.** serde-typed row structs; a row that fails
  to parse is COUNTED and reported, never coerced. Recompute the audit
  hash chain (SHA over canonical record bytes) and diff seam/tamper
  verdicts against `core/audit.verify_chain`.
- **Stage 1 — ledger identity (decimal).** Rebuild equity from fills +
  fees + marks in `rust_decimal`; assert the accounting identity against
  `equity.csv`; re-derive the SD-005 "impossible postmortem" test
  (realized ≪ 0 with MAE ≈ 0) independently.
- **Stage 2 — label recomputation.** Re-resolve every triple-barrier
  h432 label (pt/sl/time) from recorded marks; diff against the stored
  `tb_*` columns. Any label mismatch is a pipeline bug worth more than
  every other stage combined, because labels are upstream of ALL
  learning.
- **Stage 3 — metric recomputation.** Win rates + Wilson intervals per
  gate disposition (the gate-efficacy table), Brier + base-rate null,
  calibration buckets, uniqueness weights and Kish effective n. Declared
  tolerance: |Δ| ≤ 1e-9 for closed-form stats, ≤ 1 ulp-scale for
  iterative fits.
- **Stage 4 — resampling battery (rayon).** Stationary block bootstrap
  CI on expectancy (B=10k), permutation shuffle-null on OOF AUC, PBO on
  the DEPLOYED selection rule (never argmax — same law as OF-3). Large B
  cheaply is the one place Rust upgrades the *statistics*, not just the
  runtime.
- **Stage 5 — differential report.** One table: metric | python | rust |
  Δ | verdict(AGREE/FINDING). No verdict below pre-registered n, same as
  cohort_eval — the referee inherits the measurement standards, it does
  not relax them.

## 3. The learning method as a Rust-accurate sequence

The bot's learning loop, expressed as the typed pipeline a Rust evaluator
would model — one stage, one contract, one failure mode each. This IS the
algorithm; the sequencing matters because every stage's output is the
next stage's only input, so accuracy compounds (or corrupts) in order:

1. **Signal → Candidate** (`CandidateLabeler`): EVERY gate-confirmed
   signal becomes a labeled candidate, admitted or vetoed.
   *Contract:* nothing decided is unrecorded. *Failure:* selection bias —
   evaluator recomputes admitted/vetoed counts per disposition.
2. **Candidate → Label** (triple-barrier h432): pt/sl/time resolution
   against marks. *Contract:* label depends only on data ≤ resolution
   time. *Failure:* look-ahead — evaluator re-resolves from raw marks.
3. **Label → Weighted corpus** (dedup, purge, uniqueness): overlapping
   trips share information; weights → Kish ESS (n_eff), NOT row count.
   *Contract:* any SE quotes n_eff. *Failure:* optimism by
   sqrt(n/n_eff) — evaluator recomputes ESS independently.
4. **Corpus → Champion** (walk-forward logistic): expanding-window fit,
   OOF-scored only. *Contract:* no test-fold leakage (purge gap).
   *Failure:* manufactured OOS edge — evaluator's permutation null must
   land at AUC ≈ 0.5.
5. **Champion → Judge** (Brier vs base-rate null on recent closes):
   negative skill ⇒ the governor, not the model, owns sizing.
   *Contract:* the null is the floor, always reported beside the score.
6. **Judge + PSI drift → Governor** (shrinkage, kelly mult, retrain
   vote): drift_share over MARKET features only (clock features
   excluded). *Contract:* alarms never auto-tune thresholds.
7. **Exploration probes** (budgeted, dry-run only): buy labels with
   bounded paper risk; refunds on unfilled. *Contract:* probe share
   within its band; probes flagged in the corpus so EV stats can
   stratify.
8. **Outcome → Postmortem → cause tallies** → bounded, decaying
   mitigation adjustments. *Contract:* enumerable causes only (no free
   text), impossible rows quarantined (SD-005).
9. **Retrain** (the only loop the freeze keeps open) → back to 4.

Rust "provides accurate results" for this sequence precisely because
each contract above is checkable with exact arithmetic and strict
parsing, and the stages are acyclic within one pass — the evaluator
replays 1→8 as pure functions over immutable inputs, which is the shape
Rust's ownership model represents natively.

## 4. Disposition

- Class: SAFE (measurement/report) — but building it is real scope and a
  second toolchain; it earns its keep only at Stage 2 (label
  recomputation) and Stage 4 (large-B resampling). If ever built, start
  there, as an offline analyst crate diffing against the Python numbers
  above.
- Not built now, per the operator's explicit "do not implement" — and
  the current priority for evaluation truth remains the era-4 gate
  (44/50), which no evaluator in any language may hurry.

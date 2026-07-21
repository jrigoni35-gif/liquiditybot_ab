# Execution-truth harness — design + plan (2026-07-21)

## Why

A three-probe deep dive concluded the bot is not a professional system *yet* for
reasons that are evidentiary, not code-quality:

1. **The paper track record is inflated by an optimistic fill sim.** Resting
   maker limits fill ~95% at the touch with no queue position, no trade-through
   requirement, and no adverse-selection haircut (`queue_aware` ships off). The
   record loses 0/17 *even so*.
2. **No standing gate ever runs real market history.** The `replay.py` harness
   is the right architecture but has never been fed a real recording
   (`record_feeds=false`, nothing retained); every green gate runs on synthetic
   or mock data. The one real-P&L gate (OF-5 deflated Sharpe) is disarmed
   (needs 30 conviction trades; there are 4). **The battery validates the
   machine, not the money.**
3. **One commodity alpha** (order-flow + volume + EMA-cross on 5m bars),
   surrounded by sophisticated risk/execution/ML apparatus that resizes and
   vetoes but never diversifies the bet.

This work makes the system **able to tell itself the truth** — a precondition
for closing (1) and (2). It does **not** manufacture edge; that is Bucket C
(operational, time-bound) and is a written plan here, not code.

## Scope

- **A (built, hardened):** honest-measurement infrastructure — zero decision-path
  risk.
- **B (built as a conscious flip + re-baseline):** turn the fill sim honest.
- **C (plan only):** cannot be completed in a cloud session; needs the live PC
  bot + weeks of real data + research.

## A — honest-measurement infrastructure

### A1 · Recording retention + reconciliation sidecar — `data/recording.py`
- `SinkRotator`: size-capped roll to `session_*.partNN.jsonl`; all feed
  recorders in a boot share one rotator.
- `prune_recordings(retain_days, retain_files)`: bound history by age + count;
  sweeps sidecars and orphans.
- Flat-start sidecar `session_*.meta.json`: start/end `realized_pnl`, equity,
  open-position count, and `self_contained` (were all engine inputs recorded).
- `runner.py` refactored onto it (prune at boot, start sidecar at boot, end
  sidecar on shutdown; forfeited duplicate leaves the shared dir alone).
- Config: `system.recording {max_file_mb=128, retain_days=45, retain_files=60}`.
- `FeedRecorder` gained a backward-compatible `rotator=` param.

### A2/A3 · Replay-vs-live standing gate — `core/replay_gate.py`, `scripts/replay_gate.py`
- **Determinism (hard):** two replays of one recording must be identical.
- **Reconciliation (conditional):** replay realized-P&L vs the live flat-start
  delta within `max(abs_tol=0.01, rel_tol=0.5%·|Δ|)`; hard-fails only on a
  `self_contained` recording, else WARNs (unrecorded feeds move live P&L).
- **SKIP-safe:** no recordings ⇒ dormant, exit 0. Wired into
  `auto_update.battery_passes` (pre-deploy) and covered by `pytest tests/`.
- **Honest scope:** validates backtester *fidelity to the engine*, not *edge*.

### A4 · Fill-model calibrator — `scripts/calibrate_fills.py` + `core/fill_calibration.py`
- Ledger read (`outputs/fills.csv`): observed maker/taker mix + slippage
  percentiles — *context* (circular to invert against).
- Trade-through target from recorded book frames (non-circular): how often the
  market crossed a hypothetical resting limit within its life, per distance.
- Emits `outputs/fill_calibration.{md,json}`; **never writes config**.

#### Hardened estimator (`core/fill_calibration.py`)
Forward model: per-poll `p = sf_base·exp(-d̄)`, per-order `F = 1−(1−p)^n̄`.
Inversion `g(f) = clamp([1−(1−f)^(1/n̄)]·exp(d̄), 0, 1)`.

- **Wilson score interval** on the observed rate — deterministic, boundary-safe,
  subsumes a smoothing prior; propagated through `g` for the recommendation band.
- **Power gate:** DEFERRED unless `n ≥ N_min=80` and both tails `≥ E_min=10`.
  - `N_min=80`: Wilson worst-case (p=0.5) half-width ≈ ±0.11.
  - `E_min=10` both tails: standard stable-proportion floor.
  - `D_MAX=2.0` σ-units: near-touch identifiability; caps inversion amp
    `exp(d̄) ≤ 7.4×`. Hard overflow clamp `d̄ ≤ 20` separately.
- **NO_CHANGE** when the current value sits inside the band.
- **`buckets_agree`** flags MODEL-MISSPECIFIED when per-distance buckets disagree
  (sf_base is meant to be distance-independent).

## B — the conscious flip + re-baseline (outcome)

- Set `order_manager.sim_fill.queue_aware = true` as the shipped default
  (machinery + `test_sim_fill_queue` already existed; this is the switch its own
  comment anticipates). Config-guard treats it as a WARN, not FATAL.
- **Re-baseline outcome (no CI bounds changed — never widen to silence CI):**
  - `quant_trials` G1–G5: unaffected — it does not use the sim fill.
  - `pytest` 1353 · `smoke` 219 · `assurance` 47: all green.
  - Two controlled smoke fixtures (persistence round-trip, lifecycle plumbing)
    were pinned to the deterministic fill model, because their subject is
    persistence/pipeline, not fill realism (a tiny order behind realistic mock
    depth never clears under queue-gating). Fill realism itself is exercised in
    `tests/test_sim_fill_queue`.
  - The `overfit_check.py` live-data 5-fail (gap[logistic/gbt/mlp], pbo, dof
    dead-frac) is **pre-existing and independent of the fill model** — verified
    identical at `queue_aware=false`. It reads the fixed history CSV + model, not
    fills; it is a data-thinness signal (Bucket C), not a regression, and the
    deploy gate uses the synthetic overfit CI (green via pytest), not this
    live-data diagnostic.
- **Caveat carried into Bucket C:** honest fills are rarer, so the live bot may
  under-fill; verify no starvation at the live sigma/poll-cadence via
  `scripts/calibrate_fills.py` before trusting the new labels.

## Reason codes (registered `XV-*`, `core/codes.py`)
`XV-000` gate pass · `XV-001` gate dormant/skip · `XV-010` determinism fail ·
`XV-011` reconcile mismatch (self-contained) · `XV-012` reconcile warn ·
`XV-020` calibration deferred · `XV-021` calibration recommends · `XV-022`
model misspecified.

## Testing
`tests/test_fill_calibration.py` (11), `tests/test_recording.py` (6),
`tests/test_replay_gate.py` (11), `tests/test_calibrate_fills.py` (5). All
new behavior is test-first; the gate logic runs in `pytest tests/` so it is a
standing gate. Full DoD battery is the completion bar.

## Bucket C — operational work-plan (NOT code; needs the live PC + real data)

Each milestone has a hard gating criterion, in order:

1. **Turn on the truth.** Set `record_feeds=true` on the PC. Accrue recordings
   until retention holds ≥ 4–6 weeks spanning **≥1 elevated-vol / drawdown
   episode** (not a single calm tape). *Gate:* `scripts/replay_gate.py` runs
   non-dormant and PASSes on real recordings.
2. **Reconcile sim vs reality.** With `queue_aware=true` (B) live, run
   `scripts/calibrate_fills.py` weekly; drive `passive_base_prob` toward the
   recommended `sf_base★` once a near-touch bucket arms (N≥80). *Gate:*
   calibrator status leaves DEFERRED and the reconciliation gate stays green.
3. **Fix the economics or don't trade.** The closed record shows edge ~25 bps
   under a ~44 bps cost overrun and a 40 bps taker floor. Either widen real
   per-trade edge past ~50 bps or prove maker-side fills. *Gate:* pretrade EV
   net of the *calibrated* cost stack is positive out-of-sample.
4. **Earn the sample.** Accrue ≥30 **conviction** (non-probe) trades so OF-5
   deflated Sharpe arms; then hundreds across regimes. *Gate:* OF-5 armed and
   green (dsr ≥ 0.90).
5. **Diversify or own the single-signal framing.** Add a second orthogonal
   alpha (stat-arb / basis-carry / independent mean-reversion) validated through
   the full overfit battery, or size/label the system honestly as one bet.

Until milestones 1–4 hold, the green battery remains necessary-but-insufficient
and no live capital is justified.

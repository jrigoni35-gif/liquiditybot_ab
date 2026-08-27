# Archetype Null Battery + Trial Ledger — design v0.1

**2026-08-27 · SAFE-class (report-only) · operator-approved after
adversarial redesign (v0 docket: SEV-1..7; every cure incorporated
below and marked [SEV-n]).** Registry parent: THALES ladder analysis
(`docs/quant/2026-08-27_thales_ladder_analysis.md` §6 S1); docket item
TRIALS-1 (`docs/HANDOFF.md`).

## Purpose and success criterion (re-adjudicated)

Build the naive→expert reference-strategy population and the trial
ledger that ends OF-5's assumed-trial-count era. **v0.1 closes
TRIALS-1 on measured N only** [SEV-3]: `deflated_sharpe` receives a
measured trial count under a ratchet; `var_trial_sr` keeps today's
fallback until a pre-registered per-run trips floor becomes achievable
on a trip-capable tape. The population is a NULL and a ledger, never a
selection pool; no rung is ever promoted by argmax.

## Components

### 1. `scripts/trial_ledger.py` — the ledger owner
- `outputs/trial_ledger.csv` + `outputs/trial_ledger.meta.json`
  (schema_version, attempted/accepted/refused row counters [SEV-2],
  harness profiles seen, generator provenance).
- Row: `schema_version, strategy_id, source(battery|harvest), seed,
  fee_anchor(booked|true), harness_profile, cycles, trips, gross_pct,
  net_pct, sr(nullable), max_dd(nullable), n_eff(nullable),
  degenerate(bool), exit_profile`.
- `sr` is NULL unless the run has ≥ TRIPS_FLOOR=20 uncensored trips
  [SEV-3] — expected null throughout v0.1; `n_eff` accompanies any
  non-null sr (concurrent trips deflate, CLAUDE.md standard).
- **Harvest mode**: back-fills N (never SR — objective-only sources
  [SEV-3]) from `outputs/tune_search_state.json`, `outputs/sweeps/*.csv`,
  geometry_search grid size, OF-3 config count. An absent source is
  reported ABSENT, never counted as zero trials.
- Read API validates schema; invalid ledger → loud OF-5 fallback.

### 2. `scripts/archetype_battery.py` — population runner
- **Tape generator, rebuilt** [SEV-1] — self-contained in this script
  (does NOT touch smoke_test mocks): one price process per asset
  drives ALL mock venues (per-venue microstructure noise bounded well
  inside the watchdog divergence gate); candle history ROLLS with
  advancing bar times; recording cadence = the config poll interval so
  bars advance every cycle (`data/replay.py` replays at recording
  cadence); per-seed drift/vol/regime variation; pair set restricted
  to assets with their own process (no BTC-aliasing [SEV-7]). Tapes
  recorded via the existing `FeedRecorder`; replayed via
  `scripts.replay.run_replay`, which keeps the deployed fill physics
  (`dry_run=True` → `_poll_dry`/`_sim_maker_cross`).
- **Injection** [SEV-4]: extend `run_replay(cfg, recording, quiet=True,
  *, mutate_bot=None)` — keyword-only, called between bot construction
  and the loop, default None byte-identical (invariant 7,
  extend-with-defaults). Battery passes
  `mutate_bot=lambda bot: setattr(bot.gates, "evaluate_asset", rung)`
  (the precedented seam). `run_replay`'s summary gains `qa_dir` so the
  per-run QA `fills.csv` is read before the next run clobbers it.
- **Audit isolation** [SEV-4]: battery entrypoint calls
  `configure_audit`/`configure_registry` to a tmp QA root BEFORE any
  bot construction; a test pins that the production chain gains zero
  records across a battery run.
- **Harness profile** [SEV-1]: archetypes cannot clear the deployed
  admission stack (SZ-023 derived bar ≈0.69 vs cold p 0.62; probe
  throttles). Each run therefore carries a named, pre-registered
  profile of dotted-key overrides, stored on its row:
  - `native`: deployed config as-is (the deployed member's home).
  - `neutral-admission`: sizer bar relaxed + probe throttles off in
    the THROWAWAY replay config only — never a real config change.
  The deployed member runs under BOTH profiles so every archetype has
  a matched-arm comparison; the report states plainly that the
  population measures strategy∘harness.
- **Activity floor** [SEV-1]: a (tape, member, anchor) row with
  < MIN_TRIPS=1 trades is marked `degenerate=true`, counted, printed —
  never a silent zero. An ALL-degenerate battery run refuses to feed
  OF-5 at all and says so.
- **Determinism** [SEV-6]: per member, seed-1 double-run must match on
  `_DETERMINISM_KEYS` **plus cycles**; cycles equality is asserted
  across all members per tape; refusals counted/printed and reflected
  in meta (they shrink measured N, which the ratchet below absorbs).
- Grid: M tapes (default sized to keep a default run under ~20 min on
  the Windows box; CLI `--tapes/--cycles`) × 9 members × 2 fee anchors
  (booked 25/40; true 40/80 via dotted `pretrade.*`/`order_manager.*`
  keys). Runtime honesty [SEV-7]: the measured 1.4 s/replay was on the
  degenerate tape; a trip-capable tape scales toward 15–45 s/run —
  the default grid is chosen from measured runtime in the plan, and
  the report prints its own wall time.

### 3. Roster — **entries only** [SEV-5]
Archetype identity is ENTRY decisioning; ALL rungs exit through the
deployed machinery (`exit_profile="deployed"` for every v0.1 row; the
"archetype-owned exits" clause of v0 is DELETED — infeasible through
the seam and contradicted by config_guard exit floors).
- T0 `random_entry` — fires long/short with a fixed per-(asset,cycle)
  probability recorded in the harness profile (matched post-hoc to the
  deployed member's realized entry rate on the same tapes). Documented
  against `scripts/random_entry_control.py` [SEV-7]: that tool
  isolates TIMING on real tape; this rung measures the full
  pipeline-inclusive null on synthetic tape. Different questions,
  both stated.
- T0 `buy_hold` — one long per asset at first opportunity (exits:
  deployed — an honest passivity rung, not a literal never-exit).
- T1 `naive_grid` — entry at fixed evenly-spaced levels below mark.
- T1 `clockwork_dca` — entries on a wall-clock bucket.
- T2 `momentum_chaser` — last-k-bar return sign.
- T2 `stop_herder` — entries at round-number proximity.
- T3 `vol_trend` — EMA cross gated by vol target.
- MEASURED MEMBER: deployed `informed_flow`, unpatched, both profiles.
Stateful rungs are constructed fresh per run [SEV-7]; the engine may
SHADE archetype confidence (gate_stats/THALES lanes) — confidence is
an input to the pipeline, not a pass-through, and the report says so.

### 4. OF-5 consumption — **ratcheted** [SEV-2]
In `scripts/overfit_check.py` (call-site only; `ml/overfit.py`
signature already accepts the inputs):
- `n_trials_eff = max(config dsr_n_trials, measured_N)` — measured N
  can only DEEPEN deflation, never relax it below the configured
  floor.
- Measured `var_trial_sr` is accepted ONLY if the resulting `sr0` ≥
  the legacy fallback's `sr0` (computed both ways, both printed);
  otherwise legacy var is used and the refusal is printed. In v0.1
  this path is expected dormant (sr nullable).
- The OF-5 summary line always names its world: "measured ledger
  N=…, var=legacy|measured" vs "assumed N=…, var=SR² (no ledger)".
- No floor, gate, or default moves. Absent/invalid ledger ≡ today,
  byte-identical, pinned.

## Error handling
Archetype exception → row failed, battery continues, counts printed,
nonzero exit if any failed. Ledger invalid → OF-5 loud fallback.
Tape generator self-checks venue coherence (max cross-venue drift
printed; abort if it would trip the watchdog). Synthetic-time caveat:
any cohort-tool consumption of battery ledgers passes `since=0.0`.

## Testing (same commits as the code)
- Planted-edge oracle (future returns) ranks #1 by net — runs under
  `neutral-admission` so it can trade at all.
- All-null population brackets zero net at both anchors on the
  rebuilt tape (this is also the tape's own validation).
- **Tape liveness pin**: the rebuilt generator must produce ≥1
  non-degenerate trade for the oracle member — the SEV-1 recurrence
  guard; a tape that cannot host a trade is a red suite, not a quiet
  zero.
- Ratchet pins: sr0 never below legacy; `n_trials_eff` never below
  config; both OF-5 worlds pinned byte-identical where required.
- Audit-chain-untouched pin; determinism+cycles pin; fresh-state pin
  for stateful rungs; ledger schema round-trip; harvest fixtures
  (absent-source reported ABSENT).

## Non-goals (v0.1)
SPA inference / percentile claims (v1, pre-registered before first
quote); measured var_trial_sr (dormant behind the trips floor); ML
features from archetypes (freeze); any rung promotion; any engine or
config-default change beyond `run_replay(mutate_bot=)` and the
OF-5 call-site ratchet.

## File map
`scripts/archetype_battery.py` (new) · `scripts/trial_ledger.py`
(new) · `scripts/replay.py` (+`mutate_bot`, +`qa_dir` in summary) ·
`scripts/overfit_check.py` (OF-5 call-site ratchet) ·
`tests/test_archetype_battery.py`, `tests/test_trial_ledger.py`
(new) · `docs/INDEX.md` EXPLORATION row gains the battery pointer on
ship.

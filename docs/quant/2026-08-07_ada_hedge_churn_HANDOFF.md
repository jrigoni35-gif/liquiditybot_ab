# HANDOFF → VS Code session: ADA hedge churn loop (−$318 in 25 min)

**From:** cloud session (remote-control-e3h815) · **Date:** 2026-08-07
**Operator directive (verbatim):** "That is a explicitly terrible problem
I never wanna have again." Implement with your agent team; the operator
has pre-approved the work. Cloud session stays OFF these files.

## What happened (measured from the 08-07 pc-live bundle, not inferred)

Equity cliff $4,933.24 → $4,614.69 (−$318.55), 00:56Z–02:56Z 08-07.
Audit trail: **147 consecutive PT-061 closes of the SAME ADA hedge, one
every ~10 seconds, 01:09:45Z → 01:34:19Z**, every one stamped
`hedge unwind: correlation 0.00 below floor`, each −$1.0 to −$3.4.
Sum of the 147: **−$318.27** — the entire cliff. DRY_RUN, so paper; live
this burns real dollars inside every kill-switch threshold, $2 at a time.

Proof it is cold-start, not market: at 02:01/02:24/02:34/02:44 the same
check fires four ISOLATED unwinds with correlation 0.34/0.46/0.55 — the
estimator warming out of its post-restart reset (restarts logged ~01:00).

## Root cause — two stacked defects

1. **Fail-open on missing evidence** (`execution/hedging.py:95`, floor
   `min_hedge_correlation` = 0.55 at `hedging.py:41`): correlation
   **exactly 0.00 is an UNWARMED estimator** ("no data"), and the floor
   check reads it as "measured and terrible" → unwind. Identical class
   to the cold-sigma give-back bug (2026-08-01, LINK 3ea2a851): a cold
   estimator read as an extreme reading.
2. **No churn breaker between an opposing pair**: the unwinder
   (`hedging.py`) and the re-hedger (exposure bounding) share no state.
   Unwind → next fast-cycle sees uncovered exposure → re-hedge → still
   0.00 → unwind. 147 laps, each paying spread+fees. Nothing counts
   identical unwinds as anomalous. Third instance of the session's
   recurring defect shape: two automated deciders feeding each other
   with no shared clock (duplicate runners 07-16/07-27, era deadlock
   07-31, now this).

## Required fix (three parts — the class, not the instance)

1. **Warmup guard on the correlation floor**: below a minimum sample
   count, the floor check must HOLD STATE (no unwind, no re-hedge
   change), never act on 0.00/NaN. Follow the cold-sigma warmup-guard
   precedent. Lift the sample floor to config with a config_guard bound
   (no fitted literals — CLAUDE.md).
2. **Per-asset re-hedge cooldown**: after ANY hedge unwind, re-hedging
   that asset is blocked for a configurable cooldown (suppressing NEW
   risk — invariant-5 clean). The unwind side stays untouched: exits
   must remain ALWAYS allowed; fix the trigger's evidence, never gate
   the exit path itself.
3. **Churn rate-latch**: N unwinds of one asset within M minutes → new
   registered FW-* fault code (core/codes.py, never a bare string),
   freeze the hedge pair, surface on the incident board. This is the
   backstop that makes ANY future open↔close oscillation loud instead
   of a $2-per-lap silent bleed.

## Acceptance (agents must prove, not assert)

- RED test first: replay the 01:09Z shape (cold corr, 10s cadence) and
  show today's code churns; fix turns it GREEN with ≤1 unwind.
- A warm-estimator low-correlation unwind (the 02:01Z case) still fires
  — the guard must not suppress legitimate unwinds.
- Hard-stop/flatten/derisk paths byte-untouched (invariant 5 pins).
- Full CLAUDE.md battery + fresh-worktree `pytest -q -x` (the deploy
  gate) before push — a red battery self-bricks auto_update (lived
  three times this week).

Cloud session verified the evidence; everything above is reproducible
from `outputs/imported_sessions/pc-live/{audit.jsonl,equity.csv}`.

## DEADLOCK DISCIPLINE (operator directive 2026-08-07 — supersedes §fix
## part 1's "hold state" wording wherever they conflict)

Operator: "I don't want to deadlock anything so take that into account."
The naive warmup guard ("cold -> hold the unwind") is itself a deadlock:
measured restart cadence is MEDIAN 0.5h / p90 4h / max 34h (241 gaps,
07-26..08-03 audit), so an estimator that resets on restart can be
perpetually cold and a held unwind becomes a hedge frozen forever. That
is the 4th instance of this week's recurring shape - a gate whose
release condition depends on the thing it is blocking (probe share-cap,
era exclusion, heartbeat, now this). Build to these rules instead:

1. **Gate the RE-HEDGE on warm evidence, never the unwind.** New risk
   requires evidence; exits never do (invariant 5). Cold estimator ->
   the unwind MAY fire (once - idempotent, nothing left to unwind) and
   re-hedging is what waits for warmth. Composition converges to a flat
   hedge, no churn, no frozen position, no blocked exit. The $318 came
   from RE-OPENING, not from closing.
2. **Every latch has an owned release.** The churn rate-latch freezes
   re-hedging only, and auto-clears on (estimator warm AND cooldown
   elapsed) - plus operator clear. Precedents to follow: the wedge
   guard's auto-recovery (A1-F1: "the wedge must be RECOVERABLE") and
   ML-075 shadow-recovery (a kill with no refill path deadlocked).
   No latch may require the operator to notice it.
3. **Warmup/cooldown clocks ride the snapshot** (precedent:
   _last_floor_admit_ts, persisted because the deploy-restart cadence
   reset it). Persist the correlation estimator's sample count too -
   otherwise every 15-min deploy re-colds it and rule 1's "waits for
   warmth" starves re-hedging on a healthy book.
4. **Size every window against the measured restart cadence above**,
   not against intent. A warmup requirement unreachable inside typical
   uptime is a deadlock wearing a config value. config_guard FATALs for
   incoherent combos (e.g. warmup window >> p90 uptime without
   persistence; cooldown >= rate-latch window).
5. **Release conditions must be independent of the gated action.** If
   you find yourself writing "X resumes when Y, and Y needs X", stop
   and redesign - that sentence is this week's entire incident log.

## RESOLVED — implemented by the CLOUD session, cf454d5 (2026-08-07)

VS Code session: **STAND DOWN on this item — do not implement.** The
operator reassigned it mid-flight ("Complete this task") and the fix is
merged to main at `cf454d5` and ALREADY DEPLOYED (the 20:03Z pc-live
bundle reports git cf454d5ed121). Re-implementing would put two writers
on the hedger, which is this incident's own disease.

What shipped, exactly per the DEADLOCK DISCIPLINE above:

  regime/correlation.py  CorrState.samples + pair_samples(); EMPTY
                         samples = legacy warm-assumed (byte-identical
                         for every old caller/stub/snapshot, pinned)
  execution/hedging.py   open needs pair_samples >= corr_min_samples
                         (12); rehedge_cooldown_sec (600) per asset
                         after ANY unwind; churn_max_unwinds (3) in
                         churn_window_sec (900) latches (FW-070, opens
                         only) and AUTO-releases on window+warm;
                         to_dict/from_dict ride the snapshot; UNWINDS
                         NEVER GATED
  main.py                threads cycle `now`; persistence: hedger
                         section beside monitor (hasattr-guarded)
  core/config_guard.py   bounds + coherence FATAL (cooldown < window) -
                         which caught the cloud session's OWN first
                         config (900>=900) on its first battery run
  tests/test_hedge_churn.py  8 tests, written RED first, incl. both
                         acceptance cases: cold 01:09Z flap -> zero
                         opens; warm 02:01Z low-corr unwind still fires

Battery at cf454d5: pytest 3424 / smoke 219 / assurance 49 / ruff /
pyright 0 / bandit 0 / compileall.

Two notes FOR the VS Code session:
1. Your audit landing had left 3 pyright errors in shipped scope
   (main.py take_deferred seam x2, core/skimmer.py float(None) on a
   malformed record). Fixed in cf454d5; the CLAUDE.md ratchet is back
   at ZERO - please keep it there.
2. Task tracker: #147 completed (this fix); #148 (post-landing
   verification: >2 unwinds/hour on ANY asset in live audit = the
   class-level alarm) is owned by the cloud session. If you touch
   execution/hedging.py for any OTHER reason, rebase on cf454d5 first.

## WATCH CLOSED — #148 24h class-level scan CLEAN (2026-08-16)

Scan of outputs/audit.jsonl, window 2026-08-15T23:54:05Z .. 2026-08-16T23:54:05Z
inclusive (read stamp 23:54:04.96Z; file live/append-only, 45,187 records at
read). Needles "hedge unwind" + "FW-070", grep and python-parse double-derived:

- Hedge unwinds in window: 0. FW-070 latch events in window: 0.
- The scan CAN see: window held 67 audit records; the runner outage
  17:37-18:27 local that day sits inside the window and is the only
  coverage gap.
- All 159 lifetime unwind events cluster in the 2026-08-07 incident
  (01:09:45Z .. 11:35:31Z); none since. The single lifetime FW-070 string
  match is the 08-08 budget re-anchor message, not a latch firing - the
  churn guard has never needed to latch since deploy.

No recurrence at class level. #148 closed. Re-derive route: the scan method
is written into this section; do not quote its counts as current - re-run.

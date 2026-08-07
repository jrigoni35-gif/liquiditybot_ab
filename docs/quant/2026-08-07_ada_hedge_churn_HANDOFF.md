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

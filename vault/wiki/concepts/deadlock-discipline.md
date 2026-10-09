---
title: "The Deadlock Discipline (a gate's release must be independent of the gated action)"
category: concept
summary: "Operator directive 2026-08-07, provoked by the week's FOURTH gate whose release condition depended on the thing it was blocking (probe share-cap, era exclusion, liveness heartbeat, then the naive hedge warmup spec): five rules — gate new risk on evidence and never the exit; every latch owns an auto-release; clocks ride the snapshot; size every window against the MEASURED restart cadence (median 0.5h / p90 4h); and if you write 'X resumes when Y, and Y needs X' — stop. FW-070 is the first mechanism built to the rules, and its config guard caught its own author's first config"
tags: [method, deadlock, gates, latches, risk, invariants, operator-directive]
sources: 1
updated: 2026-08-07
---

# The Deadlock Discipline

## The shape this kills

A protective gate is added; its **release condition depends on the thing it is blocking**. The
gate then has an absorbing state: once it closes, nothing it permits can produce the evidence
that would reopen it. The failure is invisible in review because each half is locally reasonable
— the gate is prudent, the release is principled — and the loop between them only exists at the
system level.

The operator named it while rejecting a fix spec that had exactly this shape
(*"I don't want to deadlock anything so take that into account"* —
`docs/quant/2026-08-07_ada_hedge_churn_HANDOFF.md`, deadlock-discipline section, commit
`9b1eb6a5`): the naive hedge warmup guard ("cold estimator → hold state, no unwind, no re-hedge
change") would have frozen a hedge **forever** on a box whose **measured** restart cadence is
median 0.5h / p90 4h / max 34h (241 gaps, 07-26..08-03 audit) — an estimator that resets on
restart can be perpetually cold.

## The type instances — four in one week, plus the older siblings

| Instance | The gate | The release that needed the gated thing |
|---|---|---|
| [[concepts/probe-livelock]] | probe share cap denies probes | cap relaxes on live labels — which only probes produce |
| Era deadlock ([[sources/live-label-era-deadlock]]) | era exclusion drops old-era rows | training resumes on new-era rows — which the starved loop stops producing |
| Liveness heartbeat ([[concepts/liveness-by-output-cadence]]) | supervisor respawns on stale output | the quiet-but-healthy process is judged by the very chattiness it lacks |
| The naive hedge warmup spec (rejected pre-ship, 2026-08-07) | cold correlation → hold the unwind and the re-hedge | warmth accrues per process life; restarts reset it — a hedge frozen until an uptime that never comes |

Older siblings already paged: [[concepts/deploy-deadlock]] (a champion watermark no
post-filter corpus can ever clear), [[concepts/dead-mute-trap]] (a zeroed detector can never
re-earn its weight). The class is one family: **the release lives downstream of the block**.

## The five rules (operator directive, 2026-08-07 — binding)

1. **Gate NEW RISK on evidence, never the exit.** Cold estimator → the unwind MAY fire (once —
   idempotent, nothing left to unwind); **re-hedging is what waits for warmth**. Composition
   converges to a flat hedge: no churn, no frozen position, no blocked escape. The $318 came
   from **re-opening**, not from closing. (This is [[concepts/protective-senior-overlay]]'s
   invariant-5 stated as a design rule for guards.)
2. **Every latch has an owned release** — auto-clear on (evidence AND time), plus operator
   clear. *No latch may require the operator to notice it.* Precedents: the wedge guard's
   auto-recovery (A1-F1 "the wedge must be RECOVERABLE"), ML-075 shadow-recovery (a kill with no
   refill path deadlocked).
3. **Warmup/cooldown clocks ride the snapshot** (precedent: `_last_floor_admit_ts`, persisted
   because the deploy-restart cadence reset it). *The rule's second half — persist the
   estimator's sample counts too — did NOT ship in `cf454d5e`; owed item 35(a).*
4. **Size every window against the MEASURED restart cadence, not against intent.** A warmup
   requirement unreachable inside typical uptime is a deadlock wearing a config value.
   `config_guard` FATALs incoherent combos — and the hedge-guard FATAL (cooldown must sit below
   the latch window, else the rate-latch can never observe enough unwinds to fire) **caught its
   own author's first config (900 ≥ 900) on the first battery run**.
5. **Release conditions must be independent of the gated action.** *"If you find yourself
   writing 'X resumes when Y, and Y needs X', stop and redesign — that sentence is this week's
   entire incident log."*

## The first mechanism built to the rules

The FW-070 churn latch (`cf454d5e`, [[sources/session-20260807-hedge-churn-guards]]): freezes
**re-hedging only** (rule 1), auto-releases on **window-elapsed + estimator-warm** — time and
evidence, both of which accrue on the bar clock regardless of whether hedging is frozen (rules
2, 5); its clocks are snapshotted (rule 3, half-shipped — see above); its knobs carry
guard-enforced bounds whose FATAL messages state the deadlock rationale (rule 4). Worst-case
post-release recurrence is bounded (~1 lap per cooldown, re-latch at 3) instead of unbounded at
the fast-cycle cadence.

## How to review for this class

- For every `if <guard>: return/skip`, ask: **what produces the evidence that clears the
  guard, and does that producer run while the guard is closed?**
- For every latch, demand the **release sentence** in the same review: who clears it, on what
  clock, measured against what uptime distribution.
- Treat "hold state until healthy" specs as guilty until the release is shown independent —
  the four instances above all shipped (or nearly shipped) through review as prudence.
- The safe direction is asymmetric by invariant: **fail-closed on opens, fail-open on exits**
  ([[concepts/zero-is-not-a-reading]] rule 3 is the same asymmetry for sentinels).

## Related
[[sources/session-20260807-hedge-churn-guards]] · [[concepts/probe-livelock]] ·
[[concepts/deploy-deadlock]] · [[concepts/dead-mute-trap]] ·
[[concepts/liveness-by-output-cadence]] · [[concepts/protective-senior-overlay]] ·
[[concepts/zero-is-not-a-reading]] · [[sources/live-label-era-deadlock]] ·
[[entities/config-guard]] · [[synthesis/owed-measurements]]

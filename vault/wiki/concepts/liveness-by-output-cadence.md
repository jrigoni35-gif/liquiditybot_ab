---
title: Liveness by Output Cadence
category: concept
summary: A supervisor that judges process liveness by output-file mtime silently requires every supervised process to be chatty — a healthy process that is quiet when idle reads as dead, gets a duplicate spawned beside it, and both keep running. Second firing 2026-08-07 — a cold-booting runner whose warmup (~3.5 min) exceeds the 120s stale window gets declared stale/absent mid-warmup and displaced; the window was never sized against the measured warmup cadence
tags: [observability, supervision, failure-mode, sidecars, restart]
sources: 2
updated: 2026-08-07
---

# Liveness by Output Cadence

## The failure mode
A supervisor with no process-handle or PID-file check judges liveness by **the mtime of the
process's stdout log** (here: `pc_supervisor`, `STALE_SEC=120`). This works only under an
unstated contract: *every supervised process emits output at least once per staleness window,
even when idle*. A process that **prints only when it has work** — `gc_log_pusher` printed only
when shipping events — breaks the contract the moment work stops flowing. The supervisor then
reads healthy-but-quiet as dead and spawns a **duplicate**, and since the original never
actually died, **both run**.

## The instance (2026-08-03, [[sources/session-20260803-bug-sweep]])
During the 2026-08-02 22:05 runner bounce no events flowed; the healthy pusher went quiet past
120s; the supervisor spawned a second pair; **every log line shipped to Grafana Cloud twice for
~22 hours**. Duplication, not loss — the failure is silent on every dashboard that does not
count its own ingest.

## The fix pattern
A **quiet heartbeat**: emit a no-op line at an interval safely inside the staleness window
(55s against `STALE_SEC=120`), so idleness and death become distinguishable. The fix stayed
**stdlib-only** — the sidecar philosophy ([[entities/observability-sidecars]]) survives the fix.

Cleanup came for free: the sidecars' `_source_changed` self-restart made **both duplicate pairs
exit when the edit landed**; the supervisor relaunched one fixed pair (4 processes → 1).

## The second firing (2026-08-07 night) — the quiet process was WARMING, not idle

During the pandas-prune incident ([[sources/session-20260807-closing-batch]] §4) the class fired
in a new costume. The post-bounce runner booted 22:18:46 local and entered a **cold warmup
measured at ~3.5 minutes**; `pc_supervisor` (`check=30s, stale=120s`) logged
`runner stale/absent -> relaunching` at **22:21:45** — displacing a **healthy runner that was
busy, not idle**. The displaced runner lost the instance lock and **exited gracefully**
(`final snapshot saved`), so this firing cost a restart rather than a duplicate — the 08-03
instance duplicated a quiet *pusher*; this one displaced a warming *engine*. Same root: the
staleness window encodes an unstated contract about output cadence that the supervised process's
**slowest honest phase** (cold warmup) does not satisfy.

The sizing lesson joins [[concepts/deadlock-discipline]] rule 4 — *size every window against
the MEASURED cadence* — and the measurement now exists: `915b362f`'s `cycle_duration_max_sec`
recorded the warmup stall (45.56s first cycle; full warmup ~3.5 min) the same night. Filed as
[[synthesis/owed-measurements]] item **42(e)**: a warmup-aware stale window or a boot-grace
signal, sized from the recorded warmup durations. Compare the runner's own
`lock_boot_max_stall_sec` boot grace (owed item 30j's fix) — the lock already learned this
lesson; the supervisor has not yet.

## Accidental immunity, now a checked property
The sibling sidecars never hit this bug **only because they print every tick** — immunity by
coincidence of style, not by design. Naming the failure mode converts that: any future
supervised process must either be tick-chatty or carry an explicit heartbeat. This is the
observability-plane cousin of the absence-of-a-key lesson in
[[concepts/default-path-fallback-writes]]: an **unstated contract satisfied by accident** is a
defect waiting for the first process that satisfies it differently.

## Related
[[entities/observability-sidecars]] · [[concepts/default-path-fallback-writes]] ·
[[concepts/deadlock-discipline]] · [[sources/session-20260803-bug-sweep]] ·
[[sources/session-20260807-closing-batch]] · [[synthesis/owed-measurements]]

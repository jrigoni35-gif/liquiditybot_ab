---
title: The Observability Sidecars (pc_supervisor, gc_log_pusher)
category: entity
summary: "The out-of-process telemetry plane: stdlib-only sidecar scripts supervised by pc_supervisor, shipping logs to Grafana Cloud, self-restarting on source change — deliberately importing nothing from the engine. As of 2026-08-07: child logs rotate at the spawn boundary (64MB cap, verified live), and every supervised process is a venv shim + base-interpreter PAIR — two pids per logical process. AUDITED END-TO-END 2026-08-09 (22 agents, panel -> PromQL -> gauge -> status key -> the code): 11 defects across 15 panels, 8 decision-grade, including the strongest false claim on any board (a hero tile describing itself as the true bottom line with hedges included while plotting the one figure that excludes hedge fees) and a drawdown gauge that plots a different quantity than the hard stop that fires on it. One panel that had never left zero turned out to be the visible symptom of a LIVE RISK BUG"
tags: [subsystem, observability, sidecars, grafana]
sources: 6
updated: 2026-08-09
---

# The Observability Sidecars

The out-of-process telemetry plane around [[entities/liquiditybot]]. The engine deliberately has
no in-repo UI process; observability is external scripts reading shared state files and logs.

## The sidecar philosophy
**Stdlib-only, no engine imports.** A sidecar must never be able to break — or block — the thing
it observes. Fixes to sidecars preserve this: the 2026-08-03 heartbeat fix was explicitly kept
stdlib-only ([[sources/session-20260803-bug-sweep]]).

## The cast
- **`pc_supervisor`** — spawns and babysits the other sidecars; judges liveness by
  **stdout-log mtime** with `STALE_SEC=120`. That liveness test carries an unstated
  chattiness contract — see [[concepts/liveness-by-output-cadence]].
- **`gc_pusher`** — ships Prometheus metrics (112 emitted names as of the 2026-08-05 audit;
  names built dynamically in f-strings — see the static-scan hazard below).
- **`gc_log_pusher`** — ships log lines to Grafana Cloud (Loki). Until 2026-08-03 it printed
  **only when shipping**, which made it the one sidecar able to violate the chattiness
  contract; it now emits a **55s quiet-heartbeat line** when idle.
- **`gc_trace_pusher`** — ships OTLP traces.
- Sibling pushers/tick scripts — print every tick, and were immune to the duplicate-spawn bug
  **only for that stylistic reason** (accidental immunity, now a named requirement).

## Self-update behavior
Sidecars watch their own source via `_source_changed` and **exit on edit**, letting the
supervisor relaunch the new version. This is how the 2026-08-03 duplicate-pusher incident
self-cleaned live: both duplicate pairs exited when the fix landed, one fixed pair came back
(4 processes → 1), no manual process surgery.

## Incident history
- **2026-08-02 22:05 → ~22h:** duplicate `gc_log_pusher` pair — every log line shipped to
  Grafana Cloud **twice**. Root cause and fix: [[concepts/liveness-by-output-cadence]] /
  [[sources/session-20260803-bug-sweep]]. Blast radius: telemetry only.
- **2026-07-31:** `pc_supervisor.log` was among the six files mutated by the pytest suite's
  outputs-tree leak ([[sources/test-suite-outputs-contamination]]) — the sidecars' *logs* sit in
  the same outputs tree the contamination class wrote into.
- A prior whitelist gap: `slip_bps_notional_weighted` never reached Grafana because it was
  missing from the pusher's metric whitelist ([[sources/correction-verification]]).

## Audited state (2026-08-05, report-only)
The telemetry-stack audit ([[sources/telemetry-stack-audit]]) measured the plane end to end,
scorecard **≈80/100**:
- **~2 dozen dark metrics** — emitted but on no board, including the hash chain's own health
  counters (`audit_dropped_writes`, `audit_tail_truncations`), telemetry self-health
  (`gauges_dropped_nonfinite`), and the never-displayed `gate_divergence` watch. Same failure
  class as the `slip_bps_notional_weighted` gap above: **an absent metric renders as an empty
  panel indistinguishable from zero**.
- **Log-plane skew** — last 8k events 99.8% INFO; `regime` + `strategies` = **73% of Loki
  volume** (shipping cost + query noise; diet owed).
- **Static-scan hazard** — `gc_pusher`'s f-string metric names defeat static regex scans
  (92 phantom "ghosts"; the repo's own source-matching test, ghosts=0, is the authority).
Priorities filed as [[synthesis/owed-measurements]] items 26-28; boards change only via the
generator, never the JSON.

## Debug-sweep findings (2026-08-05, report-only)
The same-day debug sweep ([[sources/session-20260805-debug-sweep]]) touched this plane on
both sides of the ledger:
- **Finding 7 (LOW · confirmed) — FIXED same day (`b409a24b`), then fixed again (`46cdc19a`):**
  `events.jsonl` rotation at 5MB renames to `events.jsonl.1`; `gc_log_pusher` saw the new inode
  and reset `offset = 0` on the new file, never draining the rotated predecessor — the tail
  appended after its last tick (one 10s poll period; more during a push outage) was
  **permanently dropped from Loki**. A silent gap at every rotation. `tick()` now **drains the
  rotated tail before the offset reset**, provenance-checked, at-least-once contract unchanged
  (owed item 29g). The evening's adversarial pass then found the **inode-capture race inside
  that new drain** — see below.
- **Near-misses verified OK:** `gc_trace_pusher` cannot re-ship the audit trail after a
  torn-tail truncation (its offset never passes an unterminated line, so it equals the
  truncation point exactly); `pc_supervisor._spawn`'s unclosed log handle does not accumulate
  (CPython closes on function return); and **both sibling pushers are verified immune** to
  the 08-03 duplicate-spawn class — unconditional print every tick, worst-case spacing
  (60s period + 30s urlopen timeout) inside the 120s staleness window. The 08-03 accidental
  immunity is now a **measured** property, not a stylistic one.

## The boards redesign (2026-08-05 evening, commit `bc198aa5`)
Operator-ordered, and authorized against a standing deferral: the 08-01 HIG pass had recorded
*"Panel removal: not done, on purpose — needs operator judgement."* That judgement was given
([[sources/session-20260805-evening]]).

- **command → "trading desk"** — an exchange-style daily driver: money, positions & risk, geometry
  economics, per-asset edge, long book. It answers *"am I making money and what is at risk"*, not
  *"is the model calibrated."* The payoff-ratio tile now carries the **0.75 break-even threshold**
  instead of borrowing the profit-factor scale ([[concepts/payoff-asymmetry]]).
- **execution → "models · learning · execution"** — gains LEARNING BRAIN, LEARNING TRAJECTORY and
  the conviction admission bargauges (**relocated, not dropped**; the CV decode contract holds,
  repointed in tests); loses the INVENTORY & POSITIONING row, which duplicated the desk's
  positions row panel-for-panel.
- **problem_solution** — gains the **AUDIT & TELEMETRY INTEGRITY** row: `audit_dropped_writes`,
  `audit_tail_truncations`, `gauges_dropped_nonfinite` as PROBLEM tiles and **`gate_divergence` as
  a trend panel**. The dark metrics of [[sources/telemetry-stack-audit]] finding 2 are boarded, and
  the `07d38a51` KNOWN-GAP instrument is on screen for the first time
  ([[synthesis/owed-measurements]] item 26, (a)+(b) closed; the era trio remains open).
- **screening → "screening & market"** — gains CONTEXT (cycle & macro) and THALES; later the same
  evening gains the **TANGIBLE-VALUE LADDER** row for the haven gradient
  ([[synthesis/tangible-value-doctrine]]).

**Preserved deliberately:** glass skin, Apple palette, HIG post-passes, panel primitives, USD
non-scaling unit, `SPAN_NULLS_MS` honesty, `CODE_LABELS` decoding — and **UIDs unchanged**, so
links, bookmarks and the supervisor auto-import fingerprint contract survive. All of it through
the **board generator**; the JSON is generated output, never hand-edited.

> ⚠️ **Boarding a metric is not displaying it.** The brand-new `gate_divergence` panel wrapped a
> **bare `max()`** while `gc_pusher` emits the metric **per gate with a `{gate}` label** — one gate
> trending to −0.4 while another sits at +0.05 plots the **+0.05 flatline**, hiding exactly the
> sustained trend the panel's own description tells the operator to watch for. Caught by an
> adversarial pass one commit later (`46cdc19a`), fixed to `max by (gate)` with a `{{gate}}`
> legend and pinned by a test. This joins `slip_bps_notional_weighted` (never shipped) and the
> dark metrics (never boarded) as a **third way a metric can exist and tell you nothing**.

> ⚠️ **A stale fixture can erase a real metric.** The synthetic status fixture **predated** the
> `gate_divergence` instrument, so `test_every_query_hits_an_emitted_metric` read it as *never
> emitted* and declined to protect it — the phantom-ghost hazard inverted
> ([[concepts/iron-law-of-debugging]]). The fixture now carries the entry, and the later `haven`
> block was added to it **at birth**.

## Sidecar changes the same evening
- **`gc_log_pusher` inode provenance (commit `46cdc19a`)** — the 29g rotation drain saved
  **new-generation offsets under the OLD inode**: `tick()` stat'd the path once, then
  `_drain_rotated` spends **seconds of network time** before the main file is opened, so a rotation
  inside that window made the **next** tick's drain seek `.1` at a **foreign offset and skip its
  head**. A smaller instance of the hole 29g had just closed, and **invisible to 29g's own
  provenance check**. Provenance now comes from `os.fstat` on the **opened handle**.
- **`gc_pusher` gains the haven exports (commit `717b2e39`)** — gradient, `rungs_seen`, per-rung
  returns and the state label, feeding the screening board's ladder row. Report-only, like the
  module behind it.

## The dark metric that named its own cause (2026-08-05 late evening, commit `4799bfc7`)
`audit_tail_truncations` spent the whole audit as a **dark metric** — emitted, on no board, and with
**no hypothesis attached**. `bc198aa5` finally boarded it (item 26). Five hours later item 30f named
what had almost certainly been incrementing it:

> **`scripts/auto_update.py`'s force-kill grace was `45s`, while `runner.py:386` documents MEASURED
> worst-case cycle stalls of `88.1s / 55.5s / 50.2s`. Every measured stall exceeded the grace.**
> So the deploy chain — which bounces the runner on a **~15-minute cycle**
> ([[entities/auto-update]]) — was `taskkill`ing **HEALTHY** runners **mid-cycle**, and an unclean
> kill mid-append is exactly what leaves the torn audit tail the counter counts. Grace raised
> **45s → 150s**.

Three things worth keeping from this:
1. **Cause and consequence were fixed in the wrong order, and that was still correct.** 29b/29h
   shrank the *consequences* of an unclean kill (torn-tail heal, per-row fsync) weeks before 30f
   removed the *cause*. Durability first, then the stressor — the order that keeps you safe while
   you are still wrong about the cause.
2. **A boarded metric is what makes a code-reading finding land as a diagnosis.** `45 < 88.1` is a
   fact about two constants; it becomes an *incident history* only because a counter had been
   quietly recording the consequence. The dark-metric backlog was not paperwork
   ([[sources/telemetry-stack-audit]]).
3. **The connection is inference, not proof.** No trace ties a specific truncation to a specific
   `taskkill`. What is measured: the grace was below every documented stall; the counter is
   non-zero. **A post-fix reading of `audit_tail_truncations` going flat is the confirming
   measurement** — the honest close, and not yet taken.

Same commit, adjacent: **`core/skimmer.py`'s replace-hysteresis was void after every restart** —
scores were persisted but **never read back**, so every incumbent compared as **0.0** and a **0.55
candidate evicted a 0.90 incumbent on every 15-minute deploy** ([[synthesis/owed-measurements]] item
30g). Two separate defects, one shared enabler: **the deploy cadence is a load-bearing part of this
system's failure surface**, and both were invisible to anything that did not model a restart.

## Child-log rotation at the spawn boundary (2026-08-07, commit `48a63610`) — verified live
`runner.log` had reached **153.8 MB with no rotation anywhere**: the supervisor opens the child
log append-mode at each spawn and the child holds the handle for life, and **Windows refuses to
rename an open file** — so the only safe rotation point is the gap between a child's death and
its respawn. `_spawn` now calls `_rotate_child_log` immediately before re-opening
(**64 MB cap / keep 2** via `LB_CHILD_LOG_MAX_MB`/`LB_CHILD_LOG_KEEP`, sized against measured
~7 MB/day → ~3 weeks retained). **Best-effort by contract:** a lingering handle skips rotation
and appends — an unrotated log is an inconvenience, an unspawned runner is an outage.
`gc_log_pusher._drain_rotated` (the 29g work above) consumes the rename losslessly.
**Live-verified 15 minutes after commit:** `19:49:32 rotated runner.log (64MB cap)` in the
supervisor's own log, the ~154 MB archive on disk as `runner.log.1`, a fresh `runner.log`
growing beside it ([[sources/session-20260807-evening-ops]] — which also documents HOW the
commit deployed despite [[entities/auto-update]]'s local-commit blind spot: `pc_supervisor.py`
is the one self-restarting file). Closes [[synthesis/owed-measurements]] item 38(b).

## The venv shim pair — every supervised process is TWO pids (verified live 2026-08-07)
On Windows the venv's `pythonw.exe` is a redirector that spawns the base interpreter as a child
with an **identical command line** — so each logical process in this plane is a **pair**
(measured live: 10 OS processes = 5 logical; `pc_tidy.ps1:195` had noted it 07-30). The sharp
consequences ([[sources/session-20260807-evening-ops]] §5): the supervisor's `Popen` child is
the **shim** while `runner.lock` names the **base interpreter** (two authorities, two pids, one
process); the pusher bounce's commandline-matched `Stop-Process` kills **both** halves only by
accident of command-line propagation; and the spawn-time log handle is inherited down the pair,
so the rotation window above requires the **whole pair** gone. Any pid-count liveness probe or
kill escalation must expect 2 pids per logical process.

## The panel/metric-chain audit (2026-08-09, 22 agents) — 11 defects across 15 panels

([[sources/session-20260809-adversarial-audits]] §3.) The first audit to walk the **whole chain**
— panel → PromQL → `gc_pusher` gauge → `status.json` key → the code that computes it — rather
than auditing the boards or the metrics separately. **8 of the 11 defects are decision-grade**,
and one of them **led to a live risk bug**.

| ID | Defect | Status |
|---|---|---|
| **D1** | The hero tile **"Net P&L (all time)"** plots `liquiditybot_realized_total` = **−208.31** against a true all-in of **−382.34**, while its description claims *"the true bottom line, never resets, hedges included"* — **all three clauses false of the series it plots**, and *"hedges included"* false in exactly the way the number is wrong (the 185.94 of opening-leg entry **and hedge** fees is precisely what `realized_pnl_total` excludes). **The strongest false claim on any board.** | **number FIXED** by `a6334162`; **board repoint OWED** |
| **D2** | **Both drawdown gauges** (command panel id 23; problem/solution panel id 23) plot `drawdown_pct` — start-to-now, **cash-only** — while the **15% hard-stop flatten and the throttle read `drawdown_mtm_pct`** (peak-to-now, MTM). A **−20% book fires `hard_stop_triggered` while the gauge reads FULL GREEN**; the inverse is already pinned at `tests/test_audit_config_risk.py:281-288`. `runner.py:984` computes the MTM figure and **discards it as a local**; **no board references it at all.** | **OPEN, decision-grade** — [[synthesis/owed-measurements]] item 55 |
| **D3** | *"Heat vs cap"* reading **0.0% forever** | **FIXED** by `1fee174e` — see below |

> ### The case for auditing the panel chain, in one line
> **D3 was a panel that had never left zero, and it was the visible symptom of a live risk
> defect**: the sizer was reading an attribute `PortfolioState` does not have, three risk controls
> were inert, and tickets ran **13.7% larger than designed**
> ([[concepts/test-double-fidelity]]). **A gauge that has never moved is a finding, not a
> quiet subsystem.** Post-fix the same gauge reads **0.1177**.

**The dependency that ordered the work.** D1's repoint **could not land before the bounce**:
`gc_pusher` **skips absent keys**, so repointing a panel at `net_pnl_all_time` while the running
process lacked the key would have produced an **empty panel** — strictly worse than a wrong one.
The keys exist in the running process post-bounce (runner relaunched **11:46:10**), so the
repoint is **unblocked**.

> **Generalizable sequencing rule for this plane:** *a panel may only be repointed at a series the
> RUNNING process emits — not at one the committed code would emit.* `committed ≠ running` is the
> same distinction [[entities/auto-update]] records for deploys, applied to telemetry.

**Board work is queued as ONE regeneration** covering D1's repoint, D2's new series and retitle,
and every remaining panel finding. **The JSON is never hand-edited** — the generator is the only
author (the standing rule since `bc198aa5`).

## Related
[[entities/liquiditybot]] · [[concepts/liveness-by-output-cadence]] ·
[[sources/session-20260807-evening-ops]] ·
[[concepts/torn-append-fusion]] · [[entities/auto-update]] ·
[[sources/session-20260803-bug-sweep]] · [[sources/test-suite-outputs-contamination]] ·
[[sources/telemetry-stack-audit]] · [[sources/session-20260805-evening]] ·
[[synthesis/tangible-value-doctrine]] · [[sources/session-20260809-adversarial-audits]] ·
[[concepts/two-paths-one-quantity]] · [[concepts/self-flattery-gradient]] ·
[[synthesis/documentation-drift-register]]

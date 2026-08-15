# Multi-agent workflow doctrine for this repo — measured, not assumed

**Date:** 2026-08-15 · **Basis:** three workflows run this session against this
codebase, with per-run telemetry. Every claim below is a measurement from those
runs, not a generic best practice. Where the measurement contradicts common
advice, the measurement wins and the contradiction is stated.

## The telemetry

| run | pattern | agents | subagent tokens | wall | candidates | confirmed |
|---|---|---:|---:|---:|---:|---:|
| `wf_59ca8ba8-61a` war room | orchestrator + parallel verify | 16 | 1,385,695 | 2,032s | 3 cascades | — |
| `wf_fe4ccad9-568` PM scan | parallel fan-out + pipelined kill | 24 | 2,640,447 | 1,363s | 232 | **15** |
| `wf_5d7517a2-305` class scan | parallel fan-out + pipelined kill | 19 | 1,969,396 | 1,066s | 507 | **10** |
| **total** | | **59** | **5,995,538** | | **739+** | **25** |

Cost per confirmed finding: **176k tokens** (PM scan), **197k** (class scan).
That is the number to budget against — not tokens per agent.

## Finding 1 — Agents are reliable at LOCATION, unreliable at MAGNITUDE

This is the load-bearing result and it held across all three runs.

**Every pointer verified. Most headline numbers did not.**

| the agent said | re-derivation |
|---|---|
| `gate_efficacy_report.py:105` bins on disposition and never reads `label_era` | ✅ **confirmed** — 0 occurrences of `label_era` in the file |
| `session_digest.py:139` constructs an `AuditTrail` (a writer) | ✅ **confirmed** |
| `test_no_console_popups.py:81` matches its own comment banner | ✅ **confirmed** |
| "fee-free gross is negative on both statistics over 414 positions" | ❌ **did not reproduce** — entry-only is *positive* on both; hedge-inclusive mean is positive, median negative |
| "era-matched on `exit_sim`: 30.89% vs 15.06% = −15.83pp" | ❌ **did not reproduce** — measured 12.55% vs 14.12% = −1.57pp (the *direction* survived on a different era: `triple_barrier` −18.71pp) |
| "baseline uniqueness 0.054, n_eff 112.1, inflation ×4.29" | ⚠️ **different population** — whole corpus measures 0.0154 / 162.2 / ×8.07; same direction, not the same number |

**Rule: ship an agent's pointer, never its number.** The orchestrator re-derives
every figure a conclusion rests on. This is USAGE.md clause (g) applied to
delegation — and it is not a criticism of the agents. Locating a defect in
400k lines is the expensive part; arithmetic over a live CSV is the cheap part,
and the cheap part belongs where it can be checked.

## Finding 2 — The adversarial refuter killed <1%. The finder prompt killed the rest.

| run | killed by finders themselves | killed by refuters | survived |
|---|---:|---:|---:|
| PM scan | 215 | **2** (0.9%) | 15 |
| class scan | 494 | **3** (0.6%) | 10 |

Standard multi-agent advice treats adversarial verification as the quality
mechanism. **Measured here, it is not** — 99%+ of the killing happened inside
the finder, because the finder's prompt made shipping expensive:

> A finding ships only with ALL of: exact `file:line` YOU READ; what the code
> DOES that is wrong; a CONCRETE failure scenario (specific inputs → specific
> wrong output); and why an existing guard/test does not already cover it.
> Report `candidates_considered` and `candidates_killed` — a high kill count is
> evidence of strictness.

**Do not read this as "drop the refuters."** Two effects cannot be separated
from this data: (a) refuters still *corrected severity and fix-class* on
survivors, which is where a mislabelled SHIP-BLOCKED would have escaped; and
(b) the finders may have been strict *because* a refuter was known to follow.
What is measured is the kill count. What follows is a budget shift: **put the
tokens in the ship-criteria, and keep a thin refuter for classification.**

## Finding 3 — Roots and needles are the difference between a result and a void

Before the contract was enforced, an entire agent result was **void**: it ran in
the worktree, whose `outputs/` is empty, and reported a "signal drought" that
was an artifact of an empty directory. Since every prompt began with

```
CODE ROOT: <worktree>
DATA ROOT: <main tree>    <-- outputs/ lives ONLY here
```

no run has produced a void result, and **no agent returned "cannot be
established"** — the failure mode that dominated earlier sessions, where an
unnamed needle came back empty while every named needle was found.

## Finding 4 — Kill rate is the quality signal, not survivor count

93.5% and 98.0% kill rates. The output that mattered was mostly **what was
eliminated**: 217 and 497 candidate defects that a lazier pass would have
reported as findings and a human would have had to triage.

A scan reporting 200 findings has not found 200 defects; it has moved the
triage cost onto the reader. **Require the kill count in the schema** so
strictness is observable rather than hoped for.

## Finding 5 — Scope the second scan by CLASS, not by breadth

The PM scan swept generically (232 → 15). Re-running it generically would have
re-killed the same 217. The class scan instead hunted **recurrences of the five
defect classes the first scan confirmed**, each defined by its own specimen, with
refuters instructed to kill anything that was "a generic bug, not an instance of
the assigned class."

Result: 10 further confirmed findings, and **one class (reader-that-writes) came
back clean** — which is itself a result. A clean class means the defect was a
one-off rather than a habit, and the next session must not re-hunt it blind.

## The pattern this repo should default to

Not `orchestrator`. **`parallel` fan-out → pipelined per-finding kill →
single synthesis**, with the orchestrator re-deriving every load-bearing number
before it reaches a human.

```
phase 1  parallel finders          one per domain OR one per defect class
         (no barrier — pipeline)   schema forces file:line + failure scenario
                                    + why-not-already-handled + kill counts
phase 2  per-finding refuters      thin; classification and severity, not discovery
         (fan out per finding)     default refuted=true
phase 3  single synthesis          ranked, SAFE vs SHIP-BLOCKED
phase 4  ORCHESTRATOR RE-DERIVES   every number a conclusion rests on
```

Phase 4 is not optional and is not delegable. It is where two of this session's
three headline numbers were caught.

## Costing rule

Budget **~180k tokens per confirmed finding**, not per agent. A 15-finding scan
is a ~2.6M-token commitment. That is worth it for a hardened codebase where the
alternative is a defect reaching a live decision path — and it is *not* worth it
for a question one grep answers, which is why the prior-art pass (one cheap
agent asking "does this already exist?") runs before any fan-out.

## What this doctrine does not claim

It is measured on **one codebase, one session, three runs**, all read-only audit
work. It says nothing about implementation fan-outs (agents that write code), and
the finder-vs-refuter split may invert where the task is generative rather than
investigative. Treat Finding 2 as strongest-evidence-available, not settled.

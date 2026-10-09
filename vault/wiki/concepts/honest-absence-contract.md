---
title: The Honest-Absence Contract (a panel with no stated precondition cannot ship)
category: concept
summary: "The constructive answer to false-green's inverse: a board that renders Grafana's stock 'No data' collapses two opposite facts — the bot has not YET done the thing (honest absence) and the telemetry that should always be there is GONE (defect) — into one identical rendering. The contract makes the difference MECHANICALLY DECIDABLE: every panel resolves to exactly one of three states — a live value, an honest absence naming its own precondition, or THE ONE reserved defect string. Enforcement is the part that matters: an undeclared metric family raises KeyError AT BUILD TIME (proven by injection 2026-08-16), so a panel with no stated precondition CANNOT SHIP. Registry at head: 64 declared families (31 event-gated, 33 section-gated), 29 always-on metrics pinned against the exporter by a test that RUNS collect() rather than asserting a list. The diagnosis that forced it: 27 of 192 panels rendered nothing and NONE of it was a code defect"
tags: [instruments, telemetry, boards, honesty, enforcement, defect-class]
sources: 1
updated: 2026-08-16
---

# The Honest-Absence Contract

**Boundary (domain rule 9):** **repo-side / telemetry-side**. Nothing here is a
sim number, a venue number, or a P&L claim.

## The problem it solves

> **Grafana's stock "No data" says nothing about WHY**, and two entirely opposite
> facts render identically:
> **(a)** the bot has not yet done the thing the series counts — zero fills, no
> retrain, a judge window still filling. **An honest absence, and the board must
> SAY SO.**
> **(b)** the telemetry that should always be there is **gone**. **A defect, and
> the board must say THAT.**
> — `scripts/build_trading_dashboard.py:1034-1042`, paraphrased from the contract block

This is [[concepts/false-green]] **inverted**, and it is the exact shape the boards
were diagnosed with: *a panel that cannot distinguish MEASURED ZERO from NEVER
MEASURED.* It is also [[concepts/zero-is-not-a-reading]] moved from the analyst to
the display surface — the analyst's rule was *do not read a zero as a measurement*;
this makes the surface **incapable of presenting one as the other**.

## The three states, and why "mechanically decidable" is the load-bearing phrase

Every panel resolves to **exactly one** of:

| state | what renders | who decides |
|---|---|---|
| **value** | the series | the data |
| **honest absence** | the panel's **own precondition**, in operator language | the family registry |
| **defect** | **one reserved string** — `⚠ no series — exporter/pusher, not the bot` | the always-on set |

The **always-on set** is what makes the third state decidable rather than a
judgement call. It is the set of metrics `gc_pusher.collect()` emits **from a
status.json containing only `{written_at, runner_state}`** — i.e. metrics whose
emission depends on **no status content whatsoever**. If one of *those* has no
series, *"the bot has not traded yet"* is **not an available explanation**; the
pusher, the status file, or the query is at fault.

**And that set is pinned by a test that RUNS the exporter** —
`tests/test_dashboard_no_value.py::test_always_on_set_matches_the_exporter`
recomputes the set by **calling `collect()` on a minimal status**, rather than
asserting against a hand-maintained list. That is
[[concepts/tautological-instrument]]'s method (*ask the running system*) applied to
the pin itself: two hand-written copies agreeing would have been
[[concepts/false-green]]'s *"two hardcoded copies agreeing is not a test."*

## The enforcement, which is the whole point

> **An undeclared metric family raises `KeyError` AT BUILD TIME.**
> `_nv_family()`, `scripts/build_trading_dashboard.py:1188-1201`:
> *"no entry in `_NO_VALUE_BY_FAMILY`. Declare the precondition (the guard in
> `scripts/gc_pusher.py`) before shipping a panel."*

**Proven by injection, 2026-08-16** (not by reading — [[concepts/tautological-instrument]]
§the method this class actually requires):

| probe | result |
|---|---|
| `_nv_family("liquiditybot_totally_undeclared_family_xyz")` | **`KeyError` RAISED** with the declare-the-precondition message |
| `_nv_family("liquiditybot_order_maker_share")` (control) | returns the declared key, **no raise** |

Both polarities exercised, so *"the guard passed"* and *"the guard is broken"* are
**separated observations**. This is what lifts the contract out of
[[concepts/adoption-is-not-enforcement]]: *"we always state the precondition"* and
*"a panel without one cannot exist"* are different claims, and this one is the
second.

**Registry at head `c4272391`, read by RUNNING the module** (2026-08-16):

| quantity | value |
|---|---:|
| `_NO_VALUE_BY_FAMILY` declared families | **64** |
| — tier `event` (cannot exist until the named event happens) | **31** |
| — tier `section` (cannot exist until the runner writes that block) | **33** |
| `_ALWAYS_ON` metrics (defect-state eligible) | **29** |
| longest precondition string, measured | **40 chars** |

> ⚠️ **Two corrections to the catch-up's own figures, recorded per
> [[synthesis/governance-doctrine]] rule 16.** It reported *"64 families → 33
> preconditions"*: **all 64 carry a precondition**; **33** is the count of the
> `section` tier. And it reported a **"≤60 chars"** rule: **no such constraint
> exists in the code** — 40 chars is the *measured* maximum, not an enforced bound.
> A brevity discipline that lives only in the author's habit is exactly the kind of
> thing this page says must be mechanized or dropped.

**And every precondition string restates the ACTUAL guard**, with the `file:line`
of that guard in the comment beside it — e.g.
`liquiditybot_order_maker_share → ("event", "awaiting first fill")` cites
`order_manager.py:730-731`. A precondition that paraphrases the author's belief
rather than the code is [[synthesis/documentation-drift-register]] waiting to
happen.

## The rule stated once, not at 185 call sites

The contract is applied **once**, in the HIG pass, to every panel on every board —
the same doctrine as the palette pass. A presentation invariant enforced per-call-site
is an invariant that a future author forgets at exactly one site
([[concepts/adoption-is-not-enforcement]]).

## The diagnosis that forced it

**27 of 192 panels rendered nothing, and NONE of it was a code defect.** The dead
references reduced to two root causes in the live status — `ml.load_stats == {}`
and `orders == {}` — after `passive_base_prob` moved **0.45 → 0.048** at `8e5455e8`
and fills went to zero. And `gc_pusher` was **CORRECT to emit nothing**: its own
comment records that a fabricated `0` would read as *"exclusion off"* when the truth
is *"not yet measured"*.

> **The boards were not badly designed. They were badly FED — and then honest
> absence rendered as broken.** The instrument was right, the *surface* was
> lying, and every previous fix attempt had been aimed at the instrument.

## Related

- [[concepts/false-green]] — this is its inverse, and the constructive answer to it
- [[concepts/zero-is-not-a-reading]] — the analyst-side rule this mechanizes on the display
- [[concepts/adoption-is-not-enforcement]] — why build-time `KeyError` and not a style guide
- [[concepts/tautological-instrument]] — *ask the running system*; both the always-on pin and this page's own verification follow it
- [[concepts/honest-null-result]] · [[concepts/uncounted-exclusion]] — the same honesty applied to verdicts and to filtered rows
- [[entities/observability-sidecars]] · [[synthesis/documentation-drift-register]]
- [[sources/session-20260816-catchup-08-12-to-08-16]] — the filing that closed the board-rebuild loop
- Repo: `scripts/build_trading_dashboard.py:1034-1241`, `scripts/gc_pusher.py`,
  `tests/test_dashboard_no_value.py`, `docs/grafana/liquiditybot_command.json`

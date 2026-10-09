---
title: Generosity Masks Fragility
category: concept
summary: "An over-generous simulator, stub or fixture hides test fragility by making the required condition trivially available — so the tests that depend on luck pass anyway, and the flakiness only surfaces when the model is made honest. The flake wave that follows a fidelity fix is debt being DISCLOSED, not debt being created, and must not be attributed to the fix. Type specimen 2026-08-10: four full-engine bracket-exit tests depended on a random walk dipping through a resting bid, hidden for months because the fill hazard granted a fill on essentially any book; one combination failed once and passed three times with only COMMENTS changed between runs. Second specimen the same night: a heartbeat-latch test whose assert encoded one lucky THREAD SCHEDULE — the halted-runner-never-cycles schedule it read as failure is the SAFER outcome and satisfies the invariant; an uncontended scheduler is generosity too."
tags: [defect-class, testing, simulation, fidelity, flakiness, method]
sources: 1
updated: 2026-08-10
---

# Generosity Masks Fragility

## The claim

> **A test double that is too kind cannot produce the failing condition, so a test that depends on
> luck passes anyway. Raising the double's fidelity does not create the flakiness — it discloses
> it.**

The failure is structurally invisible while the generosity holds, because **every run is green**.
There is no signal to investigate: no intermittent red, no slow drift, nothing to bisect. The
fragility is latent by construction and becomes observable only at the moment the environment
stops handing out the outcome.

## The type specimen (2026-08-10, `aeeaae36`)

The fill simulator's passive hazard granted a fill on **essentially any book**
([[sources/session-20260810-fill-double-count]]). Four full-engine cases in
`tests/test_bracket_exits.py` actually depended on a **random walk happening to dip through a
resting bid** — a condition the walk supplied only sometimes. The hazard supplied it always.

**The evidence that it was luck and not design:** once the hazard was gated off, one 4-file
combination **FAILED once and then PASSED three times, with only COMMENTS changed between runs.**
Nothing about the subject changed; the seed path did.

**The fix:** a **driftless 90-cycle walk**, giving the market real opportunities to reach the
order. **Verified stable 3x** in the exact combination that flushed the flake.

## The second specimen, same night — a schedule, not a market (`c60f9772`)

`test_c1_first_lost_heartbeat_latches_new_risk_off` flaked red under `-n 8` load
([[sources/session-20260810-stressor-epoch]] §4): the heartbeat thread latched `lock_lost`
BEFORE the first loop iteration, the HALTED runner **correctly never cycled** (a peer owns the
lock), and the old `is False` assert read the empty observation as failure. **The assertion
encoded one lucky thread schedule, not the invariant** — a cycle that never runs places no
orders, so the "failing" schedule *satisfies* "new risk sealed at lost_count == 1"; only
observing `allow_new_risk=True` refutes it. **The schedule the test rejected was the SAFER
outcome.** Fixed to assert the invariant (`is not True`) with both legal schedules documented;
5x green serial. Generalization: the generous environment need not be a simulator — **an
uncontended scheduler is generosity too**, and `-n 8` load is the fidelity fix that disclosed
it.

## The rejected alternative — a green for the wrong reason

A **negative** drift also fills the orders. It was **rejected**: the drift walks price far enough
that **FW-050's 100bps collar rejects the entry**, so the test would pass by demonstrating that
the *collar* works, not that the *bracket exits* work.

> **A fix that makes a test pass for a reason unrelated to its subject is not a fix.** It converts
> a fragile test into a **tautological** one ([[concepts/tautological-instrument]]) — worse,
> because it is now permanently green and permanently uninformative.

## Why it is not the fidelity fix's fault

The attribution error is the operational danger. A fidelity improvement lands, a flake wave
appears in the same session, and the natural reading is *"the change broke the tests."* It did
not. The tests were already broken; the environment was compensating.

> **Budget for a flake wave whenever a fidelity improvement lands, and read that wave as debt
> being DISCLOSED, not debt being created.**

The same reasoning as [[concepts/inertness-protocol]], one plane over: before attributing a test
shift to the diff, ask whether the diff merely stopped *hiding* something.

## Relation to the neighbouring classes

| class | what could not happen | why |
|---|---|---|
| [[concepts/false-green]] | the **gate could not FIRE** | the failure arm was unreachable |
| **this class** | the **test could not FAIL** | the environment always supplied the condition |
| [[concepts/test-double-fidelity]] | the **double did not match production** | attribute present/absent on one side only |

**Read this page as the mirror of [[concepts/false-green]].** There, a check was structurally
incapable of reporting a real failure. Here, a check was structurally incapable of *encountering*
one. Both produce an unbroken run of greens; both are only discoverable by changing something
else and watching what falls over.

**And it compounds with [[concepts/default-path-fallback-writes]]:** when a fixture pins a
constant (`passive_base_prob=1.0`) to buy determinism, the pin holds only while that constant is
still the mechanism. A fidelity fix that moves the mechanism **silently retires the pin** — the
generosity vanishes and the fixture is back on luck without any edit to the fixture.

## The detection rule

**You cannot detect this class from green runs.** The only instruments that work:

1. **Deliberately harden the double** and watch what fails — the fidelity fix *is* the detector.
2. **Ask what supplies the precondition.** If a test's required condition is provided by the
   *environment* rather than by the *test's own setup*, it is a candidate.
3. **Perturb something irrelevant** (comments, file ordering, `-n` worker count) and re-run. A
   test whose outcome moves under a semantically null change is running on luck — the same
   signature as the load-marginal flakes on [[concepts/false-green]]'s docket.

> **A test must arrange its own precondition.** If it borrows one from a generous environment, it
> is measuring the environment's generosity and reporting it as the subject's health.

## Related
[[sources/session-20260810-fill-double-count]] · [[concepts/false-green]] ·
[[concepts/test-double-fidelity]] · [[concepts/tautological-instrument]] ·
[[concepts/default-path-fallback-writes]] · [[concepts/inertness-protocol]] ·
[[concepts/location-invariant-tests]] · [[concepts/paper-real-boundary]]

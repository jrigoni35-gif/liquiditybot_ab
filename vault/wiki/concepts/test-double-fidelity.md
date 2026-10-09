---
title: "Test-Double Fidelity (a double may only implement API the production object actually has)"
category: concept
summary: "A test double that supplies an attribute the production object lacks converts a production crash into a green test, and the green is evidence about the double, not the system — the type specimen is a heat-gate test whose docstring names the exact bug class it then reintroduced one level up, hiding an unconditional getattr-default that made three risk controls inert and every ticket 13.7% larger than designed while ~3,400 tests passed. MIRROR FORM, recurring on the same fixture 2026-08-09 (owed 59): a6334162 shipped 4 status keys and gauges without updating _SYNTH_STATUS, latent by construction until a panel referenced one — at which point test_every_query_hits_an_emitted_metric failed CORRECTLY, making it the contrast case to false-green (a gate that could fire and did); what is missing is not the check but the COUPLING, and a hazard that recurs on the identical fixture is a missing constraint rather than a mistake"
tags: [testing, doubles, fixtures, false-green, risk, invariants, status-schema]
sources: 2
updated: 2026-08-09
---

# Test-Double Fidelity

> **The rule, stated as a rule:**
> **A TEST DOUBLE MAY ONLY IMPLEMENT API THE PRODUCTION OBJECT ACTUALLY HAS.**

## The claim

When a stub, fake or fixture object provides an attribute or method that the **real** collaborator
does **not** provide, the test stops testing the system and starts testing **a system that does
not exist**. Every assertion downstream is sound; the green is real; and it is **evidence about
the double**.

This is a distinct failure from a wrong assertion. A wrong assertion is visible in the test. **A
too-generous double is invisible in the test** — it looks like setup.

## The type specimen (2026-08-09, commit `1fee174e`)

`risk/position_sizer.py` read the open book at three sites as:

```python
getattr(state, "positions", {}).values()
```

**`PortfolioState` has no `positions` attribute.** The book is `_positions`, exposed as
`open_positions()`. The `getattr` **default was therefore taken unconditionally, for the life of
the module** — verified directly: a `PortfolioState` holding a real position returns `{}`.

**~3,400 tests were green over this.** ([[sources/session-20260809-adversarial-audits]] §1)

### The sharpest instance is a test written *specifically* to catch this class

`tests/test_protocols.py::test_open_heat_reads_position_size_not_units`. Its docstring states its
own reason for existing:

> *an earlier draft read a nonexistent `units` attribute, which zeroed heat for every real
> `Position` and made the RP-050/051 heat gates unreachable in production*

Its fixture was:

```python
class _State:
    positions = {...}      # production has no such attribute
```

> **It guarded a nonexistent field on `Position` while depending on a nonexistent attribute on
> `state`.** The author understood this exact failure mode — the docstring proves it — and the
> double **reintroduced the same mode one level higher**, where the test could not see it.

**Three doubles were fixed to mirror `open_positions()`.**

## Why it is worth its own page rather than a note on `false-green`

[[concepts/false-green]] is about **a gate whose green does not entail that the gated work ran**.
This class is narrower and more insidious: **the work DID run, correctly, against an object that
production never supplies.** The gate is honest; the *world* is fabricated.

The two are neighbours. The distinguishing question:

- **false-green** — *could this have gone green without the work running?*
- **test-double fidelity** — *does anything in this test exist outside the test?*

## The cost, when it fired

Three risk controls, all inert, **all failing permissive**:

| Control | Intended | Actual |
|---|---|---|
| portfolio-heat veto (`max_portfolio_heat_frac` 0.35, `RP_HEAT_FULL`) | veto new risk at the cap | **unreachable**, heat read 0.0000 |
| signed-inventory reservation skew (`SZ-061`) | reserve against the loaded side | **never applied** |
| inventory-aggression multiplier | taper 1.10 → 0.65 as the book fills | **pinned at 1.10** — a permanent **10% size-UP** |

Measured on the live book with **real position ages**: gross heat **0.1176** (read 0.0000),
signed **+0.1052** (read 0.0000), multiplier **0.9488** vs the pinned **1.1000** — **tickets were
13.7% LARGER than designed**, precisely when risk was already on.

*(The first figure printed was −40.9%; that reconstruction stamped every position as opened NOW,
maximizing the clustering term. The corrected figure is −13.7%. See
[[concepts/adversarial-verification]].)*

## The detection rules this produces

1. **A double's surface is a claim about production.** Writing `class _State: positions = {...}`
   asserts that production states have `.positions`. If nothing checks that assertion, the test
   suite has an unpinned premise at its foundation.
2. **`getattr(obj, "name", default)` on an internal object is the smell.** Defensive `getattr`
   against *your own* types converts a `AttributeError` — the loudest, cheapest possible signal —
   into a **silent default**. Prefer the attribute access that crashes.
3. **Protocol-conformance tests, not shape-matching doubles.** Where a double must exist, derive
   it from the production accessor (`open_positions()`), never from a hand-written attribute.
4. **Pin the accessor, not the field.** The fix centralised one `_open_book()` accessor; the AST
   test pins that the sizer reaches the book **only** through it.
5. **The pin PARSES, it does not grep.** A substring check matched **the module's own prose
   describing the bug** and failed on its first run — the third time in this repo that a text
   scan was defeated by the code's own documentation ([[concepts/false-green]],
   [[concepts/iron-law-of-debugging]]).

## The mirror specimen recurs, and the same fixture is the site (2026-08-09, owed 59)

**`_SYNTH_STATUS` drifted again — and this time the gate caught it**
([[sources/session-20260809-turing-test-hedge-verdict]] §7).

`a6334162` shipped **4 new status keys plus gauges** and **did not update `_SYNTH_STATUS`**. The
defect was **latent by construction**: nothing failed until a **panel referenced one of the new
keys**, at which point `test_every_query_hits_an_emitted_metric` **failed, correctly.**

> **Two things worth separating.** The **check works** — this is the contrast case to
> [[concepts/false-green]], a gate that could fire and did. What is missing is the **coupling**:
> nothing makes it *impossible* to add a status key without updating the double, so the suite's
> protection arrives **at panel-authoring time** rather than at key-authoring time.

**This is the second time the same fixture has drifted** (the `gate_divergence` case below is the
first). A hazard that recurs on the identical object is no longer a mistake — it is a **missing
constraint**.

*What closes it:* a **schema pin between the runner's status writer and `_SYNTH_STATUS`**, so
adding a key without updating the fixture fails **at the source**. Registered as owed **59**.

## Sibling hazards already in the corpus

- **A stale fixture that erases a real metric** — the synthetic status fixture predated
  `gate_divergence`, so `test_every_query_hits_an_emitted_metric` read the metric as never-emitted
  and **declined to protect it** ([[concepts/iron-law-of-debugging]], the inverted hazard). Same
  root error, opposite sign: **the double was too POOR rather than too generous.** *(Same fixture
  as the 2026-08-09 owed-59 recurrence above — see that section.)*
- **A green test standing on a defect** — `test_monitor_deescalate_deadband`'s fixture depending
  on the old oracle baseline ([[concepts/tautological-instrument]]).

> Together these say the rule is two-sided: **a double must implement the production API, and
> only the production API — no more and no less.**

## Governance

Proposed and filed as **[[synthesis/governance-doctrine]] rule 15.**

## Related
[[concepts/false-green]] · [[concepts/zero-is-not-a-reading]] ·
[[concepts/iron-law-of-debugging]] · [[concepts/tautological-instrument]] ·
[[concepts/adoption-is-not-enforcement]] · [[concepts/adversarial-verification]] ·
[[sources/session-20260809-adversarial-audits]] ·
[[sources/session-20260809-turing-test-hedge-verdict]] ·
[[entities/observability-sidecars]] · [[synthesis/owed-measurements]] ·
[[comparisons/stated-invariants-vs-audited-reality]]

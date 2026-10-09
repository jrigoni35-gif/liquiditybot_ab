---
title: Two Paths, One Quantity
category: concept
summary: "When two code paths compute \"the same\" quantity two different ways they will eventually disagree, and if the two paths undo each other the disagreement is not a wrong answer but an infinite loop — the type specimen is execution/hedging.py, which produced this failure TWICE from the same function; the fix that addresses the class is one shared definition, not corrected arguments. THREE further instances landed in a single night (2026-08-08/09) — label_era, _explore_on, and the champion badge — establishing the severity ladder report / decide / PERSIST; and the same night produced the class's first PROSPECTIVE application, a pure shared predicate written specifically so OF-1 and OF-7 could not become the fourth. Migration idempotence is the special case where one derivation writes. FIFTH INSTANCE 2026-08-09 — the word 'drawdown': the gauge plots a cash-only start-to-now figure while the 15% hard stop and the throttle fire on peak-to-now MTM, so a −20% book reads FULL GREEN and the operator's only view cannot show the condition that flattens the book. Same day, the class's INVERSION: one predicate (`if not pos.is_hedge:`) serving two decisions that owe different answers — where this class says unify two derivations, the inversion says SPLIT one predicate. SIXTH INSTANCE 2026-08-10, the severest form yet because it produced NO disagreement to notice: the fill simulator had two MECHANISMS modelling one physical EVENT (a resting order being crossed), and since the calibrator solves sf_base so the hazard ALONE reproduces the measured crossing rate, the two paths did not disagree - they COMPOSED, into 2f-f^2 = 21.96% against an 11.66% target. That adds a rung ABOVE persist, CALIBRATE, where the duplicated derivation corrupts the constant every future record is priced by, and where the standard detection question (do the two paths agree?) returns yes and is useless - the working question is whether they fire on the same physical event."
tags: [defect-class, method, debugging, duplication, thrash, invariants]
sources: 9
updated: 2026-08-10
---

# Two Paths, One Quantity

## The claim

Whenever a quantity is computed in **two places**, the two computations are **two claims about
what the quantity means**, and nothing keeps them equal. The duplication is usually invisible
because both sites look locally correct — each is a short, obvious expression written by someone
who had the right idea in mind.

> **The severity is set by what the two paths DO, not by how far apart they are.** If they only
> *report* the quantity, the cost is a wrong number in a log. **If one path creates state and the
> other destroys it, the disagreement is not an error — it is a loop**, and it runs at whatever
> cadence the caller has.

That is the difference between a stale literal in a warning message and **147 round trips in 25
minutes**.

## The type specimen: `execution/hedging.py`, twice

One function, `HedgeEngine.evaluate()`, produced this failure **twice** — an open path and an
unwind path that each computed the quantity the *other* was gating on, differently.

| | Thrash #1 — the `signal_net` incident | Thrash #2 — `5c111962`, 2026-08-06 |
|---|---|---|
| The quantity | **net delta** | **correlation** — specifically, *which pair* |
| Open computed | total `net` vs `cap` | `corr(exposed, hedge_asset)` |
| Unwind computed | total `net` vs `band` | `corr(hedge_asset, others[0])` — the alphabetically-first **other** asset |
| Why it loops | a correctly-sized hedge is **exactly what pulls total net into the band**, so the hedge **unwound itself the moment it worked** → net back out of band → re-open | the hedge cleared its **own** floor at open and failed an **unrelated** pair's floor at unwind → unwind → net still over cap → re-open |
| Measured cost | not measured (found by reasoning; comment retained in source) | **294 fills, $72,433.15 notional, $289.73 fees = 95.6% of the window's equity drop** ([[sources/session-20260806-hedge-thrash]]) |
| Fix shape | split the quantity and **name both halves** in a comment | **extract one helper both paths call** |

> **Thrash #1's fix is why thrash #2 was possible.** #1 was fixed by *correcting the arguments* at
> one call site and writing a careful comment explaining the two quantities. That closed the
> instance and left the class wide open — the very next quantity in the same function was still
> computed twice. In the parent revision the comment explaining the first disagreement **ended at
> line 78**; the second disagreement was at **line 90** — **twelve lines below the warning about
> its own shape**.

## The general shape

1. A quantity has an **intuitive name** — *"our exposure"*, *"the correlation"*, *"the cost"*,
   *"the schema width"*. The name feels unambiguous, so nobody notices it needs a definition.
2. Two paths each need it, and each writes the two-line expression that is obvious **from where
   it stands**.
3. The expressions differ in a detail that is invisible locally: *which* positions count, *which*
   pair, *which* fee schedule, *which* literal.
4. **Under normal conditions the two agree**, so tests and eyeballs pass.
5. In one corner — a cold engine, an empty book, a fresh process, a rotated file — they diverge.
6. If the paths are **opposed** (create/destroy, admit/deny, open/unwind), divergence is
   **permanent**: each path's action re-establishes the other's precondition.

**Step 4 is what makes this class expensive.** The disagreement is not a bug that fires
immediately; it is a bug that waits for the conditions the system is worst at handling.

## The fix that addresses the class

**Correcting the arguments fixes the instance. Extracting the definition fixes the class.**

```
_exposure_by_asset(state, marks)   # ONE definition of "which asset are we exposed to"
   ├─ open   → exposed  = argmax|exposure|
   └─ unwind → dominant = argmax|exposure|      ← cannot differ, by construction
```

The property to aim for is not *"both paths use the right inputs"* — that is a claim about the
current author's care. It is **"the two paths cannot differ"** — a claim about the code's shape.
After `5c111962` the hedger **either opens and keeps, or never opens**; a cold correlation engine
makes both paths refuse, where before it made one open and the other close.

### Corollary: agreement is a stronger requirement than correctness

The hedge asset is **still selected alphabetically** (`others[0]`), which is arbitrary. The fix
did not make the choice good — it made both paths **agree about the arbitrary choice**, and that
alone ended the loop. **A system can be wrong and stable; it cannot survive being inconsistent.**
Fix the disagreement first; the choice is a separate, smaller decision.

### Corollary: a *documented* disagreement is not this defect

The same function deliberately keeps **two** delta quantities — the open tests total `net` against
a 20% cap, the unwind tests `signal_net` against an 8% band. Two quantities *and* two thresholds,
which is **hysteresis on purpose**, carrying its reason in a comment. **The defect is an
undocumented duplicate, not a deliberate asymmetry.** A future reader "unifying" that pair would
reinstate thrash #1.

## Where else this class appears in the corpus

- **The label era — the WRITE-SIDE instance, and the most expensive one (2026-08-09).**
  The producer computes `ml/history.py` `_row_era` → `triple_barrier_era(label_max_bars)`
  and persists the **horizon-qualified** `triple_barrier_h432`; the migrator computed
  `label_era_of(barrier)` and produced the **unqualified** `triple_barrier` for any `tb_*`.
  Same noun, same intuitive meaning, **one path can see the horizon and the other cannot**.
  Because the migrator **writes**, the disagreement did not produce a wrong number in a log
  — it produced a **wrong corpus**: 2,729 rows retagged, three label definitions pooled
  under one name, the era filter disarmed, and a champion deployed on the result
  ([[sources/session-20260809-corpus-corruption]], [[concepts/migration-idempotence]]).
  **This instance extends the severity ladder at the top:** the page's own scale runs
  *report the quantity* (a wrong log line) → *create/destroy* (a loop). The label-era
  instance is a third rung — **one path PERSISTS the quantity** — where a single
  disagreement is neither transient nor self-correcting, and survives every restart,
  because the loser of the disagreement is overwritten on disk.
- **The cost stack — three definitions of one number, all live.** The label floor assumes a
  **0.50%** round trip, the pre-trade gate is configured at **0.65%**, and measurement says
  **0.86%**. The labeler floors barriers using a cost **23% below** the gate's and **42% below**
  measured, and **no document reconciles this** ([[concepts/cost-truth]]). Same class, one level
  up: the paths here are *labeling* and *admission*, and they disagree about what a trade costs.
- **The schema width — two independent literals.** The width guard and its own warning message
  carried **22** (correct) and **20** (stale), so the warning reported a **phantom 69-column
  schema against a true 64** ([[sources/session-20260806-geometry-filing]]). The report-only
  version of the class: a wrong number, no loop.
- **The disposition cap — two truncation sites.** `main.py` pre-truncated to 40 chars *before*
  `mark_disposition`'s own 40-char cap; fixing the store's cap alone would have changed nothing.
  Two places implementing one policy, and **only one of them was the one everybody knew about**.
- **The assurance check counts** — a document's own spine table and verification block disagree
  (36 vs 47 checks; 188 vs 205 smoke) ([[synthesis/documentation-drift-register]]). The
  prose-level version.

## THREE instances in a single night — 2026-08-08/09

The sharpest evidence this page has for its own generality: **three distinct instances of
this one class, in three unrelated subsystems, inside one session**
([[sources/session-20260809-corpus-corruption]],
[[sources/session-20260809-gate-policy-and-self-heal]] §4). None was found by looking for
the class; each was found on its own.

| # | The quantity | Derivation A | Derivation B | What the disagreement cost |
|---|---|---|---|---|
| 1 | **`label_era`** | `migrate_history.py:125` **derives** `label_era_of(barrier)` — no horizon knowledge | `ml/history.py` `_row_era` → `triple_barrier_era(label_max_bars)` **persists** the qualified value | **2,729 corrupted corpus rows**; three label definitions pooled; era filter disarmed; a champion deployed on a data bug |
| 2 | **`_explore_on`** | the config block, through the **injectable** `main.load_config` | a **second direct read of the repo's `config.json`** inside the DSR block, **bypassing** `main.load_config` | an injected config **could not influence OF-5's phase** — a blind spot in the only mechanism that can test the gate |
| 3 | **the champion badge** | **0.1537**, computed on the **corrupted pooled 9,708-row** population | **0.2714 / 0.24728**, computed on the **clean 701-row** population | ML-083's own subject: a bug-promoted champion **wedged in**, unbeatable by any honest challenger |

**One sentence covers all three: one predicate/measurement, two derivations, silently
disagreeing.** The three differ only in *what the loser of the disagreement does*:

- #2 **reports** — the report-only rung (a wrong phase in a test path).
- #3 **decides** — the create/destroy rung (a gate verdict that cannot be overturned).
- #1 **persists** — the third rung this page added on 2026-08-09, where the disagreement is
  **written to disk** and survives every restart.

### The prospective application — the fourth instance that was designed out

**The overfit gate policy shipped the same night was deliberately built as a single pure
predicate to avoid becoming instance #4.** `gate_is_informational(explore_on, on_synthetic)`
(`scripts/overfit_check.py:101`) is called by **both** OF-1 (`:745`) and OF-7's dead-feature
check (`:943`), with the reason stated in its own docstring: *"One function so the two gates
can never drift apart, and a pure one so the policy is unit-testable instead of only
observable through a 40s CLI run."*

> **This is the first time in this corpus the class was applied BEFORE it fired.** Every
> prior instance on this page — the hedger twice, the cost stack, the schema width, the
> disposition cap, and all three above — was diagnosed after the disagreement had already
> cost something. The policy predicate is the counter-example, and it is worth noting *why*
> it was cheap: the two consumers were being written **at the same time by the same author**,
> which is precisely the window in which the two-line obvious expression is about to be
> written twice.

**The residue is honest:** a shared function is still a **convention**. Nothing gates a
future third caller of the OF-1/OF-7 policy from re-deriving the phase inline — the same
[[concepts/adoption-is-not-enforcement]] distance the hedger's `_exposure_by_asset` still
carries (owed **34a**). What #2 shows is that this is not hypothetical: `overfit_check.py`
**already had** two derivations of one flag inside a **single file**.

### The second prospective application (2026-08-10) — the ratchet consumes one verdict

The RP-072 goal ladder's **challenge ordering audit** applied the class at review time
([[sources/session-20260810-stressor-epoch]] §7.1): the escalation ratchet **consumes the
grader's own "hit" verdict** rather than re-deriving `attained >= effective_goal` at a second
site — because **two sites deriving one predicate drift silently**, and this predicate sits on
the **grading surface the $800 stressor is scored by**. One derivation of "did the month meet
its bar," consumed by both the grade record and the ratchet, with the ordering AST-pinned
(RP-071 precedes RP-072, so the month is judged by the bar it ran under). Prospective
application #2; like #1 it was cheap because both consumers were written by the same author in
the same session — the window in which this page says the class is born.

### And the fourth is registered, not fixed

The **CLI/runner ML-083 asymmetry** ([[synthesis/owed-measurements]] item **49**) is the
same class again: `scripts/train_meta.py:122` calls `should_deploy` **without** the
era-orphan condition `main.py:6330` applies, so **one deploy decision has two derivations**
and they reached **opposite verdicts two hours apart on the same corpus** (CLI REJECTED
0.2714 at 00:52; runner DEPLOYED 0.2473 at 02:56). Registered deliberately unfixed, and the
prescribed fix is **one shared gate function both callers invoke** — not a second copy of
the condition, which would leave the class open while closing the instance.

### The fifth instance — "drawdown", on the DECIDE rung, live (2026-08-09)

([[sources/session-20260809-adversarial-audits]] §3 defect D2;
[[synthesis/open-contradictions-register]] entry 23; [[synthesis/owed-measurements]] item 55.)

| The quantity | Derivation A | Derivation B |
|---|---|---|
| **"drawdown"** | **`drawdown_pct` = (start − cash − savings)/start** — start-to-now, **cash-only** — the only series `gc_pusher` carries, and what **both** gauges plot (command board panel id 23; problem/solution board panel id 23) | **`drawdown_mtm_pct`** — **peak-to-now, mark-to-market** — what the **15% hard-stop flatten AND the throttle** actually read |

**Reproduced on live code:** a book **−20% on marks** fires `hard_stop_triggered`
(*"20.00% >= 15%"*) **while the gauge reads 0.0, FULL GREEN.** The **inverse** is already pinned
at `tests/test_audit_config_risk.py:281-288`, where a **winning** account pegs the same gauge at
**15.0, red**.

`runner.py:984` **computes the MTM figure and discards it as a local.** **No board references the
MTM series at all.**

> **Why this one is worse than a reporting divergence.** The operator's only view of drawdown
> **cannot** show the condition that flattens the book. This is the **decide** rung wearing
> report-rung clothing: the *panel* reports, but the quantity it fails to show is one a
> **flatten fires on** — so the human in the loop is reading a different world than the machine
> is acting in.

**Prescribed fix follows the class rule, not the instance:** export the MTM series, repoint both
gauges, **and retitle the survivor** — *"Realized drawdown from start (reserve-inclusive)"*.
**Two quantities must keep two names.** (The audit's headline is *three* derivations; two have
cited call sites, and the third is implied by the retitle — the gauge omits the `reserve` term.)

### The inversion — ONE path serving TWO decisions

The same session produced this class's mirror, and it is worth naming because the prescription
inverts too. `main.py:1671`'s single predicate

```python
if not pos.is_hedge:      # gates BOTH perf.record_close AND breaker.record_close
```

gates **two subsystems that owe different answers**. Excluding hedges from the **performance
ledger** is indefensible (real money, real P&L). Excluding them from the **consecutive-loss
circuit breaker** is *arguable* — insurance legs lose by design
([[synthesis/owed-measurements]] item 52).

> **Where this class says *two derivations of one quantity must be unified*, the inversion says
> *one predicate serving two decisions must be SPLIT*.** Both are the same underlying error —
> **the code's structure does not match the decision structure** — and both are found by the same
> question: *how many decisions depend on this line, and do they want the same answer?*

### The SIXTH instance — two MODELS of one physical EVENT, and they did not disagree, they ADDED (2026-08-10)

The severest form yet, because it produced **no disagreement to notice**. The fill simulator had
**two mechanisms modelling one physical event — a resting order being crossed by the market**
([[sources/session-20260810-fill-double-count]], owed 57, execution-era boundary #4):

| path | what it claimed |
|---|---|
| `_sim_maker_cross` (`order_manager.py:1153`, called `:1288`) | **deterministic** — the book crossed, so fill |
| the per-poll passive hazard (`:1308`) | **stochastic** — with probability `p`, fill |

`scripts/calibrate_fills.py` measures **`f` = how often the market actually crossed a resting
limit within its life**, and `core.fill_calibration.invert_base_prob` solves `sf_base` so **the
hazard ALONE reproduces `f`**. Both paths therefore claimed *the same event at the same rate*, and
because the hazard **only ever ran inside `if book:`** it modelled nothing the snapshot could not
already show.

> **The two paths did not disagree — they COMPOSED.** Where the type specimen produced a thrash
> (two derivations undoing each other) and the fifth produced a contradiction (green gauge, firing
> stop), this one produced **a clean, quiet, arithmetically consistent number that was simply
> twice too big**: `1−(1−f)² = 2f−f² = 21.96%` against an `f = 11.66%` target, ledger-measured
> **22.30%**. Nothing was ever inconsistent, so nothing ever surfaced.

**This adds a rung ABOVE `persist` on the severity ladder — call it `CALIBRATE`.** When a
duplicated derivation feeds a *calibration*, the second path does not corrupt one record; it
corrupts **the constant that every future record is priced by**, and it does so *without any
observable inconsistency*. The report/decide/persist rungs are all detectable by comparing the two
outputs. This rung is not: **the outputs agree by construction, which is precisely the bug.**

> **The detection question changes on this rung.** "Do the two paths agree?" returns *yes* and is
> useless. The question that works is **"do these two paths fire on the same physical event?"** —
> and the answer came from reading the **calibrator's definition of what it measured**, not from
> reading either code path. The mechanism was found by asking what `f` *means*.

**And it was named, then lost.** [[sources/session-20260807-fleet-findings]] §1 stated it exactly
(*"the calibrated trade-through frequency is **spent twice**"*) — and the next morning it was
disposed of as *"conservative floor, by design"* ([[sources/session-20260808-morning-batch]]).
**This class survives a correct diagnosis if the disposition is wrong**, which makes the
disposition step part of the class's attack surface ([[concepts/self-flattery-gradient]]).

## How to find instances before they fire

- **Grep for the noun, not the bug.** The quantity has a name; find every site that computes
  something matching it. `_exposure_by_asset` was three lines that appeared twice —
  *lexically different, semantically identical* — so a duplicate-code detector would not have
  flagged it, but a search for *"which asset"* would.
- **Look at opposed paths first.** open/unwind, admit/deny, arm/disarm, write/verify. Only these
  turn a disagreement into a loop.
- **Ask what each path reads when the data is missing.** Divergence hides in the cold-start
  corner ([[concepts/zero-is-not-a-reading]]) — thrash #2's two paths agreed on every warm
  reading and disagreed on the empty one.
- **A comment explaining why two quantities differ is a marker, not a fix.** Where one such
  comment exists, the same function is likely to contain the next duplicate.

## The boundary of the class — rewritten after the panel's timeline adjudication (2026-08-07)

~~"Twelve hours after `5c111962`, the same loop shape recurred with the two-paths fix
holding."~~ **Panel-corrected ([[sources/session-20260807-institutional-review]] §B): the
147-lap event ran on PRE-`5c111962` code** — the "two incidents" were one ledger event
double-filed under two clocks, and D3 was committed nineteen minutes after it ended. What DID
outlive the pair fix is sharper evidence for this page than the original claim was: **12
residual laps (01:56Z–11:35Z) on fixed-pair code, unwinding at warm, genuine correlations
0.34–0.55 below floor** — because the opener judges the **delta cap** while the unwinder
judges a **correlation floor**, two different variables with **no shared deadband**. The class
is not just "two computations of one quantity"; its neighbor is **two different quantities
deciding one create/destroy pair, with nothing forcing the closer's condition to be the
opener's negation.** Alongside that, the cold post-restart EWMA flapping |rho|≈1 ↔ 0.0 during
the main event is [[concepts/zero-is-not-a-reading]]'s half of the disease. The lesson for
THIS page:

> **"The two paths cannot differ" is a property of the code's shape; it does not make the shared
> quantity STABLE.** An opposed create/destroy pair needs two guarantees: one definition
> (this class), and a reading that cannot flap across the threshold between cycles (evidence
> gating + hysteresis). `5c111962` bought the first; `cf454d5e` bought the second — a warmup
> gate on the evidence count, a re-hedge cooldown, and the FW-070 rate-latch, all on the open
> side only. The 08-06 residual *"any future disagreement thrashes at the same cadence with
> nothing to stop it"* (owed 34c) was the accurate prediction: it fired before it closed.

The fixed-point test this page asked for now exists (`af544d4c` — evaluate, **apply**, evaluate;
red against the parent blob at 13 opens/12 unwinds, green at 1/0). The AST call-site gate (34a)
remains open — and the panel's Jane Street lens found the "computed once" citation for the
shared helper **false** (`_exposure_by_asset` is *called* at both `hedging.py:184` and `:230`;
sharing the function, not the computation), which cost that lens its unconditional approval:
**the class is still policed by comments, not construction.** The panel's prescription matches
34a: freeze one `HedgeCycleInputs` per cycle (dominant asset, pair, corr, net, cap, band), pass
it to both arms, and AST-gate out-of-band `corr_state.corr(...)` reads.

## The enforcement gap, stated honestly

**`5c111962` shipped no gate for this class.** The shared helper is a **convention**, and the
commit's own `test_exposure_helper_excludes_hedges_and_is_shared` asserts sharing **in its name
only** — it calls the helper directly and never checks that either path uses it. Nothing fails if
a future author re-inlines a third definition. That is exactly the distance
[[concepts/adoption-is-not-enforcement]] names, and it was open again **one day after** the
append gate closed it for its own class.

**What a gate would look like here** is genuinely harder than the AST append gate: "no quantity is
computed twice" is not a mechanical predicate. The tractable substitutes, smallest first: assert
at the **call-site level** that both branches invoke the helper (AST, the same technique as
`test_append_invariant.py`); or pin the **behavioural** property — apply the returned actions to
the book and assert a **fixed point**, which is the test `5c111962` intended to write and did not
([[sources/session-20260806-hedge-thrash]] §5).

## Related
[[concepts/migration-idempotence]] — the **special case** of this class where one of the two
derivations **writes**; an idempotence failure is two-derivations-of-one-truth with the loser
overwritten on disk, which is why that page's fixed-point test is the strongest gate any
instance of this class has yet earned.

[[sources/session-20260809-gate-policy-and-self-heal]] ·
[[sources/session-20260809-corpus-corruption]] ·
[[sources/session-20260806-hedge-thrash]] · [[sources/session-20260807-hedge-churn-guards]] ·
[[sources/session-20260810-fill-double-count]] · [[concepts/self-flattery-gradient]] ·
[[sources/session-20260807-institutional-review]] ·
[[concepts/zero-is-not-a-reading]] · [[concepts/deadlock-discipline]] ·
[[concepts/adoption-is-not-enforcement]] · [[concepts/iron-law-of-debugging]] ·
[[concepts/cost-truth]] · [[concepts/tautological-instrument]] ·
[[concepts/dead-mute-trap]] · [[concepts/probe-livelock]] · [[concepts/deploy-deadlock]] ·
[[comparisons/stated-invariants-vs-audited-reality]] ·
[[comparisons/harness-vs-live-cost-stack]] · [[synthesis/documentation-drift-register]] ·
[[synthesis/owed-measurements]]

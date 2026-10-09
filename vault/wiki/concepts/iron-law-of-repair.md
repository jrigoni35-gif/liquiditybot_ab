---
title: The Iron Law of Repair (focused-fix five-phase protocol)
category: concept
summary: "Governance rule 20's substance, given its own page. THE IRON LAW: no fixes without completing SCOPE -> TRACE -> DIAGNOSE first — five phases in order (SCOPE feature manifest, TRACE inbound AND outbound dependencies incl. env vars and config, DIAGNOSE code/runtime/tests/logs/config with HIGH/MED/LOW risk labels and a CONFIRMED root cause, FIX in the order dependencies->types->logic->tests->integration one issue at a time, VERIFY feature tests + consumer tests + full suite), escalate at 3+ cascading fixes because that is an architecture problem and belongs to the operator. Source of truth is referenced BY PATH so this page cannot drift from it. DELEGATION COROLLARY: subagents do not inherit the parent's skills, so every fix-capable agent prompt must carry the law by path; read-only investigator agents are Phases 1-3 by construction. CARRIES A LIVE TEMPORARY SUSPENSION — the optimization carve-out, ACTIVE 2026-08-16, which EXPIRES rather than accrues and must be re-confirmed with the operator before any later session leans on it; the default state is the full Iron Law, and the carve-out suspends CEREMONY ONLY, never rigor (read the module first, measure do not infer, no silent behavior changes, DoD matrix still runs)"
tags: [governance, delegation, discipline, method, repair, doctrine, temporary-carve-out]
sources: 2
updated: 2026-08-16
---

# The Iron Law of Repair

> [!warning] This page carries a LIVE TEMPORARY SUSPENSION
> The **optimization carve-out** below was declared by the operator on
> **2026-08-16** and described by the operator, the same day, as **"just
> temporary"**. It is **NOT standing law**. The **default state of this page is
> the full Iron Law**. See §The carve-out — TEMPORARY, ACTIVE 2026-08-16 for the
> expiry rule before relying on it.

**Operator directive, 2026-08-16.** Binding as [[synthesis/governance-doctrine]]
**rule 20**. Measured session [[sources/session-20260811-16-vscode-3b307393]] §5;
re-filed with its temporary status corrected in
[[sources/session-20260816-catchup-08-12-to-08-16]].

**Boundary (domain rule 9):** everything on this page is **repo-side / process-side**.
No sim number, no venue number, no P&L claim is involved. Nothing here relaxes
[[synthesis/governance-doctrine]] rule 17 — an agent running all five phases is
still forbidden from cohort-resetting changes without operator adjudication.

## Source of truth — referenced by PATH, never pasted

```
C:\Users\haird\.claude\skills\focused-fix\SKILL.md
```

**318 lines** (`wc -l`, read 2026-08-16). *Referenced, not copied* — a pasted
protocol is a protocol that drifts from its source, and this vault has a register
for exactly that failure ([[synthesis/documentation-drift-register]]). What
follows is the load-bearing shape; the skill file is the authority, and any
disagreement resolves **to the file**.

## The law

> ```
> NO FIXES WITHOUT COMPLETING SCOPE → TRACE → DIAGNOSE FIRST
> ```
> *"If you haven't finished Phase 3, you cannot propose fixes. Period."*
> — `SKILL.md:36-44`, verbatim

## The five phases, in order

| Phase | Key action | Output |
|---|---|---|
| **1 SCOPE** | Read **every** file in the feature; map entry points | Feature manifest |
| **2 TRACE** | Map dependencies **inbound AND outbound** — including **environment variables and config** | Dependency map |
| **3 DIAGNOSE** | Check code, runtime, tests, logs, config; label each issue **HIGH / MED / LOW**; root cause **CONFIRMED, not assumed** | Diagnosis report |
| **4 FIX** | In this exact order: **dependencies → types → logic → tests → integration**, **ONE issue at a time** | Fix log per issue |
| **5 VERIFY** | Feature tests **and** consumer tests (everything that imports it) **and** the full suite | Completion report |

Phase 4's own rule — *"if a fix breaks something else, STOP and re-evaluate (go
back to DIAGNOSE)"* (`SKILL.md:206`) — is why the order is not decorative. The
phases are a **ratchet**, not a checklist.

## The escalation rule — 3 strikes is an architecture problem

> **If 3+ fixes create NEW issues (not pre-existing ones), STOP immediately.**
> *"This pattern indicates an architectural problem, not a bug collection."*
> **Do NOT attempt fix #4 without this discussion.** — `SKILL.md:211-221`

Fix #4 without the discussion is the failure this rule exists to stop: a session
converting an architectural defect into a **cascade of local patches**, each one
individually defensible. It is the repair-side twin of
[[concepts/unfalsifiable-explanation]] — every patch has a reason, and the
composite is the problem.

**The escalation is to the OPERATOR.** An agent cannot adjudicate its own
architecture question, and a session that has already spent three fixes is the
least neutral reader of whether a fourth is warranted
([[concepts/self-flattery-gradient]]).

## The delegation corollary — an unstated protocol is an absent protocol

> **Subagents do not inherit the parent's loaded skills.** A protocol the
> orchestrator is following is **invisible** to the agent it dispatches.

Therefore:

- **Every fix-capable agent prompt carries the law BY PATH.** Not "follow the
  focused-fix protocol" — the *path*, so the agent can read the authority itself.
- **Read-only investigator agents are Phases 1–3 by construction.** They cannot
  reach Phase 4, so the law costs them nothing; what they owe is the *diagnosis
  report*, with risk labels and a confirmed root cause, not a fix.

Same failure shape as the delegated-measurement contract, whose cause is
**measured**: under-determined specs produced **5 of 9 wrong numbers** in one
session, because **agents fill gaps silently rather than halting**. Pair this with
[[concepts/location-not-magnitude]] (*ship the pointer, never the number* — what
to trust coming back) and [[concepts/session-identity-is-not-stable]] (rule 19 —
the orchestrator's own numbers decay too).

## The carve-out — TEMPORARY, ACTIVE 2026-08-16, NOT STANDING LAW

> [!warning] **STATUS: TEMPORARY. This is a live suspension, and it EXPIRES rather than accrues.**
> Declared 2026-08-16; the operator's follow-up the same day was **"just
> temporary"**. **The default state is the full Iron Law above.** A later session
> **must NOT cite this section as settled practice.** If it is load-bearing for
> what you are about to do, **re-confirm it with the operator first** — an
> unre-confirmed carve-out is expired, not inherited.

**What is exempted:** optimizations are exempt from **the phase gate**. Operator's
words, verbatim: *"ignore for optimizations but do not assume or cheat the code"*,
then *"just temporary"*.

**What is exempted is CEREMONY. Rigor is never suspended.** Three obligations
bind absolutely under the carve-out:

1. **READ THE MODULE FIRST.** No guessed APIs, no assumed signatures, no invented
   attributes. **Specimen:** ~3,400 tests went green over a **fabricated object**
   because the sizer read an attribute `PortfolioState` does not have and the test
   doubles supplied it — three risk controls inert, every test passing
   ([[concepts/false-green]] §the sixth way; [[concepts/test-double-fidelity]]).
   An optimization is exactly the kind of change whose author believes they
   already know the interface.
2. **MEASURE, DO NOT INFER.** An optimization's claim **IS** its before/after
   number; without one it has claimed nothing. **Precedent already in this
   corpus:** parallelizing the Kraken book fetches **measured ZERO gain and was
   reverted** — the rate limit was the wall, so the lever was cutting call
   **COUNT**, not concurrency. An optimization that skipped the measurement would
   have shipped a change that bought nothing. This is
   [[concepts/tautological-instrument]]'s standing method: *static inference about
   what a system does is nearly always vacuous; ask the running system.*
3. **NO SILENT BEHAVIOR CHANGES**, no cheating the code to move a number, and the
   **DoD matrix still runs**. A faster wrong answer is not an optimization.

**The shape, and why it is safe to state as a rule:**

> **Speed is licensed; assumption is not.**

That is the same shape as [[concepts/never-widen-a-gate]]'s hard-won boundary —
*a gate may be DISCONNECTED from a verdict it was never evidence for, but never
WIDENED.* Both permit a **structural** relaxation (skip the phases / detach the
verdict) while forbidding the **epistemic** one (assume the interface / loosen the
threshold). In both cases the relaxation is only legitimate because the thing that
actually protects the system — the measurement — is untouched. And in both cases
the danger is identical: **the relaxation is the part that gets remembered, and
the condition is the part that gets dropped.** Hence the expiry stamp at the top
of this section rather than a footnote at the bottom.

## Why this is a separate page from the Iron Law of Debugging

[[concepts/iron-law-of-debugging]] — *no fix may be chosen until the mechanism is
named* — governs the **content** of a diagnosis. This page governs its
**procedure**. They compose exactly:

- The debugging law says a Phase-3 diagnosis is not finished until the mechanism
  is **named**, not merely plausible.
- The repair law says you may not act on it until Phases 1–2 have shown you
  **what else touches the thing you are about to change**.

Both were learned the same way: the debugging law from four hours spent on an
unnamed mechanism, the repair law from delegation producing 5 of 9 wrong numbers
against under-determined specs.

## Related

- [[synthesis/governance-doctrine]] — rule 20 (this page is its substance)
- [[concepts/iron-law-of-debugging]] — the content half of the same discipline
- [[concepts/location-not-magnitude]] — what a delegated agent is reliable for
- [[concepts/session-identity-is-not-stable]] — rule 19; a protocol carried in
  session memory is recall, not law
- [[concepts/never-widen-a-gate]] — *speed is licensed, assumption is not* is the
  same shape as *disconnected but never widened*
- [[concepts/false-green]] · [[concepts/test-double-fidelity]] — the fabricated-object
  specimen the carve-out's rule 1 exists to prevent
- [[concepts/tautological-instrument]] — *ask the running system*, the method
  behind the carve-out's rule 2
- [[concepts/no-orphan-claims]] — rule 18; a temporary status filed as standing
  law is precisely the stale-page failure it forbids
- [[sources/session-20260811-16-vscode-3b307393]] — §5, the originating directive
- [[sources/session-20260816-catchup-08-12-to-08-16]] — the amendment that marked
  the carve-out temporary
- Skill: `C:\Users\haird\.claude\skills\focused-fix\SKILL.md` (318 lines, read 2026-08-16)

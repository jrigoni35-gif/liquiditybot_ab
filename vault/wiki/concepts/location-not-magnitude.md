---
title: Location, Not Magnitude (what delegated agents are reliable for)
category: concept
summary: "Measured across three fan-outs on 2026-08-15 (59 agents, ~6.0M subagent tokens): every file:line POINTER a delegated agent produced verified, while most headline NUMBERS failed re-derivation. Ship an agent's pointer, never its number — the orchestrator re-derives anything a conclusion rests on. Two companion measurements: adversarial refuters killed under 1% of candidates (2 of 232, 3 of 507) while the finders' own ship-criteria killed 99%+, so strictness belongs in the finder prompt and not primarily in the reviewer; and kill RATE is the quality signal, not survivor count. The response is a red-team panel that assigns positions to argue rather than asking for review, because agreement is the cheap default. Extended 2026-08-16 by the delegation-discipline directive: subagents do NOT inherit the parent skills, so an editing agent gets the focused-fix 5-phase protocol embedded BY PATH — an unstated protocol is an absent protocol — with optimizations exempt from the phase gate but not from rigor (measure, never infer)"
tags: [method, delegation, agents, verification, epistemics, workflow]
sources: 2
updated: 2026-08-16
---

# Location, Not Magnitude

**The rule:** a delegated agent is reliable for **where** to look and unreliable
for **what the number is**. Ship its pointer; re-derive its arithmetic.

## The measurement

Three read-only audit fan-outs against this repo on 2026-08-15 — **59 agents,
~5,995,538 subagent tokens** (`wf_59ca8ba8-61a` war room, `wf_fe4ccad9-568`
preventive-maintenance scan, `wf_5d7517a2-305` defect-class scan).

**Every pointer verified:**

- `gate_efficacy_report.py:105` really does bin on disposition and never read
  `label_era` — 0 occurrences of the string in the file.
- `core/session_digest.py:139` really did construct an `AuditTrail` (a writer)
  against the live hash-chained trail.
- `tests/test_no_console_popups.py:81` really does match its own comment banner.

**Most headline numbers did not:**

| agent claim | re-derivation |
|---|---|
| fee-free gross negative on both statistics over 414 positions | entry-only is **positive** on both; medians reproduce (−0.0293 vs −0.0295), means do not (+0.0042 vs −0.0186) |
| era-matched `exit_sim` = 30.89% vs 15.06% = −15.83pp | **−1.57pp** (12.55% vs 14.12%); the direction survived on a *different* era, `triple_barrier` −18.71pp |
| baseline uniqueness 0.054, n_eff 112.1, ×4.29 | different population — whole corpus is 0.0154 / 162.2 / **×8.07** |

This is **not a criticism of the agents**. Locating a defect in a large tree is
the expensive part; arithmetic over a live CSV is the cheap part, and the cheap
part belongs where it can be checked. The failure mode is the orchestrator
*forwarding* a number rather than recomputing it — which is
[[concepts/adversarial-verification]] applied to one's own delegation, and the
delegated form of *re-derive, don't recall*.

## Companion measurement 1 — adversarial verification killed under 1%

| scan | candidates | killed by the **finders** | killed by the **refuters** |
|---|---:|---:|---:|
| preventive maintenance | 232 | 215 | **2** (0.9%) |
| defect-class recurrence | 507 | 494 | **3** (0.6%) |

Standard multi-agent practice treats the adversarial reviewer as *the* quality
mechanism. Measured here it is not — the strictness lived in the finder's
ship-criteria, which made shipping expensive:

> A finding ships only with ALL of: exact `file:line` YOU READ; what the code
> DOES that is wrong; a CONCRETE failure scenario; and why an existing
> guard/test does not already cover it. Report `candidates_killed` — a high
> kill count is evidence of strictness.

**Two effects cannot be separated from this data**, and the page says so rather
than overclaiming: refuters still corrected severity and `fix_class` on
survivors — where a mislabelled SAFE would have escaped adjudication — and the
finders may have been strict *because* a refuter was known to follow. What is
measured is the kill count. What follows is a budget shift toward ship-criteria,
**not** a case for removing refuters.

## Companion measurement 2 — kill rate is the quality signal

93.5% and 98.0%. The output that mattered was mostly **what was eliminated**:
217 and 497 candidate defects a lazier pass would have reported, with the triage
cost landing on the reader. **A scan returning 200 findings has not found 200
defects.** Require the kill count in the schema so strictness is observable
rather than hoped for.

Cost to budget against: **~180k tokens per CONFIRMED finding** (176k and 197k
measured) — not per agent.

## Why a panel, and why it assigns positions

The same session's author shipped **four** instances of defect classes he had
personally catalogued hours earlier: test pins matching their own comments, a
falsifier that could not arm, a fixture on the wrong median convention, and a
duplicated string predicate. Each was caught by the next layer down; **none by
the author at the time of writing**.

So the response is not "review harder". Agreement is the cheap default, and a
reviewer *permitted* to agree generally will. `.claude/workflows/red-team-panel.js`
makes it structurally unavailable:

1. **Mandated positions, not opinions** — each lens prosecutes an assigned
   thesis ("the numbers are wrong", "this should not exist", "this will decay").
2. **Cross-examination by a different lens** — every objection is `ESCALATE`d,
   `UPHOLD`ed or `WITHDRAW`n by someone who did not raise it, which kills
   rubber-stamping *and* pile-on. **A high withdrawal count is healthy.**
3. **A docket, not a verdict** — approval language is forbidden; the author
   answers each objection `CONCEDE / CONTEST / DEFER`, and a contest requires
   evidence.
4. **Concession rate is the health metric** — 0% means theatre, 100% means the
   author stopped thinking.

Each lens is grounded in a defect this repo shipped, because generic personas
produce generic objections — which is precisely how "looks good" survives a
review process.

## The protocol does not travel — an unstated protocol is an absent protocol (2026-08-16)

**Operator directive, 2026-08-16.** Binding as [[synthesis/governance-doctrine]]
rule 20; measured session [[sources/session-20260811-16-vscode-3b307393]] §5.

The page above says what a delegated agent is *reliable for*. This says what a
delegated agent **does not arrive with**:

> **Subagents do not inherit the parent's skills.** A protocol the orchestrator
> is following is invisible to the agent it dispatches.

So every delegated agent that **may EDIT anything** gets the focused-fix
five-phase protocol embedded **BY PATH** in its prompt —
`C:\Users\haird\.claude\skills\focused-fix\SKILL.md` — with its phases
(**SCOPE → TRACE → DIAGNOSE → FIX → VERIFY**), its IRON LAW (*no fixes without
completing scope/trace/diagnose first*), and its escalation trigger (**3+
cascading fixes**).

This is the **same failure shape** as the delegated-measurement contract, whose
measured cause is on record: under-determined specs produced **5 of 9 wrong
numbers** in one session, because **agents fill gaps silently rather than
halting**. Pair the two rules — *ship the pointer, not the number* is what to
trust on the way back; *paste the protocol* is what to send on the way out.

> [!warning] **Operator carve-out — TEMPORARY, ACTIVE 2026-08-16, not standing law.**
> **AMENDED 2026-08-16** (same session as the filing): the operator has since called this
> carve-out **"just temporary"**. **The default is the full Iron Law**; this suspension
> **expires rather than accrues** and must be **re-confirmed with the operator** before any
> later session leans on it. Full text, expiry rule, and the law itself:
> **[[concepts/iron-law-of-repair]]**.

**OPTIMIZATIONS are exempt from the phase gate, and NOT from rigor.** Read the
module first (no guessed APIs) · **measure rather than infer** · no silent behavior changes ·
no cheating the code to move a number · the DoD matrix still runs. The precedent the directive
names is this repo's own: **parallelizing the book fetches measured ZERO gain and was
reverted — the rate limit was the wall.** An optimization that skipped the
measurement would have shipped a change that bought nothing, which is the exact
error the exemption is *not* granting.

## Scope limit, stated on its face

One codebase, one session, three runs, **all read-only audit work**. It says
nothing about generative fan-outs, and the finder-vs-refuter split may invert
where the task is to write rather than to investigate. Treat the
under-1% refuter result as strongest-evidence-available, not settled.

## Related

- [[concepts/adversarial-verification]] — the practice this qualifies
- [[concepts/false-green]] — what an unfireable check looks like
- [[concepts/no-orphan-claims]] — governance rule 18; obligation (b) is the same law applied to the wiki
- [[concepts/session-identity-is-not-stable]] — rule 19; the orchestrator's OWN numbers decay too
- [[concepts/iron-law-of-repair]] — rule 20's substance: the five phases, the 3-strike escalation, and the TEMPORARY optimization carve-out
- [[sources/session-20260815-scans-and-corrections]] — the run this is measured on
- [[sources/session-20260811-16-vscode-3b307393]] — §5, the delegation-discipline directive (rule 20)
- Repo: `docs/quant/2026-08-15_agent_workflow_doctrine.md`, `.claude/workflows/red-team-panel.js`

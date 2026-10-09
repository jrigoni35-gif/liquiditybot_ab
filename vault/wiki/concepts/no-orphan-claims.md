---
title: No Orphan Claims (consult, reference back, or go find one)
category: concept
summary: "Operator directive 2026-08-14, governance rule 18: the wiki is not where knowledge is stored, it is where knowledge is kept TRUE. Three obligations in order — consult the wiki before deriving; when the wiki is silent, walk to the primary artifact it cites and answer from THAT rather than from recall; and when no reference exists at all, FIND one. 'No citation available' is a task, not a disposition — an unsourced claim converts into an owed measurement, a graded literature pass, or a measurement run now, and never into a fact. Currency is part of correctness: a page a measurement contradicts gets its callout the same session, because everything here is read as settled"
tags: [governance, epistemics, sourcing, doctrine, recall]
sources: 2
updated: 2026-08-16
---

# No Orphan Claims

**Operator directive, 2026-08-14. Binding as [[synthesis/governance-doctrine]]
rule 18.** Schema copies in the vault's `CLAUDE.md` / `AGENTS.md` domain rule 10.

> The wiki is not a place knowledge is **stored**. It is the place knowledge is
> **kept true**.

Storage is passive and degrades silently. This corpus has repeatedly shown what
that costs: a claim written down once is thereafter believed *because it is
written down* ([[synthesis/documentation-drift-register]]), and a stale page is
not a neutral artifact — it is an active source of false confidence, precisely
because everything filed here is read as settled.

## The three obligations, in order

### (a) Consult first

Read `wiki/index.md` **before** deriving anything — not afterwards to check an
answer already formed. Recall-before-derive is cheaper than re-derivation and
it is the only reason the corpus compounds instead of being rebuilt each
session.

**Measured cost of skipping it:** a 1.12M-token architecture fan-out
re-derived a taxonomy this vault already held. The spend was not the error; the
*order* was.

### (b) When the wiki does not know — reference back

Do **not** answer from the model's own recall, and do **not** file that answer.
Walk to the primary artifact the relevant page cites — `raw/`, a commit, a
`file:line`, a ledger, a measurement — and answer from **that**, citing what
you walked to.

**A page that is silent on a question is not evidence of absence.** It is an
instruction to go one level down.

This obligation runs against the vault's own content too, which is its sharpest
edge: **recall-before-derive must never become reuse of a cached conclusion as
evidence.** Thrift and verification trade against each other permanently. The
mitigation is not to abandon recall — it is to **re-derive any number that is
load-bearing in the current turn**, including one this vault states, and
including one you yourself stated earlier in the same session.

> **Type specimen (2026-08-14, this directive's own session).** A session
> reported that owed item 67's ALGO-5 trigger had fired "6x over" at 182
> uncensored paths. It had not: item 67's measure is the ALGO-4 ledger
> (`outputs/trade_paths.csv`, **10 rows** against ~30), while the 182 were
> `signal_history` **barrier resolutions** — a different population whose name
> also reduces to "paths". The error was caught only because the ingest
> checklist forced the owed page open to edit it. **Obligation (b) is what the
> checklist was mechanically enforcing.**

> **The mechanism behind (b), measured 2026-08-16.** Until now, "recall decays"
> was an assertion about model behavior. It has a **carrier-level cause**: a
> Claude session is a *process*, and a single VS Code session ran for **four
> calendar days** with its in-context "now" frozen at 2026-08-12 while disk
> reached 2026-08-16 and **33 commits** from other sessions landed unseen. A
> conclusion held inside such a session is not a stale memory — it is a correct
> statement **about a world that no longer exists**, complete with intact
> citation formatting. That is failure mode 2 below, reached by a road the model
> cannot detect from the inside. **Hence: re-derive against disk, and record a
> session identity plus a wall-clock date on every filed claim** —
> [[concepts/session-identity-is-not-stable]],
> [[synthesis/governance-doctrine]] rule 19,
> [[sources/session-20260811-16-vscode-3b307393]].
>
> The same session supplied **three self-corrections at filing**, all of them
> obligation (b) firing: "25 commits" (re-derived **33** all / **24**
> first-parent), "contamination outlived the fix by ~21 h" (re-derived
> **24.74 h**), and "the journal showed 4 started and 0 result" (re-derived
> **8 started, 4 result** — four agents with no completion record).

### (c) When no reference exists — find one

> **"No citation available" is a task, not a disposition.**

An unsourced claim is **not filed and not acted on**. It converts into exactly
one of three things, and never into a fact:

| conversion | goes to |
|---|---|
| a measurement that would settle it | [[synthesis/owed-measurements]], with what would close it |
| a literature question | a graded pass on [[concepts/evidence-grading-ladder]] |
| something answerable from the repo now | run the measurement **this session** |

The third option is the one most often skipped and usually the cheapest. Much
of what this corpus treated as unknowable was a `grep` and an arithmetic
identity away — the money-path decomposition and the label-geometry breakeven
both turned out to be computable from artifacts already on disk.

## Currency is part of correctness

A page contradicted by a measurement gets its callout **in the same session
that measured it**, on **both** sides (domain rule 6,
[[synthesis/open-contradictions-register]]). Deferring the correction is not a
smaller version of making it — between the measurement and the edit, the page
is actively wrong and is being read as settled.

This is the same discipline as *file confirmed findings same-session*
(rule 12 / domain rule 8), applied to the negative case: **filing what is newly
true and un-filing what is newly false are the same obligation.**

## Why the order matters

The three run in sequence because each failure mode is downstream of the last:

1. Skip **(a)** → pay to re-derive what you own.
2. Do (a), skip **(b)** → answer from recall, and file a plausible claim with a
   wikilink that makes it *look* sourced. This is the most dangerous outcome,
   because the citation formatting survives while the citation does not.
3. Do (a) and (b), skip **(c)** → the honest dead end: *"cannot be
   established."* Which is where the corpus stalls, and why (c) exists —
   an unnamed needle returns "cannot be established" while every named needle
   is found ([[concepts/honest-null-result]] is the *legitimate* version, and
   requires the exact data requirement stated).

## Related

- [[synthesis/governance-doctrine]] — rule 18; the rules that decide what may change
- [[concepts/evidence-grading-ladder]] — how a found reference gets graded
- [[synthesis/owed-measurements]] — where an unanswerable question is parked with its closing condition
- [[synthesis/documentation-drift-register]] — what happens when currency lapses
- [[concepts/unfalsifiable-explanation]] — the claim that cannot be wrong is the claim with no reference to check
- [[concepts/session-identity-is-not-stable]] — rule 19; the measured mechanism behind obligation (b)
- [[concepts/honest-null-result]] · [[concepts/adversarial-verification]] · [[synthesis/evidence-closed-register]]

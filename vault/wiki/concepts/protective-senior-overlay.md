---
title: Protective Senior Overlay
category: concept
summary: An exit class that is senior to any bracket or schedule and always allowed to fire, because blocks stop new risk and never escapes — applied under incident pressure 2026-08-07, when all three hedge churn guards were placed on the OPEN side and unwinds stayed ungated
tags: [exits, risk, invariants]
sources: 3
updated: 2026-08-07
---

# Protective Senior Overlay

## Definition
An exit whose purpose is **loss avoidance** rather than profit-taking, granted seniority over bracket
deadlines and scheduled exits. Members: the no-progress time stop, the give-back ratchet, and the hard
stop.

## The governing invariant
> "Exits are ALWAYS allowed — disarm, faults, and kill switches block new risk, never escapes."

## The incident that forced the classification
A bracket redesign suppressed **both** the scheduled profit-take **and** the no-progress time stop for
bracket positions, handing the time dimension to the bracket deadline. But the time stop fires at bar
36 while the deadline sits at bar 96 — a **60-bar unprotected wedge**. One position realized **-1.69%
against an expected -0.08%**, where the suppressed scratch would have taken **~-0.2%**. Because probes
are essentially all model-lane flow, this disabled no-progress protection **fleet-wide**; fake-out
entries pay **8-20x the intended scratch cost**.

## The fix
Suppression narrowed to cover **only** the scheduled profit-take. The time stop is reclassified as a
protective senior overlay in the same class as the ratchet and hard stop.

## The accepted divergence
A senior overlay closing a position means **the traded bet carries protections the label does not
model**. This is a conscious label/trade divergence, the same one the give-back ratchet and chandelier
already had. It is also, later, exactly what produces the [[concepts/clock-inversion]] — so the
divergence is real and has a cost.

## The invariant applied under incident pressure (2026-08-07)
The hedge-churn guards (`cf454d5e`, [[sources/session-20260807-hedge-churn-guards]]) are the
invariant exercised in the hardest direction: fixing a loop in which the **unwind itself was a
symptom**, every guard still went on the **open side only** — warmup evidence gate, per-asset
re-hedge cooldown, and the FW-070 churn latch all block **re-opening**; the unwind path is never
consulted and may always fire (once — idempotent). The operator's deadlock discipline generalizes
the invariant into design rules for any latch ([[concepts/deadlock-discipline]] rule 1: *"new
risk requires evidence; exits never do — the $318 came from RE-OPENING, not from closing"*). The
temptation the discipline rejected — "cold estimator → hold the unwind" — would have traded a
churn for a frozen position, i.e. broken this page's invariant to protect a fee bill.

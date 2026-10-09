---
title: The Dead-Mute Trap
category: concept
summary: A zeroed weight removes a detector from the recorded set, so it can never accrue the grades needed to recover
tags: [feedback, defect-class, thales]
sources: 1
updated: 2026-08-01
---

# The Dead-Mute Trap

## Definition
A self-regulating weight that **also gates recording**. Once the weight reaches zero, the component is
no longer written into the record that the weight is computed from — so no new evidence can ever arrive
and the zero is permanent.

## The mechanism
The gate `if w > 0` decides whether a detector is appended to the fired set. The fired set is what
`note_outcome` grades. Weight zero -> not fired -> not graded -> weight stays zero. **An absorbing
state.**

## Why it is easy to miss
Each half is reasonable in isolation: muting a useless detector avoids ledger churn, and grading only
what actually influenced a trade is correct. The trap is in the composition.

## The fix
A **probation** path: a muted detector continues to be recorded (and graded) even while contributing
zero influence, so it can earn its way back.

## The general pattern
Any feedback loop where **the output gates the input** needs an explicit escape. Compare
[[concepts/probe-livelock]] (throttling suppresses the very flow that would relax the throttle) and
[[concepts/deploy-deadlock]] (a reject never clears the flag that triggers the retry). All three are the
same shape: **a self-reinforcing absorbing state created by composing two individually-correct rules.**

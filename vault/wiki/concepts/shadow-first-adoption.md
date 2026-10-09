---
title: Shadow-First Adoption
category: concept
summary: Every new mechanism defaults to non-influencing, collecting evidence before it is permitted to affect a decision
tags: [governance, thales, promotion]
sources: 4
updated: 2026-08-01
---

# Shadow-First Adoption

## Definition
A new mechanism ships **running but non-influencing**. It computes, logs, and accumulates hit-rate
telemetry while contributing exactly zero to any decision. Promotion to influence is a separate,
evidence-gated, human decision.

> **"Enabling detectors is not enabling influence."**

## The ladder
**shadow** (default) -> **advise** (bounded, clamped shading) -> future rungs (sizer coupling,
exit-timing coupling, learned weights — explicitly out of scope).

**Each promotion requires**: shadow hit-rate beats null, the overfit battery green, and the quant-trial
gates green. Promotion is **decided by a human**, driven by evidence, and **gated on evidence joined to
trade outcomes, not on firing frequency**.

## The chicken-and-egg it created
The vindication ledger only learned in advise mode, while promotion to advise required shadow evidence
— so **the reliability layer had never engaged and could not**. Every shade event ever recorded was a
"would-shade" with zero applied. The fix was to unlock shadow grading so the ledger accrues evidence in
both modes.

## The design cost this reveals
Shadow-first is not free: a mechanism can sit inert for its entire life while everyone assumes it is
working. The audit question that catches this is **"is it earning its keep?"** — does it measurably
reach a decision and improve an outcome? See [[sources/thales-unit-audit]].

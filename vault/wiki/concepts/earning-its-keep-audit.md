---
title: Earning-Its-Keep Audit
category: concept
summary: Asking whether a shipped layer measurably reaches decisions and improves outcomes, rather than whether it works as specified
tags: [audit, method, quality]
sources: 2
updated: 2026-08-01
---

# Earning-Its-Keep Audit

## The question
Not "is this correct?" but **"does this measurably reach a decision, and does it improve the outcome?"**

## What it found on a mature subsystem
- The engine **does not reach sizing at all** — every shade event ever recorded was a "would-shade",
  zero applied.
- The reliability layer had **never engaged and could not**, by construction.
- One mechanism was gated off and **enabling it would be a provable no-op**: the trim requires a
  confidence band that **no observed row has ever entered** (would-trim set n = 0). Hence the explicit
  warning: **"do not enable it 'to do something' — it will do nothing."**
- A detector with 43% of rows scoring above its threshold showed **zero discrimination** on realized
  outcomes (mean PnL -$0.164 vs -$0.166; win% 17.5 vs 14.7).
- **No dose-response**: high-signal entries did not lose more; the mid band was worst.

## Why this class of finding is invisible to normal testing
Every one of these components passed its unit tests. They compute what they are specified to compute.
The defect is at the level of **wiring, thresholds versus realized distributions, and effect size** —
questions no unit test asks.

## The three checks that generalize
1. **Reach** — trace the value from computation to the decision that consumes it. Is there a live path?
2. **Range** — compare the threshold against the *observed distribution*, not against intuition.
3. **Effect** — join the signal to realized outcomes and look for dose-response.

## Related
[[concepts/adversarial-verification]] catches correct-but-inert fixes; this catches
correct-but-inconsequential subsystems.

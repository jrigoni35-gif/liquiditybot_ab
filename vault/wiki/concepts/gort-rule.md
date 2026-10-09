---
title: The Gort Rule (PBO Admission Policy)
category: concept
summary: Binding four-part policy: no policy-class challenger becomes champion-swap eligible until measured inside CSCV under the deployed selection rule
tags: [policy, binding, pbo, admission]
sources: 2
updated: 2026-08-01
---

# The Gort Rule (PBO Admission Policy)

**Status: BINDING.** Defined in [[sources/pbo-admission-policy]].

## The four rules
1. **CSCV entry gates champion-swap eligibility.** Any policy-class challenger enters OF-3's CSCV as a
   measured config BEFORE it may be considered for a champion swap. "Shipping the code path disabled is
   not, by itself, admission."
2. **Every space expansion is a conscious re-baseline**, investigated with the
   [[concepts/inertness-protocol]].
3. **The deployed [[concepts/simplicity-ladder]] rule is the only selection read** — never argmax. "A
   challenger that would win on argmax but isn't what the deployed rule would have picked is not
   evidence for anything; it is exactly the overfitting CSCV exists to catch."
4. **[[concepts/evidence-floors]] gate family admission ahead of any PBO reading** — checked FIRST,
   because "a family fit on too few real closed-trade labels only manufactures a lucky winner, which
   inflates PBO for no real reason."

## Policy-class challenger
Any of: a new model family, a **schema variant** (column subset/superset), a **row-inclusion variant**
(which rows train), or a **constraint variant** (monotone or other structural constraint).

## Ladder rung vs experiment axis
Rungs are production selection paths; schema/epoch arms are **report-only measurement axes inside
CSCV**, never a production selection path.

## Also binding under this policy
- The [[concepts/coverage-floor]] on feature pruning.
- The **consumer-consistency prerequisite**: every training-corpus consumer must see the same filtered
  view as the production loader before any filter flips on, because "PBO must measure the rule the
  system actually runs."

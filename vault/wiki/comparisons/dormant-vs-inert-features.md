---
title: Dormant vs Inert Features
category: comparison
summary: Two populations inside the always-dead set that demand opposite treatment
tags: [comparison, features, pruning]
sources: 3
updated: 2026-08-01
---

# Dormant vs Inert Features

Both appear in the always-dead set. Only one is prune-eligible.

| | Dormant / coverage-starved | Inert |
|---|---|---|
| Why it is dead | **lack of exposure** — the phenomenon has not occurred | real variance, well covered, **zero measured DoF** |
| Coverage | near-zero nonzero fraction | high nonzero fraction, many distinct values |
| Verdict | **never prune-eligible** | legitimate prune candidate |
| Interpretation | **capability held in reserve** | capability proven useless |

## The load-bearing example
Two manipulation detectors sit at 1.34% and 1.49% nonzero. They are dormant, not useless —
**"pruning them would permanently blind the anti-predation layer at exactly the moment manipulation
begins to fire."**

## Why there is deliberately no numeric threshold
One feature cleared at **5.45%** nonzero while another failed at **1.49%**. The distinction is about
*why* the column is empty, which no single statistic captures. Because the floor is only ever used to
**block** a prune, ambiguity errs safe — but every application must carry a **written, named
justification**.

## The demonstration that the distinction is real
Pruning the raw always-dead list (8 features) **wins** under the deployed selection rule; pruning only
the policy-cleared subset (5 features) **loses badly**. The winning read is disqualified because the win
is **mechanical**: dropping nearly-all-zero columns lowers effective degrees of freedom, improving the
selection-bias metric "almost by construction." **The divergence is the evidence that the floor is
binding.**

## The unresolved case
One feature has 79% coverage but a near-constant standard deviation — classified **scale-suspect**,
neither dormant nor clearly inert, pending resolution.

## Related
[[concepts/coverage-floor]] · [[concepts/dof-budget]] · [[sources/phase3-adjudication]]

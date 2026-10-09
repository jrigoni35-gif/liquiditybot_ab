---
title: Defect-Category Audit
category: concept
summary: Grading code sites against canonical peer-reviewed anchors per defect class, with CONFORMS, ACTIONABLE, or KNOWN-DEVIATION verdicts
tags: [audit, method, literature]
sources: 3
updated: 2026-08-01
---

# Defect-Category Audit

## Method
Enumerate **defect classes** (not modules), attach a canonical peer-reviewed anchor to each, then grade
specific code sites against it:
- **CONFORMS** — matches the canonical treatment
- **ACTIONABLE** — a real defect, with the size of the error quantified
- **KNOWN-DEVIATION** — a conscious departure, bounded and documented

## The classes covered
Numerical stability · data leakage · survivorship and selection · ratio-aggregation bias ·
missing-data conventions · point-in-time and off-by-one-bar · quantization and serialization.
A companion pass graded eight **estimator formulas** the same way.

## Why the framing works
It finds defects that are **arithmetically correct and semantically wrong** — code that runs, passes
tests, and returns a plausible number computed against the wrong null, in the wrong domain, or at the
wrong weighting. Testing cannot find these; only re-derivation against a canonical source can.

## The operating-point discipline
Every verdict is stated **at the system's actual operating point** (bar size, volatility, horizon,
sample size), not in general. This is what makes several CONFORMS verdicts honest — for example an
approximation that conforms at a 2-hour horizon with an explicit **BOUNDARY**: do not extend it
multi-day without a direct check.

## Two exemplary non-fixes
- A missing-data indicator column was judged **"not earned at 253 live rows"**; a liveness diagnostic
  shipped instead as the promotion trigger.
- A canonical sampling refinement was deliberately skipped as second-order at this scale — and the
  omission **documented in-code**.

## Citation hygiene as part of the deliverable
Live-verified versus canonical-from-knowledge citations are split explicitly, unverifiable ones are
flagged, and an incorrect author attribution in the tasking itself was corrected in the report.

## Related
[[concepts/variance-domain-averaging]] · [[concepts/ratio-aggregation-bias]] ·
[[concepts/adversarial-verification]] · [[sources/defect-categories-audit]] ·
[[sources/literature-estimator-audit]]

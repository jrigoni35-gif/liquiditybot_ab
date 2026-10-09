---
title: The DEFER Verdict
category: concept
summary: A measured, informative non-adoption — distinct from a failure and from a negative result being hidden
tags: [governance, adjudication, discipline]
sources: 3
updated: 2026-08-01
---

# The DEFER Verdict

## Definition
An experiment is run to completion, measured against the binding standard, and **not adopted** — with
the measurement recorded. DEFER is a first-class outcome, not a euphemism for failure.

> "A DEFER verdict is a successful, informative outcome of this measurement exercise — not a failure of
> it; nothing here was stretched to manufacture an ADOPT."

## The separation it enforces
**Measurement is separated from adoption by a mandatory separate operator sign-off commit.** Shipping a
code path disabled is the *prerequisite* for admission, never admission itself.

## How deferral matured
1. **Ad hoc reaction** — one gate failure triggers a revert, with the diff preserved verbatim "so
   re-running the experiment is a paste away."
2. **Operating posture** — "no lever moves before it resolves"; six explicit KEEP decisions.
3. **Designed mode** — instruments ship **inert by construction**, and their inertness is *proven*
   (md5-identical verdict lines, per-family retrain comparisons) rather than asserted.

## The companion honesty rule
When an experiment "wins" under a reading the binding policy disqualifies, that is recorded as a
disqualified reading, not quietly promoted. See [[concepts/coverage-floor]] for the worked case.

## Related
- [[concepts/never-widen-a-gate]] · [[concepts/shadow-first-adoption]] · [[concepts/honest-null-result]]

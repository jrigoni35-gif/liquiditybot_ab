---
title: Inertness Protocol
category: concept
summary: Prove a metric shift is corpus-driven rather than code-driven by running the prior baseline commit against the current corpus in a scratch worktree
tags: [method, overfit, verification]
sources: 3
updated: 2026-08-01
---

# Inertness Protocol

## Definition
Before re-baselining any overfit or selection metric, check out the **prior baseline commit** into a
scratch worktree and run it against the **CURRENT corpus**. If the result is identical, the shift is
**corpus-driven, not code-driven**, and the new baseline may be consciously recorded.

## Why it exists
The overfit battery flips passed/failed counts constantly as the corpus grows. Without this protocol
there is no way to distinguish "our change broke something" from "the data moved," and the temptation
is to attribute every flip to the most recent diff — which in this corpus was repeatedly cosmetic
(a CSS string, two row titles, dashboard label decode).

## Escalating standards of proof
1. Identical failure (same metric, same winner, same split grid)
2. Identical numbers across all checks
3. **md5-identical per-check verdict lines** — the strongest form used, e.g. hash
   `f68296e3775e3787f3c473c461563a92` on both sides across all eight checks

## Status
Codified as **rule 2** of the [[concepts/gort-rule]]: every space expansion is a conscious re-baseline,
and the resulting shift is investigated with this protocol and documented — "never silently absorbed
into 'PBO is what it is this week'."

## Established in
[[sources/of3-pbo-data-shift]], which applies it at all eight baseline crossings.

## Related
- [[concepts/conscious-re-baseline]]
- [[concepts/never-widen-a-gate]]

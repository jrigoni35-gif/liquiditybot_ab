---
title: OF-3 / PBO Data Shift Watch Doc (2026-07-24 to 07-28)
category: source
summary: Living log proving every overfit-battery baseline flip is corpus-driven not code-driven, via a repeatable inertness experiment
tags: [pbo, overfit, inertness, re-baseline, living-doc]
sources: 1
updated: 2026-08-01
---

# OF-3 / PBO Data Shift Watch Doc (2026-07-24 to 07-28)

**Raw source:** `raw/quant/2026-07-24_of3_pbo_data_shift.md`

## What this document is
A **living watch doc** appended through 2026-07-28 with eight successive baseline entries. Its
purpose is to prove that every OF-3 / overfit-battery flip is **corpus-driven, not code-driven**,
using the [[concepts/inertness-protocol]].

## The initial breach
2026-07-24: OF-3 flipped to FAIL with `pbo=0.56` over 7 configs / 70 splits on the DEPLOYED
[[concepts/simplicity-ladder]] selection, at 3,651 corpus rows. Prior baseline was 4 passed / 4
failed. New baseline 3 passed / 5 failed.

**Inertness proof**: commit `060b217` (last green baseline) checked out into a scratch worktree and
run against the CURRENT corpus produced the IDENTICAL failure — same pbo, same winner, same split
grid. The shift is entirely the +23 rows merged at session start.

## The crossing series (8 entries)
| # | Date | Rows | Result | pbo |
|---|---|---|---|---|
| 1 | 07-24 | 3,651 | 3/5 | 0.56 |
| 2 | 07-24 | 3,910 | 4/4 | — |
| 3 | 07-24 pm | 4,049 | 5/3 | — |
| 4 | 07-25 am | 4,301 | 3/5 | 0.53 |
| 5 | 07-25 mid | 4,407 | 5/3 | — |
| 6 | 07-25 pm | 4,633 | 4/4 | — |
| 7 | 07-26 | 4,692 | 5/3 | 0.07 |
| 8 | 07-26 | 4,642 | 4/4 | 0.23 |
| — | 07-28 | 4,907 | 5/3 | **0.03** (healthiest recorded) |

Triggering diffs were repeatedly cosmetic — "a CSS string + two row titles", dashboard code-label
decode only — which is exactly what makes the inertness proof load-bearing.

## Escalating rigour
The inertness experiment hardens over time: identical result -> identical numbers -> **md5-identical
per-check verdict lines** (`f68296e3775e3787f3c473c461563a92`).

## Two demotions of naive metrics
- **Row count is not a monotone clock** — survivors fell 4,692 -> 4,642 while the raw file grew to
  4,722, because clash-dedup absorbed more duplicate pairs. "Read it with the dedup stats."
- **Single-point `dead_frac` is a noisy estimator** — at one seed the reading was 0.60 (gate 0.55),
  but across 3 seeds x 3 n_splits only 13 features are unanimously dead and only 5 clear the
  [[concepts/coverage-floor]]. "Do not tune the gate to it."

## The eighth transition — end of the series
The 2026-07-28 import pushed `triple_barrier` rows past 150, so [[concepts/era-exclusion]] armed and
ACTIVATED. This is explicitly **"not a crossing within the old series — it is the end of that
series"**: all seven prior crossings measured a mixed-era population that no longer exists. New
baseline on 661 clean rows: 3 passed / 4 failed, with rows/feature 10.7 "just above the 10 floor —
the corpus only barely qualifies to be measured at all."

## Standing rules
- Re-baseline consciously at every crossing; **never widen a gate**. "Shrink the space, never the gate."
- Treat any single-check flip inside the {3,4,5}-passed band as documented oscillation unless the
  inertness experiment says otherwise.
- Watch condition: if PBO still straddles 0.5 once live labels resume and reach +100 (340 total),
  shrink the 7-config ladder breadth.

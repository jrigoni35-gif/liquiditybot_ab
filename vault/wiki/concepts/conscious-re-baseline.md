---
title: Conscious Re-baseline
category: concept
summary: Explicitly documenting a new passed/failed baseline instead of silently absorbing drift or moving a gate — extended 2026-08-07 to environment conditions; every historical battery wall-time baseline was silently conditioned on a years-old undocumented Defender exclusion, discovered only when it was removed
tags: [governance, overfit, documentation, environment]
sources: 4
updated: 2026-08-07
---

# Conscious Re-baseline

## Definition
When a battery's passed/failed state changes, the change is **written down** — with the corpus size,
the triggering diff, the [[concepts/inertness-protocol]] result, and the new standing baseline —
rather than being silently absorbed or compensated for by a threshold edit.

## The reading rule adopted
"Treat any single-check flip inside the {3,4,5}-passed band as the documented oscillation unless the
inertness experiment says otherwise." Turning a recurring alarm into a *documented oscillation* is
itself the deliverable.

## Two naive metrics it demotes
- **Row count is not a monotone clock.** Survivors fell 4,692 -> 4,642 while the raw file grew to
  4,722, because clash-dedup absorbed more duplicate candidate/live pairs. "Read it with the dedup
  stats."
- **A single-point reading is a noisy estimator.** One seed gave `dead_frac` 0.60 against a 0.55 gate;
  across 3 seeds x 3 n_splits only 13 features were unanimously dead, and only 5 cleared the
  [[concepts/coverage-floor]].

## The hazard it creates
Baselines become **ambiguous without their corpus size**. On a single day the corpus produced both
"5 passed / 3 failed" (4,692 rows) and "4 passed / 4 failed" (4,642 rows) — a genuine trap.
**Always qualify a baseline by row count.** See [[synthesis/open-contradictions-register]].

## The environment extension (2026-08-07) — a baseline is conditioned on things nobody wrote down

The Defender posture change ([[sources/session-20260807-closing-batch]] §1) added a second axis
to the rule: a timing baseline is conditioned not just on the corpus but on the **machine
posture it ran under** — and that condition can be years old and undocumented. Event log 5007
proved a **broad AV exclusion over `Documents\liquiditybot` predated the corpus's entire battery
history**, so every recorded wall time (623s serial, ~375–400s under xdist) was measured with
the repo and `.venv` **effectively unscanned**, a condition no baseline ever stated. The
re-baseline was done consciously in both directions: the exclusion removed, the cost measured
(**3438/0/1 in 401.30s vs 375.39s = +6.9%**, honestly caveated — same-posture spread 359–401s
exceeds the pair delta), and the **new posture written down with the baseline** (source scanned;
only `.venv` + pytest-temp excluded; documented, revertible). The rule as extended: **qualify a
timing baseline by its corpus size AND its named environment posture** — an unstated condition
is a silent re-baseline waiting to happen in reverse.

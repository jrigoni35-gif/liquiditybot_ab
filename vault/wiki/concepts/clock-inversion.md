---
title: Clock Inversion
category: concept
summary: A protective overlay firing systematically before the label's own vertical barrier, guaranteeing labels never resolve in-era
tags: [labeling, exits, diagnosis]
sources: 2
updated: 2026-08-01
---

# Clock Inversion

## Definition
When a protective exit overlay fires at bar N and the label's vertical barrier sits at bar M with
**N << M**, positions close before the label can resolve. Every close then falls back to a generic
barrier tag, so **no live row can ever join the current label era**.

## The instance
The no-progress time stop fires at **bar 36 (3 hours)**; the label's vertical sat at **bar 96 (8
hours)**. Live median hold **13.6 bars** vs candidate **43.2 bars**; share reaching the vertical **live
9.3% vs candidate 33.8%**. Live positions close **~3x sooner** than the label's horizon.

## Why it hid for so long
The overlay's closes deliberately stamp a generic barrier "so there is no tb-era contamination" — a
design choice made for good reasons in [[sources/pt060-bracket-wedge]], which then became the exact
mechanism starving the era. **The same decision was correct locally and wrong globally.**

## Two wrong diagnoses preceded it
1. "`log_close` hardcodes the barrier string" — true, but fixing the emission did not fix the flow.
2. "The barriers are unreachable by this strategy" — **retracted in-document** as apples-to-oranges: it
   measured excursions over the actual short holding window against a barrier defined over a 96-bar
   horizon. Candidate rows reach PT 17.9% / SL 34.5% / TIME 47.5%, so the barriers **are** reachable.

## The resolution
**Don't move the overlay, move the vertical.** Re-aligning the horizon 96 -> ~24 bars suppresses no
protective exit, converts ~100% of probes to era-valid rows at a quarter of the capital-time, and
dominates the alternative of letting probes ride to the vertical (which would re-run a documented
-1.69% incident).

Verified live: `tb_*` live rows **0 -> 3**. See [[comparisons/horizon-96-vs-24-bars]] for the
before/after, including why the fix made the barrier-to-sigma ratio *worse*.

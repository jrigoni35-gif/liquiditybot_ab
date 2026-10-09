---
title: Honest Null Result
category: concept
summary: Reporting INSUFFICIENT_EVIDENCE with the exact data requirement, rather than fitting a verdict to inadequate data
tags: [measurement, discipline, method]
sources: 2
updated: 2026-08-01
---

# Honest Null Result

## Definition
When the data cannot support a verdict, the instrument returns **INSUFFICIENT_EVIDENCE** with a coded
disposition — and specifies exactly what data would resolve it.

## The instance
An attempt to adjudicate whether a fill model's hazard is time-consistent excluded **366 of 366
recorded tapes**, fitting **zero**. The guard: per-tape median intra-frame gap of 0.011-0.018s against
a 5-second poll interval — the recordings were **burst re-reads**, measuring intra-second book flicker
rather than the per-poll quantity under test.

Critically: there are only ~2 book polls per tape and the longest observed episode is **0 polls against
a horizon of 5**, so the question is **structurally unobservable in these recordings regardless of how
many more sessions are collected**. Adding data of the same kind would never help.

## What makes it *honest* rather than merely negative
- The verdict rule was **stated in advance** (relative misstatement > 10% AND a likelihood-ratio p
  < 0.05).
- The **scope was narrowed explicitly** — this tests hazard *shape*; the *level* belongs to a different
  instrument.
- **Caveats that would qualify a future positive** were written down in advance: the queue-aware mode
  means the assumption under test only applies post-queue-clear, and unmodeled heterogeneity biases a
  pooled hazard toward apparent decrease.
- The remediation is concrete: record at the engine cadence with enough polls to cover the horizon.

## Net movement
Across two documents on this question: **zero**. But the instrument now exists and the data requirement
is specified — which is what converts an open question into a scheduled one.

## Related
[[concepts/iron-law-of-debugging]] · [[concepts/defer-verdict]] ·
[[sources/fill-hazard-l1]] · [[synthesis/owed-measurements]]

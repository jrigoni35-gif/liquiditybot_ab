---
title: Hummingbot and freqtrade
category: entity
summary: The two most-deployed open-source retail bots, whose documented defaults are the ground truth for detector calibration — and, since the 2026-08-10 engineering sweep, precedent mines for this repo's own conflict classes (freqtrade's minimal_roi with its documented near-TP/far-SL trap, hummingbot's hard time-limit barrier, NostalgiaForInfinity's no-hard-SL position and its documented drawdown cost)
tags: [external, adversary, calibration, precedents]
sources: 3
updated: 2026-08-10
---

# Hummingbot and freqtrade

The two frameworks whose **documented default configurations** serve as the calibration ground truth for
the manipulation-footprint detectors. See [[concepts/calibration-check]].

## Hummingbot (pure market making)
- A refresh timer cancels and replaces resting orders every N seconds **even when nothing moved** — "a
  *clock*, not event-driven flow."
- Fixed, usually symmetric spreads.
- Multi-level ladders at evenly-spaced increments with often uniform size.
- A self-referential mid as price source, with no external anchor.

Maps to the metronome and grid-ladder detectors. **Both calibrate YES; neither fires live** — the
venue's major books are not dominated by default-config retail market makers.

## freqtrade
- A **time-since-entry** exit ladder.
- A **single fixed stop-loss percentage**, so many bots on the same strategy cluster stops a fixed
  distance below entries and at round numbers.
- A trailing stop armed at a fixed profit offset.

The fixed stop maps to stop-herding — **"and it is the one firing live."** The time-since-entry ladder
is an [[concepts/honest-coverage-gap|honest coverage gap]]: it fires relative to each trade's own entry,
unobservable from public data.

## Why they are treated as entities rather than tools
They are modeled as **adversary populations with knowable priors**. Their published defaults are stable
external facts, which converts detector calibration from a fitting problem into a specification-matching
problem with no degrees-of-freedom cost.

## Second role acquired 2026-08-10: precedent mines, not just adversary priors
The Grand Synthesis engineering sweep ([[sources/sweep-20260811-engineering-precedents]]) read the
same frameworks from the other side — as **documented-fix archives** for this repo's own conflict
classes:

- **freqtrade** — `minimal_roi` (the time-decay exit mechanism ALGO-6 adapts) carries a
  **documented trap**: aggressive decay tables REPRODUCE near-TP/far-SL, the exact
  disposition-geometry this book measured at 2.20x ([[concepts/behavioral-isomorphism]]). Its
  issue catalog also locates the real cost of stop-on-exchange vs in-bot at **state
  reconciliation** — the class this repo's OM-085/restore work already covers (ALREADY AHEAD).
- **hummingbot** — ships a **hard time-limit barrier** as its triple-barrier default; the
  vertical barrier as first-class exit is ALGO-6's second half.
- **NostalgiaForInfinity** (freqtrade's most-documented strategy family) — the strongest
  documented **no-hard-SL + staged-derisk** position, filed WITH its documented cost (deep
  drawdowns): the honest bound on "just remove the stop," REJECTED against the survival floor.
- **The brookmiles artifact** (+2506% in 11 days, a backtest fill-geometry artifact) —
  external confirmation of [[concepts/generosity-masks-fragility]].

The headline negative from the sweep: **nobody in either world documents symmetric-R brackets
as their disposition fix** — the maker world converged on inventory skew, the retail-bot world
on time-decay + time-limits + ratchet-invariant stops. Full adjudication:
[[synthesis/grand-synthesis-algorithm-package]].

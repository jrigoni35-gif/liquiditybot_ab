---
title: THALES Doctrine
category: source
summary: A bank of detectors for the predictable footprints lazily-configured retail trading bots leave in public data, plus a bounded advice channel and a certificate hierarchy
tags: [thales, manipulation, detectors, doctrine, certificates]
sources: 1
updated: 2026-08-01
---

# THALES Doctrine

**Raw source:** `raw/architecture/THALES.md`

Named for Thales of Miletus cornering the olive presses on foresight alone: **"we do not out-speed
anyone, we out-*notice* them."**

## Thesis
Most deployed retail/prosumer bots run on lazy defaults — they act on clocks instead of events, park
orders at obvious levels, trust a single feed, and never validate their pipelines. **This repo's own
pre-audit history is the design template**: each of its own past sins maps to a market-wide archetype.

## The detector bank
- **TH-010 `grid_ladder`** — grid bots placing evenly-spaced uniform ladders. Detection: spacing
  regularity x size uniformity x **persistence** (real ladders rest; MM churn doesn't). Exploit:
  **grids are short-gamma on trends** — they sell into rallies and buy into crashes.
- **TH-011 `metronome_mm`** — clock-driven quoting. Detection: **autocorrelation of top-of-book
  replacement events**; a dominant fixed-lag peak means timer-driven. Exploit: **clock-quoters are
  stale immediately after fast moves**.
- **TH-012 `clockwork_flow`** — DCA bots and naive TWAP slicers at fixed timestamps. Detection:
  bucketed time-of-day stats **activated only if the bucket effect beats a shuffled null**; no
  significance means score 0. "Seasonality mining is the classic overfit trap — the shuffle-null and
  the warmup gate are mandatory, not optional."
- **TH-013 `stop_herding`** — stops cluster at round numbers and obvious swing extremes.
  **Two-sided**: defensively shade down entries whose stop would land in a hot cluster ("we stop being
  the lemming"); offensively shade mean-reversion up after a confirmed sweep-and-revert.
- **TH-014 `feed_integrity`** — "the data itself is the attack surface." Garbage is rejected at the
  sanitize boundary; **THALES's complementary role is to notice the *pattern*** via a rolling
  clean-rate. **Defensive only: shade DOWN, never up, never a direction.**
- **TH-016 `observation_lapse`** — the detector-of-self. "We LIVED this one from the inside": a restart
  restored a day-old snapshot and **every surviving layer kept treating its pre-gap memory as
  current.** Response is hygiene only — reset continuity-dependent memory, then **mute the advice
  channel in BOTH modes** for a warmup. **"A muted THALES is exactly the pre-THALES bot."**

## The activation ladder
**shadow** (default; detectors run, zero influence) -> **advise** (bounded `conf_mult`, clamped) ->
future rungs (explicitly not in v1). **Each promotion requires: shadow hit-rate beats null, OF battery
green, quant-trial gates green.** "Enabling detectors is not enabling influence."

## V2 — the vindication loop
V1's fixed gains were "hand-crafted priors that nothing ever validated." Now each detector's gain
scales by `w = max(0, 2*WilsonLCB90 - 1)`. **Weights ATTENUATE only** — "a proven detector approaches
but never exceeds its configured gain. Amplification is knob-tuning and belongs to the gated tuning
pass, not a live feedback loop." `feed_integrity` is **permanently EXEMPT** — grading it by trade
outcomes "would let a lucky win on dirty data teach the engine to trust dirty feeds." Shadow-mode
advice **never trains the ledger**. See [[concepts/vindication-ledger]].

## V3 — the certificate hierarchy (design only)
**An influence on a real-time loop is admissible only with a CERTIFICATE — a bound that holds before
the data arrives.**
1. **Time certificate** — advice must fit the cycle's budget by construction or abstain. **"A late
   answer in a real-time loop is a wrong answer."**
2. **Evidence certificate** (V2, shipped).
3. **Significance certificate** — calendar/seasonal context enters only past a shuffle-null test.
4. **The asymmetry law** — layers too slow to ever earn an evidence certificate **may only shade DOWN,
   never boost**: **"A false shade costs opportunity; a false boost costs money. Slow layers get veto
   rights, not alpha rights."** See [[concepts/asymmetry-law]].

## Hard boundaries
**Detect and react only. "No spoofing, no layering, no orders placed to trigger anyone's stops, no
wash activity."** Advice never touches direction, `all_confirmed`, or any risk-stack clamp. Every
disposition carries a registered TH-xxx code. Detector observation state must never survive a restart.

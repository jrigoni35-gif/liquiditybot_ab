---
title: The Vindication Ledger
category: concept
summary: Detector weights scaled by a Wilson lower-bound on realized vindication, attenuating only, so a stale detector mutes itself without a hand-tuned edit
tags: [thales, evidence, self-muting]
sources: 3
updated: 2026-08-01
---

# The Vindication Ledger

## Definition
Every influencing detector records which way it shaded each entry; at close, each shade is graded
vindicated or not. A detector's configured gain is scaled by
**`w = max(0, 2 * WilsonLCB90 - 1)`** — its lower-bounded vindication rate.

## Design properties
- **Attenuate only.** "A proven detector approaches but never exceeds its configured gain.
  Amplification is knob-tuning and belongs to the gated tuning pass, not a live feedback loop."
- **Cold start is exactly the prior.** Below a minimum grade count, `w = 1.0`.
- **Self-muting.** A detector that cannot beat its null at the 90% lower bound is muted.
- **Safety detectors are exempt.** Grading feed-integrity by trade outcomes "would let a lucky win on
  dirty data teach the engine to trust dirty feeds." Likewise the spoof-flicker safety shade — "a
  failed spoofer must not teach the ledger to ignore spoofing."
- **Shadow advice never trains the ledger** — it never influenced the trade, so it must not.

## Why it is the right shape for an arms race
An adversary adapts; a detector's edge decays. Self-muting retires a stale detector **automatically
rather than by a fitted-literal edit**, which is what keeps the response inside the no-fitted-literals
discipline.

## Two defects found in it
1. **[[concepts/wrong-null-calibration|Wrong null]]** — vindication was graded against a 0.5 coin-flip
   while the realized base win rate was 15.8%, so a detector with a **2x win-rate lift was muted** while
   a **no-skill detector kept its voice**.
2. **[[concepts/dead-mute-trap|Dead-mute trap]]** — once muted, the detector was no longer recorded as
   fired, so it could **never accrue the grades needed to recover**.

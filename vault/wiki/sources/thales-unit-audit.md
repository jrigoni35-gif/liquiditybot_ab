---
title: THALES Unit Audit (2026-07-29)
category: source
summary: Unit-coherence and earning-its-keep audit of the manipulation-defense layer: detector arithmetic largely clean, three calibration defects found, engine shown structurally inert
tags: [thales, audit, calibration, manipulation]
sources: 1
updated: 2026-08-01
---

# THALES Unit Audit (2026-07-29)

**Raw source:** `raw/quant/2026-07-29_thales_unit_audit.md`

## Two stacks share the "manipulation" label
**ThalesEngine** (TH-010..TH-021) shades confidence and is currently `influence:"shadow"`;
**manip_suspect** (MAX of spoof_score, whiplash_suspicion, cross-venue divergence) is live and
enabled. Only the latter reaches sizing.

## Three calibration defects
- **A-1 (HIGH, latent)** — **wrong-null calibration**. Reliability weight `w = max(0, 2*WilsonLCB-1)`
  grades vindication against a **0.5 coin-flip null**, but the realized live base win rate is
  **15.8% (40/253)**. Consequence at n=20: a detector with a **2x win-rate lift (32%) is muted
  (w=0)** while a **no-skill down detector keeps its voice (w=0.443)**. Worse, once w=0 the detector
  is no longer appended to `fired`, so it **can never redeem itself** — the
  [[concepts/dead-mute-trap]].
- **A-2 (HIGH telemetry / LOW decision)** — stop-zone proximity tolerance is not normalized by magnet
  spacing, so the band covers 30-100% of the gap between adjacent magnets. `th_stopzone` mean 0.42,
  **43.4% of 6,462 rows > 0.5**. Realized-outcome check: mean net PnL -$0.164/trade above 0.5 vs
  -$0.166 below, win% 17.5 vs 14.7 — **zero discrimination**.
- **A-3 (MEDIUM)** — TH-017 flicker score is an EWMA **per snapshot** while spoofing is a wall-time
  process. The same spoofer reads as firing at 5s cadence, saturating at 10s, and **never firing** at
  2.5s.

## Earning its keep — B findings
- **B-1a**: ThalesEngine does not reach sizing. All **65 shade events ever recorded are "would-shade"
  (0 up / 65 down, mean x0.948, zero applied)**.
- **B-1b**: probes bypass/dilute the shade **three ways** — EV bypass, a `p_win` floor of 0.7 applied
  AFTER any shade, and the explore floor re-inflating notional after a manip downsize.
- **B-2**: the reliability layer has **never engaged and cannot in shadow mode** — a
  **chicken-and-egg**: promotion to advise requires shadow evidence, but the ledger only learns in
  advise. Only TH-013 has ever fired (65/65 events).
- **B-3**: the learning down-weight IS wired, active and material — corpus manip_suspect mean 0.233
  gives an average training weight factor ~0.88.
- **B-4**: TH-021 evidence-concentration shade is gated off, and enabling it today is a **provable
  NO-OP** — all 422 instrumented rows have confidence >= 0.701 while the trim needs < 0.65.
  **"Do not enable TH-021 'to do something' — it will do nothing."**
- **B-5**: **no dose-response**. manip < 0.3 -> win 18.4%; 0.3-0.6 -> win 2.9%; >= 0.6 -> win 9.1%.
  **High-manip entries do NOT lose more; the mid band is worst.**

## Shipped
A-1 base-rate null + dead-mute probation; B-2 shadow grading unlock; A-3 wall-time normalization;
A-2 geometric-null subtraction; B-1b probe floor withheld under manip downsize.

## Related
[[entities/thales-engine]] · [[comparisons/thales-engine-vs-manip-suspect]]

---
title: Probe Livelock
category: concept
summary: The probe share cap denies probes, so no admissions occur, so no live labels accrue, so the conditions that would relax the cap never arrive
tags: [exploration, learning, livelock]
sources: 3
updated: 2026-08-14
---

# Probe Livelock

## The loop
1. The probe share cap denies probe entries.
2. No admissions of any kind occur.
3. No live labels accrue.
4. The regime-coverage and evidence floors that would relax the cap are never met.
5. Return to 1.

## How it was first characterized
As a real, quantified but **accepted** cost of correct throttling — a MIXED verdict: the throttle
"correctly suppresses net-negative probe flow BUT slows live-label accrual." The chain was named
explicitly: **throttle -> labels -> governor**. Bear regime sat at **4/60** live labels, so conviction's
regime-known term could never admit bear conviction, keeping the governor shadowed longer.

## The escalation
A day later it is reclassified as a **livelock requiring structural repair**, and the operator elects to
**pay for labels with simulated bleed** — see [[concepts/priced-bleed]].

## The chosen fix
A **structural drought-scoped floor**: a minimum probe allowance engaging only during a measured
drought (zero admissions of any kind for a configured span) and only when the share cap is the binding
denial. Chosen over a plain config lever because it is surgical, deterministic on replay,
config-derived rather than magic-numbered, observable via a registered code, and **provably
byte-identical outside a drought**.

Rejected variants: window time-decay (breaks replay determinism) and a denial-counting denominator
(widens in all states).

## Second-order damage
The drought did not merely slow learning — it **biased the measurement corpus**. A one-sided inflow of
+252 drought-era candidates at 92% label-0 arrived while live labels sat frozen, skewing the very
population the overfit battery was measuring.

## The terminal state (2026-08-14): the probe lane IS the live corpus

The fix worked, and the result is the loop's end state rather than its escape. Measured over the
exact 24h window `[1786664298, 1786750698]` (snapshot 2026-08-14T23:38:18Z):

| | count |
|---|---:|
| labels total | **123** |
| `source=candidate` | 119 (96.7%) |
| **`source=live`** | **4 (3.3%)** |
| of those live, **`probe=1`** | **3** |

**The gate itself produced exactly ONE entry in 24 hours** — BTC, `label=0`, **−$0.42**. The
three probes returned +0.02 / +0.13 / +0.12. Net 24h **−$0.15**, which double-derives
`outputs/pipeline_audit.md` by an independent route. Twelve-day mean: **124.5 labels/day, of
which 3.0 live/day (2.4%)**.

So the drought floor is no longer a floor under a temporary hole — **it is supplying
essentially the entire live-label stream**, and therefore essentially the entire era-4 accrual.
The livelock is not running, and what replaced it is a corpus whose live half is a lane
deliberately exempt from the EV gate ([[concepts/pooled-populations]]: probe and conviction
populations differ BY DESIGN and must never be pooled — here the pooled population is
**75% probe**).

Two consequences worth stating plainly, neither of them a proposal:

1. **The era-4 verdict is accruing on a population the strategy's own gate did not select.**
   Whether that satisfies the pre-registration is operator-owned, not a measurement question.
2. **The accrual rate is the binding constraint on the readout**, at ~3–4 closes/day against a
   pre-registered n=50 — and the rate is set by the probe allowance, not by the gate.

Related: [[concepts/priced-bleed]] (the tuition this lane buys, and its attached falsifier),
[[synthesis/owed-measurements]] item 54 (the probe/conviction split, SHIPPED and INERT).
— [[sources/session-20260814-cohort-instruments]] §supporting measurement

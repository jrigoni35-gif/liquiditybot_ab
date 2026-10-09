---
title: Livelock F0 Decision (2026-07-25)
category: source
summary: Operator chose a structural drought-scoped probe floor over a config lever to break the probe/label livelock, with the bleed explicitly priced
tags: [livelock, probe, decision, sz-048]
sources: 1
updated: 2026-08-01
---

# Livelock F0 Decision (2026-07-25)

**Raw source:** `raw/quant/2026-07-25_livelock_f0_decision.md`

## Decision
**F0b — structural drought-scoped probe floor**, chosen over F0a (plain config lever), F0a+F0b
combined, and report-first.

## The livelock
The probe share cap keeps denying probes, so no admissions occur, so no live labels accrue, so the
conditions that would relax the cap never arrive. See [[concepts/probe-livelock]].

## Priced bleed
Probes accounted for **-$22.87 of -$31.68 net** over the P3 window. It is paper mode, "so the bleed
is simulated while the labels are real learning." Pricing the cost before deciding is the pattern —
see [[concepts/priced-bleed]].

## Eight binding conditions (C2 grill verdict)
1. Activates only on ZERO admissions of ANY kind for >= configured spans (the ML-073 drought clock).
2. AND only when the share cap is the binding denial.
3. Span/count-keyed, **never wall-clock** (replay determinism).
4. Rate/threshold in `config.json` with a `config_guard` derivation tied to the 8h label horizon.
5. A new registered SZ-* code is recorded into the window.
6. Non-drought behaviour is **byte-identical** (test-pinned).
7. Conviction is never throttled.
8. All existing probe bounds remain intact.

## Rejected variants
- **Window time-decay** — rejected for replay determinism.
- **Denial-counting denominator** — rejected because it widens in all states.

## Downstream
The resulting SZ-048 drought floor is the triggering diff in the fifth crossing of
[[sources/of3-pbo-data-shift]] (`b550b6f..34bb82d`, "touches probe admission at runtime only").

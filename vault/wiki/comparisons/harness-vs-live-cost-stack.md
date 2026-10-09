---
title: Harness vs Live Cost Stack
category: comparison
summary: Why the Monte-Carlo harness fails a gate that the live configuration is argued not to violate
tags: [comparison, cost, gates, harness]
sources: 3
updated: 2026-08-01
---

# Harness vs Live Cost Stack

## The disagreement
Mirroring the deployed exit geometry into the Monte-Carlo harness **fails G1**. The same geometry runs
live. Both facts stand.

| | Harness | Live |
|---|---|---|
| Cost stack | 40 bps/side (synthetic) | ~20.5 bps (measured) |
| Implied cost floor | 1.2% | 0.615% |
| Legacy tier-1 trigger | 1.0% | vol-clamped, varies |
| Floor binds | **always** (1.2% > 1.0%) | **only in low-vol regimes** |

## The resolution offered
Because the harness's synthetic cost is roughly double the measured live cost, its floor binds on every
path while the live floor binds only where the vol-clamped trigger falls below it. **The harness
overstates the floor's bite.**

## What was done about it
The enablement was **reverted**, not the gate widened. The live configuration was held at KEEP
**pending a live paper-telemetry verdict** — and because the two levers are coupled, "changing one
re-runs untested coupling" ([[concepts/lever-coupling]]).

## The unresolved part
**No document in the corpus records that verdict's outcome.** The system is therefore knowingly running
a geometry that fails its own harness's G1 gate, on an argument that has not been closed. Filed in
[[synthesis/open-contradictions-register]].

## The general lesson
A simulation harness is a **model of the system, not the system**. When it disagrees with production,
the first question is which of the two has the wrong cost assumptions — and the answer must be measured,
not asserted. Note the direction of the discipline: the divergence was used to **defer**, never to
dismiss the gate.

## Related
[[sources/harness-enablement-g1-finding]] · [[concepts/quant-trial-gates]] · [[concepts/cost-truth]]

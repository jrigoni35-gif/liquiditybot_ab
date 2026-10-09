---
title: ContextFeed (the external-context ingestion seam)
category: entity
summary: The engine's designed seam for keyless external context sources — per-source 3x-grace known=False staleness states (dials go stale, never frozen), a wall-clock poll budget, injectable fetch, config-lifted knobs, and CX reason codes — adjudicated 2026-08-08 as agile enough to carry all six institutional/government data adoptions, with three named gaps (UA config-lift, per-source grace for shutdown-class weekly gaps, and the deliberately GATED corpus-injection path, ruled a feature not a defect)
tags: [entity, feeds, context, ingestion, data-sources, staleness]
sources: 1
updated: 2026-08-08
---

# ContextFeed (the external-context ingestion seam)

## What it is

The engine's ingestion seam for **keyless external context sources** — the layer the
2026-08-08 institutional/government data adjudication
([[sources/session-20260808-institutional-data-adjudication]]) examined for agility and
ruled: **this is the designed seam; new sources go here.** As characterized by that
adjudication (agent-verified against the code, not independently re-verified at filing):

- **5 keyless sources** currently registered.
- **Per-source 3x-grace `known=False` states** — a source that misses ~3x its expected
  cadence stops asserting values; downstream dials **go stale, not frozen**. The government
  agent's headline recommendation ("dials must go stale, not frozen") turned out to be
  **already implemented** as this discipline — the input-plane cousin of
  [[concepts/zero-is-not-a-reading]] (absence must never masquerade as a reading).
- **Wall-clock poll budget** — external polling is budgeted, not free-running.
- **Injectable fetch** — the HTTP layer is injectable, so sources are testable without the
  network.
- **Config-lifted knobs** and **CX reason codes** for its decisions.

This is the same degrade-independently-to-neutral design that
[[concepts/availability-failure-mode]] exists to protect: every source must be able to die
alone without lying.

## The three gaps (2026-08-08 adjudication)

1. **The UA header needs a config-lift with real operator contact.** The current `_UA`
   advertises **"contact: none"**, which **fails SEC EDGAR's name+email User-Agent policy**
   (403 without it — verified first-hand by the agents) and is inadequate for NY Fed
   endpoints. Blocks the EDGAR 8-K and ETF-flow adoptions until lifted.
2. **Weekly-cadence sources need wider-than-3x grace.** The CFTC COT shutdown precedent
   (2025: **multi-week publication gaps**) would burn a 3x-grace weekly source to
   `known=False` for the duration; grace must be per-source configurable so a known
   publication gap degrades gracefully instead of permanently.
3. **Corpus injection is deliberately GATED — a feature, not a defect.** Nothing a
   ContextFeed source ingests can reach the training corpus directly. The only path is:
   **telemetry → risk-gate consumer behind quant gates → schema graduation via schema-AB +
   era stamp, only when labels fund it** ([[concepts/dof-budget]],
   [[concepts/shadow-first-adoption]]). The adjudication examined this as a possible
   agility gap and ruled it the opposite.

## Related

[[sources/session-20260808-institutional-data-adjudication]] ·
[[concepts/availability-failure-mode]] · [[concepts/zero-is-not-a-reading]] ·
[[concepts/shadow-first-adoption]] · [[entities/read-only-venues]]

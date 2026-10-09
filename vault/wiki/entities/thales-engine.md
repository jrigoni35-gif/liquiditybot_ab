---
title: ThalesEngine
category: entity
status: SETTLED
summary: The manipulation-footprint detector bank and bounded advice channel, currently running in shadow mode with only one detector ever firing
tags: [subsystem, manipulation, detectors]
sources: 8
updated: 2026-08-27
---

# ThalesEngine

A bank of detectors for **the predictable footprints that lazily-configured retail trading bots leave in
public market data**, plus a clamped advice channel. Named for Thales of Miletus cornering the olive
presses on foresight alone: **"we do not out-speed anyone, we out-*notice* them."**

## Detectors
| Code | Name | Target |
|---|---|---|
| TH-010 | `grid_ladder` | evenly-spaced uniform ladders from grid bots |
| TH-011 | `metronome_mm` | clock-driven cancel/replace quoting |
| TH-012 | `clockwork_flow` | fixed-timestamp DCA / TWAP flow |
| TH-013 | `stop_herding` | stop clusters at round numbers and swing extremes |
| TH-014 | `feed_integrity` | the pattern of dirty data (defensive only) |
| TH-016 | `observation_lapse` | **the detector of self** — our own observation gaps |
| TH-017 | `spoof_flicker` | large levels pulled without the mid crossing them |
| TH-021 | evidence concentration | diffuse-but-marginal signals |

## Current state
`influence: "shadow"`. All **65 shade events ever recorded are "would-shade" (0 up / 65 down, zero
applied)**. Only **TH-013 has ever fired** — 100% of advice events. See
[[sources/thales-unit-audit]] and [[sources/thales-frameworks-calibration]].

## Hard boundaries
**Detect and react only.** "No spoofing, no layering, no orders placed to trigger anyone's stops, no
wash activity." Advice never touches direction, the confirmation flag, or any risk-stack clamp. Every
disposition carries a registered code. Detector observation state must never survive a restart.

## The layer it is often confused with
A separate, **live** manip-suspect composite does reach sizing (downsize band and veto threshold). The
two are distinct — see [[comparisons/thales-engine-vs-manip-suspect]]. As of 2026-08-21 that live
composite has stamped **454 SZ-045 refusals**, so "the veto has never fired in anger" is no longer true
of the live layer.

## A caution that lands on TH-017 by shape, not by measurement
The live layer's `spoof` component — *large near-touch level vanished untouched* — was put to a paired
injection on 2026-08-21 and **failed identifiability**: honest maker repricing in a melt-up and true
layering both score 0.949 with the same event count and the same `spoofy` label at matched cadence
([[concepts/observational-equivalence]]). **TH-017 `spoof_flicker` was NOT the object tested**, but it is
described in the same words ("large levels pulled without the mid crossing them"), so its shadow record
should be read as *unfalsified*, not *validated*, until it is run against its own benign twin. This is
the practical content of the standing rule that a detector ships with the most innocent process that
produces the same shape.

## Governing concepts
[[concepts/observational-equivalence]] · [[concepts/shadow-first-adoption]] · [[concepts/vindication-ledger]] ·
[[concepts/certificate-hierarchy]] · [[concepts/asymmetry-law]] · [[concepts/cost-imposition]]

*2026-08-27: the lazy-bot/insecurity question THALES instruments now has a behavioral literature
companion — `docs/research/behavioral/` cross-references THALES in 6 of its 7 files (TH-011
metronome-MM named explicitly in `02_exchange_economics.md:173`; sentiment bots get their own
file, `05_sentiment_bots.md`); its feature candidates are pre-registered only, FORBIDDEN until
boundary adjudication. Uncommitted at filing — committed `f17e28b5` and pushed 2026-08-28,
citation-verified (19+19 corrections; sent-ret-1 regraded "B in-sample; D at our horizon",
sent-ret-2 to C, and the derived sentiment feature is D-grade at our horizon — a caution the
THALES sentiment lens inherits).
([[sources/session-20260827-sdd-verification-and-era-confound]] §4)*

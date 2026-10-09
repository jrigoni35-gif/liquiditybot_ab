---
title: THALES Frameworks Calibration
category: source
summary: Maps the documented default configurations of the two most-deployed open-source retail bots to THALES detectors, with a calibration verdict per footprint and the live shadow result
tags: [thales, calibration, footprints, hummingbot, freqtrade]
sources: 1
updated: 2026-08-01
---

# THALES Frameworks Calibration

**Raw source:** `raw/architecture/THALES_FRAMEWORKS.md`

The **calibration evidence** for [[sources/thales-doctrine]]. It checks each detector against the
documented defaults of the two most-deployed open-source retail bots.

## Hummingbot Pure Market Making defaults
`order_refresh_time` cancels and replaces resting orders on a timer (common template 30s) — "a
*clock*, not event-driven flow." `bid_spread`/`ask_spread` fixed and usually symmetric. `order_levels`
places N orders per side at evenly-spaced increments with often uniform size — an even, size-uniform
two-sided ladder.

## freqtrade defaults
`minimal_roi` is a **time-since-entry** exit ladder. `stoploss` is a single fixed percentage, so many
bots on the same strategy **cluster stop orders a fixed % below entries** and at round numbers.
`trailing_stop_positive` arms at a fixed profit offset.

## Mapping and verdicts
| Footprint | Detector | Verdict |
|---|---|---|
| Hummingbot `order_refresh_time` ~30s | TH-011 metronome_mm | **YES** — 30s sits well above the 8s floor, reads as near-zero CV |
| Hummingbot `order_levels` | TH-010 grid_ladder | **YES** — even spacing + size uniformity + Jaccard persistence |
| freqtrade fixed `stoploss` | TH-013 stop_herding | **YES — and it is the one firing live** |
| freqtrade `minimal_roi` | TH-012 clockwork_flow | **PARTIAL / GAP** |

The `minimal_roi` gap is deliberate: it fires N minutes after each trade's *own* entry, "which is not
observable from public data without tracking a counterparty's entry timestamps. **Left uncovered on
purpose rather than faked.**" See [[concepts/honest-coverage-gap]].

## The live shadow result
Only **TH-013 stop_herding** is present on the venue's major books — **100% of THALES advice events**;
grid and metronome ~0.

> "The venue's major books are not dominated by default-config retail MM/grid bots, so the
> Hummingbot-targeting detectors correctly stay quiet — **that is calibration working, not calibration
> missing.**"

## Why nothing was retuned
The detectors already admit the documented framework defaults, so tuning to the current tape "would be
fitting to noise — exactly the overfit sin CLAUDE.md forbids." This is the
[[concepts/calibration-check]] pattern: verify the threshold already admits the documented default
rather than fitting the tape.

## Owed next step
TH-013 "has now cleared the frequency bar; the honest next step is a **shadow-vs-advise A/B on that
single detector** once enough labeled trades accrue" — not yet run. Promotion is gated on evidence
joined to trade outcomes, **not on firing frequency**, and is decided by a human.

## Related
[[entities/retail-bot-frameworks]] · [[entities/thales-engine]] · [[concepts/calibration-check]]

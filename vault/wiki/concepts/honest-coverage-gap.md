---
title: Honest Coverage Gap
category: concept
summary: Declining to build a detector for a footprint that is genuinely unobservable, rather than faking coverage
tags: [method, honesty, detectors]
sources: 1
updated: 2026-08-01
---

# Honest Coverage Gap

## Definition
When a known adversary behavior produces **no observable signature in the data you actually have**, the
correct response is to **document the gap** rather than ship a detector that appears to cover it.

## The instance
A widely-deployed retail bot's time-based exit ladder fires N minutes after **each trade's own entry** —
"which is not observable from public data without tracking a counterparty's entry timestamps."

> **"Left uncovered on purpose rather than faked."**

## The companion insight — silence as evidence
The detectors aimed at a different framework's footprint fire at approximately zero on the live venue.
Rather than treating that as a calibration failure:

> "The venue's major books are not dominated by default-config retail bots, so those detectors
> correctly stay quiet — **that is calibration working, not calibration missing.**"

## The calibration-check pattern
Thresholds were validated by confirming they **already admit the documented default configurations** of
the target systems — not by tuning to the observed tape. Tuning to the tape "would be fitting to noise."
See [[concepts/calibration-check]].

## Why this belongs in a knowledge base
Both halves are claims that decay silently. A gap that is documented can be revisited when new data
becomes available; a faked detector accumulates false confidence. And "zero firings" needs its
interpretation recorded, or a future reader will read it as breakage.

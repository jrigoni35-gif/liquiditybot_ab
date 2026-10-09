---
title: Calibration Check
category: concept
summary: Verifying a detector's thresholds already admit the documented default configuration of its target, rather than tuning to the observed tape
tags: [detectors, calibration, overfit]
sources: 1
updated: 2026-08-01
---

# Calibration Check

## Definition
Validate a threshold by checking it **already admits the documented, published default configuration**
of the system it is meant to detect — not by fitting it to whatever the current market data shows.

## Worked example
A target framework's documented default refresh interval is ~30 seconds. The detector's minimum
interval floor is 8 seconds, so a 30-second cadence sits comfortably above the floor and reads as
near-zero variation. **The threshold admits the documented default -> calibrated.** No retune needed.

## Why tuning to the tape is forbidden
> Tuning to the current tape "would be fitting to noise — exactly the overfit sin the project law
> forbids."

The tape is one sample from one venue in one period. The published default is a **stable, external,
verifiable fact about the adversary population**.

## The transferable idea
When building a detector for *other people's systems*, the ground truth is their **documentation**, not
your observations. Their defaults are knowable in advance, which converts detector calibration from a
fitting problem into a **specification-matching** problem — and specification-matching has no
degrees-of-freedom cost.

## The population being calibrated against
[[entities/retail-bot-frameworks]]

## The limit, stated honestly
Detectors with no live positive samples are **unfalsified in practice**. Their calibration rests
entirely on the documentation argument.

---
title: OKX and Binance.US (read-only data venues)
category: entity
summary: Public keyless data sources whose consensus serves as a truth check, never an execution path
tags: [venue, external, data]
sources: 4
updated: 2026-08-01
---

# OKX and Binance.US (read-only data venues)

Public, **read-only, keyless** market-data sources. They never receive an order.

## What they are used for
- A **composite** cross-venue book and microprice.
- A **venue divergence trip** — when the execution venue's mid dislocates beyond a threshold from the
  composite, new entries are blocked until re-agreement.
- A cross-venue divergence term feeding the manipulation-suspicion composite.
- Funding-rate context (one of the two is spot-only, so the funding gate rides a single perp).
- An existing feature that **monetizes the fragmentation** directly.

## The consolidated-tape finding
Crypto has no native consolidated tape, and self-built consolidated books yield real cost reduction.
The verdict: **execution venue + these two read-only feeds IS the crypto consolidated-tape equivalent
at this scale.** No new market-data feed was adopted.

## Their audited hazard
Book-expiry handling let combined-book samples **poison per-venue imbalance, depth and mid histories**
for ~30 minutes, producing false regime readings — an example of the composite leaking into statistics
that were supposed to be venue-specific.

## Scope boundary
These are **market** data only. Social feeds are deliberately outside the observation surface — "a
deliberate scope boundary, not a gap." See [[sources/criminology-manipulation-lens]].

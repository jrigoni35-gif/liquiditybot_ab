---
title: Failure-Plane Taxonomy
category: concept
summary: Organizing defenses by the plane on which something fails — config, data, order, runtime, market, account, operator visibility
tags: [hardening, operations, taxonomy]
sources: 1
updated: 2026-08-01
---

# Failure-Plane Taxonomy

## The planes
**config-time · data · order · runtime · market · account · operator-visibility**

Each catalog row names four things: **what fails, which layer catches it, the exact code location, and
what the operator sees.**

## Why the fourth column matters
A defense that fires invisibly is only half a defense. Tying every failure mode to an operator-visible
consequence is what makes the catalog an operations document rather than a design document.

## Representative defenses by plane
- **Config** — refuse live start on fees below the venue floor; enforce **ladder ordering** so the
  daily-loss limit trips before the hard-stop drawdown ("brake before parachute").
- **Data** — stale-data trip; **venue divergence trip** at >150 bps dislocation from the cross-venue
  composite; **tick quarantine** holding stop evaluation one cycle on an anomalous print.
- **Order** — price collar (entries reject, **exits clamp and are never blocked**); rate limits with a
  2x budget for exits; dupe suppression; notional caps.
- **Runtime** — a venue-side **dead-man switch** that fires if the bot stops refreshing it; checksummed
  snapshots with a backup generation.
- **Market** — a **rate**-based PnL-velocity breaker complementing the *level*-based drawdown limit,
  because "a flash crash rips through a level trigger"; an exit-escalation ladder ending in a market
  order.
- **Account** — venue-reported balance as ground truth. **"The ledger is never silently 'corrected' —
  hidden adjustments are how small errors become unexplainable ones."**

## The recurring asymmetry
Across every plane, **entries fail closed and exits fail safe**. This single rule is the most-repeated
statement in the entire architecture corpus.

## Source and enforcement
[[sources/hardening-catalog]] is the catalog; [[entities/config-guard]] enforces the config-time
plane; [[entities/kraken]] hosts the venue-side dead-man switch.

## The honest residual
An explicit list of what is **still on the operator** — key hygiene, host security ("anyone with write
access to the control directory sends commands"), dependency drift, and manual fee-tier updates.

---
title: Assurance Rev 3.0
category: source
summary: Government-protocol rewrite of the trading core with DO-178C-style traceability, delivered as the seven-module assurance spine plus a requirement trace matrix
tags: [assurance, invariants, reason-codes, audit-trail]
sources: 1
updated: 2026-08-01
---

# Assurance Rev 3.0

**Raw source:** `raw/architecture/ASSURANCE.md`

The authoritative source for invariants and reason-code families. It **supersedes ARCHITECTURE_V2's
execution core**.

## Method
Modules already at assurance grade (watchdog, config_guard, persistence, sanitize, alerts, runtime,
feeds, regimes, sentiment) are carried forward **unchanged**: "rewriting sound code for its own sake
adds risk, not assurance."

## The assurance spine — seven modules
`core/codes.py` (append-only reason-code registry) | `core/audit.py` (hash-chained JSONL,
`verify()` replays it) | `core/fault.py` (latching faults, INIT/ARMED/DEGRADED/HALTED) |
`core/clock.py` (monotonic authority; wall time for audit stamps only) | `ml/contracts.py`
(versioned feature contract) | `ml/registry.py` (SHA-256 model identity, immutable archive, model
cards, lifecycle ledger) | `scripts/assurance_check.py` (offline power-on built-in test).
See [[concepts/assurance-spine]].

## Named invariants
- **FW-01/02** — every order input positively validated; unverifiable reference **fails closed for
  entries, safe for exits**. Rate limit, dupe suppression, price collar, notional ceilings on EVERY
  order. **The firewall never raises at runtime**; the self-test refuses to arm on failure.
- **QT-01** — half spread >= maker fee + margin, so **a passive round trip is never net-negative by
  construction**.
- **OM-01** — order status changes only through the legal-transition table; violations forced to a
  safe terminal, **never a fabricated fill**. OM-02: market orders exist only as escalated exits.
- **ML-01/02** — no inference on inputs the contract hasn't passed; no artifact load without integrity
  verification against the registry ledger.
- **TX-01** — **urgency is a placement preference, never an EV bypass**; taker entries clear the FULL
  taker cost stack. TX-02: improve-style prices strictly inside the spread.
- **SYS-02** — the session config SHA-256 fingerprint is the audit chain's first record.

## Two corrections shipped
- **SYS-01 (rev-1 latent bug)**: `tier_closed` was never written, so **tier 1 re-fired forever and
  tiers 2-4 plus the trailing stop were unreachable**.
- **SZ-01**: Kelly is now sized on payoffs **net of round-trip fees** — "same p(win) now sizes
  smaller than rev 1; that is the correction, not a regression."

## Operations doctrine
**"DEGRADED means degraded"** — nothing auto-clears. Audit chain and registry ledger are append-only.
**"The governor can only make the bot more conservative than config."** The fix for a level-2 model
"is a better model through the deployment gate, not a bigger knob." The firewall's "disable via 1e9"
trick is refused at init.

## Stated gap
The active engine was switched to `informed_flow`, which has **zero paper hours** — must be run in
dry_run first, and its thresholds must be tuned by replay sweeps, not intuition.

---
title: Compliance and Market Conduct
category: source
summary: The absolute-legal-limit map benchmarking prohibited-conduct classes against engineering mechanisms, with jurisdictional honesty about which rulebook binds
tags: [compliance, market-conduct, audit-trail, long-book]
sources: 1
updated: 2026-08-01
---

# Compliance and Market Conduct

**Raw source:** `raw/architecture/compliance_market_conduct.md`

## Jurisdictional framing
The bot trades spot crypto in dry-run paper mode. CME rules are used deliberately anyway because the
rulebook is the clearest codification of market abuse, regulators have applied the same manipulation
theories to crypto venues, and the venue's own terms prohibit the same conduct classes.

## Spoofing — the intent test
The legal test is **intent at the time of order entry**, and **intent may be inferred from conduct
alone**. Mechanisms: entries are maker-first limit orders with a registered reason code; each
cancel/reprice is bounded (`max_reprices` default **1**) and itself audit-coded.

> **"There is no code path that places an order whose purpose is its own cancellation, and no layered-
> ladder machinery exists."**

## The audit trail is the intent record
"Under an inferred-intent standard, a complete truthful decision log is the defense." For any order the
system can reconstruct why it was placed, why it moved, and why it was cancelled.
**"If a regulator asked 'why did the bot do X at time T,' the answer is a file, not a recollection."**

## Long-book cadence controls
The accumulation book reprices at most once per ~30s pass per asset, and only once the bid has drifted
past a staleness band (0.5 + 0.2 + 0.15 = **0.85%**); each resting bid carries its own TTL (6h) instead
of the 5m book's ~25s timeout. `config_guard` FATALs floors under every cadence knob, so **"a config
change alone cannot turn the patient accumulation book into a touch-hugging flicker quoter without
first tripping config_guard."**

## Named-and-closed self-trade risk
The long book can rest a same-pair BUY for hours while the 5m book's exit-escalation ladder or a
marketable sell reaches down through the book — **a literal self-fill, or the venue's self-trade
prevention cancelling the escape leg instead of the entry**. Fix: cancel our own resting long-book bid
FIRST before any non-post-only sell, coded **LB-022**, wired into **four call sites**. A post-only
maker exit is **deliberately exempt** — "a resting ask can never cross the book, so passive-passive
same-pair quoting is bona fide two-sided market making." **Cancel failure never blocks the sell**;
venue STP is the documented backstop for the residual race.

## Position limits
Spot crypto has no exchange-imposed position limits, so the bot imposes its own — inventory caps,
portfolio heat cap, per-asset concentration bounds, all config-guarded: "the self-regulatory analog of
exchange position accountability, **enforced in code, not policy**."

## Defensive research ingestion
Wash-trading research is ingested defensively: candle volume is re-grounded on the execution venue "so
the model never learns from fabricated external volume."

## Standing obligation
**"Any future book that rests entries for hours must be wired into the same guard before ARM LIVE."**

## Related
[[entities/long-book]] · [[entities/reason-code-registry]] · [[entities/kraken]] ·
[[synthesis/manipulation-defense-doctrine]]

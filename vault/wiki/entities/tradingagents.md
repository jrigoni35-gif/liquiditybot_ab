---
title: TradingAgents
category: entity
summary: An external LLM trading scaffold adjudicated as producing text where this system produces numbers
tags: [external, llm, adjudicated]
sources: 2
updated: 2026-08-04
---

# TradingAgents

An external LLM research scaffold: a graph of analyst agents, a bull/bear debate, a three-persona risk
debate, and a portfolio-manager verdict emitting a **five-word rating plus prose**, with markdown memory
fed back as few-shot context.

## Its own disclaimer
Its README disclaims it as **"not a strategy with a fixed, replicable return."**

## The verdict
> "Every mechanism in TA that produces a *number* (cost, slippage, EV, Kelly fraction, drawdown
> throttle, leverage headroom), liquiditybot already computes deterministically, replayably, and
> overfit-audited; TA produces none of them — **it produces text**."

## What was taken
Exactly one thing worth having: a **human-legible per-decision outcome narrative**, and **only offline,
never in the engine**. Plus a dispatch-exhaustiveness test idiom, a keyless sentiment source, and a
guarded macro feed.

## What was taken that it did not intend to offer
Its **bug classes**, harvested from its issue tracker as a read-only self-check list — a serialized
string defeating a type guard, a config value read into a local and never forwarded, state leaking
between runs, resume identity not keyed on full state shape.

> **Adopt other people's failures, refuse their successes.**

## Standing rule established
**"Any LLM-derived multiplier/rating/adjustment touching sizing/gates/exits is REJECT, not ADAPT."**
Corroborated later by an external result showing LLM agents' decisions vary by underlying model — filed
as **"negative evidence FOR us."**

See [[comparisons/tradingagents-vs-liquiditybot]] and [[concepts/adoption-ledger]].
Sibling adjudication (2026-08-04): [[entities/mythos-router]] — the second external system
run through the ledger; that one produced *receipts* rather than text, and one of its
mechanisms was actually adopted ([[sources/session-20260804-mythos-router]]).

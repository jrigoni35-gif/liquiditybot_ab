---
title: TradingAgents vs liquiditybot
category: comparison
summary: A text-producing LLM scaffold against a number-producing deterministic engine, and what that asymmetry permits each to claim
tags: [comparison, llm, external]
sources: 2
updated: 2026-08-01
---

# TradingAgents vs liquiditybot

| Dimension | TradingAgents | liquiditybot |
|---|---|---|
| Output | prose + a five-word rating | continuous probabilities and sized orders |
| Determinism | temperature-dependent, model-dependent | step-able, replayable, seed-fixed |
| Cost modeling at decision time | **none** | full stack, fill-probability weighted |
| Backtest statistics | **zero** | OF-1..OF-8 + G1-G5 + PBO + deflated Sharpe |
| Memory | prose re-injected as few-shot context | numeric mitigations bounded by config |
| Auditability | run logs | hash-chained trail with registered codes |
| Self-assessment | "not a strategy with a fixed, replicable return" | invariant-bound, gate-enforced |

## The one asymmetry that favours the other side
A **human-legible per-decision narrative** joining a disposition to its eventual outcome. All the inputs
exist here — audit trail, postmortem taxonomy, goals ledger, cause tallies, replay — "but **no single
human-readable line-per-decision-with-eventual-outcome view stitched across them**." Dashboards show
metric panels, not this.

## The adoption shape it must take
Offline script, reads existing files only, **zero engine state, zero new reason code, never imported by
the decision cycle**, deterministic templated strings over the enumerable cause taxonomy — **not prose**,
and no degrees-of-freedom cost.

## The methodological point
Its headline evaluation is rejected as "not an evaluation methodology" (single trade, cost-blind, n=1),
while its **bug reports are mined as a self-check list**. That inversion — value in the failures, not
the results — is the reusable part. See [[concepts/adoption-ledger]].

## The boundary it fixed in writing
**No LLM in the decision cycle.** Any LLM-derived number touching sizing, gates or exits is a REJECT.
The system is repeatedly attracted to LLM *artifacts* (memory schemas, retention tiers, legibility
patterns) while rejecting LLM *computation*.

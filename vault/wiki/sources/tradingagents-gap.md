---
title: TradingAgents Adoption Ledger (2026-07-23)
category: source
summary: Adjudication of an external LLM trading scaffold: 4 ADOPTs confined to offline reporting and dev process, 12 explicit REJECTs, plus a self-check list derived from their bug reports
tags: [external-systems, llm, adoption-ledger, rejects]
sources: 1
updated: 2026-08-01
---

# TradingAgents Adoption Ledger (2026-07-23)

**Raw source:** `raw/research/2026-07-23_tradingagents_gap.md`

## The discriminator
**"Produces numbers vs produces text."** TradingAgents is a LangGraph scaffold running analysts ->
bull/bear debate -> three-persona risk debate -> a five-word rating plus prose. Its own README
disclaims it as "not a strategy with a fixed, replicable return."

> "Every mechanism in TA that produces a number (cost, slippage, EV, Kelly fraction, drawdown
> throttle, leverage headroom), liquiditybot already computes deterministically, replayably, and
> overfit-audited; TA produces none of them — it produces text."

TA is ahead on **exactly one thing worth having**: a human-legible, per-decision "what did I decide
and how did it turn out" narrative loop — "and only offline, never in the engine."

## The four ADOPTs
- **A1 (highest value)** — read-only `lessons_digest.py` + `decision_ledger.py`. All the inputs exist
  (hash-chained audit, postmortem taxonomy, goals ledger, monitor cause tallies, replay) "but **no
  single human-readable line-per-decision-with-eventual-outcome view stitched across them**." Shape
  under our law: new `scripts/`, reads existing JSONL/CSV only, **zero engine state, zero new `Code`,
  never imported by `cycle_once`**. Content is **deterministic templated strings**, not prose. No
  OF-7 DoF cost.
- **A4 (real DoF risk — guard hard)** — a 3-series FRED macro feed (fed funds, 10y-2y, VIX) consumed
  as slow **structural-stress confirmation**, never a signal generator, gate, or sizer input. The
  full 18-series set is **rejected outright** (monthly CPI stale ~8,928 cycles).
- **A2** — StockTwits read-only crowd sentiment; advisory-only, low priority.
- **A3** — the router-exhaustiveness test idiom (assert a dispatch table's entire return range is a
  subset of the handled path map). Test-only.

## The 12 REJECTs
LangGraph in-engine; bull/bear debate (no stopping rule, temperature-dependent, un-replayable);
three-persona risk debate ("grep: no kelly/cvar/var/leverage" — zero numeric output); the 5-tier
ordinal PM verdict (feeding Kelly would need an invented bucket->prob literal); soft structured-output
schemas; SqliteSaver; yfinance cache; the vendor fallback chain; the look-ahead cutoff-filter pattern;
Polymarket; full 18-series FRED as ML features; the LLM retry budget; TA's cost-blind n=1 "alpha
benchmark" — "not an evaluation methodology."

**"Any LLM-derived multiplier/rating/adjustment touching sizing/gates/exits is REJECT, not ADAPT."**

## The self-check list
Derived from TA's own GitHub issues rather than its features — a serialized-string `isinstance` guard
no-op'ing a look-ahead filter (#1115), a config read-into-local-then-never-forwarded (#764), sub-dict
leak between runs (#788), resume identity not keyed on full state shape (#1089), dispatch path-map not
covering the return range (#1088). The pattern: **adopt other people's failures, refuse their
successes.** See [[concepts/adoption-ledger]].

## Related
[[entities/tradingagents]] · [[comparisons/tradingagents-vs-liquiditybot]]

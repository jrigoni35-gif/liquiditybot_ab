---
title: "Engineering-precedents sweep (Grand Synthesis input 2) — what other builders documented for this repo's conflict classes"
category: source
summary: "The open-source precedent mine the Grand Synthesis trigger required: NOBODY documented symmetric-R brackets as their fix — the maker world converged on inventory skew and the retail-bot world on time-decay exits (freqtrade minimal_roi, with the documented trap that aggressive tables REPRODUCE near-TP/far-SL) + hard time-limit barriers (hummingbot's triple-barrier default) + ratchet-invariant stops; mark-price/composite-index stop triggering is the ONLY anti-wick mechanism with documented rationale AND deployment (BitMEX fair-price marking; Kraken 2021 ETH −63% single-venue flash crash is the motivating incident class); the hard part of stop-on-exchange vs in-bot is STATE RECONCILIATION (freqtrade's issue catalog — the same class as this repo's OM-085/restore work); close-based/time-confirmed stops are a documented DEBATE with no validated fix anywhere; NostalgiaForInfinity is the best-documented no-hard-SL+staged-derisk position and its documented cost is deep drawdowns; the brookmiles +2506%-in-11-days artifact externally confirms generosity-masks-fragility; and own-hedge-cadence-as-signal has NO open-source precedent — unclaimed territory, ship only as a falsification instrument"
tags: [engineering, sweep, freqtrade, hummingbot, stops, precedents, grand-synthesis, adoption-ledger]
sources: 1
source_path: engineering-precedents sweep agent report (relayed by the Grand Synthesis session; underlying report not separately archived at filing)
source_date: 2026-08
authors: [engineering-sweep agent, filed by the Grand Synthesis session]
ingested: 2026-08-10
updated: 2026-08-10
---

# Engineering-precedents sweep — Grand Synthesis input 2 (2026-08-11 session)

**What this is.** The documented-fixes-and-failure-modes sweep required by the Grand Synthesis
trigger ([[sources/directive-20260811-grand-synthesis]], trigger input 2;
[[synthesis/owed-measurements]] item 66): freqtrade / hummingbot / Lean / market-maker
precedents for the three conflict classes — **disposition-geometry**
([[concepts/behavioral-isomorphism]]), **stop-hunt**, and **hedge-signal** — adjudicated on the
[[concepts/adoption-ledger]] grammar (ADOPT / ADAPT / REJECT / ALREADY AHEAD). Verdicts filed
as relayed by the executing session (same provenance note as
[[sources/sweep-20260811-academic-stops]]).

**Boundary statement** (governance rule 13): repo-side survey of OTHER systems' documentation;
no number below is a measurement of this book.

## The headline negative: nobody documented symmetric-R brackets as their fix

Across the swept corpus, **no open-source system documents symmetric-R brackets** (equal-distance
TP/SL) **as the fix** for disposition-geometry. What the two worlds converged on instead:

- **Maker world → inventory skew.** Market-making frameworks manage adverse selection by
  skewing quotes against inventory, not by bracket geometry at all.
- **Retail-bot world → time-decay exits + hard time limits + ratchet-invariant stops.**
  - **freqtrade `minimal_roi`**: a time-since-entry decaying profit target — **with the
    documented trap that aggressive tables REPRODUCE near-TP/far-SL**, i.e. the exact
    disposition-geometry this repo measured at 2.20x
    ([[concepts/behavioral-isomorphism]]). The mechanism is sound; the parameterization is
    where the bias re-enters. Direct design input (and warning label) for
    [[synthesis/grand-synthesis-algorithm-package|ALGO-6]].
  - **hummingbot's triple-barrier default** ships a **hard time-limit barrier** — the
    vertical barrier as a first-class exit, not an afterthought.
  - **Ratchet-invariant stops**: frameworks ENFORCE monotone-toward-profit stop movement in
    the framework itself (a stop may tighten, never loosen) — an invariant, not a strategy
    choice.

## Mark-price stop triggering — the ONLY anti-wick mechanism with rationale AND deployment

**Mark-price / composite-index stop triggering** is the one anti-stop-hunt mechanism in the
swept corpus with BOTH a documented rationale and production deployment: **BitMEX fair-price
marking**, motivated by exactly the incident class of the **Kraken 2021 ETH −63% single-venue
flash crash** — a stop triggered off a single venue's last-trade print is triggerable by that
venue's wick; a stop triggered off a composite mark is not. Design input for
[[synthesis/grand-synthesis-algorithm-package|ALGO-7]] — whose first step is to **verify this
engine already triggers off the trusted mark** before changing anything.

## Stop-on-exchange vs stop-in-bot: the hard part is STATE RECONCILIATION

The freqtrade issue catalog's documented pain is not which side holds the stop — it is
**reconciling bot state with exchange state** after restarts, partial fills, and cancels.
**Same defect class as this repo's OM-085 restart-replay guard and the restore work**
([[synthesis/owed-measurements]] item 62, `6fe6d98d`) — this repo is **ALREADY AHEAD** on the
class, having shipped write-path idempotence with tests; the precedent confirms the class is
the real cost center, not the stop's location.

## Close-based / time-confirmed stops: a documented DEBATE, no validated fix

"Trigger the stop only on candle close" / "only after N seconds beyond the level" is a live
debate in every swept community — **no system documents a validated fix**. Filed as a genuine
open question, NOT adoptable on precedent; if it is ever tested here it goes through
[[synthesis/grand-synthesis-algorithm-package|ALGO-5]]'s counterfactual replay, not through a
config default.

## NostalgiaForInfinity: the best-documented no-hard-SL position — and its price

**NostalgiaForInfinity** (the most-forked freqtrade strategy family) documents the strongest
no-hard-stop-loss + **staged de-risk** position in the corpus — and equally documents its
cost: **deep drawdowns**. Filed as the honest bound on "just remove the stop": the alternative
to stop-out losses is documented drawdown depth, not documented profit.

## External confirmation: the backtest-geometry exploitation trap

The **brookmiles +2506%-in-11-days artifact** — a freqtrade backtest whose return was an
artifact of backtest fill geometry — externally confirms this repo's
[[concepts/generosity-masks-fragility]] class: an over-generous execution model converts
geometry into fictional edge, and the fiction survives until the model is made honest
(this repo's own 1.88x double-count is the in-house specimen,
[[sources/session-20260810-fill-double-count]]).

## Own-hedge-cadence-as-signal: NO precedent exists

For the hedge-signal class (the operator's own-hedge-cadence question, owed 52 context):
**no open-source precedent exists anywhere in the swept corpus.** The nearest analog —
**equity-curve trading filters** (trade the strategy only when its own equity curve is above
its MA) — **mostly FAILS** in documented tests. Verdict: **unclaimed territory** — which cuts
both ways (nobody validated it, nobody killed it). Adjudication: **ship only as a
falsification instrument** ([[synthesis/grand-synthesis-algorithm-package|ALGO-3]], the
defensive-cadence ledger designed to kill its own hypothesis), never as a feature
([[synthesis/evidence-closed-register]] NOT-ADOPTED row: own-hedge-as-feature).

## Adoption-ledger summary

| Precedent | Verdict |
|---|---|
| Time-decay exit ladder (freqtrade `minimal_roi` mechanism) | **ADAPT** — ALGO-6, parameters from ALGO-5's replay, never an aggressive table (the documented trap) |
| Hard time-limit barrier (hummingbot triple-barrier default) | **ADAPT** — ALGO-6's second half; attacks the 2.20x holding asymmetry structurally |
| Ratchet-invariant stops (framework-enforced monotone-toward-profit) | **ADAPT** — invariant enforcement, pending the geometry-epoch adjudication |
| Mark-price/composite stop triggering (BitMEX fair-price class) | **ADOPT-VERIFY** — ALGO-7: verify the engine's existing mark usage first |
| Inventory skew (maker world) | **REJECT for this book** — this is not a maker book; filed as the maker-world answer for completeness |
| Symmetric-R brackets as the disposition fix | **NO PRECEDENT** — nobody documents it; do not cite "standard practice" for it |
| No-hard-SL + staged de-risk (NostalgiaForInfinity) | **REJECT** — documented cost (deep drawdowns) fails the survival floor ([[synthesis/risk-posture-doctrine]]) |
| Close-based/time-confirmed stops | **DEFER** — documented debate, no validated fix anywhere |
| Stop-state reconciliation discipline | **ALREADY AHEAD** — OM-085/restore work covers the class |
| Own-hedge-cadence-as-signal | **ADAPT-AS-FALSIFIER ONLY** — ALGO-3; no precedent, nearest analog mostly fails |

## Related

[[sources/directive-20260811-grand-synthesis]] ·
[[synthesis/grand-synthesis-algorithm-package]] · [[sources/sweep-20260811-academic-stops]] ·
[[concepts/adoption-ledger]] · [[entities/retail-bot-frameworks]] ·
[[concepts/behavioral-isomorphism]] · [[concepts/generosity-masks-fragility]] ·
[[synthesis/owed-measurements]] · [[synthesis/evidence-closed-register]]
